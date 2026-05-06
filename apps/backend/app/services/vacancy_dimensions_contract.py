from __future__ import annotations

import hashlib
from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_DIMENSIONS = "vacancy_dimensions.v2"

ATOMIC_DIMENSION_KEYS = (
    "responsibilities",
    "required_criteria",
    "desirable_criteria",
    "benefits",
    "about_the_company",
    "unclassified",
)

LEGACY_OTHER_CONDITION_KEYS = (
    "schedule",
    "availability",
    "travel",
    "legal_requirements",
    "relocation",
    "mobility_requirements",
)

GROUP_CODE_BY_DIMENSION = {
    "responsibilities": "resp",
    "required_criteria": "req",
    "desirable_criteria": "des",
    "benefits": "ben",
    "about_the_company": "comp",
    "work_conditions": "cond",
}


class RawTextItem(TypedDict):
    raw_text: str


class SalaryNormalization(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str
    raw_text: str


class VacancyDimensionsPayload(TypedDict):
    work_conditions: list[RawTextItem]
    responsibilities: list[RawTextItem]
    required_criteria: list[RawTextItem]
    desirable_criteria: list[RawTextItem]
    benefits: list[RawTextItem]
    about_the_company: list[RawTextItem]
    unclassified: list[RawTextItem]


class VacancyDimensionsContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    vacancy_dimensions: VacancyDimensionsPayload
    warnings: list[str]
    coverage_notes: list[str]


class EnrichedVacancyDimensionItem(TypedDict):
    raw_text: str
    item_id: str
    item_index: int
    group_code: str


class EnrichedVacancyDimensionsPayload(TypedDict):
    work_conditions: list[EnrichedVacancyDimensionItem]
    responsibilities: list[EnrichedVacancyDimensionItem]
    required_criteria: list[EnrichedVacancyDimensionItem]
    desirable_criteria: list[EnrichedVacancyDimensionItem]
    benefits: list[EnrichedVacancyDimensionItem]
    about_the_company: list[EnrichedVacancyDimensionItem]


class EnrichedVacancyDimensionsContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    vacancy_dimensions: EnrichedVacancyDimensionsPayload


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_text_list(raw: Any, *, max_items: int = 50, max_chars: int = 200) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        cleaned = _clean_text(value, max_chars=max_chars)
        if not cleaned:
            continue
        signature = cleaned.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(cleaned)
        if len(items) >= max_items:
            break
    return items


def _normalize_number(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def empty_salary_normalization() -> SalaryNormalization:
    return {
        "min": None,
        "max": None,
        "currency": "",
        "period": "",
        "raw_text": "",
    }


def normalize_salary_normalization(raw: Any) -> SalaryNormalization:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_salary_normalization()
    normalized["min"] = _normalize_number(source.get("min"))
    normalized["max"] = _normalize_number(source.get("max"))
    normalized["currency"] = _clean_text(source.get("currency"), max_chars=32)
    normalized["period"] = _clean_text(source.get("period"), max_chars=32)
    normalized["raw_text"] = _clean_text(
        source.get("raw_text") or source.get("text"),
        max_chars=300,
    )
    return normalized


def _extract_raw_text(value: Any) -> str:
    if isinstance(value, str):
        return _clean_text(value, max_chars=500)
    if not isinstance(value, dict):
        return ""
    for key in ("raw_text", "task", "requirement", "benefit", "text"):
        cleaned = _clean_text(value.get(key), max_chars=500)
        if cleaned:
            return cleaned
    return ""


def _normalize_raw_text_item(raw: Any) -> RawTextItem | None:
    cleaned = _extract_raw_text(raw)
    if not cleaned:
        return None
    return {"raw_text": cleaned}


def _normalize_raw_text_list(raw: Any, *, max_items: int = 50) -> list[RawTextItem]:
    if not isinstance(raw, list):
        return []
    items: list[RawTextItem] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_raw_text_item(value)
        if not normalized:
            continue
        signature = normalized["raw_text"].casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
        if len(items) >= max_items:
            break
    return items


def normalize_quality_notes(raw: Any, *, max_items: int = 100, max_chars: int = 300) -> list[str]:
    return _normalize_text_list(raw, max_items=max_items, max_chars=max_chars)


def merge_quality_notes(*groups: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for note in normalize_quality_notes(group):
            signature = note.casefold()
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(note)
    return merged


def _collect_other_condition_candidates(source: dict[str, Any]) -> list[Any]:
    candidates: list[Any] = []
    raw_other_conditions = source.get("other_conditions")
    if isinstance(raw_other_conditions, list):
        candidates.extend(raw_other_conditions)

    for key in LEGACY_OTHER_CONDITION_KEYS:
        value = source.get(key)
        if isinstance(value, list):
            candidates.extend(value)
            continue
        if isinstance(value, dict):
            text_value = _clean_text(value.get("raw_text") or value.get("text"), max_chars=500)
            if text_value:
                candidates.append(text_value)
            for list_key in ("documents_required", "driving_license", "other"):
                candidates.extend(_normalize_text_list(value.get(list_key), max_items=20, max_chars=120))
            continue
        if value is not None:
            candidates.append(value)
    return candidates


def _append_legacy_work_condition_text(candidates: list[Any], value: Any) -> None:
    if isinstance(value, list):
        candidates.extend(value)
        return
    if isinstance(value, dict):
        raw_text = _clean_text(value.get("raw_text") or value.get("text"), max_chars=500)
        if raw_text:
            candidates.append(raw_text)
            return
        value_text = _clean_text(value.get("value") or value.get("type"), max_chars=500)
        if value_text:
            candidates.append(value_text)
        places = value.get("places")
        if isinstance(places, list):
            candidates.extend(places)
        return
    if value is not None:
        candidates.append(value)


def _normalize_work_conditions(raw: Any) -> list[RawTextItem]:
    if isinstance(raw, list):
        return _normalize_raw_text_list(raw, max_items=50)
    if not isinstance(raw, dict):
        item = _normalize_raw_text_item(raw)
        return [item] if item else []

    candidates: list[Any] = []
    for key in ("salary", "modality", "location", "contract_type"):
        _append_legacy_work_condition_text(candidates, raw.get(key))
    candidates.extend(_collect_other_condition_candidates(raw))
    return _normalize_raw_text_list(candidates, max_items=50)


def _empty_vacancy_dimensions_payload() -> VacancyDimensionsPayload:
    return {
        "work_conditions": [],
        "responsibilities": [],
        "required_criteria": [],
        "desirable_criteria": [],
        "benefits": [],
        "about_the_company": [],
        "unclassified": [],
    }


def empty_vacancy_dimensions_contract() -> VacancyDimensionsContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS,
        "vacancy_id": "",
        "generated_at": "",
        "vacancy_dimensions": _empty_vacancy_dimensions_payload(),
        "warnings": [],
        "coverage_notes": [],
    }


def normalize_vacancy_dimensions_contract(raw: Any) -> VacancyDimensionsContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_dimensions_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    payload = source.get("vacancy_dimensions")
    payload_source = payload if isinstance(payload, dict) else {}
    normalized["vacancy_dimensions"] = {
        "work_conditions": _normalize_work_conditions(payload_source.get("work_conditions")),
        "responsibilities": _normalize_raw_text_list(payload_source.get("responsibilities")),
        "required_criteria": _normalize_raw_text_list(
            payload_source.get("required_criteria")
            if payload_source.get("required_criteria") is not None
            else payload_source.get("required_competencies")
        ),
        "desirable_criteria": _normalize_raw_text_list(
            payload_source.get("desirable_criteria")
            if payload_source.get("desirable_criteria") is not None
            else payload_source.get("desirable_competencies")
        ),
        "benefits": _normalize_raw_text_list(payload_source.get("benefits")),
        "about_the_company": _normalize_raw_text_list(payload_source.get("about_the_company")),
        "unclassified": _normalize_raw_text_list(payload_source.get("unclassified")),
    }
    normalized["warnings"] = normalize_quality_notes(source.get("warnings"))
    normalized["coverage_notes"] = normalize_quality_notes(source.get("coverage_notes"))
    return normalized


def normalize_item_fingerprint_text(raw_text: str) -> str:
    return " ".join(str(raw_text or "").strip().lower().split())


def build_item_fingerprint_id(vacancy_id: str, group_code: str, raw_text: str) -> str:
    normalized_raw_text = normalize_item_fingerprint_text(raw_text)
    fingerprint_input = "|".join([str(vacancy_id or "").strip(), group_code, normalized_raw_text])
    digest = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:10]
    return f"{group_code}_{digest}"


def _enrich_items(
    items: list[RawTextItem],
    *,
    vacancy_id: str,
    group_code: str,
) -> list[EnrichedVacancyDimensionItem]:
    enriched: list[EnrichedVacancyDimensionItem] = []
    for index, item in enumerate(items):
        raw_text = item["raw_text"]
        enriched.append(
            {
                "raw_text": raw_text,
                "item_id": build_item_fingerprint_id(vacancy_id, group_code, raw_text),
                "item_index": index,
                "group_code": group_code,
            }
        )
    return enriched


def enrich_vacancy_dimensions_items(raw: Any) -> EnrichedVacancyDimensionsContract:
    normalized = normalize_vacancy_dimensions_contract(raw)
    payload = normalized["vacancy_dimensions"]
    vacancy_id = normalized["vacancy_id"]

    enriched: EnrichedVacancyDimensionsContract = {
        "contract_version": normalized["contract_version"],
        "vacancy_id": vacancy_id,
        "generated_at": normalized["generated_at"],
        "vacancy_dimensions": {
            "work_conditions": _enrich_items(
                payload["work_conditions"],
                vacancy_id=vacancy_id,
                group_code=GROUP_CODE_BY_DIMENSION["work_conditions"],
            ),
            "responsibilities": _enrich_items(
                payload["responsibilities"],
                vacancy_id=vacancy_id,
                group_code=GROUP_CODE_BY_DIMENSION["responsibilities"],
            ),
            "required_criteria": _enrich_items(
                payload["required_criteria"],
                vacancy_id=vacancy_id,
                group_code=GROUP_CODE_BY_DIMENSION["required_criteria"],
            ),
            "desirable_criteria": _enrich_items(
                payload["desirable_criteria"],
                vacancy_id=vacancy_id,
                group_code=GROUP_CODE_BY_DIMENSION["desirable_criteria"],
            ),
            "benefits": _enrich_items(
                payload["benefits"],
                vacancy_id=vacancy_id,
                group_code=GROUP_CODE_BY_DIMENSION["benefits"],
            ),
            "about_the_company": _enrich_items(
                payload["about_the_company"],
                vacancy_id=vacancy_id,
                group_code=GROUP_CODE_BY_DIMENSION["about_the_company"],
            ),
        },
    }
    return enriched


def is_vacancy_dimensions_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_DIMENSIONS
