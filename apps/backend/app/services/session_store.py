from datetime import UTC, datetime
from threading import Lock
from typing import TypedDict

from app.core.settings import Settings
from app.services.firestore_client import get_firestore_client


class SessionRecord(TypedDict):
    session_id: str
    username: str
    expires_at: str
    created_at: str


_store_lock = Lock()
_sessions: dict[str, SessionRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_firestore_backend(settings: Settings) -> bool:
    return settings.persistence_backend.lower() == "firestore"


def _parse_iso(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _is_expired(expires_at_raw: str) -> bool:
    parsed = _parse_iso(expires_at_raw)
    if parsed is None:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed <= datetime.now(tz=UTC)


def upsert_session(
    session_id: str,
    username: str,
    expires_at: str,
    settings: Settings,
) -> None:
    record: SessionRecord = {
        "session_id": session_id,
        "username": username,
        "expires_at": expires_at,
        "created_at": _now_iso(),
    }

    if _is_firestore_backend(settings):
        client = get_firestore_client(settings)
        client.collection("sessions").document(session_id).set(record)
        return

    with _store_lock:
        _sessions[session_id] = record


def get_session(session_id: str, settings: Settings) -> SessionRecord | None:
    if _is_firestore_backend(settings):
        client = get_firestore_client(settings)
        ref = client.collection("sessions").document(session_id)
        snapshot = ref.get()
        if not snapshot.exists:
            return None
        payload = snapshot.to_dict() or {}
        record: SessionRecord = {
            "session_id": str(payload.get("session_id", session_id)),
            "username": str(payload.get("username", "")),
            "expires_at": str(payload.get("expires_at", "")),
            "created_at": str(payload.get("created_at", "")),
        }
        if _is_expired(record["expires_at"]):
            ref.delete()
            return None
        return record

    with _store_lock:
        record = _sessions.get(session_id)
        if not record:
            return None
        if _is_expired(record["expires_at"]):
            _sessions.pop(session_id, None)
            return None
        return record


def delete_session(session_id: str, settings: Settings) -> None:
    if _is_firestore_backend(settings):
        client = get_firestore_client(settings)
        client.collection("sessions").document(session_id).delete()
        return

    with _store_lock:
        _sessions.pop(session_id, None)
