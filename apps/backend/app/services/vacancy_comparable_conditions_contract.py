from __future__ import annotations

from typing import Any, TypedDict

from app.services.candidate_preference_profile_contract import CONTRACT_TYPE_VALUES, MODALITY_VALUES


CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS = "vacancy_comparable_conditions.v1"
COMPARABLE_CONFIDENCE_VALUES = {"none", "low", "medium", "high"}
VACANCY_CONTRACT_TYPE_VALUES = set(CONTRACT_TYPE_VALUES) | {"unknown"}
VACANCY_MODALITY_VALUES = set(MODALITY_VALUES) | {"unknown"}
VARIABLE_COMPONENT_TYPE_VALUES = {"", "commission", "bonus", "mixed", "unknown"}


class ComparableLocationPayload(TypedDict):
    raw: str
    normalized_city: str
    normalized_country: str
    confidence: str


class ComparableModalityPayload(TypedDict):
    raw: str
    mode: str
    intensity: str
    confidence: str


class ComparableCompensationPayload(TypedDict):
    raw: str
    currency: str
    min_amount: int | None
    max_amount: int | None
    period: str
    has_variable_component: bool
    variable_component_type: str
    variable_component_note: str
    confidence: str


class ComparableContractTypePayload(TypedDict):
    raw: str
    value: str
    confidence: str


class VacancyComparableConditionsContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    location: ComparableLocationPayload
    modality: ComparableModalityPayload
    compensation: ComparableCompensationPayload
    contract_type: ComparableContractTypePayload
    warnings: list[str]


def _clean_text(value: Any, *, max_chars: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _normalize_confidence(value: Any) -> str:
    normalized = _clean_text(value, max_chars=16).lower()
    return normalized if normalized in COMPARABLE_CONFIDENCE_VALUES else "none"


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "yes", "si", "sí"):
        return True
    return False


def _empty_location() -> ComparableLocationPayload:
    return {
        "raw": "",
        "normalized_city": "",
        "normalized_country": "",
        "confidence": "none",
    }


def _empty_modality() -> ComparableModalityPayload:
    return {
        "raw": "",
        "mode": "unknown",
        "intensity": "",
        "confidence": "none",
    }


def _empty_compensation() -> ComparableCompensationPayload:
    return {
        "raw": "",
        "currency": "",
        "min_amount": None,
        "max_amount": None,
        "period": "",
        "has_variable_component": False,
        "variable_component_type": "",
        "variable_component_note": "",
        "confidence": "none",
    }


def _empty_contract_type() -> ComparableContractTypePayload:
    return {
        "raw": "",
        "value": "unknown",
        "confidence": "none",
    }


def _normalize_location(raw: Any) -> ComparableLocationPayload:
    if not isinstance(raw, dict):
        return _empty_location()
    return {
        "raw": _clean_text(raw.get("raw"), max_chars=240),
        "normalized_city": _clean_text(raw.get("normalized_city"), max_chars=120),
        "normalized_country": _clean_text(raw.get("normalized_country"), max_chars=120),
        "confidence": _normalize_confidence(raw.get("confidence")),
    }


def _normalize_modality(raw: Any) -> ComparableModalityPayload:
    if not isinstance(raw, dict):
        return _empty_modality()
    mode = _clean_text(raw.get("mode"), max_chars=24).lower()
    return {
        "raw": _clean_text(raw.get("raw"), max_chars=240),
        "mode": mode if mode in VACANCY_MODALITY_VALUES else "unknown",
        "intensity": _clean_text(raw.get("intensity"), max_chars=32),
        "confidence": _normalize_confidence(raw.get("confidence")),
    }


def _normalize_compensation(raw: Any) -> ComparableCompensationPayload:
    if not isinstance(raw, dict):
        return _empty_compensation()
    has_variable_component = _normalize_bool(raw.get("has_variable_component"))
    variable_component_type = _clean_text(raw.get("variable_component_type"), max_chars=24).lower()
    if variable_component_type not in VARIABLE_COMPONENT_TYPE_VALUES:
        variable_component_type = "unknown" if has_variable_component else ""
    return {
        "raw": _clean_text(raw.get("raw"), max_chars=300),
        "currency": _clean_text(raw.get("currency"), max_chars=16).upper(),
        "min_amount": _normalize_optional_int(raw.get("min_amount")),
        "max_amount": _normalize_optional_int(raw.get("max_amount")),
        "period": _clean_text(raw.get("period"), max_chars=32),
        "has_variable_component": has_variable_component,
        "variable_component_type": variable_component_type,
        "variable_component_note": _clean_text(raw.get("variable_component_note"), max_chars=120),
        "confidence": _normalize_confidence(raw.get("confidence")),
    }


def _normalize_contract_type(raw: Any) -> ComparableContractTypePayload:
    if not isinstance(raw, dict):
        return _empty_contract_type()
    value = _clean_text(raw.get("value"), max_chars=24).lower()
    return {
        "raw": _clean_text(raw.get("raw"), max_chars=240),
        "value": value if value in VACANCY_CONTRACT_TYPE_VALUES else "unknown",
        "confidence": _normalize_confidence(raw.get("confidence")),
    }


def _normalize_string_list(raw: Any, *, max_items: int = 20, max_chars: int = 240) -> list[str]:
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


def empty_vacancy_comparable_conditions_contract() -> VacancyComparableConditionsContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS,
        "vacancy_id": "",
        "generated_at": "",
        "location": _empty_location(),
        "modality": _empty_modality(),
        "compensation": _empty_compensation(),
        "contract_type": _empty_contract_type(),
        "warnings": [],
    }


def normalize_vacancy_comparable_conditions_contract(raw: Any) -> VacancyComparableConditionsContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_comparable_conditions_contract()
    normalized["contract_version"] = (
        _clean_text(source.get("contract_version"), max_chars=64)
        or CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS
    )
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    normalized["location"] = _normalize_location(source.get("location"))
    normalized["modality"] = _normalize_modality(source.get("modality"))
    normalized["compensation"] = _normalize_compensation(source.get("compensation"))
    normalized["contract_type"] = _normalize_contract_type(source.get("contract_type"))
    normalized["warnings"] = _normalize_string_list(source.get("warnings"))
    return normalized


def is_vacancy_comparable_conditions_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        _clean_text(raw.get("contract_version"), max_chars=64)
        == CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS
    )
