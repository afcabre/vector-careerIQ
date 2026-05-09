from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2,
    build_prompt_text,
)
from app.services.vacancy_alignment_report_service import (
    _contract_candidate_from_llm,
    _extract_json_object,
    _opportunity_context_payload,
    _person_context_payload,
    _system_prompt_from_global_layers,
)
from app.services.vacancy_alignment_report_v2_contract import (
    FINAL_RECOMMENDATIONS,
    VACANCY_FIT_ROW_STATES,
    VacancyAlignmentReportV2Contract,
    empty_vacancy_alignment_report_v2_contract,
    normalize_vacancy_alignment_report_v2_contract,
)
from app.services.vacancy_alignment_summary_v2_contract import (
    is_vacancy_alignment_summary_v2_contract,
    normalize_vacancy_alignment_summary_v2_contract,
)
from app.services.vacancy_evidence_adjudication_contract import (
    ALIGNMENT_STATUS_CONFLICT,
    ALIGNMENT_STATUS_DIRECT,
    ALIGNMENT_STATUS_INDIRECT,
    ALIGNMENT_STATUS_NOT_APPLICABLE,
    ALIGNMENT_STATUS_NOT_EVIDENCED,
    ALIGNMENT_STATUS_PARTIAL,
    PRIORITY_DESIRABLE,
    VacancyEvidenceAdjudicationContract,
    is_vacancy_evidence_adjudication_contract,
    normalize_vacancy_evidence_adjudication_contract,
)
from app.services.vacancy_evidence_analysis_contract import (
    is_vacancy_evidence_analysis_contract,
    normalize_vacancy_evidence_analysis_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


class VacancyAlignmentReportV2BuildError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _has_meaningful_report(contract: VacancyAlignmentReportV2Contract) -> bool:
    report = contract["report"]
    return any(
        [
            bool(report["executive_summary"]["summary"]),
            bool(report["vacancy_fit_matrix"]),
            bool(report["candidate_preference_matrix"]),
            bool(report["strengths"]),
            bool(report["gaps"]),
            bool(contract["rendered_markdown"]),
        ]
    )


def _evaluable_item_ids(contract: VacancyEvidenceAdjudicationContract) -> set[str]:
    item_ids: set[str] = set()
    for item in contract["items"]:
        if item["alignment_status"] == ALIGNMENT_STATUS_NOT_APPLICABLE:
            continue
        if item["item_id"]:
            item_ids.add(item["item_id"])
    return item_ids


def _fit_matrix_diff(
    report_contract: VacancyAlignmentReportV2Contract,
    adjudication_contract: VacancyEvidenceAdjudicationContract,
) -> tuple[list[str], list[str]]:
    expected_item_ids = _evaluable_item_ids(adjudication_contract)
    actual_rows = report_contract["report"]["vacancy_fit_matrix"]
    actual_item_ids = {row["item_id"] for row in actual_rows if row["item_id"]}
    missing = sorted(expected_item_ids - actual_item_ids)
    extra = sorted(actual_item_ids - expected_item_ids)
    return missing, extra


def _expected_row_state(item: dict[str, Any]) -> str:
    if item["alignment_status"] == ALIGNMENT_STATUS_DIRECT:
        return "🟢 Cumple"
    if item["alignment_status"] in {ALIGNMENT_STATUS_PARTIAL, ALIGNMENT_STATUS_INDIRECT}:
        return "🟡 Parcial"
    if item["alignment_status"] == ALIGNMENT_STATUS_CONFLICT:
        return "🔴 En conflicto"
    if item["alignment_status"] == ALIGNMENT_STATUS_NOT_EVIDENCED:
        if item["priority"] == PRIORITY_DESIRABLE or item["group"] == "desirable_criteria":
            return "🔵 Deseable no evidenciado"
        return "⚪ Sin informacion"
    return ""


def _build_adjudication_index(contract: VacancyEvidenceAdjudicationContract) -> dict[str, dict[str, Any]]:
    return {item["item_id"]: item for item in contract["items"] if item["item_id"]}


def _describe_adjudication_item(item: dict[str, Any]) -> str:
    item_id = str(item.get("item_id", "")).strip()
    raw_text = str(item.get("raw_text", "")).strip()
    if item_id and raw_text:
        return f"{item_id}: {raw_text}"
    return item_id or raw_text or "unknown_item"


def _format_fit_matrix_completeness_detail(
    *,
    missing_item_ids: list[str],
    extra_item_ids: list[str],
    adjudication_contract: VacancyEvidenceAdjudicationContract,
) -> str:
    adjudication_index = _build_adjudication_index(adjudication_contract)
    missing_descriptions = [
        _describe_adjudication_item(adjudication_index[item_id])
        for item_id in missing_item_ids
        if item_id in adjudication_index
    ]
    detail_parts = [
        f"missing_item_ids={missing_item_ids}",
        f"extra_item_ids={extra_item_ids}",
    ]
    if missing_descriptions:
        detail_parts.append(f"missing_items={missing_descriptions}")
    return " ".join(detail_parts)


def _validate_fit_matrix(
    report_contract: VacancyAlignmentReportV2Contract,
    adjudication_contract: VacancyEvidenceAdjudicationContract,
) -> None:
    missing, extra = _fit_matrix_diff(report_contract, adjudication_contract)
    if missing or extra:
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 report matrix completeness check failed."
            f" {_format_fit_matrix_completeness_detail(missing_item_ids=missing, extra_item_ids=extra, adjudication_contract=adjudication_contract)}"
        )

    adjudication_index = _build_adjudication_index(adjudication_contract)
    for row in report_contract["report"]["vacancy_fit_matrix"]:
        row_state = row["estado"]
        if row_state not in VACANCY_FIT_ROW_STATES:
            raise VacancyAlignmentReportV2BuildError(
                "Step 8 v2 report uses an invalid vacancy_fit_matrix estado."
            )
        adjudicated = adjudication_index.get(row["item_id"])
        if not adjudicated:
            raise VacancyAlignmentReportV2BuildError(
                "Step 8 v2 report references an unknown item_id in vacancy_fit_matrix."
            )
        expected_state = _expected_row_state(adjudicated)
        if expected_state and row_state != expected_state:
            raise VacancyAlignmentReportV2BuildError(
                "Step 8 v2 report contradicts adjudication status in vacancy_fit_matrix."
            )


def _validate_recommendations(report_contract: VacancyAlignmentReportV2Contract) -> None:
    executive = report_contract["report"]["executive_summary"]["final_recommendation"]
    conclusion = report_contract["report"]["actionable_conclusion"]["final_decision"]
    decision_table = report_contract["report"]["decision_table"]["recomendacion"]["resultado"]
    for value in (executive, conclusion, decision_table):
        if value and value not in FINAL_RECOMMENDATIONS:
            raise VacancyAlignmentReportV2BuildError(
                "Step 8 v2 report uses an invalid final recommendation."
            )


def _run_fit_matrix_repair_completion(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    person_id: str,
    person_context: str,
    opportunity_context: str,
    missing_items: list[dict[str, Any]],
    settings: Any,
    llm_temperature: float,
) -> list[dict[str, Any]]:
    missing_items_json = json.dumps(missing_items, ensure_ascii=False)
    user_prompt = (
        "Actua como analista senior de alineacion candidato-vacante. "
        "Tu unica tarea es completar filas faltantes de vacancy_fit_matrix para los criterios indicados. "
        "Responde SOLO JSON valido con exactamente esta raiz: {\"vacancy_fit_matrix\": [...]} y nada mas. "
        "Debes devolver exactamente una fila por cada item recibido en missing_items, sin omitir ninguno ni inventar otros. "
        "Cada fila debe incluir exactamente: item_id, criterio, categoria, origen_del_criterio, prioridad, estado, lo_que_solicita_la_vacante, evidencia_del_candidato, tipo_de_evidencia, fuerza_de_evidencia, descripcion_corta, riesgo_para_la_postulacion, fuentes. "
        "Usa unicamente la evidencia proporcionada dentro de cada item. "
        "Mapeo obligatorio: direct -> 🟢 Cumple; partial o indirect -> 🟡 Parcial; not_evidenced obligatorio -> ⚪ Sin informacion; not_evidenced deseable -> 🔵 Deseable no evidenciado; conflict -> 🔴 En conflicto. "
        "No inventes informacion. No omitas item_id. No devuelvas filas para otros criterios. "
        "Persona: {person_context}. Vacante: {opportunity_context}. "
        f"Missing items: {missing_items_json}."
    )
    response_text = complete_prompt(
        _system_prompt_from_global_layers(person),
        user_prompt,
        settings,
        temperature=llm_temperature,
        person_id=person_id,
        opportunity_id=str(opportunity.get("opportunity_id", "")).strip(),
        flow_key=FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2,
        trace_truncation_override=False,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 matrix repair response unavailable; alignment report aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 matrix repair response is not valid JSON; alignment report aborted."
        )

    candidate = normalize_vacancy_alignment_report_v2_contract(
        {
            "report": {
                "vacancy_fit_matrix": (
                    parsed.get("vacancy_fit_matrix")
                    if isinstance(parsed, dict)
                    else []
                )
            },
            "rendered_markdown": "",
        }
    )
    return list(candidate["report"]["vacancy_fit_matrix"])


def _merge_fit_matrix_rows(
    *,
    report_contract: VacancyAlignmentReportV2Contract,
    adjudication_contract: VacancyEvidenceAdjudicationContract,
    repaired_rows: list[dict[str, Any]],
) -> VacancyAlignmentReportV2Contract:
    normalized = normalize_vacancy_alignment_report_v2_contract(report_contract)
    expected_item_ids = _evaluable_item_ids(adjudication_contract)
    existing_rows = {
        row["item_id"]: row
        for row in normalized["report"]["vacancy_fit_matrix"]
        if row["item_id"] in expected_item_ids
    }
    for row in repaired_rows:
        item_id = str(row.get("item_id", "")).strip()
        if item_id and item_id in expected_item_ids:
            existing_rows[item_id] = row

    merged_rows: list[dict[str, Any]] = []
    for item in adjudication_contract["items"]:
        if item["alignment_status"] == ALIGNMENT_STATUS_NOT_APPLICABLE or not item["item_id"]:
            continue
        row = existing_rows.get(item["item_id"])
        if row:
            merged_rows.append(row)

    normalized["report"]["vacancy_fit_matrix"] = merged_rows
    return normalize_vacancy_alignment_report_v2_contract(normalized)


def _run_report_completion(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    person_id: str,
    person_context: str,
    opportunity_context: str,
    evidence_adjudication_json: str,
    alignment_summary_json: str,
    evidence_analysis_json: str,
    settings: Any,
    llm_temperature: float,
    phase_label: str,
    retry_hint: str = "",
) -> VacancyAlignmentReportV2Contract:
    fallback_user_prompt = (
        "Actua como analista senior de alineacion candidato-vacante, orientado a ayudar al candidato y/o a su tutor a decidir si conviene priorizar esta vacante. "
        "Responde SOLO JSON valido conforme a vacancy_alignment_report.v2. "
        "No escribas texto fuera del JSON. Debes producir exactamente dos claves raiz: report, rendered_markdown. "
        "Usa vacancy_evidence_adjudication.v1 como insumo principal. Usa vacancy_alignment_summary.v2 como resumen auxiliar. Usa vacancy_evidence_analysis.v1 solo como respaldo. "
        "No inventes informacion, no infles el perfil, no omitas criterios evaluados y no recalcules scores. "
        "vacancy_fit_matrix debe incluir todos los criterios evaluados excepto not_applicable. "
        "Antes de responder, verifica internamente que vacancy_fit_matrix contiene exactamente todos los item_id evaluables de vacancy_evidence_adjudication.v1 y ninguno extra. "
        "Mapeo obligatorio: direct -> 🟢 Cumple; partial/indirect -> 🟡 Parcial; not_evidenced obligatorio -> ⚪ Sin informacion; not_evidenced deseable -> 🔵 Deseable no evidenciado; conflict -> 🔴 En conflicto. "
        "Usa solo estas recomendaciones: Avanzar, Avanzar con reservas, Avanzar si se valida X, No priorizar, Descartar. "
        "Persona: {person_context}. Vacante: {opportunity_context}. "
        "Entrada vacancy_evidence_adjudication.v1: {evidence_adjudication_json}. "
        "Entrada vacancy_alignment_summary.v2: {alignment_summary_json}. "
        "Entrada vacancy_evidence_analysis.v1: {evidence_analysis_json}. "
        "Instruccion adicional de completitud: {retry_hint}."
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2,
        context={
            "person_context": person_context,
            "opportunity_context": opportunity_context,
            "evidence_adjudication_json": evidence_adjudication_json,
            "alignment_summary_json": alignment_summary_json,
            "evidence_analysis_json": evidence_analysis_json,
            "retry_hint": retry_hint,
        },
        fallback=fallback_user_prompt,
    )
    if retry_hint.strip():
        user_prompt = f"{user_prompt}\n\nControl adicional de completitud:\n{retry_hint.strip()}"
    response_text = complete_prompt(
        _system_prompt_from_global_layers(person),
        user_prompt,
        settings,
        temperature=llm_temperature,
        person_id=person_id,
        opportunity_id=str(opportunity.get("opportunity_id", "")).strip(),
        flow_key=FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2,
        trace_truncation_override=False,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancyAlignmentReportV2BuildError(
            f"{phase_label} LLM response unavailable; alignment report aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyAlignmentReportV2BuildError(
            f"{phase_label} LLM response is not valid JSON; alignment report aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    return normalize_vacancy_alignment_report_v2_contract(candidate)


def extract_vacancy_alignment_report_v2(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    vacancy_evidence_adjudication_artifact: dict[str, Any],
    vacancy_alignment_summary_v2_artifact: dict[str, Any],
    vacancy_evidence_analysis_artifact: dict[str, Any],
    settings: Any,
) -> VacancyAlignmentReportV2Contract:
    if not isinstance(vacancy_evidence_adjudication_artifact, dict) or not is_vacancy_evidence_adjudication_contract(
        vacancy_evidence_adjudication_artifact
    ):
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 requires a valid vacancy_evidence_adjudication.v1 artifact."
        )
    if not isinstance(vacancy_alignment_summary_v2_artifact, dict) or not is_vacancy_alignment_summary_v2_contract(
        vacancy_alignment_summary_v2_artifact
    ):
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 requires a valid vacancy_alignment_summary.v2 artifact."
        )
    if not isinstance(vacancy_evidence_analysis_artifact, dict) or not is_vacancy_evidence_analysis_contract(
        vacancy_evidence_analysis_artifact
    ):
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 requires a valid vacancy_evidence_analysis.v1 artifact."
        )

    normalized_adjudication = normalize_vacancy_evidence_adjudication_contract(
        vacancy_evidence_adjudication_artifact
    )
    normalized_summary = normalize_vacancy_alignment_summary_v2_contract(
        vacancy_alignment_summary_v2_artifact
    )
    normalized_analysis = normalize_vacancy_evidence_analysis_contract(
        vacancy_evidence_analysis_artifact
    )

    person_id = str(person.get("person_id", "")).strip() or str(opportunity.get("person_id", "")).strip()
    vacancy_id = (
        normalized_adjudication["vacancy_id"]
        or normalized_summary["vacancy_id"]
        or normalized_analysis["vacancy_id"]
        or str(opportunity.get("opportunity_id", "")).strip()
    )
    generated_at = _now_iso()

    person_context = json.dumps(_person_context_payload(person), ensure_ascii=False)
    opportunity_context = json.dumps(_opportunity_context_payload(opportunity), ensure_ascii=False)
    evidence_adjudication_json = json.dumps(normalized_adjudication, ensure_ascii=False)
    alignment_summary_json = json.dumps(normalized_summary, ensure_ascii=False)
    evidence_analysis_json = json.dumps(normalized_analysis, ensure_ascii=False)
    runtime_config = get_vacancy_v2_runtime_config(settings)
    llm_temperature = float(runtime_config["step3"]["llm_temperature"])
    normalized = _run_report_completion(
        person=person,
        opportunity=opportunity,
        person_id=person_id,
        person_context=person_context,
        opportunity_context=opportunity_context,
        evidence_adjudication_json=evidence_adjudication_json,
        alignment_summary_json=alignment_summary_json,
        evidence_analysis_json=evidence_analysis_json,
        settings=settings,
        llm_temperature=llm_temperature,
        phase_label="Step 8 v2",
    )
    normalized["vacancy_id"] = vacancy_id
    normalized["person_id"] = person_id
    normalized["generated_at"] = generated_at
    normalized["source_artifacts"] = {
        "evidence_adjudication_version": normalized_adjudication["contract_version"],
        "alignment_summary_version": normalized_summary["contract_version"],
        "evidence_analysis_version": normalized_analysis["contract_version"],
    }

    missing_item_ids, extra_item_ids = _fit_matrix_diff(normalized, normalized_adjudication)
    if missing_item_ids or extra_item_ids:
        adjudication_index = _build_adjudication_index(normalized_adjudication)
        missing_items = [
            adjudication_index[item_id]
            for item_id in missing_item_ids
            if item_id in adjudication_index
        ]
        repaired_rows = _run_fit_matrix_repair_completion(
            person=person,
            opportunity=opportunity,
            person_id=person_id,
            person_context=person_context,
            opportunity_context=opportunity_context,
            missing_items=missing_items,
            settings=settings,
            llm_temperature=llm_temperature,
        )
        normalized = _merge_fit_matrix_rows(
            report_contract=normalized,
            adjudication_contract=normalized_adjudication,
            repaired_rows=repaired_rows,
        )
        normalized["vacancy_id"] = vacancy_id
        normalized["person_id"] = person_id
        normalized["generated_at"] = generated_at
        normalized["source_artifacts"] = {
            "evidence_adjudication_version": normalized_adjudication["contract_version"],
            "alignment_summary_version": normalized_summary["contract_version"],
            "evidence_analysis_version": normalized_analysis["contract_version"],
        }

    _validate_fit_matrix(normalized, normalized_adjudication)
    _validate_recommendations(normalized)

    if _has_meaningful_report(normalized):
        return normalized

    raise VacancyAlignmentReportV2BuildError(
        "Step 8 v2 LLM response produced empty alignment report; extraction aborted."
    )
