from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


CRITICALITY_VALUES = {"normal", "high_penalty", "non_negotiable"}
CULTURAL_FIELD_OPTIONS: dict[str, set[str]] = {
    "work_modality": {"onsite", "hybrid", "remote"},
    "schedule_flexibility": {
        "fixed_schedule",
        "partial_flexibility",
        "high_flexibility",
    },
    "work_intensity": {"low", "medium", "high"},
    "environment_predictability": {
        "very_stable",
        "moderately_stable",
        "balanced",
        "moderately_dynamic",
        "very_dynamic",
    },
    "company_scale": {"local", "regional", "multilatina", "multinational", "family_owned"},
    "organization_structure_level": {
        "low",
        "medium_low",
        "medium",
        "medium_high",
        "high",
    },
    "organizational_moment": {
        "consolidated",
        "transformation",
        "high_growth",
        "reorganization",
    },
    "cultural_formality": {
        "very_informal",
        "more_informal",
        "intermediate",
        "more_formal",
        "very_formal",
    },
}


class CulturalFieldPreferenceRecord(TypedDict):
    enabled: bool
    selected_values: list[str]
    criticality: str


class PersonRecord(TypedDict):
    person_id: str
    full_name: str
    target_roles: list[str]
    location: str
    years_experience: int
    skills: list[str]
    culture_preferences: list[str]
    cultural_fit_preferences: dict[str, CulturalFieldPreferenceRecord]
    culture_preferences_notes: str
    created_at: str
    updated_at: str


_store_lock = Lock()
_persons: dict[str, PersonRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"p-{uuid.uuid4().hex[:8]}"


def _seed_records() -> list[PersonRecord]:
    now = _now_iso()
    return [
        {
            "person_id": "p-001",
            "full_name": "Camila Torres",
            "target_roles": ["Product Designer"],
            "location": "Bogota",
            "years_experience": 5,
            "skills": ["UX", "UI", "Figma"],
            "culture_preferences": ["aprendizaje continuo", "liderazgo cercano"],
            "cultural_fit_preferences": _default_cultural_fit_preferences(),
            "culture_preferences_notes": "",
            "created_at": now,
            "updated_at": now,
        },
        {
            "person_id": "p-002",
            "full_name": "Mateo Rojas",
            "target_roles": ["Data Analyst"],
            "location": "Medellin",
            "years_experience": 4,
            "skills": ["SQL", "Python", "Power BI"],
            "culture_preferences": ["claridad en objetivos", "colaboracion"],
            "cultural_fit_preferences": _default_cultural_fit_preferences(),
            "culture_preferences_notes": "",
            "created_at": now,
            "updated_at": now,
        },
    ]


def _default_cultural_fit_preferences() -> dict[str, CulturalFieldPreferenceRecord]:
    return {
        field_id: {
            "enabled": False,
            "selected_values": [],
            "criticality": "normal",
        }
        for field_id in CULTURAL_FIELD_OPTIONS
    }


def _dedupe_non_empty(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _sanitize_cultural_field(
    field_id: str,
    raw_value: Any,
) -> CulturalFieldPreferenceRecord:
    allowed = CULTURAL_FIELD_OPTIONS[field_id]
    default = {
        "enabled": False,
        "selected_values": [],
        "criticality": "normal",
    }
    if not isinstance(raw_value, dict):
        return default

    enabled = bool(raw_value.get("enabled", False))
    selected_raw = raw_value.get("selected_values", [])
    selected: list[str] = []
    if isinstance(selected_raw, list):
        for item in selected_raw:
            value = str(item).strip()
            if value and value in allowed and value not in selected:
                selected.append(value)

    criticality_raw = str(raw_value.get("criticality", "normal")).strip()
    criticality = criticality_raw if criticality_raw in CRITICALITY_VALUES else "normal"
    return {
        "enabled": enabled,
        "selected_values": selected,
        "criticality": criticality,
    }


def sanitize_cultural_fit_preferences(
    raw_value: Any,
) -> dict[str, CulturalFieldPreferenceRecord]:
    defaults = _default_cultural_fit_preferences()
    if not isinstance(raw_value, dict):
        return defaults

    normalized: dict[str, CulturalFieldPreferenceRecord] = {}
    for field_id in CULTURAL_FIELD_OPTIONS:
        normalized[field_id] = _sanitize_cultural_field(field_id, raw_value.get(field_id))
    return normalized


def _memory_seed() -> None:
    with _store_lock:
        if _persons:
            return
        for record in _seed_records():
            _persons[record["person_id"]] = record


def _firestore_seed() -> None:
    settings = get_settings()
    client = get_firestore_client(settings)
    collection = client.collection("persons")
    if any(True for _ in collection.limit(1).stream()):
        return
    for record in _seed_records():
        collection.document(record["person_id"]).set(record)


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _normalize_firestore_record(person_id: str, payload: dict | None) -> PersonRecord:
    source = payload or {}
    legacy_culture_preferences = [
        str(item).strip() for item in source.get("culture_preferences", []) if str(item).strip()
    ]
    return PersonRecord(
        person_id=person_id,
        full_name=str(source.get("full_name", "")),
        target_roles=[str(item) for item in source.get("target_roles", [])],
        location=str(source.get("location", "")),
        years_experience=int(source.get("years_experience", 0)),
        skills=[str(item) for item in source.get("skills", [])],
        culture_preferences=legacy_culture_preferences,
        cultural_fit_preferences=sanitize_cultural_fit_preferences(
            source.get("cultural_fit_preferences", {})
        ),
        culture_preferences_notes=str(source.get("culture_preferences_notes", "")).strip(),
        created_at=str(source.get("created_at", "")),
        updated_at=str(source.get("updated_at", "")),
    )


def seed_persons() -> None:
    settings = get_settings()
    if not settings.firestore_seed_on_startup:
        return
    if _is_firestore_backend():
        _firestore_seed()
        return
    _memory_seed()


def list_persons() -> list[PersonRecord]:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items = [
            _normalize_firestore_record(doc.id, doc.to_dict())
            for doc in client.collection("persons").stream()
        ]
        return sorted(items, key=lambda item: item["full_name"])

    with _store_lock:
        return sorted(_persons.values(), key=lambda item: item["full_name"])


def get_person(person_id: str) -> PersonRecord | None:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        snapshot = client.collection("persons").document(person_id).get()
        if not snapshot.exists:
            return None
        return _normalize_firestore_record(person_id, snapshot.to_dict())

    with _store_lock:
        return _persons.get(person_id)


def create_person(
    full_name: str,
    target_roles: list[str],
    location: str,
    years_experience: int,
    skills: list[str],
    culture_preferences: list[str] | None = None,
    cultural_fit_preferences: dict[str, Any] | None = None,
    culture_preferences_notes: str | None = None,
) -> PersonRecord:
    person_id = _new_id()
    now = _now_iso()
    record: PersonRecord = {
        "person_id": person_id,
        "full_name": full_name,
        "target_roles": target_roles,
        "location": location,
        "years_experience": years_experience,
        "skills": skills,
        "culture_preferences": _dedupe_non_empty(culture_preferences or []),
        "cultural_fit_preferences": sanitize_cultural_fit_preferences(cultural_fit_preferences),
        "culture_preferences_notes": str(culture_preferences_notes or "").strip(),
        "created_at": now,
        "updated_at": now,
    }

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("persons").document(person_id).set(record)
        return record

    with _store_lock:
        _persons[person_id] = record
    return record


def update_person(
    person_id: str,
    full_name: str | None,
    target_roles: list[str] | None,
    location: str | None,
    years_experience: int | None,
    skills: list[str] | None,
    culture_preferences: list[str] | None,
    cultural_fit_preferences: dict[str, Any] | None,
    culture_preferences_notes: str | None,
) -> PersonRecord | None:
    if _is_firestore_backend():
        existing = get_person(person_id)
        if not existing:
            return None

        if full_name is not None:
            existing["full_name"] = full_name
        if target_roles is not None:
            existing["target_roles"] = target_roles
        if location is not None:
            existing["location"] = location
        if years_experience is not None:
            existing["years_experience"] = years_experience
        if skills is not None:
            existing["skills"] = skills
        if culture_preferences is not None:
            existing["culture_preferences"] = _dedupe_non_empty(culture_preferences)
        if cultural_fit_preferences is not None:
            existing["cultural_fit_preferences"] = sanitize_cultural_fit_preferences(
                cultural_fit_preferences
            )
        if culture_preferences_notes is not None:
            existing["culture_preferences_notes"] = culture_preferences_notes.strip()
        existing["updated_at"] = _now_iso()

        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("persons").document(person_id).set(existing)
        return existing

    with _store_lock:
        existing = _persons.get(person_id)
        if not existing:
            return None
        if full_name is not None:
            existing["full_name"] = full_name
        if target_roles is not None:
            existing["target_roles"] = target_roles
        if location is not None:
            existing["location"] = location
        if years_experience is not None:
            existing["years_experience"] = years_experience
        if skills is not None:
            existing["skills"] = skills
        if culture_preferences is not None:
            existing["culture_preferences"] = _dedupe_non_empty(culture_preferences)
        if cultural_fit_preferences is not None:
            existing["cultural_fit_preferences"] = sanitize_cultural_fit_preferences(
                cultural_fit_preferences
            )
        if culture_preferences_notes is not None:
            existing["culture_preferences_notes"] = culture_preferences_notes.strip()
        existing["updated_at"] = _now_iso()
        _persons[person_id] = existing
        return existing
