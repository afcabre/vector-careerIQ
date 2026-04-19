from __future__ import annotations

from typing import TypedDict

from app.services.assessment_consolidator import ConsolidatedAssessment
from app.services.criterion_evaluator import CriterionEvaluationRow


class RenderedSection(TypedDict):
    section_id: str
    title: str
    body: str


class RenderedAssessmentOutput(TypedDict):
    markdown: str
    sections: list[RenderedSection]


def _bullets(values: list[str], *, empty_message: str, limit: int = 8) -> str:
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    if not cleaned:
        return f"- {empty_message}"
    return "\n".join(f"- {item}" for item in cleaned[:limit])


def _criteria_snapshot(rows: list[CriterionEvaluationRow]) -> str:
    if not rows:
        return "- Sin criterios evaluados"
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("origin", "")) not in {"vacante_obligatoria", "vacante_condicion"},
            str(row.get("evaluation", {}).get("status", "")),
            str(row.get("criterion_label", "")),
        ),
    )
    lines: list[str] = []
    for row in ordered:
        evaluation = row.get("evaluation", {})
        lines.append(
            f"- {row.get('criterion_label', '')} "
            f"[{row.get('origin', '')} / {row.get('category', '')}] "
            f"=> {evaluation.get('status', '')} ({evaluation.get('resolution_source', 'deterministic')})"
        )
    return "\n".join(lines)


def render_assessment_output(
    *,
    consolidated_assessment: ConsolidatedAssessment,
    criteria_evaluation: list[CriterionEvaluationRow],
) -> RenderedAssessmentOutput:
    objective_fit = consolidated_assessment.get("objective_fit", {})
    preference_fit = consolidated_assessment.get("preference_fit", {})
    sections: list[RenderedSection] = [
        {
            "section_id": "summary",
            "title": "Resumen ejecutivo",
            "body": (
                f"Fit objetivo: {objective_fit.get('level', 'unknown')} "
                f"(score {objective_fit.get('score', 0)}). "
                f"Fit preferencial: {preference_fit.get('level', 'unknown')} "
                f"(score {preference_fit.get('score', 0)}).\n\n"
                f"Decision recomendada: {consolidated_assessment.get('recommended_decision', '')}\n"
                f"Motivo: {consolidated_assessment.get('recommended_decision_reason', '')}"
            ),
        },
        {
            "section_id": "strengths",
            "title": "Fortalezas",
            "body": _bullets(
                list(consolidated_assessment.get("strengths", [])),
                empty_message="Sin fortalezas concluyentes",
            ),
        },
        {
            "section_id": "gaps",
            "title": "Brechas",
            "body": _bullets(
                list(consolidated_assessment.get("gaps", [])),
                empty_message="Sin brechas relevantes registradas",
            ),
        },
        {
            "section_id": "alerts",
            "title": "Alertas y conflictos",
            "body": _bullets(
                [
                    *list(consolidated_assessment.get("blocking_issues", [])),
                    *list(consolidated_assessment.get("relevant_alerts", [])),
                    *list(consolidated_assessment.get("unknowns", [])),
                ],
                empty_message="Sin alertas criticas ni incertidumbres mayores",
            ),
        },
        {
            "section_id": "criteria_snapshot",
            "title": "Resumen por criterio",
            "body": _criteria_snapshot(criteria_evaluation),
        },
    ]

    markdown_parts = [f"## {section['title']}\n\n{section['body']}" for section in sections]
    return {
        "markdown": "\n\n".join(markdown_parts).strip(),
        "sections": sections,
    }
