from datetime import UTC, datetime

from app.core.settings import Settings, get_settings
from app.services.firestore_client import get_firestore_client


def _default_operator_payload(settings: Settings) -> dict[str, str | bool]:
    now = datetime.now(tz=UTC).isoformat()
    return {
        "operator_id": settings.tutor_username,
        "username": settings.tutor_username,
        "password_hash": settings.tutor_password_hash,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def _is_firestore_backend(settings: Settings) -> bool:
    return settings.persistence_backend.lower() == "firestore"


def seed_operator() -> None:
    settings = get_settings()
    if not settings.firestore_seed_on_startup:
        return
    if not _is_firestore_backend(settings):
        return

    client = get_firestore_client(settings)
    ref = client.collection("operators").document(settings.tutor_username)
    snapshot = ref.get()
    if snapshot.exists:
        current = snapshot.to_dict() or {}
        current["operator_id"] = settings.tutor_username
        current["username"] = settings.tutor_username
        current["password_hash"] = settings.tutor_password_hash
        current["active"] = True
        current["updated_at"] = datetime.now(tz=UTC).isoformat()
        if "created_at" not in current:
            current["created_at"] = current["updated_at"]
        ref.set(current)
        return

    ref.set(_default_operator_payload(settings))


def get_password_hash_for_operator(username: str) -> str | None:
    settings = get_settings()
    if not _is_firestore_backend(settings):
        if username == settings.tutor_username:
            return settings.tutor_password_hash
        return None

    client = get_firestore_client(settings)
    snapshot = client.collection("operators").document(username).get()
    if not snapshot.exists:
        return None
    payload = snapshot.to_dict() or {}
    if not payload.get("active", False):
        return None
    password_hash = payload.get("password_hash")
    if not isinstance(password_hash, str) or not password_hash:
        return None
    return password_hash
