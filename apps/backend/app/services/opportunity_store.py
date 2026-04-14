from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


OPPORTUNITY_STATUSES = [
    "detected",
    "analyzed",
    "prioritized",
    "application_prepared",
    "applied",
    "discarded",
]


class OpportunityRecord(TypedDict):
    opportunity_id: str
    person_id: str
    source_type: str
    source_provider: str
    source_url: str
    title: str
    company: str
    location: str
    status: str
    notes: str
    snapshot_raw_text: str
    snapshot_payload: dict[str, Any]
    created_at: str
    updated_at: str


_store_lock = Lock()
_opportunities: dict[str, OpportunityRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"o-{uuid.uuid4().hex[:10]}"


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _normalize(payload: dict | None) -> OpportunityRecord:
    source = payload or {}
    return {
        "opportunity_id": str(source.get("opportunity_id", "")),
        "person_id": str(source.get("person_id", "")),
        "source_type": str(source.get("source_type", "manual_text")),
        "source_provider": str(source.get("source_provider", "")),
        "source_url": str(source.get("source_url", "")),
        "title": str(source.get("title", "")),
        "company": str(source.get("company", "")),
        "location": str(source.get("location", "")),
        "status": str(source.get("status", "detected")),
        "notes": str(source.get("notes", "")),
        "snapshot_raw_text": str(source.get("snapshot_raw_text", "")),
        "snapshot_payload": dict(source.get("snapshot_payload", {})),
        "created_at": str(source.get("created_at", "")),
        "updated_at": str(source.get("updated_at", "")),
    }


def _list_firestore(person_id: str) -> list[OpportunityRecord]:
    settings = get_settings()
    client = get_firestore_client(settings)
    items = [
        _normalize(doc.to_dict())
        for doc in client.collection("opportunities").where("person_id", "==", person_id).stream()
    ]
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)


def list_opportunities(person_id: str) -> list[OpportunityRecord]:
    if _is_firestore_backend():
        return _list_firestore(person_id)

    with _store_lock:
        items = [item for item in _opportunities.values() if item["person_id"] == person_id]
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)


def find_opportunity(person_id: str, opportunity_id: str) -> OpportunityRecord | None:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        snapshot = client.collection("opportunities").document(opportunity_id).get()
        if not snapshot.exists:
            return None
        data = _normalize(snapshot.to_dict())
        if data["person_id"] != person_id:
            return None
        return data

    with _store_lock:
        existing = _opportunities.get(opportunity_id)
        if not existing or existing["person_id"] != person_id:
            return None
        return existing


def _find_by_url(person_id: str, source_url: str) -> OpportunityRecord | None:
    if not source_url.strip():
        return None
    for item in list_opportunities(person_id):
        if item["source_url"] == source_url:
            return item
    return None


def _save(record: OpportunityRecord) -> OpportunityRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("opportunities").document(record["opportunity_id"]).set(record)
        return record

    with _store_lock:
        _opportunities[record["opportunity_id"]] = record
    return record


def create_opportunity(
    person_id: str,
    source_type: str,
    source_provider: str,
    source_url: str,
    title: str,
    company: str,
    location: str,
    snapshot_raw_text: str,
    snapshot_payload: dict[str, Any] | None,
) -> OpportunityRecord:
    now = _now_iso()
    record: OpportunityRecord = {
        "opportunity_id": _new_id(),
        "person_id": person_id,
        "source_type": source_type,
        "source_provider": source_provider,
        "source_url": source_url.strip(),
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "status": "detected",
        "notes": "",
        "snapshot_raw_text": snapshot_raw_text.strip(),
        "snapshot_payload": snapshot_payload or {},
        "created_at": now,
        "updated_at": now,
    }
    return _save(record)


def save_from_search(
    person_id: str,
    source_provider: str,
    source_url: str,
    title: str,
    company: str,
    location: str,
    snippet: str,
    normalized_payload: dict[str, Any] | None,
) -> tuple[OpportunityRecord, bool]:
    existing = _find_by_url(person_id, source_url)
    if existing:
        return existing, False

    created = create_opportunity(
        person_id=person_id,
        source_type="search",
        source_provider=source_provider,
        source_url=source_url,
        title=title,
        company=company,
        location=location,
        snapshot_raw_text=snippet,
        snapshot_payload=normalized_payload,
    )
    return created, True


def import_url_opportunity(
    person_id: str,
    source_url: str,
    title: str,
    company: str,
    location: str,
    raw_text: str,
) -> tuple[OpportunityRecord, bool]:
    existing = _find_by_url(person_id, source_url)
    if existing:
        return existing, False

    created = create_opportunity(
        person_id=person_id,
        source_type="manual_url",
        source_provider="manual",
        source_url=source_url,
        title=title,
        company=company,
        location=location,
        snapshot_raw_text=raw_text or f"Snapshot from {source_url}",
        snapshot_payload={},
    )
    return created, True


def import_text_opportunity(
    person_id: str,
    title: str,
    company: str,
    location: str,
    raw_text: str,
) -> OpportunityRecord:
    return create_opportunity(
        person_id=person_id,
        source_type="manual_text",
        source_provider="manual",
        source_url="",
        title=title,
        company=company,
        location=location,
        snapshot_raw_text=raw_text,
        snapshot_payload={},
    )


def is_valid_transition(current: str, new_status: str) -> bool:
    return new_status in OPPORTUNITY_STATUSES


def update_opportunity(
    person_id: str,
    opportunity_id: str,
    status: str | None,
    notes: str | None,
) -> OpportunityRecord | None:
    existing = find_opportunity(person_id, opportunity_id)
    if not existing:
        return None

    if status is not None:
        if not is_valid_transition(existing["status"], status):
            return None
        existing["status"] = status

    if notes is not None:
        existing["notes"] = notes

    existing["updated_at"] = _now_iso()
    return _save(existing)
