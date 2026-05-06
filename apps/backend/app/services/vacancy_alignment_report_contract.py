from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT = "vacancy_alignment_report.v1"


class DecisionTableEntry(TypedDict):
    resultado: str
    descripcion_corta: str


class DecisionTablePayload(TypedDict):
    alineacion_general: DecisionTableEntry
    fit_objetivo: DecisionTableEntry
    fit_preferencial: DecisionTableEntry
    requisitos_criticos_cumplidos: DecisionTableEntry
    bloqueadores: DecisionTableEntry
    alertas_relevantes: DecisionTableEntry
    potencial_mejora_fit: DecisionTableEntry
    recomendacion: DecisionTableEntry


class VacancyFitMatrixRow(TypedDict):
    criterio: str
    categoria: str
    origen_del_criterio: str
    estado: str
    lo_que_solicita_la_vacante: str
    evidencia_del_candidato: str
    descripcion_corta: str


class CandidatePreferenceMatrixRow(TypedDict):
    criterio: str
    categoria: str
    origen_del_criterio: str
    estado: str
    lo_que_ofrece_o_define_la_vacante: str
    preferencia_o_condicion_del_candidato: str
    descripcion_corta: str


class ImprovementActionsPayload(TypedDict):
    reinforce_in_cv_or_profile: list[str]
    validate_with_recruiter: list[str]
    application_narrative: list[str]


class ActionableConclusionPayload(TypedDict):
    final_decision: str
    main_reason: str
    recommended_next_step: str


class SourceArtifactsPayload(TypedDict):
    alignment_summary_version: str
    evidence_analysis_version: str


class AlignmentReportPayload(TypedDict):
    executive_summary: str
    decision_table: DecisionTablePayload
    vacancy_fit_matrix: list[VacancyFitMatrixRow]
    candidate_preference_matrix: list[CandidatePreferenceMatrixRow]
    fit_answer: str
    strengths: list[str]
    gaps: list[str]
    preference_conflicts: list[str]
    improvement_actions: ImprovementActionsPayload
    alerts_and_conflicts: list[str]
    actionable_conclusion: ActionableConclusionPayload


class VacancyAlignmentReportContract(TypedDict):
    contract_version: str
    vacancy_id: str
    person_id: str
    generated_at: str
    source_artifacts: SourceArtifactsPayload
    report: AlignmentReportPayload
    rendered_markdown: str


def _clean_text(value: Any, *, max_chars: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _clean_markdown(value: Any, *, max_chars: int = 24000) -> str:
    text = str(value or "")
    if not text.strip():
        return ""
    normalized_lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(normalized_lines).strip()
    if not normalized:
        return ""
    return normalized[:max_chars].rstrip()


def _normalize_string_list(raw: Any, *, max_items: int = 100, max_chars: int = 400) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw[:max_items]:
        normalized = _clean_text(value, max_chars=max_chars)
        if not normalized:
            continue
        signature = normalized.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _empty_decision_entry() -> DecisionTableEntry:
    return {"resultado": "", "descripcion_corta": ""}


def _normalize_decision_entry(raw: Any) -> DecisionTableEntry:
    if not isinstance(raw, dict):
        return _empty_decision_entry()
    return {
        "resultado": _clean_text(raw.get("resultado"), max_chars=80),
        "descripcion_corta": _clean_text(raw.get("descripcion_corta"), max_chars=120),
    }


def _empty_decision_table() -> DecisionTablePayload:
    return {
        "alineacion_general": _empty_decision_entry(),
        "fit_objetivo": _empty_decision_entry(),
        "fit_preferencial": _empty_decision_entry(),
        "requisitos_criticos_cumplidos": _empty_decision_entry(),
        "bloqueadores": _empty_decision_entry(),
        "alertas_relevantes": _empty_decision_entry(),
        "potencial_mejora_fit": _empty_decision_entry(),
        "recomendacion": _empty_decision_entry(),
    }


def _normalize_decision_table(raw: Any) -> DecisionTablePayload:
    if not isinstance(raw, dict):
        return _empty_decision_table()
    return {
        "alineacion_general": _normalize_decision_entry(raw.get("alineacion_general")),
        "fit_objetivo": _normalize_decision_entry(raw.get("fit_objetivo")),
        "fit_preferencial": _normalize_decision_entry(raw.get("fit_preferencial")),
        "requisitos_criticos_cumplidos": _normalize_decision_entry(raw.get("requisitos_criticos_cumplidos")),
        "bloqueadores": _normalize_decision_entry(raw.get("bloqueadores")),
        "alertas_relevantes": _normalize_decision_entry(raw.get("alertas_relevantes")),
        "potencial_mejora_fit": _normalize_decision_entry(raw.get("potencial_mejora_fit")),
        "recomendacion": _normalize_decision_entry(raw.get("recomendacion")),
    }


def _empty_vacancy_fit_row() -> VacancyFitMatrixRow:
    return {
        "criterio": "",
        "categoria": "",
        "origen_del_criterio": "",
        "estado": "",
        "lo_que_solicita_la_vacante": "",
        "evidencia_del_candidato": "",
        "descripcion_corta": "",
    }


def _normalize_vacancy_fit_row(raw: Any) -> VacancyFitMatrixRow | None:
    if not isinstance(raw, dict):
        return None
    row = _empty_vacancy_fit_row()
    row["criterio"] = _clean_text(raw.get("criterio"), max_chars=240)
    row["categoria"] = _clean_text(raw.get("categoria"), max_chars=80)
    row["origen_del_criterio"] = _clean_text(raw.get("origen_del_criterio"), max_chars=80)
    row["estado"] = _clean_text(raw.get("estado"), max_chars=80)
    row["lo_que_solicita_la_vacante"] = _clean_text(raw.get("lo_que_solicita_la_vacante"), max_chars=500)
    row["evidencia_del_candidato"] = _clean_text(raw.get("evidencia_del_candidato"), max_chars=500)
    row["descripcion_corta"] = _clean_text(raw.get("descripcion_corta"), max_chars=160)
    if not row["criterio"]:
        return None
    return row


def _normalize_vacancy_fit_rows(raw: Any) -> list[VacancyFitMatrixRow]:
    if not isinstance(raw, list):
        return []
    items: list[VacancyFitMatrixRow] = []
    seen: set[str] = set()
    for value in raw:
        row = _normalize_vacancy_fit_row(value)
        if not row:
            continue
        signature = "|".join([row["criterio"].casefold(), row["categoria"].casefold(), row["origen_del_criterio"].casefold()])
        if signature in seen:
            continue
        seen.add(signature)
        items.append(row)
    return items


def _empty_preference_row() -> CandidatePreferenceMatrixRow:
    return {
        "criterio": "",
        "categoria": "",
        "origen_del_criterio": "",
        "estado": "",
        "lo_que_ofrece_o_define_la_vacante": "",
        "preferencia_o_condicion_del_candidato": "",
        "descripcion_corta": "",
    }


def _normalize_preference_row(raw: Any) -> CandidatePreferenceMatrixRow | None:
    if not isinstance(raw, dict):
        return None
    row = _empty_preference_row()
    row["criterio"] = _clean_text(raw.get("criterio"), max_chars=240)
    row["categoria"] = _clean_text(raw.get("categoria"), max_chars=80)
    row["origen_del_criterio"] = _clean_text(raw.get("origen_del_criterio"), max_chars=80)
    row["estado"] = _clean_text(raw.get("estado"), max_chars=80)
    row["lo_que_ofrece_o_define_la_vacante"] = _clean_text(raw.get("lo_que_ofrece_o_define_la_vacante"), max_chars=500)
    row["preferencia_o_condicion_del_candidato"] = _clean_text(raw.get("preferencia_o_condicion_del_candidato"), max_chars=500)
    row["descripcion_corta"] = _clean_text(raw.get("descripcion_corta"), max_chars=160)
    if not row["criterio"]:
        return None
    return row


def _normalize_preference_rows(raw: Any) -> list[CandidatePreferenceMatrixRow]:
    if not isinstance(raw, list):
        return []
    items: list[CandidatePreferenceMatrixRow] = []
    seen: set[str] = set()
    for value in raw:
        row = _normalize_preference_row(value)
        if not row:
            continue
        signature = "|".join([row["criterio"].casefold(), row["categoria"].casefold(), row["origen_del_criterio"].casefold()])
        if signature in seen:
            continue
        seen.add(signature)
        items.append(row)
    return items


def _empty_improvement_actions() -> ImprovementActionsPayload:
    return {
        "reinforce_in_cv_or_profile": [],
        "validate_with_recruiter": [],
        "application_narrative": [],
    }


def _normalize_improvement_actions(raw: Any) -> ImprovementActionsPayload:
    if not isinstance(raw, dict):
        return _empty_improvement_actions()
    return {
        "reinforce_in_cv_or_profile": _normalize_string_list(raw.get("reinforce_in_cv_or_profile")),
        "validate_with_recruiter": _normalize_string_list(raw.get("validate_with_recruiter")),
        "application_narrative": _normalize_string_list(raw.get("application_narrative")),
    }


def _empty_actionable_conclusion() -> ActionableConclusionPayload:
    return {
        "final_decision": "",
        "main_reason": "",
        "recommended_next_step": "",
    }


def _normalize_actionable_conclusion(raw: Any) -> ActionableConclusionPayload:
    if not isinstance(raw, dict):
        return _empty_actionable_conclusion()
    return {
        "final_decision": _clean_text(raw.get("final_decision"), max_chars=120),
        "main_reason": _clean_text(raw.get("main_reason"), max_chars=500),
        "recommended_next_step": _clean_text(raw.get("recommended_next_step"), max_chars=500),
    }


def _empty_report() -> AlignmentReportPayload:
    return {
        "executive_summary": "",
        "decision_table": _empty_decision_table(),
        "vacancy_fit_matrix": [],
        "candidate_preference_matrix": [],
        "fit_answer": "",
        "strengths": [],
        "gaps": [],
        "preference_conflicts": [],
        "improvement_actions": _empty_improvement_actions(),
        "alerts_and_conflicts": [],
        "actionable_conclusion": _empty_actionable_conclusion(),
    }


def _normalize_report(raw: Any) -> AlignmentReportPayload:
    if not isinstance(raw, dict):
        return _empty_report()
    return {
        "executive_summary": _clean_text(raw.get("executive_summary"), max_chars=2000),
        "decision_table": _normalize_decision_table(raw.get("decision_table")),
        "vacancy_fit_matrix": _normalize_vacancy_fit_rows(raw.get("vacancy_fit_matrix")),
        "candidate_preference_matrix": _normalize_preference_rows(raw.get("candidate_preference_matrix")),
        "fit_answer": _clean_text(raw.get("fit_answer"), max_chars=1200),
        "strengths": _normalize_string_list(raw.get("strengths")),
        "gaps": _normalize_string_list(raw.get("gaps")),
        "preference_conflicts": _normalize_string_list(raw.get("preference_conflicts")),
        "improvement_actions": _normalize_improvement_actions(raw.get("improvement_actions")),
        "alerts_and_conflicts": _normalize_string_list(raw.get("alerts_and_conflicts")),
        "actionable_conclusion": _normalize_actionable_conclusion(raw.get("actionable_conclusion")),
    }


def empty_vacancy_alignment_report_contract() -> VacancyAlignmentReportContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT,
        "vacancy_id": "",
        "person_id": "",
        "generated_at": "",
        "source_artifacts": {
            "alignment_summary_version": "",
            "evidence_analysis_version": "",
        },
        "report": _empty_report(),
        "rendered_markdown": "",
    }


def normalize_vacancy_alignment_report_contract(raw: Any) -> VacancyAlignmentReportContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_alignment_report_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["person_id"] = _clean_text(source.get("person_id"), max_chars=80)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    source_artifacts = source.get("source_artifacts") if isinstance(source.get("source_artifacts"), dict) else {}
    normalized["source_artifacts"] = {
        "alignment_summary_version": _clean_text(source_artifacts.get("alignment_summary_version"), max_chars=64),
        "evidence_analysis_version": _clean_text(source_artifacts.get("evidence_analysis_version"), max_chars=64),
    }
    normalized["report"] = _normalize_report(source.get("report"))
    normalized["rendered_markdown"] = _clean_markdown(source.get("rendered_markdown"), max_chars=24000)
    return normalized


def is_vacancy_alignment_report_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT
