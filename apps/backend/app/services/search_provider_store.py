from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


PROVIDER_ADZUNA = "adzuna"
PROVIDER_REMOTIVE = "remotive"
PROVIDER_TAVILY = "tavily"
SEARCH_PROVIDER_KEYS = [PROVIDER_ADZUNA, PROVIDER_REMOTIVE, PROVIDER_TAVILY]


class SearchProviderRecord(TypedDict):
    provider_key: str
    is_enabled: bool
    updated_by: str
    created_at: str
    updated_at: str


_store_lock = Lock()
_search_provider_configs: dict[str, SearchProviderRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _default_configs() -> dict[str, SearchProviderRecord]:
    now = _now_iso()
    return {
        key: SearchProviderRecord(
            provider_key=key,
            is_enabled=True,
            updated_by="system",
            created_at=now,
            updated_at=now,
        )
        for key in SEARCH_PROVIDER_KEYS
    }


def _normalize_firestore_record(
    provider_key: str,
    payload: dict[str, Any] | None,
) -> SearchProviderRecord:
    defaults = _default_configs()
    base = defaults[provider_key]
    source = payload or {}
    return SearchProviderRecord(
        provider_key=provider_key,
        is_enabled=bool(source.get("is_enabled", base["is_enabled"])),
        updated_by=str(source.get("updated_by", base["updated_by"])).strip() or "system",
        created_at=str(source.get("created_at", base["created_at"])).strip() or base["created_at"],
        updated_at=str(source.get("updated_at", base["updated_at"])).strip() or base["updated_at"],
    )


def reset_search_provider_configs() -> None:
    with _store_lock:
        _search_provider_configs.clear()


def seed_search_provider_configs() -> None:
    settings = get_settings()
    if not settings.firestore_seed_on_startup:
        return
    if not _is_firestore_backend():
        return

    client = get_firestore_client(settings)
    defaults = _default_configs()
    for key, record in defaults.items():
        doc_ref = client.collection("search_provider_configs").document(key)
        if doc_ref.get().exists:
            continue
        doc_ref.set(record)


def list_search_provider_configs() -> list[SearchProviderRecord]:
    defaults = _default_configs()

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items: dict[str, SearchProviderRecord] = {key: value.copy() for key, value in defaults.items()}
        for doc in client.collection("search_provider_configs").stream():
            key = doc.id
            if key not in defaults:
                continue
            items[key] = _normalize_firestore_record(key, doc.to_dict())
        return [items[key] for key in SEARCH_PROVIDER_KEYS]

    with _store_lock:
        items: dict[str, SearchProviderRecord] = {key: value.copy() for key, value in defaults.items()}
        for key, value in _search_provider_configs.items():
            if key not in defaults:
                continue
            items[key] = value.copy()
    return [items[key] for key in SEARCH_PROVIDER_KEYS]


def get_search_provider_config(provider_key: str) -> SearchProviderRecord:
    key = provider_key.strip().lower()
    defaults = _default_configs()
    if key not in defaults:
        raise KeyError(provider_key)

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        snapshot = client.collection("search_provider_configs").document(key).get()
        if not snapshot.exists:
            return defaults[key].copy()
        return _normalize_firestore_record(key, snapshot.to_dict())

    with _store_lock:
        current = _search_provider_configs.get(key)
        if current:
            return current.copy()
    return defaults[key].copy()


def is_search_provider_enabled(provider_key: str) -> bool:
    return bool(get_search_provider_config(provider_key)["is_enabled"])


def update_search_provider_config(
    provider_key: str,
    *,
    is_enabled: bool,
    updated_by: str,
) -> SearchProviderRecord:
    current = get_search_provider_config(provider_key)
    current["is_enabled"] = bool(is_enabled)
    current["updated_by"] = updated_by.strip() or "tutor"
    current["updated_at"] = _now_iso()

    key = current["provider_key"]
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("search_provider_configs").document(key).set(current)
        return current

    with _store_lock:
        _search_provider_configs[key] = current
    return current
