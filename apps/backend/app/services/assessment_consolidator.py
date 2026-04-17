from __future__ import annotations

from typing import Any, TypedDict

from app.services.criterion_evaluator import (
    STATUS_CONFLICT,
    STATUS_MEETS,
    STATUS_NOT_EVIDENCED_DESIRABLE,
    STATUS_PARTIAL,
    STATUS_UNKNOWN,
    CriterionEvaluationRow,
)


DECISION_ADVANCE = "Avanzar"
DECISION_ADVANCE_WITH_RESERVATIONS = "Avanzar con reservas"
DECISION_ADVANCE_IF_VALIDATE = "Avanzar si se valida X"
DECISION_DEPRIORITIZE = "No priorizar"
DECISION_DISCARD = "Descartar"


class FitSummary(TypedDict):
    level: str
    score: float
    total: int
    counts: dict[str, int]
    summary: str


class ConsolidatedAssessment(TypedDict):
    objective_fit: FitSummary
    preference_fit: FitSummary
    blocking_issues: list[str]
    relevant_alerts: list[str]
    strengths: list[str]
    gaps: list[str]
    unknowns: list[str]
    recommended_decision: str
    recommended_decision_reason: str


def _counts_template() -> dict[str, int]:
    return {
        STATUS_MEETS: 0,
        STATUS_PARTIAL: 0,
        STATUS_UNKNOWN: 0,
        STATUS_CONFLICT: 0,
        STATUS_NOT_EVIDENCED_DESIRABLE: 0,
    }


def _safe_note(row: CriterionEvaluationRow) -> str:
    evaluation = row.get("evaluation", {})
    note = str(evaluation.get("semantic_notes", "")).strip()
    if note:
        return note
    return "Sin nota explicita"


def _row_label(row: CriterionEvaluationRow) -> str:
    label = str(row.get("criterion_label", "")).strip()
    if label:
        return label
    return str(row.get("criterion_id", "")).strip() or "criterio_sin_nombre"


def _row_origin(row: CriterionEvaluationRow) -> str:
    return str(row.get("origin", "")).strip()


def _row_status(row: CriterionEvaluationRow) -> str:
    return str(row.get("evaluation", {}).get("status", STATUS_UNKNOWN)).strip()


def _row_weight(row: CriterionEvaluationRow) -> float:
    status = _row_status(row)
    if status == STATUS_MEETS:
        return 1.0
    if status == STATUS_PARTIAL:
        return 0.55
    if status == STATUS_UNKNOWN:
        return 0.35
    if status == STATUS_NOT_EVIDENCED_DESIRABLE:
        return 0.4
    return 0.0


def _fit_level(score: float, total: int) -> str:
    if total <= 0:
        return "unknown"
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _fit_summary(rows: list[CriterionEvaluationRow]) -> FitSummary:
    counts = _counts_template()
    if not rows:
        return FitSummary(
            level="unknown",
            score=0.0,
            total=0,
            counts=counts,
            summary="Sin criterios comparables",
        )

    total_weight = 0.0
    for row in rows:
        status = _row_status(row)
        counts[status] = counts.get(status, 0) + 1
        total_weight += _row_weight(row)

    total = len(rows)
    score = round(total_weight / total, 3)
    level = _fit_level(score, total)
    summary_bits: list[str] = []
    if counts[STATUS_MEETS]:
        summary_bits.append(f"{counts[STATUS_MEETS]} cumplen")
    if counts[STATUS_PARTIAL]:
        summary_bits.append(f"{counts[STATUS_PARTIAL]} parciales")
    if counts[STATUS_CONFLICT]:
        summary_bits.append(f"{counts[STATUS_CONFLICT]} conflictos")
    if counts[STATUS_UNKNOWN]:
        summary_bits.append(f"{counts[STATUS_UNKNOWN]} sin informacion")
    if counts[STATUS_NOT_EVIDENCED_DESIRABLE]:
        summary_bits.append(f"{counts[STATUS_NOT_EVIDENCED_DESIRABLE]} deseables no evidenciados")
    summary = ", ".join(summary_bits) if summary_bits else "Sin hallazgos relevantes"
    return FitSummary(
        level=level,
        score=score,
        total=total,
        counts=counts,
        summary=summary,
    )


def _dedupe(values: list[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        items.append(cleaned)
    return items


def _strengths(rows: list[CriterionEvaluationRow]) -> list[str]:
    values: list[str] = []
    for row in rows:
        if _row_status(row) != STATUS_MEETS:
            continue
        values.append(f"{_row_label(row)}: {_safe_note(row)}")
    return _dedupe(values)


def _gaps(rows: list[CriterionEvaluationRow]) -> list[str]:
    values: list[str] = []
    for row in rows:
        status = _row_status(row)
        if status not in {STATUS_PARTIAL, STATUS_CONFLICT, STATUS_NOT_EVIDENCED_DESIRABLE}:
            continue
        values.append(f"{_row_label(row)}: {_safe_note(row)}")
    return _dedupe(values)


def _unknowns(rows: list[CriterionEvaluationRow]) -> list[str]:
    values: list[str] = []
    for row in rows:
        if _row_status(row) != STATUS_UNKNOWN:
            continue
        missing = row.get("evaluation", {}).get("missing_information", [])
        suffix = ""
        if isinstance(missing, list) and missing:
            suffix = f" ({', '.join(str(item) for item in missing if str(item).strip())})"
        values.append(f"{_row_label(row)}: {_safe_note(row)}{suffix}")
    return _dedupe(values)


def _blocking_issues(rows: list[CriterionEvaluationRow]) -> list[str]:
    values: list[str] = []
    for row in rows:
        evaluation = row.get("evaluation", {})
        if not bool(evaluation.get("is_blocking", False)):
            continue
        values.append(f"{_row_label(row)}: {_safe_note(row)}")
    return _dedupe(values)


def _relevant_alerts(rows: list[CriterionEvaluationRow]) -> list[str]:
    values: list[str] = []
    for row in rows:
        status = _row_status(row)
        origin = _row_origin(row)
        if status == STATUS_CONFLICT:
            values.append(f"{_row_label(row)}: {_safe_note(row)}")
            continue
        if status == STATUS_PARTIAL and origin in {"vacante_obligatoria", "vacante_condicion"}:
            values.append(f"{_row_label(row)}: validacion adicional recomendada")
            continue
        if status == STATUS_UNKNOWN and origin in {"vacante_obligatoria", "vacante_condicion"}:
            values.append(f"{_row_label(row)}: falta evidencia comparativa")
    return _dedupe(values)


def _validation_targets(rows: list[CriterionEvaluationRow]) -> list[str]:
    values: list[str] = []
    for row in rows:
        origin = _row_origin(row)
        status = _row_status(row)
        if origin not in {"vacante_obligatoria", "vacante_condicion"}:
            continue
        if status not in {STATUS_PARTIAL, STATUS_UNKNOWN}:
            continue
        values.append(_row_label(row))
    return _dedupe(values)


def _recommended_decision(
    *,
    objective_fit: FitSummary,
    preference_fit: FitSummary,
    blocking_issues: list[str],
    alerts: list[str],
    validation_targets: list[str],
) -> tuple[str, str]:
    objective_score = float(objective_fit.get("score", 0.0) or 0.0)
    preference_score = float(preference_fit.get("score", 0.0) or 0.0)
    objective_counts = objective_fit.get("counts", {})
    total_objective = int(objective_fit.get("total", 0) or 0)
    conflict_count = int(objective_counts.get(STATUS_CONFLICT, 0) or 0)
    unknown_count = int(objective_counts.get(STATUS_UNKNOWN, 0) or 0)
    partial_count = int(objective_counts.get(STATUS_PARTIAL, 0) or 0)

    if blocking_issues:
        return DECISION_DISCARD, f"Existen bloqueadores explicitos: {blocking_issues[0]}"

    if total_objective >= 3 and objective_score < 0.25:
        return DECISION_DISCARD, "El ajuste objetivo es demasiado bajo para priorizar la vacante"

    if validation_targets:
        preview = ", ".join(validation_targets[:2])
        suffix = "..." if len(validation_targets) > 2 else ""
        return DECISION_ADVANCE_IF_VALIDATE, f"Conviene validar primero: {preview}{suffix}"

    if objective_score >= 0.8 and conflict_count == 0 and partial_count <= 1 and preference_score >= 0.55:
        return DECISION_ADVANCE, "La mayor parte de los criterios centrales muestra ajuste suficiente"

    if objective_score >= 0.6:
        if alerts or preference_score < 0.45 or unknown_count > 0:
            return DECISION_ADVANCE_WITH_RESERVATIONS, "Hay ajuste base, pero persisten alertas o brechas relevantes"
        return DECISION_ADVANCE, "El ajuste objetivo y preferencial es consistente"

    if objective_score >= 0.4:
        return DECISION_DEPRIORITIZE, "El ajuste existe, pero no destaca frente a las brechas detectadas"

    return DECISION_DEPRIORITIZE, "La vacante no muestra suficiente encaje objetivo para avanzar"


def consolidate_assessment(
    rows: list[CriterionEvaluationRow],
) -> ConsolidatedAssessment:
    objective_rows = [
        row for row in rows if bool(row.get("evaluation", {}).get("affects_objective_fit", False))
    ]
    preference_rows = [
        row for row in rows if bool(row.get("evaluation", {}).get("affects_preference_fit", False))
    ]

    objective_fit = _fit_summary(objective_rows)
    preference_fit = _fit_summary(preference_rows)
    blocking_issues = _blocking_issues(rows)
    relevant_alerts = _relevant_alerts(rows)
    strengths = _strengths(rows)
    gaps = _gaps(rows)
    unknowns = _unknowns(rows)
    decision, reason = _recommended_decision(
        objective_fit=objective_fit,
        preference_fit=preference_fit,
        blocking_issues=blocking_issues,
        alerts=relevant_alerts,
        validation_targets=_validation_targets(rows),
    )
    return ConsolidatedAssessment(
        objective_fit=objective_fit,
        preference_fit=preference_fit,
        blocking_issues=blocking_issues,
        relevant_alerts=relevant_alerts,
        strengths=strengths,
        gaps=gaps,
        unknowns=unknowns,
        recommended_decision=decision,
        recommended_decision_reason=reason,
    )


def consolidated_assessment_context(payload: ConsolidatedAssessment) -> str:
    objective_fit = payload.get("objective_fit", {})
    preference_fit = payload.get("preference_fit", {})
    lines = [
        "Consolidacion deterministica del analisis:",
        (
            f"- Fit objetivo: nivel={objective_fit.get('level', '')}, "
            f"score={objective_fit.get('score', 0)}, resumen={objective_fit.get('summary', '')}"
        ),
        (
            f"- Fit preferencial: nivel={preference_fit.get('level', '')}, "
            f"score={preference_fit.get('score', 0)}, resumen={preference_fit.get('summary', '')}"
        ),
        f"- Decision recomendada: {payload.get('recommended_decision', '')}",
        f"- Motivo: {payload.get('recommended_decision_reason', '')}",
    ]
    blocking = payload.get("blocking_issues", [])
    if isinstance(blocking, list) and blocking:
        lines.append("- Bloqueadores:")
        lines.extend(f"  - {str(item).strip()}" for item in blocking[:5] if str(item).strip())
    alerts = payload.get("relevant_alerts", [])
    if isinstance(alerts, list) and alerts:
        lines.append("- Alertas relevantes:")
        lines.extend(f"  - {str(item).strip()}" for item in alerts[:5] if str(item).strip())
    return "\n".join(lines)
