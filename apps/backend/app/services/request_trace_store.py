from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


class RequestTraceRecord(TypedDict):
    trace_id: str
    person_id: str
    opportunity_id: str
    destination: str
    flow_key: str
    request_payload: dict[str, Any]
    created_at: str


_store_lock = Lock()
_request_traces: dict[str, RequestTraceRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"t-{uuid.uuid4().hex[:10]}"


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _normalize(payload: dict[str, Any] | None) -> RequestTraceRecord:
    source = payload or {}
    raw_request_payload = source.get("request_payload", {})
    if not isinstance(raw_request_payload, dict):
        raw_request_payload = {}
    return {
        "trace_id": str(source.get("trace_id", "")),
        "person_id": str(source.get("person_id", "")),
        "opportunity_id": str(source.get("opportunity_id", "")),
        "destination": str(source.get("destination", "")),
        "flow_key": str(source.get("flow_key", "")),
        "request_payload": raw_request_payload,
        "created_at": str(source.get("created_at", "")),
    }


def _save(record: RequestTraceRecord) -> RequestTraceRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("request_traces").document(record["trace_id"]).set(record)
        return record

    with _store_lock:
        _request_traces[record["trace_id"]] = record
    return record


def add_request_trace(
    *,
    person_id: str,
    destination: str,
    flow_key: str,
    request_payload: dict[str, Any],
    opportunity_id: str = "",
) -> RequestTraceRecord:
    record: RequestTraceRecord = {
        "trace_id": _new_id(),
        "person_id": person_id,
        "opportunity_id": opportunity_id.strip(),
        "destination": destination.strip().lower(),
        "flow_key": flow_key.strip(),
        "request_payload": request_payload,
        "created_at": _now_iso(),
    }
    return _save(record)


def list_request_traces(
    *,
    person_id: str,
    opportunity_id: str | None = None,
    destination: str | None = None,
    limit: int = 50,
) -> list[RequestTraceRecord]:
    normalized_destination = (destination or "").strip().lower()
    normalized_opportunity_id = (opportunity_id or "").strip()

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items = [
            _normalize(doc.to_dict())
            for doc in client.collection("request_traces").where("person_id", "==", person_id).stream()
        ]
    else:
        with _store_lock:
            items = [item for item in _request_traces.values() if item["person_id"] == person_id]

    if normalized_opportunity_id:
        items = [item for item in items if item["opportunity_id"] == normalized_opportunity_id]
    if normalized_destination:
        items = [item for item in items if item["destination"] == normalized_destination]
    items = sorted(items, key=lambda item: item["created_at"], reverse=True)
    return items[: max(1, limit)]


def reset_request_traces() -> None:
    with _store_lock:
        _request_traces.clear()
