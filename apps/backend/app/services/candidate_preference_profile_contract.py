from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE = "candidate_preference_profile.v1"
PERSON_ARTIFACT_STATUSES = {"none", "draft", "approved", "error"}
MODALITY_VALUES = {"onsite", "hybrid", "remote"}
CRITICALITY_VALUES = {"normal", "high_penalty", "non_negotiable"}
UNKNOWN_COMPATIBILITY_VALUES = {"unknown", "not_captured"}


class SalaryExpectationPayload(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str


class ComparablePreferencesPayload(TypedDict):
    current_location: str
    accepted_locations: list[str]
    accepted_modalities: list[str]
    remote_accepted: bool | None
    salary_expectation: SalaryExpectationPayload
    relocation_willingness: str
    travel_willingness: str
    hard_constraints: list[str]


class CompanyPreferencePayload(TypedDict):
    field_id: str
    selected_values: list[str]
    criticality: str


class CandidatePreferenceProfileContract(TypedDict):
    contract_version: str
    person_id: str
    generated_at: str
    comparable_preferences: ComparablePreferencesPayload
    contrastable_company_preferences: list[CompanyPreferencePayload]
    warnings: list[str]


def _clean_text(value: Any, *, upper: bool = False, max_chars: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())[:max_chars].rstrip()
    return compact.upper() if upper else compact


def _normalize_string_list(
    raw: Any,
    *,
    allowed: set[str] | None = None,
    max_items: int = 20,
    max_chars: int = 120,
) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw[:max_items]:
        normalized = _clean_text(value, max_chars=max_chars)
        if not normalized:
            continue
        if allowed is not None and normalized not in allowed:
            continue
        signature = normalized.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _coerce_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _empty_salary_expectation() -> SalaryExpectationPayload:
    return {
        "min": None,
        "max": None,
        "currency": "",
        "period": "",
    }


def _normalize_salary_expectation(raw: Any) -> SalaryExpectationPayload:
    if not isinstance(raw, dict):
        return _empty_salary_expectation()
    return {
        "min": _coerce_optional_int(raw.get("min")),
        "max": _coerce_optional_int(raw.get("max")),
        "currency": _clean_text(raw.get("currency"), upper=True, max_chars=8),
        "period": _clean_text(raw.get("period"), max_chars=16),
    }


def _empty_comparable_preferences() -> ComparablePreferencesPayload:
    return {
        "current_location": "",
        "accepted_locations": [],
        "accepted_modalities": [],
        "remote_accepted": None,
        "salary_expectation": _empty_salary_expectation(),
        "relocation_willingness": "unknown",
        "travel_willingness": "unknown",
        "hard_constraints": [],
    }


def _normalize_comparable_preferences(raw: Any) -> ComparablePreferencesPayload:
    if not isinstance(raw, dict):
        return _empty_comparable_preferences()
    remote_accepted_raw = raw.get("remote_accepted")
    remote_accepted = remote_accepted_raw if isinstance(remote_accepted_raw, bool) else None
    relocation = _clean_text(raw.get("relocation_willingness"), max_chars=24).lower()
    travel = _clean_text(raw.get("travel_willingness"), max_chars=24).lower()
    return {
        "current_location": _clean_text(raw.get("current_location")),
        "accepted_locations": _normalize_string_list(
            raw.get("accepted_locations"),
            max_items=20,
            max_chars=120,
        ),
        "accepted_modalities": _normalize_string_list(
            raw.get("accepted_modalities"),
            allowed=MODALITY_VALUES,
            max_items=8,
            max_chars=16,
        ),
        "remote_accepted": remote_accepted,
        "salary_expectation": _normalize_salary_expectation(raw.get("salary_expectation")),
        "relocation_willingness": (
            relocation if relocation in UNKNOWN_COMPATIBILITY_VALUES else "unknown"
        ),
        "travel_willingness": travel if travel in UNKNOWN_COMPATIBILITY_VALUES else "unknown",
        "hard_constraints": _normalize_string_list(
            raw.get("hard_constraints"),
            max_items=20,
            max_chars=240,
        ),
    }


def _normalize_company_preference(raw: Any) -> CompanyPreferencePayload | None:
    if not isinstance(raw, dict):
        return None
    criticality = _clean_text(raw.get("criticality"), max_chars=24)
    item = {
        "field_id": _clean_text(raw.get("field_id"), max_chars=64),
        "selected_values": _normalize_string_list(
            raw.get("selected_values"),
            max_items=10,
            max_chars=64,
        ),
        "criticality": criticality if criticality in CRITICALITY_VALUES else "normal",
    }
    if not item["field_id"]:
        return None
    return item


def _normalize_company_preferences(raw: Any) -> list[CompanyPreferencePayload]:
    if not isinstance(raw, list):
        return []
    items: list[CompanyPreferencePayload] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_company_preference(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                normalized["field_id"].casefold(),
                ",".join(item.casefold() for item in normalized["selected_values"]),
                normalized["criticality"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def empty_candidate_preference_profile_contract() -> CandidatePreferenceProfileContract:
    return {
        "contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
        "person_id": "",
        "generated_at": "",
        "comparable_preferences": _empty_comparable_preferences(),
        "contrastable_company_preferences": [],
        "warnings": [],
    }


def normalize_candidate_preference_profile_contract(raw: Any) -> CandidatePreferenceProfileContract:
    base = empty_candidate_preference_profile_contract()
    source = raw if isinstance(raw, dict) else {}
    contract_version = _clean_text(source.get("contract_version"), max_chars=64)
    base["contract_version"] = (
        contract_version or CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE
    )
    base["person_id"] = _clean_text(source.get("person_id"), max_chars=64)
    base["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    base["comparable_preferences"] = _normalize_comparable_preferences(
        source.get("comparable_preferences")
    )
    base["contrastable_company_preferences"] = _normalize_company_preferences(
        source.get("contrastable_company_preferences")
    )
    base["warnings"] = _normalize_string_list(
        source.get("warnings"),
        max_items=20,
        max_chars=240,
    )
    return base


def is_candidate_preference_profile_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return _clean_text(raw.get("contract_version"), max_chars=64) == (
        CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE
    )
