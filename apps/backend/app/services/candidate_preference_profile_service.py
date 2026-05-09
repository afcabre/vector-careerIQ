from __future__ import annotations

from datetime import UTC, datetime

from app.services.candidate_preference_profile_contract import (
    CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
    CandidatePreferenceProfileContract,
    CompanyPreferencePayload,
    normalize_candidate_preference_profile_contract,
)
from app.services.candidate_profile_normalizer import normalize_candidate_profile
from app.services.person_store import PersonRecord


CONTRASTABLE_COMPANY_PREFERENCE_FIELDS = {
    "company_scale",
    "environment_predictability",
    "organization_structure_level",
    "organizational_moment",
    "cultural_formality",
    "work_intensity",
    "schedule_flexibility",
}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def build_candidate_preference_profile(person: PersonRecord) -> CandidatePreferenceProfileContract:
    normalized = normalize_candidate_profile(person)
    identity = normalized.get("identity", {})
    salary_expectation = normalized.get("salary_expectation", {})
    cultural_preferences = normalized.get("cultural_preferences", [])

    accepted_modalities: list[str] = []
    remote_accepted: bool | None = None
    contrastable_company_preferences: list[CompanyPreferencePayload] = []
    warnings: list[str] = []

    for preference in cultural_preferences:
        field_id = str(preference.get("field_id", "")).strip()
        if not field_id or not preference.get("enabled"):
            continue
        selected_values = list(preference.get("selected_values", []))
        criticality = str(preference.get("criticality", "normal")).strip() or "normal"
        if field_id == "work_modality":
            accepted_modalities = [value for value in selected_values if value in {"onsite", "hybrid", "remote"}]
            remote_accepted = "remote" in accepted_modalities
            continue
        if field_id not in CONTRASTABLE_COMPANY_PREFERENCE_FIELDS:
            continue
        contrastable_company_preferences.append(
            {
                "field_id": field_id,
                "selected_values": selected_values,
                "criticality": criticality,
            }
        )

    current_location = str(identity.get("location", "")).strip()
    if current_location:
        warnings.append("accepted_locations_not_captured")
    else:
        warnings.append("current_location_missing")

    if remote_accepted is None:
        warnings.append("accepted_modalities_not_captured")
    if salary_expectation.get("min") is None and salary_expectation.get("max") is None:
        warnings.append("salary_expectation_not_captured")

    warnings.extend(
        [
            "relocation_willingness_not_captured",
            "travel_willingness_not_captured",
            "hard_constraints_not_captured",
            "languages_not_captured_in_structured_profile",
        ]
    )

    artifact = {
        "contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
        "person_id": str(person.get("person_id", "")).strip(),
        "generated_at": _now_iso(),
        "comparable_preferences": {
            "current_location": current_location,
            "accepted_locations": [],
            "accepted_modalities": accepted_modalities,
            "remote_accepted": remote_accepted,
            "salary_expectation": {
                "min": salary_expectation.get("min"),
                "max": salary_expectation.get("max"),
                "currency": str(salary_expectation.get("currency", "")).strip(),
                "period": str(salary_expectation.get("period", "")).strip(),
            },
            "relocation_willingness": "unknown",
            "travel_willingness": "unknown",
            "hard_constraints": [],
        },
        "contrastable_company_preferences": contrastable_company_preferences,
        "warnings": warnings,
    }
    return normalize_candidate_preference_profile_contract(artifact)
