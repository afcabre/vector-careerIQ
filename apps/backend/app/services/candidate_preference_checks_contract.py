from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS = "candidate_preference_checks.v1"
PREFERENCE_CHECK_STATE_VALUES = {
    "🟢 Cumple",
    "🟡 Parcial",
    "⚪ Sin informacion",
    "🔴 En conflicto",
}
PREFERENCE_CHECK_CONFIDENCE_VALUES = {"none", "low", "medium", "high"}
PREFERENCE_CHECK_KEYS = {"location", "modality", "compensation", "contract_type"}


class CandidatePreferenceCheckRow(TypedDict):
    criterion_key: str
    criterion: str
    state: str
    vacancy_value: str
    candidate_value: str
    why: str
    confidence: str


class CandidatePreferenceChecksContract(TypedDict):
    contract_version: str
    vacancy_id: str
    person_id: str
    generated_at: str
    rows: list[CandidatePreferenceCheckRow]
    warnings: list[str]


def _clean_text(value: Any, *, max_chars: int = 400) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


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


def _normalize_row(raw: Any) -> CandidatePreferenceCheckRow | None:
    if not isinstance(raw, dict):
        return None
    key = _clean_text(raw.get("criterion_key"), max_chars=32).lower()
    state = _clean_text(raw.get("state"), max_chars=40)
    confidence = _clean_text(raw.get("confidence"), max_chars=16).lower()
    if key not in PREFERENCE_CHECK_KEYS:
        return None
    if state not in PREFERENCE_CHECK_STATE_VALUES:
        state = "⚪ Sin informacion"
    if confidence not in PREFERENCE_CHECK_CONFIDENCE_VALUES:
        confidence = "none"
    return {
        "criterion_key": key,
        "criterion": _clean_text(raw.get("criterion"), max_chars=80),
        "state": state,
        "vacancy_value": _clean_text(raw.get("vacancy_value"), max_chars=240),
        "candidate_value": _clean_text(raw.get("candidate_value"), max_chars=240),
        "why": _clean_text(raw.get("why"), max_chars=400),
        "confidence": confidence,
    }


def empty_candidate_preference_checks_contract() -> CandidatePreferenceChecksContract:
    return {
        "contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS,
        "vacancy_id": "",
        "person_id": "",
        "generated_at": "",
        "rows": [],
        "warnings": [],
    }


def normalize_candidate_preference_checks_contract(raw: Any) -> CandidatePreferenceChecksContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_candidate_preference_checks_contract()
    normalized["contract_version"] = (
        _clean_text(source.get("contract_version"), max_chars=64)
        or CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS
    )
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["person_id"] = _clean_text(source.get("person_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    rows_source = source.get("rows") if isinstance(source.get("rows"), list) else []
    rows: list[CandidatePreferenceCheckRow] = []
    seen_keys: set[str] = set()
    for item in rows_source:
        normalized_row = _normalize_row(item)
        if not normalized_row:
            continue
        key = normalized_row["criterion_key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        rows.append(normalized_row)
    normalized["rows"] = rows
    normalized["warnings"] = _normalize_string_list(source.get("warnings"))
    return normalized


def is_candidate_preference_checks_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        _clean_text(raw.get("contract_version"), max_chars=64)
        == CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS
    )
