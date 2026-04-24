from __future__ import annotations

import re
from typing import Any, TypedDict


CONTRACT_VERSION_V2 = "vacancy_structure.v2"
DEFAULT_TEXT = "no_especificado"

PRIORITY_REQUIRED = "required"
PRIORITY_PREFERRED = "preferred"
PRIORITY_CONSTRAINT = "constraint"
PRIORITY_SIGNAL = "signal"

KNOWN_PRIORITIES = {
    PRIORITY_REQUIRED,
    PRIORITY_PREFERRED,
    PRIORITY_CONSTRAINT,
    PRIORITY_SIGNAL,
}

KNOWN_DIMENSIONS = {
    "seniority",
    "experience",
    "responsibility",
    "skill",
    "tool",
    "language",
    "education",
    "certification",
    "leadership",
    "modality",
    "location",
    "schedule",
    "contract_type",
    "compensation",
    "availability",
    "travel",
    "domain",
    "other",
}

KNOWN_CONFIDENCE = {"low", "medium", "high"}


class VacancyRolePropertiesV2(TypedDict):
    organizational_level: str
    company_type: str
    sector: str


class VacancyCriterionV2(TypedDict):
    criterion_id: str
    label: str
    priority: str
    vacancy_dimension: str
    category: str
    raw_text: str
    normalized_value: dict[str, Any]
    metadata: dict[str, Any]


class VacancyStructureV2(TypedDict):
    contract_version: str
    summary: str
    role_properties: VacancyRolePropertiesV2
    criteria: list[VacancyCriterionV2]
    confidence: str
    extraction_source: str


def _clean_text(value: Any, *, max_chars: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    return compact[:max_chars].rstrip()


def _normalize_priority(value: Any) -> str:
    text = _clean_text(value, max_chars=32).lower()
    if text in KNOWN_PRIORITIES:
        return text
    return PRIORITY_REQUIRED


def _normalize_dimension(value: Any) -> str:
    text = _clean_text(value, max_chars=40).lower()
    if text in KNOWN_DIMENSIONS:
        return text
    return "other"


def _normalize_confidence(value: Any) -> str:
    text = _clean_text(value, max_chars=16).lower()
    if text in KNOWN_CONFIDENCE:
        return text
    return "medium"


def _normalize_role_properties(raw: Any) -> VacancyRolePropertiesV2:
    source = raw if isinstance(raw, dict) else {}
    return {
        "organizational_level": _clean_text(
            source.get("organizational_level"),
            max_chars=80,
        )
        or DEFAULT_TEXT,
        "company_type": _clean_text(source.get("company_type"), max_chars=80) or DEFAULT_TEXT,
        "sector": _clean_text(source.get("sector"), max_chars=120) or DEFAULT_TEXT,
    }


def _criterion_signature(criterion: VacancyCriterionV2) -> str:
    return "|".join(
        [
            criterion["priority"],
            criterion["vacancy_dimension"],
            criterion["category"],
            criterion["label"].lower(),
            criterion["raw_text"].lower(),
        ]
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:72] or "criterion"


def _normalize_criterion(
    raw: Any,
    *,
    position: int,
) -> VacancyCriterionV2 | None:
    if not isinstance(raw, dict):
        return None
    label = _clean_text(raw.get("label"), max_chars=180)
    raw_text = _clean_text(raw.get("raw_text"), max_chars=320)
    if not label and not raw_text:
        return None
    if not label:
        label = raw_text
    category = _clean_text(raw.get("category"), max_chars=80).lower() or "general"
    criterion_id = _clean_text(raw.get("criterion_id"), max_chars=120)
    if not criterion_id:
        criterion_id = f"criterion_{position}_{_slugify(label)}"
    normalized_value = raw.get("normalized_value")
    metadata = raw.get("metadata")
    return {
        "criterion_id": criterion_id,
        "label": label,
        "priority": _normalize_priority(raw.get("priority")),
        "vacancy_dimension": _normalize_dimension(raw.get("vacancy_dimension")),
        "category": category,
        "raw_text": raw_text,
        "normalized_value": dict(normalized_value) if isinstance(normalized_value, dict) else {},
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
    }


def empty_vacancy_structure_v2() -> VacancyStructureV2:
    return {
        "contract_version": CONTRACT_VERSION_V2,
        "summary": "",
        "role_properties": _normalize_role_properties({}),
        "criteria": [],
        "confidence": "low",
        "extraction_source": "none",
    }


def normalize_vacancy_structure_v2(raw: Any) -> VacancyStructureV2:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_structure_v2()
    normalized["summary"] = _clean_text(source.get("summary"), max_chars=420)
    normalized["role_properties"] = _normalize_role_properties(source.get("role_properties"))
    normalized["confidence"] = _normalize_confidence(source.get("confidence"))
    normalized["extraction_source"] = (
        _clean_text(source.get("extraction_source"), max_chars=40).lower() or "unknown"
    )

    criteria: list[VacancyCriterionV2] = []
    seen: set[str] = set()
    raw_criteria = source.get("criteria")
    if isinstance(raw_criteria, list):
        for index, item in enumerate(raw_criteria, start=1):
            criterion = _normalize_criterion(item, position=index)
            if not criterion:
                continue
            signature = _criterion_signature(criterion)
            if signature in seen:
                continue
            seen.add(signature)
            criteria.append(criterion)
    normalized["criteria"] = criteria
    return normalized


def is_vacancy_structure_v2(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_V2
