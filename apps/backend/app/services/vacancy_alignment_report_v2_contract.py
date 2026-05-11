from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2 = "vacancy_alignment_report.v2"
VACANCY_FIT_ROW_STATES = {
    "🟢 Cumple",
    "🟡 Parcial",
    "⚪ Sin informacion",
    "🔴 En conflicto",
    "🔵 Deseable no evidenciado",
}
PREFERENCE_ROW_STATES = {
    "🟢 Cumple",
    "🟡 Parcial",
    "⚪ Sin informacion",
    "🔴 En conflicto",
}
FINAL_RECOMMENDATIONS = {
    "Avanzar",
    "Avanzar con reservas",
    "Avanzar si se valida X",
    "No priorizar",
    "Descartar",
}
FIT_LEVELS = {"alto", "medio_alto", "medio", "bajo", "informacion_insuficiente"}
CONFIDENCE_LEVELS_ES = {"alta", "media", "baja"}
FIT_ANSWER_OPTIONS = {"sí", "si", "parcialmente", "no", "información insuficiente", "informacion insuficiente"}


class ExecutiveSummaryPayload(TypedDict):
    fit_level: str
    final_recommendation: str
    summary: str
    main_strength: str
    main_gap_or_risk: str
    confidence: str


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


class VacancyFitMatrixRowV2(TypedDict):
    item_id: str
    criterio: str
    categoria: str
    origen_del_criterio: str
    prioridad: str
    estado: str
    lo_que_solicita_la_vacante: str
    evidencia_del_candidato: str
    tipo_de_evidencia: str
    fuerza_de_evidencia: str
    descripcion_corta: str
    riesgo_para_la_postulacion: str
    fuentes: list[str]


class CandidatePreferenceMatrixRowV2(TypedDict):
    criterio: str
    categoria: str
    origen_del_criterio: str
    estado: str
    lo_que_ofrece_o_define_la_vacante: str
    preferencia_o_condicion_del_candidato: str
    descripcion_corta: str
    validacion_recomendada: str


class FitAnswerPayload(TypedDict):
    encaja: str
    respuesta_para_el_candidato: str


class StrengthItemV2(TypedDict):
    fortaleza: str
    por_que_importa: str
    evidencia: str


class GapItemV2(TypedDict):
    brecha: str
    tipo: str
    impacto: str
    accion_recomendada: str


class PreferenceConflictItemV2(TypedDict):
    criterio: str
    estado: str
    descripcion: str
    validacion_recomendada: str


class ImprovementActionsPayloadV2(TypedDict):
    reinforce_in_cv_or_profile: list[str]
    validate_with_recruiter: list[str]
    application_narrative: list[str]


class AlertConflictItemV2(TypedDict):
    tipo: str
    severidad: str
    descripcion: str


class ActionableConclusionPayloadV2(TypedDict):
    final_decision: str
    main_reason: str
    recommended_next_step: str
    confidence: str


class AlignmentReportPayloadV2(TypedDict):
    executive_summary: ExecutiveSummaryPayload
    decision_table: DecisionTablePayload
    vacancy_fit_matrix: list[VacancyFitMatrixRowV2]
    candidate_preference_matrix: list[CandidatePreferenceMatrixRowV2]
    fit_answer: FitAnswerPayload
    strengths: list[StrengthItemV2]
    gaps: list[GapItemV2]
    preference_conflicts: list[PreferenceConflictItemV2]
    improvement_actions: ImprovementActionsPayloadV2
    alerts_and_conflicts: list[AlertConflictItemV2]
    actionable_conclusion: ActionableConclusionPayloadV2


class SourceArtifactsPayloadV2(TypedDict):
    evidence_adjudication_version: str
    alignment_summary_version: str
    evidence_analysis_version: str
    fit_presentation_version: str
    preference_checks_version: str


class VacancyAlignmentReportV2Contract(TypedDict):
    contract_version: str
    vacancy_id: str
    person_id: str
    generated_at: str
    source_artifacts: SourceArtifactsPayloadV2
    report: AlignmentReportPayloadV2
    rendered_markdown: str


def _clean_text(value: Any, *, max_chars: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _clean_markdown(value: Any, *, max_chars: int = 32000) -> str:
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
        "resultado": _clean_text(raw.get("resultado"), max_chars=120),
        "descripcion_corta": _clean_text(raw.get("descripcion_corta"), max_chars=240),
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


def _empty_executive_summary() -> ExecutiveSummaryPayload:
    return {
        "fit_level": "",
        "final_recommendation": "",
        "summary": "",
        "main_strength": "",
        "main_gap_or_risk": "",
        "confidence": "",
    }


def _normalize_executive_summary(raw: Any) -> ExecutiveSummaryPayload:
    if not isinstance(raw, dict):
        return _empty_executive_summary()
    fit_level = _clean_text(raw.get("fit_level"), max_chars=40)
    final_recommendation = _clean_text(raw.get("final_recommendation"), max_chars=80)
    confidence = _clean_text(raw.get("confidence"), max_chars=16)
    return {
        "fit_level": fit_level if fit_level in FIT_LEVELS else "",
        "final_recommendation": (
            final_recommendation if final_recommendation in FINAL_RECOMMENDATIONS else ""
        ),
        "summary": _clean_text(raw.get("summary"), max_chars=2000),
        "main_strength": _clean_text(raw.get("main_strength"), max_chars=400),
        "main_gap_or_risk": _clean_text(raw.get("main_gap_or_risk"), max_chars=400),
        "confidence": confidence if confidence in CONFIDENCE_LEVELS_ES else "",
    }


def _normalize_sources(raw: Any) -> list[str]:
    return _normalize_string_list(raw, max_items=20, max_chars=200)


def _normalize_vacancy_fit_row(raw: Any) -> VacancyFitMatrixRowV2 | None:
    if not isinstance(raw, dict):
        return None
    estado = _clean_text(raw.get("estado"), max_chars=40)
    row: VacancyFitMatrixRowV2 = {
        "item_id": _clean_text(raw.get("item_id"), max_chars=64),
        "criterio": _clean_text(raw.get("criterio"), max_chars=280),
        "categoria": _clean_text(raw.get("categoria"), max_chars=80),
        "origen_del_criterio": _clean_text(raw.get("origen_del_criterio"), max_chars=80),
        "prioridad": _clean_text(raw.get("prioridad"), max_chars=40),
        "estado": estado if estado in VACANCY_FIT_ROW_STATES else "",
        "lo_que_solicita_la_vacante": _clean_text(raw.get("lo_que_solicita_la_vacante"), max_chars=800),
        "evidencia_del_candidato": _clean_text(raw.get("evidencia_del_candidato"), max_chars=800),
        "tipo_de_evidencia": _clean_text(raw.get("tipo_de_evidencia"), max_chars=40),
        "fuerza_de_evidencia": _clean_text(raw.get("fuerza_de_evidencia"), max_chars=40),
        "descripcion_corta": _clean_text(raw.get("descripcion_corta"), max_chars=240),
        "riesgo_para_la_postulacion": _clean_text(raw.get("riesgo_para_la_postulacion"), max_chars=40),
        "fuentes": _normalize_sources(raw.get("fuentes")),
    }
    if not row["item_id"] and not row["criterio"]:
        return None
    return row


def _normalize_vacancy_fit_rows(raw: Any) -> list[VacancyFitMatrixRowV2]:
    if not isinstance(raw, list):
        return []
    items: list[VacancyFitMatrixRowV2] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_vacancy_fit_row(value)
        if not normalized:
            continue
        signature = "|".join([normalized["item_id"].casefold(), normalized["criterio"].casefold()])
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _normalize_preference_row(raw: Any) -> CandidatePreferenceMatrixRowV2 | None:
    if not isinstance(raw, dict):
        return None
    estado = _clean_text(raw.get("estado"), max_chars=40)
    row: CandidatePreferenceMatrixRowV2 = {
        "criterio": _clean_text(raw.get("criterio"), max_chars=240),
        "categoria": _clean_text(raw.get("categoria"), max_chars=80),
        "origen_del_criterio": _clean_text(raw.get("origen_del_criterio"), max_chars=80),
        "estado": estado if estado in PREFERENCE_ROW_STATES else "",
        "lo_que_ofrece_o_define_la_vacante": _clean_text(raw.get("lo_que_ofrece_o_define_la_vacante"), max_chars=700),
        "preferencia_o_condicion_del_candidato": _clean_text(raw.get("preferencia_o_condicion_del_candidato"), max_chars=700),
        "descripcion_corta": _clean_text(raw.get("descripcion_corta"), max_chars=240),
        "validacion_recomendada": _clean_text(raw.get("validacion_recomendada"), max_chars=400),
    }
    if not row["criterio"]:
        return None
    return row


def _normalize_preference_rows(raw: Any) -> list[CandidatePreferenceMatrixRowV2]:
    if not isinstance(raw, list):
        return []
    items: list[CandidatePreferenceMatrixRowV2] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_preference_row(value)
        if not normalized:
            continue
        signature = "|".join([normalized["criterio"].casefold(), normalized["categoria"].casefold()])
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _normalize_fit_answer(raw: Any) -> FitAnswerPayload:
    if not isinstance(raw, dict):
        return {"encaja": "", "respuesta_para_el_candidato": ""}
    encaja = _clean_text(raw.get("encaja"), max_chars=40)
    return {
        "encaja": encaja if encaja in FIT_ANSWER_OPTIONS else "",
        "respuesta_para_el_candidato": _clean_text(raw.get("respuesta_para_el_candidato"), max_chars=1200),
    }


def _normalize_strength_item(raw: Any) -> StrengthItemV2 | None:
    if not isinstance(raw, dict):
        return None
    item: StrengthItemV2 = {
        "fortaleza": _clean_text(raw.get("fortaleza"), max_chars=280),
        "por_que_importa": _clean_text(raw.get("por_que_importa"), max_chars=400),
        "evidencia": _clean_text(raw.get("evidencia"), max_chars=500),
    }
    if not item["fortaleza"]:
        return None
    return item


def _normalize_gap_item(raw: Any) -> GapItemV2 | None:
    if not isinstance(raw, dict):
        return None
    item: GapItemV2 = {
        "brecha": _clean_text(raw.get("brecha"), max_chars=280),
        "tipo": _clean_text(raw.get("tipo"), max_chars=80),
        "impacto": _clean_text(raw.get("impacto"), max_chars=40),
        "accion_recomendada": _clean_text(raw.get("accion_recomendada"), max_chars=400),
    }
    if not item["brecha"]:
        return None
    return item


def _normalize_preference_conflict_item(raw: Any) -> PreferenceConflictItemV2 | None:
    if not isinstance(raw, dict):
        return None
    item: PreferenceConflictItemV2 = {
        "criterio": _clean_text(raw.get("criterio"), max_chars=280),
        "estado": _clean_text(raw.get("estado"), max_chars=40),
        "descripcion": _clean_text(raw.get("descripcion"), max_chars=500),
        "validacion_recomendada": _clean_text(raw.get("validacion_recomendada"), max_chars=400),
    }
    if not item["criterio"]:
        return None
    return item


def _normalize_improvement_actions(raw: Any) -> ImprovementActionsPayloadV2:
    if not isinstance(raw, dict):
        return {
            "reinforce_in_cv_or_profile": [],
            "validate_with_recruiter": [],
            "application_narrative": [],
        }
    return {
        "reinforce_in_cv_or_profile": _normalize_string_list(raw.get("reinforce_in_cv_or_profile")),
        "validate_with_recruiter": _normalize_string_list(raw.get("validate_with_recruiter")),
        "application_narrative": _normalize_string_list(raw.get("application_narrative")),
    }


def _normalize_alert_conflict_item(raw: Any) -> AlertConflictItemV2 | None:
    if not isinstance(raw, dict):
        return None
    item: AlertConflictItemV2 = {
        "tipo": _clean_text(raw.get("tipo"), max_chars=80),
        "severidad": _clean_text(raw.get("severidad"), max_chars=40),
        "descripcion": _clean_text(raw.get("descripcion"), max_chars=500),
    }
    if not item["descripcion"] and not item["tipo"]:
        return None
    return item


def _normalize_actionable_conclusion(raw: Any) -> ActionableConclusionPayloadV2:
    if not isinstance(raw, dict):
        return {
            "final_decision": "",
            "main_reason": "",
            "recommended_next_step": "",
            "confidence": "",
        }
    final_decision = _clean_text(raw.get("final_decision"), max_chars=80)
    confidence = _clean_text(raw.get("confidence"), max_chars=16)
    return {
        "final_decision": final_decision if final_decision in FINAL_RECOMMENDATIONS else "",
        "main_reason": _clean_text(raw.get("main_reason"), max_chars=500),
        "recommended_next_step": _clean_text(raw.get("recommended_next_step"), max_chars=500),
        "confidence": confidence if confidence in CONFIDENCE_LEVELS_ES else "",
    }


def _normalize_unique_list(raw: Any, normalizer: Any) -> list[Any]:
    if not isinstance(raw, list):
        return []
    items: list[Any] = []
    seen: set[str] = set()
    for value in raw:
        normalized = normalizer(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                str(normalized.get("item_id", "")).casefold(),
                str(normalized.get("criterio", "")).casefold(),
                str(normalized.get("fortaleza", "")).casefold(),
                str(normalized.get("brecha", "")).casefold(),
                str(normalized.get("descripcion", "")).casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _empty_report() -> AlignmentReportPayloadV2:
    return {
        "executive_summary": _empty_executive_summary(),
        "decision_table": _empty_decision_table(),
        "vacancy_fit_matrix": [],
        "candidate_preference_matrix": [],
        "fit_answer": {"encaja": "", "respuesta_para_el_candidato": ""},
        "strengths": [],
        "gaps": [],
        "preference_conflicts": [],
        "improvement_actions": _normalize_improvement_actions({}),
        "alerts_and_conflicts": [],
        "actionable_conclusion": _normalize_actionable_conclusion({}),
    }


def _normalize_report(raw: Any) -> AlignmentReportPayloadV2:
    if not isinstance(raw, dict):
        return _empty_report()
    return {
        "executive_summary": _normalize_executive_summary(raw.get("executive_summary")),
        "decision_table": _normalize_decision_table(raw.get("decision_table")),
        "vacancy_fit_matrix": _normalize_vacancy_fit_rows(raw.get("vacancy_fit_matrix")),
        "candidate_preference_matrix": _normalize_preference_rows(raw.get("candidate_preference_matrix")),
        "fit_answer": _normalize_fit_answer(raw.get("fit_answer")),
        "strengths": _normalize_unique_list(raw.get("strengths"), _normalize_strength_item),
        "gaps": _normalize_unique_list(raw.get("gaps"), _normalize_gap_item),
        "preference_conflicts": _normalize_unique_list(
            raw.get("preference_conflicts"),
            _normalize_preference_conflict_item,
        ),
        "improvement_actions": _normalize_improvement_actions(raw.get("improvement_actions")),
        "alerts_and_conflicts": _normalize_unique_list(
            raw.get("alerts_and_conflicts"),
            _normalize_alert_conflict_item,
        ),
        "actionable_conclusion": _normalize_actionable_conclusion(raw.get("actionable_conclusion")),
    }


def empty_vacancy_alignment_report_v2_contract() -> VacancyAlignmentReportV2Contract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2,
        "vacancy_id": "",
        "person_id": "",
        "generated_at": "",
        "source_artifacts": {
            "evidence_adjudication_version": "",
            "alignment_summary_version": "",
            "evidence_analysis_version": "",
            "fit_presentation_version": "",
            "preference_checks_version": "",
        },
        "report": _empty_report(),
        "rendered_markdown": "",
    }


def normalize_vacancy_alignment_report_v2_contract(raw: Any) -> VacancyAlignmentReportV2Contract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_alignment_report_v2_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["person_id"] = _clean_text(source.get("person_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    source_artifacts = source.get("source_artifacts") if isinstance(source.get("source_artifacts"), dict) else {}
    normalized["source_artifacts"] = {
        "evidence_adjudication_version": _clean_text(source_artifacts.get("evidence_adjudication_version"), max_chars=64),
        "alignment_summary_version": _clean_text(source_artifacts.get("alignment_summary_version"), max_chars=64),
        "evidence_analysis_version": _clean_text(source_artifacts.get("evidence_analysis_version"), max_chars=64),
        "fit_presentation_version": _clean_text(source_artifacts.get("fit_presentation_version"), max_chars=64),
        "preference_checks_version": _clean_text(source_artifacts.get("preference_checks_version"), max_chars=64),
    }
    normalized["report"] = _normalize_report(source.get("report"))
    normalized["rendered_markdown"] = _clean_markdown(source.get("rendered_markdown"))
    return normalized


def is_vacancy_alignment_report_v2_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        str(raw.get("contract_version", "")).strip()
        == CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2
    )
