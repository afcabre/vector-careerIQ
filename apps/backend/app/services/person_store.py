from datetime import UTC, datetime
from threading import Lock
from typing import TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


class PersonRecord(TypedDict):
    person_id: str
    full_name: str
    target_roles: list[str]
    location: str
    years_experience: int
    skills: list[str]
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
            "created_at": now,
            "updated_at": now,
        },
    ]


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
    return PersonRecord(
        person_id=person_id,
        full_name=str(source.get("full_name", "")),
        target_roles=[str(item) for item in source.get("target_roles", [])],
        location=str(source.get("location", "")),
        years_experience=int(source.get("years_experience", 0)),
        skills=[str(item) for item in source.get("skills", [])],
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
        existing["updated_at"] = _now_iso()
        _persons[person_id] = existing
        return existing
