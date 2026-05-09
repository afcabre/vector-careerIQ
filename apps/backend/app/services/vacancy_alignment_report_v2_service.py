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


def _validate_fit_matrix(
    report_contract: VacancyAlignmentReportV2Contract,
    adjudication_contract: VacancyEvidenceAdjudicationContract,
) -> None:
    expected_item_ids = _evaluable_item_ids(adjudication_contract)
    actual_rows = report_contract["report"]["vacancy_fit_matrix"]
    actual_item_ids = {row["item_id"] for row in actual_rows if row["item_id"]}
    if actual_item_ids != expected_item_ids:
        missing = sorted(expected_item_ids - actual_item_ids)
        extra = sorted(actual_item_ids - expected_item_ids)
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 report matrix completeness check failed."
            f" missing_item_ids={missing} extra_item_ids={extra}"
        )

    adjudication_index = _build_adjudication_index(adjudication_contract)
    for row in actual_rows:
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

    fallback_user_prompt = (
        "Actua como analista senior de alineacion candidato-vacante, orientado a ayudar al candidato y/o a su tutor a decidir si conviene priorizar esta vacante. "
        "Responde SOLO JSON valido conforme a vacancy_alignment_report.v2. "
        "No escribas texto fuera del JSON. Debes producir exactamente dos claves raiz: report, rendered_markdown. "
        "Usa vacancy_evidence_adjudication.v1 como insumo principal. Usa vacancy_alignment_summary.v2 como resumen auxiliar. Usa vacancy_evidence_analysis.v1 solo como respaldo. "
        "No inventes informacion, no infles el perfil, no omitas criterios evaluados y no recalcules scores. "
        "vacancy_fit_matrix debe incluir todos los criterios evaluados excepto not_applicable. "
        "Mapeo obligatorio: direct -> 🟢 Cumple; partial/indirect -> 🟡 Parcial; not_evidenced obligatorio -> ⚪ Sin informacion; not_evidenced deseable -> 🔵 Deseable no evidenciado; conflict -> 🔴 En conflicto. "
        "Usa solo estas recomendaciones: Avanzar, Avanzar con reservas, Avanzar si se valida X, No priorizar, Descartar. "
        "Persona: {person_context}. Vacante: {opportunity_context}. "
        "Entrada vacancy_evidence_adjudication.v1: {evidence_adjudication_json}. "
        "Entrada vacancy_alignment_summary.v2: {alignment_summary_json}. "
        "Entrada vacancy_evidence_analysis.v1: {evidence_analysis_json}."
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2,
        context={
            "person_context": person_context,
            "opportunity_context": opportunity_context,
            "evidence_adjudication_json": evidence_adjudication_json,
            "alignment_summary_json": alignment_summary_json,
            "evidence_analysis_json": evidence_analysis_json,
        },
        fallback=fallback_user_prompt,
    )
    runtime_config = get_vacancy_v2_runtime_config(settings)
    llm_temperature = float(runtime_config["step3"]["llm_temperature"])

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
            "Step 8 v2 LLM response unavailable; alignment report aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyAlignmentReportV2BuildError(
            "Step 8 v2 LLM response is not valid JSON; alignment report aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    normalized = normalize_vacancy_alignment_report_v2_contract(candidate)
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
