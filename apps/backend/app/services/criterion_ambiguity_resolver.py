from __future__ import annotations

import json
from typing import Any

from app.core.settings import Settings
from app.services.criterion_evaluator import (
    EVIDENCE_DIRECT,
    EVIDENCE_INDIRECT,
    EVIDENCE_NONE,
    GAP_DESIRABLE,
    GAP_EVIDENCE,
    GAP_NONE,
    GAP_PREFERENCE,
    GAP_QUALIFICATION,
    STATUS_CONFLICT,
    STATUS_MEETS,
    STATUS_NOT_EVIDENCED_DESIRABLE,
    STATUS_PARTIAL,
    STATUS_UNKNOWN,
    CriterionEvaluationRow,
)
from app.services.guardrail_service import enforce_output_guardrails
from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt


ALLOWED_STATUSES = {
    STATUS_MEETS,
    STATUS_PARTIAL,
    STATUS_UNKNOWN,
    STATUS_CONFLICT,
    STATUS_NOT_EVIDENCED_DESIRABLE,
}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
MAX_AMBIGUITY_ROWS = 6
VACANCY_RAW_TEXT_MAX_CHARS = 1200


def _extract_json_object(raw_text: str) -> dict[str, object] | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_ambiguous(row: CriterionEvaluationRow) -> bool:
    evaluation = row.get("evaluation", {})
    status = str(evaluation.get("status", STATUS_UNKNOWN)).strip()
    confidence = str(evaluation.get("confidence", "low")).strip()
    if status == STATUS_UNKNOWN:
        return True
    if status == STATUS_PARTIAL and confidence in {"low", "medium"}:
        return True
    return False


def _matches_preview(row: CriterionEvaluationRow) -> list[str]:
    retrieval = row.get("retrieval_evidence", {})
    lines: list[str] = []
    cv_matches = retrieval.get("cv_matches", [])
    if isinstance(cv_matches, list):
        for item in cv_matches[:1]:
            if not isinstance(item, dict):
                continue
            snippet = str(item.get("text", "")).strip()
            if not snippet:
                continue
            score = item.get("score", "")
            lines.append(f"cv(score={score}): {snippet}")
    profile_matches = retrieval.get("profile_evidence", [])
    if isinstance(profile_matches, list):
        for item in profile_matches[:1]:
            text = str(item).strip()
            if text:
                lines.append(f"profile: {text}")
    return lines


def _ambiguity_priority(row: CriterionEvaluationRow) -> tuple[int, int, int, str]:
    origin = str(row.get("origin", "")).strip()
    status = str(row.get("evaluation", {}).get("status", STATUS_UNKNOWN)).strip()
    confidence = str(row.get("evaluation", {}).get("confidence", "low")).strip()
    origin_rank = {
        "vacante_obligatoria": 0,
        "vacante_condicion": 1,
        "preferencia_candidato": 2,
        "vacante_deseable": 3,
    }.get(origin, 4)
    status_rank = {
        STATUS_PARTIAL: 0,
        STATUS_UNKNOWN: 1,
    }.get(status, 2)
    confidence_rank = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }.get(confidence, 3)
    return (
        origin_rank,
        status_rank,
        confidence_rank,
        str(row.get("criterion_label", "")).strip(),
    )


def _ambiguity_prompt(
    *,
    ambiguous_rows: list[CriterionEvaluationRow],
    total_ambiguous_rows: int,
    person_context: str,
    opportunity_context: str,
    vacancy_raw_text: str,
) -> str:
    lines = [
        "Resuelve solo criterios ambiguos de alineacion perfil-vacante.",
        "Debes devolver JSON valido sin markdown con esta forma:",
        '{"resolved":[{"criterion_id":"","status":"","confidence":"","semantic_notes":"","missing_information":[]}]}',
        "Reglas:",
        "- Usa solo estos status: meets, partial, unknown, conflict, not_evidenced_desirable",
        "- Usa solo confidence: low, medium, high",
        "- La fuente principal es la vacante estructurada y la evidencia por criterio",
        "- Usa el texto libre de vacante solo como apoyo contextual",
        "- No inventes evidencia ausente",
        "- Si persiste duda, conserva unknown o partial",
        "",
        "Persona:",
        person_context,
        "",
        "Vacante estructurada:",
        opportunity_context,
        "",
        "Texto libre de la vacante (auxiliar):",
        vacancy_raw_text[:VACANCY_RAW_TEXT_MAX_CHARS].strip() or "No disponible",
        "",
        "Criterios ambiguos:",
    ]
    if total_ambiguous_rows > len(ambiguous_rows):
        lines.append(
            f"Nota: se priorizan {len(ambiguous_rows)} criterios ambiguos de {total_ambiguous_rows} totales para reducir latencia."
        )
    for row in ambiguous_rows:
        evaluation = row.get("evaluation", {})
        lines.append(
            f"- criterion_id={row.get('criterion_id', '')} | "
            f"label={row.get('criterion_label', '')} | "
            f"origin={row.get('origin', '')} | "
            f"category={row.get('category', '')} | "
            f"status_actual={evaluation.get('status', '')} | "
            f"nota_actual={evaluation.get('semantic_notes', '')}"
        )
        payload = row.get("criterion_payload", {})
        if payload:
            lines.append(f"  payload={json.dumps(payload, ensure_ascii=False)}")
        for item in _matches_preview(row):
            lines.append(f"  evidencia={item}")
    return "\n".join(lines)


def _status_gap_type(status: str, origin: str, affects_preference_fit: bool) -> str:
    if status == STATUS_MEETS:
        return GAP_NONE
    if status == STATUS_CONFLICT:
        return GAP_PREFERENCE if affects_preference_fit else GAP_QUALIFICATION
    if status == STATUS_NOT_EVIDENCED_DESIRABLE or origin == "vacante_deseable":
        return GAP_DESIRABLE
    if status == STATUS_UNKNOWN:
        return GAP_EVIDENCE
    return GAP_QUALIFICATION


def _status_evidence_strength(status: str, row: CriterionEvaluationRow) -> str:
    retrieval = row.get("retrieval_evidence", {})
    cv_matches = retrieval.get("cv_matches", [])
    profile_matches = retrieval.get("profile_evidence", [])
    has_matches = bool(cv_matches) or bool(profile_matches)
    if not has_matches:
        return EVIDENCE_NONE
    if status == STATUS_MEETS:
        return EVIDENCE_DIRECT
    return EVIDENCE_INDIRECT


def resolve_criteria_ambiguity(
    *,
    rows: list[CriterionEvaluationRow],
    person_context: str,
    opportunity_context: str,
    vacancy_raw_text: str,
    system_prompt: str,
    settings: Settings,
    person_id: str,
    opportunity_id: str,
    run_id: str,
) -> list[CriterionEvaluationRow]:
    all_ambiguous_rows = [row for row in rows if _is_ambiguous(row)]
    if not all_ambiguous_rows:
        return rows
    ambiguous_rows = sorted(all_ambiguous_rows, key=_ambiguity_priority)[:MAX_AMBIGUITY_ROWS]

    prompt = _ambiguity_prompt(
        ambiguous_rows=ambiguous_rows,
        total_ambiguous_rows=len(all_ambiguous_rows),
        person_context=person_context,
        opportunity_context=opportunity_context,
        vacancy_raw_text=vacancy_raw_text,
    )
    response = complete_prompt(
        system_prompt,
        prompt,
        settings,
        temperature=0.1,
        person_id=person_id,
        opportunity_id=opportunity_id,
        flow_key="analyze_profile_match_ambiguity",
        run_id=run_id,
    )
    response = enforce_output_guardrails(response)
    if response == FALLBACK_MESSAGE:
        return rows

    payload = _extract_json_object(response)
    if not payload:
        return rows

    raw_resolved = payload.get("resolved", [])
    if not isinstance(raw_resolved, list):
        return rows
    resolved_by_id: dict[str, dict[str, Any]] = {}
    for item in raw_resolved:
        if not isinstance(item, dict):
            continue
        criterion_id = str(item.get("criterion_id", "")).strip()
        status = str(item.get("status", "")).strip()
        confidence = str(item.get("confidence", "")).strip()
        if not criterion_id or status not in ALLOWED_STATUSES or confidence not in ALLOWED_CONFIDENCE:
            continue
        resolved_by_id[criterion_id] = item

    if not resolved_by_id:
        return rows

    updated_rows: list[CriterionEvaluationRow] = []
    for row in rows:
        criterion_id = str(row.get("criterion_id", "")).strip()
        resolved = resolved_by_id.get(criterion_id)
        if not resolved:
            updated_rows.append(row)
            continue
        updated = dict(row)
        evaluation = dict(row.get("evaluation", {}))
        status = str(resolved.get("status", evaluation.get("status", STATUS_UNKNOWN))).strip()
        affects_preference_fit = bool(evaluation.get("affects_preference_fit", False))
        evaluation["status"] = status
        evaluation["confidence"] = str(
            resolved.get("confidence", evaluation.get("confidence", "medium"))
        ).strip()
        evaluation["semantic_notes"] = str(
            resolved.get("semantic_notes", evaluation.get("semantic_notes", ""))
        ).strip()
        missing_information = resolved.get("missing_information", evaluation.get("missing_information", []))
        if isinstance(missing_information, list):
            evaluation["missing_information"] = [
                str(item).strip() for item in missing_information if str(item).strip()
            ]
        evaluation["evidence_strength"] = _status_evidence_strength(status, row)
        evaluation["gap_type"] = _status_gap_type(
            status,
            str(row.get("origin", "")).strip(),
            affects_preference_fit,
        )
        evaluation["is_blocking"] = bool(
            status == STATUS_CONFLICT
            and str(row.get("origin", "")).strip() in {"vacante_obligatoria", "vacante_condicion"}
        )
        evaluation["resolution_source"] = "llm_assisted"
        updated["evaluation"] = evaluation
        updated_rows.append(updated)  # type: ignore[arg-type]
    return updated_rows
