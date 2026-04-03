from datetime import UTC, datetime
from threading import Lock
from typing import TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


ARTIFACT_TYPES = ["cover_letter", "experience_summary"]


class ArtifactRecord(TypedDict):
    artifact_id: str
    person_id: str
    opportunity_id: str
    artifact_type: str
    content: str
    is_current: bool
    created_at: str
    updated_at: str


_store_lock = Lock()
_artifacts: dict[str, ArtifactRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"a-{uuid.uuid4().hex[:10]}"


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _normalize(payload: dict | None) -> ArtifactRecord:
    source = payload or {}
    return {
        "artifact_id": str(source.get("artifact_id", "")),
        "person_id": str(source.get("person_id", "")),
        "opportunity_id": str(source.get("opportunity_id", "")),
        "artifact_type": str(source.get("artifact_type", "")),
        "content": str(source.get("content", "")),
        "is_current": bool(source.get("is_current", False)),
        "created_at": str(source.get("created_at", "")),
        "updated_at": str(source.get("updated_at", "")),
    }


def _list_for_opportunity(person_id: str, opportunity_id: str) -> list[ArtifactRecord]:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items = [
            _normalize(doc.to_dict())
            for doc in client.collection("application_artifacts").where("person_id", "==", person_id).stream()
        ]
    else:
        with _store_lock:
            items = [item for item in _artifacts.values() if item["person_id"] == person_id]
    filtered = [item for item in items if item["opportunity_id"] == opportunity_id]
    return sorted(filtered, key=lambda item: item["updated_at"], reverse=True)


def list_current_artifacts(person_id: str, opportunity_id: str) -> list[ArtifactRecord]:
    return [item for item in _list_for_opportunity(person_id, opportunity_id) if item["is_current"]]


def _save(record: ArtifactRecord) -> ArtifactRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("application_artifacts").document(record["artifact_id"]).set(record)
        return record
    with _store_lock:
        _artifacts[record["artifact_id"]] = record
    return record


def upsert_current_artifact(
    person_id: str,
    opportunity_id: str,
    artifact_type: str,
    content: str,
) -> ArtifactRecord:
    now = _now_iso()
    current_items = _list_for_opportunity(person_id, opportunity_id)
    for item in current_items:
        if item["artifact_type"] == artifact_type and item["is_current"]:
            item["is_current"] = False
            item["updated_at"] = now
            _save(item)

    record: ArtifactRecord = {
        "artifact_id": _new_id(),
        "person_id": person_id,
        "opportunity_id": opportunity_id,
        "artifact_type": artifact_type,
        "content": content.strip(),
        "is_current": True,
        "created_at": now,
        "updated_at": now,
    }
    return _save(record)
