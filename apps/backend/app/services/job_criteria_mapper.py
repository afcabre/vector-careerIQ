from __future__ import annotations

import re
from typing import Any, TypedDict

from app.services.opportunity_store import OpportunityRecord


ORIGIN_REQUIRED = "vacante_obligatoria"
ORIGIN_DESIRABLE = "vacante_deseable"
ORIGIN_CONDITION = "vacante_condicion"

CATEGORY_SENIORITY = "seniority_y_trayectoria"
CATEGORY_RESPONSIBILITIES = "responsabilidades_del_rol"
CATEGORY_SKILLS = "habilidades_y_competencias"
CATEGORY_TOOLS = "herramientas_y_tecnologias"
CATEGORY_EDUCATION = "idiomas_y_formacion"
CATEGORY_WORK_CONDITIONS = "condiciones_de_trabajo"

TOOL_HINTS = (
    "figma",
    "sketch",
    "photoshop",
    "illustrator",
    "after effects",
    "jira",
    "notion",
    "miro",
    "power bi",
    "tableau",
    "excel",
    "sql",
    "python",
    "r ",
    "looker",
    "ga4",
    "google analytics",
    "hubspot",
    "salesforce",
    "workday",
)

EDUCATION_HINTS = (
    "titulo",
    "degree",
    "bachelor",
    "master",
    "maestr",
    "licenci",
    "ingenier",
    "profesional",
    "certific",
    "diplom",
)

LANGUAGE_HINTS = (
    "ingles",
    "english",
    "portugues",
    "french",
    "frances",
    "german",
    "alem",
    "idioma",
    "b2",
    "c1",
    "c2",
)


class JobCriterion(TypedDict):
    criterion_id: str
    criterion_label: str
    category: str
    origin: str
    source_field: str
    criterion_payload: dict[str, Any]


class JobCriteriaMap(TypedDict):
    criteria: list[JobCriterion]
    summary: dict[str, int]


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return base[:80] or "criterion"


def _clean_text(value: Any, *, max_chars: int = 220) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    return compact[:max_chars].rstrip()


def _normalize_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        text = _clean_text(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items


def _category_for_requirement(text: str) -> str:
    lowered = f" {text.lower()} "
    if any(hint in lowered for hint in TOOL_HINTS):
        return CATEGORY_TOOLS
    if any(hint in lowered for hint in EDUCATION_HINTS) or any(
        hint in lowered for hint in LANGUAGE_HINTS
    ):
        return CATEGORY_EDUCATION
    return CATEGORY_SKILLS


def _append(
    criteria: list[JobCriterion],
    *,
    criterion_label: str,
    category: str,
    origin: str,
    source_field: str,
    criterion_payload: dict[str, Any],
) -> None:
    criterion_id = f"{source_field}:{_slugify(criterion_label)}:{len(criteria)}"
    criteria.append(
        JobCriterion(
            criterion_id=criterion_id,
            criterion_label=criterion_label,
            category=category,
            origin=origin,
            source_field=source_field,
            criterion_payload=criterion_payload,
        )
    )


def map_job_criteria(opportunity: OpportunityRecord) -> JobCriteriaMap:
    structured = opportunity.get("vacancy_profile", {})
    if not isinstance(structured, dict):
        return JobCriteriaMap(criteria=[], summary={"total": 0})

    criteria: list[JobCriterion] = []

    seniority = _clean_text(structured.get("seniority"), max_chars=80)
    if seniority and seniority != "no_especificado":
        _append(
            criteria,
            criterion_label=f"Seniority requerido: {seniority}",
            category=CATEGORY_SENIORITY,
            origin=ORIGIN_REQUIRED,
            source_field="seniority",
            criterion_payload={"value": seniority},
        )

    organizational_level = _clean_text(
        structured.get("organizational_level"),
        max_chars=80,
    )
    if organizational_level and organizational_level != "no_especificado":
        _append(
            criteria,
            criterion_label=f"Nivel organizacional: {organizational_level}",
            category=CATEGORY_SENIORITY,
            origin=ORIGIN_REQUIRED,
            source_field="organizational_level",
            criterion_payload={"value": organizational_level},
        )

    for item in _normalize_list(structured.get("funciones_responsabilidades")):
        _append(
            criteria,
            criterion_label=item,
            category=CATEGORY_RESPONSIBILITIES,
            origin=ORIGIN_REQUIRED,
            source_field="funciones_responsabilidades",
            criterion_payload={"text": item},
        )

    for item in _normalize_list(structured.get("requisitos_obligatorios")):
        _append(
            criteria,
            criterion_label=item,
            category=_category_for_requirement(item),
            origin=ORIGIN_REQUIRED,
            source_field="requisitos_obligatorios",
            criterion_payload={"text": item},
        )

    for item in _normalize_list(structured.get("requisitos_deseables")):
        _append(
            criteria,
            criterion_label=item,
            category=_category_for_requirement(item),
            origin=ORIGIN_DESIRABLE,
            source_field="requisitos_deseables",
            criterion_payload={"text": item},
        )

    conditions = structured.get("condiciones_trabajo", {})
    if isinstance(conditions, dict):
        for field, label in (
            ("modality", "Modalidad"),
            ("schedule", "Horario"),
            ("contract_type", "Tipo de contrato"),
            ("location", "Ubicacion"),
        ):
            value = _clean_text(conditions.get(field), max_chars=100)
            if value and value != "no_especificado":
                _append(
                    criteria,
                    criterion_label=f"{label}: {value}",
                    category=CATEGORY_WORK_CONDITIONS,
                    origin=ORIGIN_CONDITION,
                    source_field=f"condiciones_trabajo.{field}",
                    criterion_payload={"field": field, "value": value},
                )
        salary = conditions.get("salary", {})
        if isinstance(salary, dict):
            minimum = salary.get("min")
            maximum = salary.get("max")
            currency = _clean_text(salary.get("currency"), max_chars=20)
            period = _clean_text(salary.get("period"), max_chars=20)
            text_original = _clean_text(salary.get("text_original"))
            if minimum is not None or maximum is not None or text_original:
                value = (
                    f"{minimum if minimum is not None else '?'}-"
                    f"{maximum if maximum is not None else '?'}"
                    + (f" {currency}" if currency and currency != "no_especificado" else "")
                    + (f" ({period})" if period and period != "no_especificado" else "")
                ).strip("- ")
                if not value:
                    value = text_original
                _append(
                    criteria,
                    criterion_label=f"Salario: {value}",
                    category=CATEGORY_WORK_CONDITIONS,
                    origin=ORIGIN_CONDITION,
                    source_field="condiciones_trabajo.salary",
                    criterion_payload={
                        "field": "salary",
                        "min": minimum,
                        "max": maximum,
                        "currency": currency,
                        "period": period,
                        "text_original": text_original,
                    },
                )

    summary = {
        "total": len(criteria),
        ORIGIN_REQUIRED: sum(1 for item in criteria if item["origin"] == ORIGIN_REQUIRED),
        ORIGIN_DESIRABLE: sum(1 for item in criteria if item["origin"] == ORIGIN_DESIRABLE),
        ORIGIN_CONDITION: sum(1 for item in criteria if item["origin"] == ORIGIN_CONDITION),
    }
    return JobCriteriaMap(criteria=criteria, summary=summary)


def job_criteria_context(mapped: JobCriteriaMap) -> str:
    criteria = mapped.get("criteria", [])
    if not criteria:
        return "Criterios evaluables derivados: no disponibles."
    lines = [
        "Criterios evaluables derivados desde la vacante estructurada:"
    ]
    for item in criteria:
        lines.append(
            f"- [{item['origin']}] {item['category']}: {item['criterion_label']}"
        )
    summary = mapped.get("summary", {})
    lines.append(
        "Resumen de criterios: "
        + f"total={summary.get('total', 0)}, "
        + f"obligatorios={summary.get(ORIGIN_REQUIRED, 0)}, "
        + f"deseables={summary.get(ORIGIN_DESIRABLE, 0)}, "
        + f"condiciones={summary.get(ORIGIN_CONDITION, 0)}"
    )
    return "\n".join(lines)
