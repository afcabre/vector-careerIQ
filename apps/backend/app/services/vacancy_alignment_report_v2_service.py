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
from app.services.vacancy_fit_presentation_contract import (
    is_vacancy_fit_presentation_contract,
    normalize_vacancy_fit_presentation_contract,
)
from app.services.candidate_preference_checks_contract import (
    is_candidate_preference_checks_contract,
    normalize_candidate_preference_checks_contract,
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


def _has_meaningful_executive_summary(report: dict[str, Any]) -> bool:
    payload = report["executive_summary"]
    return any(
        [
            bool(payload["fit_level"]),
            bool(payload["final_recommendation"]),
            bool(payload["summary"]),
            bool(payload["main_strength"]),
            bool(payload["main_gap_or_risk"]),
            bool(payload["confidence"]),
        ]
    )


def _has_meaningful_decision_table(report: dict[str, Any]) -> bool:
    decision_table = report["decision_table"]
    for key in (
        "alineacion_general",
        "fit_objetivo",
        "fit_preferencial",
        "requisitos_criticos_cumplidos",
        "bloqueadores",
        "alertas_relevantes",
        "potencial_mejora_fit",
        "recomendacion",
    ):
        entry = decision_table[key]
        if entry["resultado"] or entry["descripcion_corta"]:
            return True
    return False


def _has_meaningful_fit_answer(report: dict[str, Any]) -> bool:
    payload = report["fit_answer"]
    return bool(payload["encaja"] or payload["respuesta_para_el_candidato"])


def _has_meaningful_actionable_conclusion(report: dict[str, Any]) -> bool:
    payload = report["actionable_conclusion"]
    return any(
        [
            bool(payload["final_decision"]),
            bool(payload["main_reason"]),
            bool(payload["recommended_next_step"]),
            bool(payload["confidence"]),
        ]
    )


def _missing_required_narrative_sections(report_contract: VacancyAlignmentReportV2Contract) -> list[str]:
    report = report_contract["report"]
    missing: list[str] = []
    if not _has_meaningful_executive_summary(report):
        missing.append("executive_summary")
    if not _has_meaningful_decision_table(report):
        missing.append("decision_table")
    if not _has_meaningful_fit_answer(report):
        missing.append("fit_answer")
    if not _has_meaningful_actionable_conclusion(report):
        missing.append("actionable_conclusion")
    return missing


def _priority_es_from_type_label(type_label: str) -> str:
    normalized = str(type_label or "").strip().casefold()
    if normalized == "deseable":
        return "Deseable"
    return "Importante"


def _origin_es_from_group(group: str) -> str:
    if group == "required_criteria":
        return "Vacante obligatoria"
    if group == "desirable_criteria":
        return "Vacante deseable"
    if group == "responsibilities":
        return "Responsabilidad"
    return "Vacante condicion"


def _category_es_from_group(group: str) -> str:
    if group == "responsibilities":
        return "Responsabilidades"
    if group == "desirable_criteria":
        return "Conocimientos"
    return "Experiencia"


def _tipo_evidencia_es_from_state(state: str) -> str:
    if state == "🟢 Cumple":
        return "directa"
    if state == "🟡 Parcial":
        return "parcial"
    if state == "🔴 En conflicto":
        return "conflicto"
    return "no evidenciada"


def _fuerza_evidencia_es_from_confidence(confidence: str, evidence_count: int) -> str:
    if evidence_count <= 0:
        return "ninguna"
    normalized = str(confidence or "").strip().casefold()
    if normalized == "high":
        return "alta"
    if normalized == "medium":
        return "media"
    if normalized == "low":
        return "baja"
    return "media"


def _riesgo_postulacion_es(candidate_risk: str) -> str:
    normalized = str(candidate_risk or "").strip().casefold()
    if normalized == "none":
        return "ninguno"
    if normalized == "low":
        return "bajo"
    if normalized == "medium":
        return "medio"
    if normalized == "high":
        return "alto"
    return "medio"


def _evidencia_candidato_from_row(row: dict[str, Any]) -> str:
    evidence = row.get("evidence")
    if isinstance(evidence, list):
        snippets = [
            str(item.get("snippet", "")).strip()
            for item in evidence
            if isinstance(item, dict) and str(item.get("snippet", "")).strip()
        ]
        if snippets:
            return " | ".join(snippets[:3])
    return str(row.get("why", "")).strip()


def _fuentes_from_row(row: dict[str, Any]) -> list[str]:
    evidence = row.get("evidence")
    if not isinstance(evidence, list):
        return []
    sources: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source_ref = str(item.get("source_ref", "")).strip()
        if not source_ref:
            continue
        signature = source_ref.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        sources.append(source_ref)
    return sources


def _deterministic_fit_matrix_from_presentation(
    vacancy_fit_presentation_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    presentation = normalize_vacancy_fit_presentation_contract(vacancy_fit_presentation_artifact)
    rows: list[dict[str, Any]] = []
    for group in ("required_criteria", "responsibilities", "desirable_criteria"):
        for row in presentation["groups"][group]:
            rows.append(
                {
                    "item_id": row["item_id"],
                    "criterio": row["criterion"],
                    "categoria": _category_es_from_group(row["group"]),
                    "origen_del_criterio": _origin_es_from_group(row["group"]),
                    "prioridad": _priority_es_from_type_label(row["type_label"]),
                    "estado": row["state"],
                    "lo_que_solicita_la_vacante": row["criterion"],
                    "evidencia_del_candidato": _evidencia_candidato_from_row(row),
                    "tipo_de_evidencia": _tipo_evidencia_es_from_state(row["state"]),
                    "fuerza_de_evidencia": _fuerza_evidencia_es_from_confidence(
                        row["confidence"],
                        int(row["evidence_count"]),
                    ),
                    "descripcion_corta": row["why"],
                    "riesgo_para_la_postulacion": _riesgo_postulacion_es(row["candidate_risk"]),
                    "fuentes": _fuentes_from_row(row),
                }
            )
    return rows


def _preference_category_es(criterion_key: str) -> str:
    return {
        "location": "Ubicación",
        "modality": "Modalidad",
        "compensation": "Compensación",
        "contract_type": "Condiciones laborales",
    }.get(criterion_key, "Otro")


def _deterministic_preference_matrix(
    candidate_preference_checks_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = normalize_candidate_preference_checks_contract(candidate_preference_checks_artifact)
    rows: list[dict[str, Any]] = []
    for row in checks["rows"]:
        rows.append(
            {
                "criterio": row["criterion"],
                "categoria": _preference_category_es(row["criterion_key"]),
                "origen_del_criterio": "Preferencia del candidato",
                "estado": row["state"],
                "lo_que_ofrece_o_define_la_vacante": row["vacancy_value"],
                "preferencia_o_condicion_del_candidato": row["candidate_value"],
                "descripcion_corta": row["why"],
                "validacion_recomendada": (
                    "Validar con reclutador si el detalle final cambia esta condicion."
                    if row["state"] in {"🟡 Parcial", "⚪ Sin informacion"}
                    else ""
                ),
            }
        )
    return rows


def _expected_fit_matrix_item_ids_from_presentation(
    vacancy_fit_presentation_artifact: dict[str, Any],
) -> set[str]:
    presentation = normalize_vacancy_fit_presentation_contract(vacancy_fit_presentation_artifact)
    item_ids: set[str] = set()
    for group in ("required_criteria", "responsibilities", "desirable_criteria"):
        for row in presentation["groups"][group]:
            item_id = str(row.get("item_id", "")).strip()
            if item_id:
                item_ids.add(item_id)
    return item_ids


def _fit_matrix_diff(
    report_contract: VacancyAlignmentReportV2Contract,
    vacancy_fit_presentation_artifact: dict[str, Any],
) -> tuple[list[str], list[str]]:
    expected_item_ids = _expected_fit_matrix_item_ids_from_presentation(vacancy_fit_presentation_artifact)
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
    vacancy_fit_presentation_artifact: dict[str, Any],
) -> str:
    presentation = normalize_vacancy_fit_presentation_contract(vacancy_fit_presentation_artifact)
    presentation_index: dict[str, dict[str, Any]] = {}
    for group in ("required_criteria", "responsibilities", "desirable_criteria"):
        for row in presentation["groups"][group]:
            item_id = str(row.get("item_id", "")).strip()
            if item_id:
                presentation_index[item_id] = row
    missing_descriptions = [
        f"{item_id}: {str(presentation_index[item_id].get('criterion', '')).strip()}"
        for item_id in missing_item_ids
        if item_id in presentation_index
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
    vacancy_fit_presentation_artifact: dict[str, Any],
) -> None:
    missing, extra = _fit_matrix_diff(report_contract, vacancy_fit_presentation_artifact)
    if missing or extra:
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 report matrix completeness check failed."
            f" {_format_fit_matrix_completeness_detail(missing_item_ids=missing, extra_item_ids=extra, vacancy_fit_presentation_artifact=vacancy_fit_presentation_artifact)}"
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
    fit_presentation_json: str,
    preference_checks_json: str,
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
        "Usa vacancy_fit_presentation.v1 como matriz profesional autoritativa y candidate_preference_checks.v1 como matriz de preferencias autoritativa. "
        "Cuando hables de ubicacion, modalidad, compensacion o tipo de contrato, candidate_preference_checks.v1 es la fuente de verdad. "
        "No digas que falta evidencia en el CV o en el perfil para esas condiciones si candidate_preference_checks.v1 ya resolvio la comparacion. "
        "No menciones preferencias culturales blandas o campos fuera de candidate_preference_checks.v1 al redactar el ajuste preferencial. "
        "No inventes informacion, no infles el perfil, no omitas criterios evaluados y no recalcules scores. "
        "vacancy_fit_matrix debe reflejar exactamente los rows de vacancy_fit_presentation.v1. "
        "candidate_preference_matrix debe reflejar exactamente los rows de candidate_preference_checks.v1. "
        "Mapeo obligatorio: direct -> 🟢 Cumple; partial/indirect -> 🟡 Parcial; not_evidenced obligatorio -> ⚪ Sin informacion; not_evidenced deseable -> 🔵 Deseable no evidenciado; conflict -> 🔴 En conflicto. "
        "Usa solo estas recomendaciones: Avanzar, Avanzar con reservas, Avanzar si se valida X, No priorizar, Descartar. "
        "Persona: {person_context}. Vacante: {opportunity_context}. "
        "Entrada vacancy_evidence_adjudication.v1: {evidence_adjudication_json}. "
        "Entrada vacancy_alignment_summary.v2: {alignment_summary_json}. "
        "Entrada vacancy_evidence_analysis.v1: {evidence_analysis_json}. "
        "Entrada vacancy_fit_presentation.v1: {fit_presentation_json}. "
        "Entrada candidate_preference_checks.v1: {preference_checks_json}. "
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
            "fit_presentation_json": fit_presentation_json,
            "preference_checks_json": preference_checks_json,
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
    vacancy_fit_presentation_artifact: dict[str, Any],
    candidate_preference_checks_artifact: dict[str, Any],
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
    if not isinstance(vacancy_fit_presentation_artifact, dict) or not is_vacancy_fit_presentation_contract(
        vacancy_fit_presentation_artifact
    ):
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 requires a valid vacancy_fit_presentation.v1 artifact."
        )
    if not isinstance(candidate_preference_checks_artifact, dict) or not is_candidate_preference_checks_contract(
        candidate_preference_checks_artifact
    ):
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 requires a valid candidate_preference_checks.v1 artifact."
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
    normalized_fit_presentation = normalize_vacancy_fit_presentation_contract(
        vacancy_fit_presentation_artifact
    )
    normalized_preference_checks = normalize_candidate_preference_checks_contract(
        candidate_preference_checks_artifact
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
    fit_presentation_json = json.dumps(normalized_fit_presentation, ensure_ascii=False)
    preference_checks_json = json.dumps(normalized_preference_checks, ensure_ascii=False)
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
        fit_presentation_json=fit_presentation_json,
        preference_checks_json=preference_checks_json,
        settings=settings,
        llm_temperature=llm_temperature,
        phase_label="Step 8 v2",
    )
    normalized["report"]["vacancy_fit_matrix"] = _deterministic_fit_matrix_from_presentation(
        normalized_fit_presentation
    )
    normalized["report"]["candidate_preference_matrix"] = _deterministic_preference_matrix(
        normalized_preference_checks
    )
    normalized = normalize_vacancy_alignment_report_v2_contract(normalized)
    missing_narrative_sections = _missing_required_narrative_sections(normalized)
    if missing_narrative_sections:
        retry_hint = (
            "Completa obligatoriamente las secciones narrativas faltantes en JSON: "
            + ", ".join(missing_narrative_sections)
            + ". Usa candidate_preference_checks.v1 como autoridad dura para cualquier afirmacion sobre ubicacion, modalidad, compensacion y tipo de contrato. "
            + "No declares 'no evidenciado en el CV' para preferencias si candidate_preference_checks.v1 ya devolvio un estado."
        )
        normalized = _run_report_completion(
            person=person,
            opportunity=opportunity,
            person_id=person_id,
            person_context=person_context,
            opportunity_context=opportunity_context,
            evidence_adjudication_json=evidence_adjudication_json,
            alignment_summary_json=alignment_summary_json,
            evidence_analysis_json=evidence_analysis_json,
            fit_presentation_json=fit_presentation_json,
            preference_checks_json=preference_checks_json,
            settings=settings,
            llm_temperature=llm_temperature,
            phase_label="Step 8 v2 retry",
            retry_hint=retry_hint,
        )
        normalized["report"]["vacancy_fit_matrix"] = _deterministic_fit_matrix_from_presentation(
            normalized_fit_presentation
        )
        normalized["report"]["candidate_preference_matrix"] = _deterministic_preference_matrix(
            normalized_preference_checks
        )
        normalized = normalize_vacancy_alignment_report_v2_contract(normalized)
    normalized["vacancy_id"] = vacancy_id
    normalized["person_id"] = person_id
    normalized["generated_at"] = generated_at
    normalized["source_artifacts"] = {
        "evidence_adjudication_version": normalized_adjudication["contract_version"],
        "alignment_summary_version": normalized_summary["contract_version"],
        "evidence_analysis_version": normalized_analysis["contract_version"],
        "fit_presentation_version": normalized_fit_presentation["contract_version"],
        "preference_checks_version": normalized_preference_checks["contract_version"],
    }

    _validate_fit_matrix(
        normalized,
        normalized_adjudication,
        normalized_fit_presentation,
    )
    _validate_recommendations(normalized)
    missing_narrative_sections = _missing_required_narrative_sections(normalized)
    if missing_narrative_sections:
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 report omitted required narrative sections after retry: "
            + ", ".join(missing_narrative_sections)
        )

    if _has_meaningful_report(normalized):
        return normalized

    raise VacancyAlignmentReportV2BuildError(
        "Step 8 v2 LLM response produced empty alignment report; extraction aborted."
    )
