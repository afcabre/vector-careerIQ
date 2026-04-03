from datetime import UTC, datetime
from threading import Lock
from typing import TypedDict
import uuid


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


def seed_persons() -> None:
    with _store_lock:
        if _persons:
            return
        now = _now_iso()
        for record in [
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
        ]:
            _persons[record["person_id"]] = record


def list_persons() -> list[PersonRecord]:
    with _store_lock:
        return sorted(_persons.values(), key=lambda item: item["full_name"])


def get_person(person_id: str) -> PersonRecord | None:
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
