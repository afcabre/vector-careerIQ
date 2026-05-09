from __future__ import annotations

from datetime import UTC, datetime

from app.services.candidate_preference_profile_contract import (
    CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
    CandidatePreferenceProfileContract,
    normalize_candidate_preference_profile_contract,
)
from app.services.candidate_profile_normalizer import normalize_candidate_profile
from app.services.person_store import PersonRecord


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def build_candidate_preference_profile(person: PersonRecord) -> CandidatePreferenceProfileContract:
    normalized = normalize_candidate_profile(person)
    identity = normalized.get("identity", {})
    salary_expectation = normalized.get("salary_expectation", {})
    warnings: list[str] = []

    current_location = str(identity.get("location", "")).strip()
    accepted_locations = list(person.get("accepted_locations", []))
    accepted_modalities = list(person.get("accepted_modalities", []))
    contract_types_accepted = list(person.get("contract_types_accepted", []))
    relocation_willingness = str(person.get("relocation_willingness", "unknown")).strip() or "unknown"
    travel_willingness = str(person.get("travel_willingness", "unknown")).strip() or "unknown"
    hard_constraints = list(person.get("hard_constraints", []))

    if not current_location:
        warnings.append("current_location_missing")
    if not accepted_locations:
        warnings.append("accepted_locations_not_captured")
    if not accepted_modalities:
        warnings.append("accepted_modalities_not_captured")
    if not contract_types_accepted:
        warnings.append("contract_types_accepted_not_captured")
    if salary_expectation.get("min") is None and salary_expectation.get("max") is None:
        warnings.append("salary_expectation_not_captured")
    if relocation_willingness == "unknown":
        warnings.append("relocation_willingness_not_captured")
    if travel_willingness == "unknown":
        warnings.append("travel_willingness_not_captured")
    if not hard_constraints:
        warnings.append("hard_constraints_not_captured")
    if not normalized.get("target_profile", {}).get("languages"):
        warnings.append("languages_not_captured_in_structured_profile")

    artifact = {
        "contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
        "person_id": str(person.get("person_id", "")).strip(),
        "generated_at": _now_iso(),
        "comparable_preferences": {
            "current_location": current_location,
            "accepted_locations": accepted_locations,
            "accepted_modalities": accepted_modalities,
            "contract_types_accepted": contract_types_accepted,
            "salary_expectation": {
                "min": salary_expectation.get("min"),
                "max": salary_expectation.get("max"),
                "currency": str(salary_expectation.get("currency", "")).strip(),
                "period": str(salary_expectation.get("period", "")).strip(),
            },
            "relocation_willingness": relocation_willingness,
            "travel_willingness": travel_willingness,
            "hard_constraints": hard_constraints,
        },
        "warnings": warnings,
    }
    return normalize_candidate_preference_profile_contract(artifact)
