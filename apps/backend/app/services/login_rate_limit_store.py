from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import TypedDict

from app.core.settings import Settings, get_settings
from app.services.firestore_client import get_firestore_client


class LoginRateLimitRecord(TypedDict):
    key: str
    failed_attempts: list[str]
    blocked_until: str
    updated_at: str


_store_lock = Lock()
_login_limits: dict[str, LoginRateLimitRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_firestore_backend(settings: Settings) -> bool:
    return settings.persistence_backend.lower() == "firestore"


def _parse_iso(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _normalize(payload: dict | None) -> LoginRateLimitRecord:
    source = payload or {}
    raw_attempts = source.get("failed_attempts", [])
    if not isinstance(raw_attempts, list):
        raw_attempts = []
    failed_attempts = [str(item) for item in raw_attempts if str(item).strip()]
    return {
        "key": str(source.get("key", "")),
        "failed_attempts": failed_attempts,
        "blocked_until": str(source.get("blocked_until", "")),
        "updated_at": str(source.get("updated_at", "")),
    }


def _doc_id(key: str) -> str:
    return key.replace("|", "__").replace("/", "_")


def _get_record(key: str, settings: Settings) -> LoginRateLimitRecord | None:
    if _is_firestore_backend(settings):
        client = get_firestore_client(settings)
        snapshot = client.collection("login_rate_limits").document(_doc_id(key)).get()
        if not snapshot.exists:
            return None
        record = _normalize(snapshot.to_dict())
        record["key"] = key
        return record

    with _store_lock:
        record = _login_limits.get(key)
        if not record:
            return None
        return {
            "key": record["key"],
            "failed_attempts": [*record["failed_attempts"]],
            "blocked_until": record["blocked_until"],
            "updated_at": record["updated_at"],
        }


def _save_record(record: LoginRateLimitRecord, settings: Settings) -> None:
    if _is_firestore_backend(settings):
        client = get_firestore_client(settings)
        client.collection("login_rate_limits").document(_doc_id(record["key"])).set(record)
        return

    with _store_lock:
        _login_limits[record["key"]] = {
            "key": record["key"],
            "failed_attempts": [*record["failed_attempts"]],
            "blocked_until": record["blocked_until"],
            "updated_at": record["updated_at"],
        }


def _delete_record(key: str, settings: Settings) -> None:
    if _is_firestore_backend(settings):
        client = get_firestore_client(settings)
        client.collection("login_rate_limits").document(_doc_id(key)).delete()
        return
    with _store_lock:
        _login_limits.pop(key, None)


def get_blocked_until(key: str, settings: Settings) -> datetime | None:
    record = _get_record(key, settings)
    if not record:
        return None
    blocked_until = _parse_iso(record["blocked_until"])
    if not blocked_until:
        return None
    if blocked_until <= datetime.now(tz=UTC):
        record["blocked_until"] = ""
        _save_record(record, settings)
        return None
    return blocked_until


def register_failed_attempt(key: str, settings: Settings) -> datetime | None:
    now = datetime.now(tz=UTC)
    window = max(1, settings.login_rate_limit_window_seconds)
    max_attempts = max(1, settings.login_rate_limit_max_attempts)
    block_seconds = max(1, settings.login_rate_limit_block_seconds)

    record = _get_record(key, settings) or {
        "key": key,
        "failed_attempts": [],
        "blocked_until": "",
        "updated_at": _now_iso(),
    }
    blocked_until = _parse_iso(record["blocked_until"])
    if blocked_until and blocked_until > now:
        return blocked_until

    valid_after = now - timedelta(seconds=window)
    kept_attempts: list[str] = []
    for item in record["failed_attempts"]:
        parsed = _parse_iso(item)
        if parsed and parsed >= valid_after:
            kept_attempts.append(parsed.isoformat())

    kept_attempts.append(now.isoformat())
    record["failed_attempts"] = kept_attempts
    record["updated_at"] = now.isoformat()

    if len(kept_attempts) >= max_attempts:
        new_blocked_until = now + timedelta(seconds=block_seconds)
        record["blocked_until"] = new_blocked_until.isoformat()
        _save_record(record, settings)
        return new_blocked_until

    record["blocked_until"] = ""
    _save_record(record, settings)
    return None


def clear_failed_attempts(key: str, settings: Settings) -> None:
    _delete_record(key, settings)


def reset_login_rate_limits() -> None:
    with _store_lock:
        _login_limits.clear()
