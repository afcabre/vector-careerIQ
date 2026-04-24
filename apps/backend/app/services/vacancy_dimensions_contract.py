from __future__ import annotations

import copy
import hashlib
from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_DIMENSIONS = "vacancy_dimensions.v2"

WORK_CONDITION_KEYS = (
    "salary",
    "modality",
    "location",
    "contract_type",
    "other_conditions",
)

ATOMIC_DIMENSION_KEYS = (
    "responsibilities",
    "required_criteria",
    "desirable_criteria",
    "benefits",
    "about_the_company",
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
    "other_conditions": "cond",
}


class RawTextItem(TypedDict):
    raw_text: str


class SalarySignal(TypedDict):
    raw_text: str


class SalaryNormalization(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str
    raw_text: str


class ModalityCondition(TypedDict):
    value: str
    raw_text: str


class LocationCondition(TypedDict):
    places: list[str]
    raw_text: str


class ContractTypeCondition(TypedDict):
    value: str
    raw_text: str


class WorkConditionsPayload(TypedDict):
    salary: SalarySignal
    modality: ModalityCondition
    location: LocationCondition
    contract_type: ContractTypeCondition
    other_conditions: list[RawTextItem]


class VacancyDimensionsPayload(TypedDict):
    work_conditions: WorkConditionsPayload
    responsibilities: list[RawTextItem]
    required_criteria: list[RawTextItem]
    desirable_criteria: list[RawTextItem]
    benefits: list[RawTextItem]
    about_the_company: list[RawTextItem]


class VacancyDimensionsContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    vacancy_dimensions: VacancyDimensionsPayload


class EnrichedVacancyDimensionItem(TypedDict):
    raw_text: str
    item_id: str
    item_index: int
    group_code: str


class EnrichedWorkConditionsPayload(TypedDict):
    salary: SalarySignal
    modality: ModalityCondition
    location: LocationCondition
    contract_type: ContractTypeCondition
    other_conditions: list[EnrichedVacancyDimensionItem]


class EnrichedVacancyDimensionsPayload(TypedDict):
    work_conditions: EnrichedWorkConditionsPayload
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


def _empty_work_conditions() -> WorkConditionsPayload:
    return {
        "salary": {
            "raw_text": "",
        },
        "modality": {
            "value": "",
            "raw_text": "",
        },
        "location": {
            "places": [],
            "raw_text": "",
        },
        "contract_type": {
            "value": "",
            "raw_text": "",
        },
        "other_conditions": [],
    }


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


def _normalize_work_conditions(raw: Any) -> WorkConditionsPayload:
    source = raw if isinstance(raw, dict) else {}
    normalized = _empty_work_conditions()

    source_salary = source.get("salary")
    salary = source_salary if isinstance(source_salary, dict) else {}
    salary_fallback_text = source_salary if not isinstance(source_salary, dict) else ""
    normalized["salary"] = {
        "raw_text": _clean_text(
            salary.get("raw_text") or salary.get("text") or salary_fallback_text,
            max_chars=300,
        )
    }

    modality = source.get("modality") if isinstance(source.get("modality"), dict) else {}
    normalized["modality"] = {
        "value": _clean_text(modality.get("value") or modality.get("type"), max_chars=80),
        "raw_text": _clean_text(modality.get("raw_text") or modality.get("text"), max_chars=300),
    }

    location = source.get("location") if isinstance(source.get("location"), dict) else {}
    location_places = location.get("places")
    if not isinstance(location_places, list):
        location_value = _clean_text(location.get("value"), max_chars=120)
        location_places = [location_value] if location_value else []
    normalized["location"] = {
        "places": _normalize_text_list(location_places, max_items=20, max_chars=120),
        "raw_text": _clean_text(location.get("raw_text") or location.get("text"), max_chars=300),
    }

    contract_type = source.get("contract_type") if isinstance(source.get("contract_type"), dict) else {}
    normalized["contract_type"] = {
        "value": _clean_text(contract_type.get("value") or contract_type.get("type"), max_chars=80),
        "raw_text": _clean_text(contract_type.get("raw_text") or contract_type.get("text"), max_chars=300),
    }

    normalized["other_conditions"] = _normalize_raw_text_list(
        _collect_other_condition_candidates(source),
        max_items=50,
    )
    return normalized


def _empty_vacancy_dimensions_payload() -> VacancyDimensionsPayload:
    return {
        "work_conditions": _empty_work_conditions(),
        "responsibilities": [],
        "required_criteria": [],
        "desirable_criteria": [],
        "benefits": [],
        "about_the_company": [],
    }


def empty_vacancy_dimensions_contract() -> VacancyDimensionsContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS,
        "vacancy_id": "",
        "generated_at": "",
        "vacancy_dimensions": _empty_vacancy_dimensions_payload(),
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
    }
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
            "work_conditions": {
                "salary": copy.deepcopy(payload["work_conditions"]["salary"]),
                "modality": copy.deepcopy(payload["work_conditions"]["modality"]),
                "location": copy.deepcopy(payload["work_conditions"]["location"]),
                "contract_type": copy.deepcopy(payload["work_conditions"]["contract_type"]),
                "other_conditions": _enrich_items(
                    payload["work_conditions"]["other_conditions"],
                    vacancy_id=vacancy_id,
                    group_code=GROUP_CODE_BY_DIMENSION["other_conditions"],
                ),
            },
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
