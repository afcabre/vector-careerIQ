from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict
import uuid
import json
import re

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


class RequestTraceRecord(TypedDict):
    trace_id: str
    person_id: str
    opportunity_id: str
    run_id: str
    destination: str
    flow_key: str
    step_order: int
    tool_name: str
    stage: str
    status: str
    input_summary: str
    output_summary: str
    started_at: str
    finished_at: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    created_at: str


_store_lock = Lock()
_request_traces: dict[str, RequestTraceRecord] = {}

_REDACTED = "[REDACTED]"
_MAX_TRACE_PAYLOAD_CHARS = 16_000
_MAX_TRACE_STRING_CHARS = 1_800
_MAX_TRACE_LIST_ITEMS = 50
_MAX_TRACE_OBJECT_KEYS = 80
_MAX_TRACE_DEPTH = 6
_SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "authorization",
    "token",
    "secret",
    "password",
    "private_key",
    "client_secret",
    "x-rapidapi-key",
    "cookie",
)
_INLINE_SECRET_PATTERNS = [
    re.compile(
        r"(?i)((?:api[_-]?key|token|secret|password|client[_-]?secret|x-rapidapi-key)=)([^&\s]+)"
    ),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)"),
]


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
    raw_response_payload = source.get("response_payload", {})
    if not isinstance(raw_response_payload, dict):
        raw_response_payload = {}
    return {
        "trace_id": str(source.get("trace_id", "")),
        "person_id": str(source.get("person_id", "")),
        "opportunity_id": str(source.get("opportunity_id", "")),
        "run_id": str(source.get("run_id", "")),
        "destination": str(source.get("destination", "")),
        "flow_key": str(source.get("flow_key", "")),
        "step_order": int(source.get("step_order", 0) or 0),
        "tool_name": str(source.get("tool_name", "")),
        "stage": str(source.get("stage", "")),
        "status": str(source.get("status", "")),
        "input_summary": str(source.get("input_summary", "")),
        "output_summary": str(source.get("output_summary", "")),
        "started_at": str(source.get("started_at", "")),
        "finished_at": str(source.get("finished_at", "")),
        "request_payload": raw_request_payload,
        "response_payload": raw_response_payload,
        "created_at": str(source.get("created_at", "")),
    }


def _looks_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def _truncate_text(value: str, max_chars: int = _MAX_TRACE_STRING_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]} ...[truncated {omitted} chars]"


def _redact_inline_secrets(value: str) -> str:
    redacted = value
    for pattern in _INLINE_SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def _sanitize_value(value: Any, *, depth: int) -> Any:
    if depth > _MAX_TRACE_DEPTH:
        return "[MAX_DEPTH_REACHED]"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        return _truncate_text(_redact_inline_secrets(value))

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        items = list(value.items())
        for index, (raw_key, raw_value) in enumerate(items):
            if index >= _MAX_TRACE_OBJECT_KEYS:
                sanitized["__truncated_keys"] = len(items) - _MAX_TRACE_OBJECT_KEYS
                break
            key = str(raw_key)
            if _looks_sensitive_key(key):
                sanitized[key] = _REDACTED
                continue
            sanitized[key] = _sanitize_value(raw_value, depth=depth + 1)
        return sanitized

    if isinstance(value, list):
        sanitized_items: list[Any] = []
        for index, item in enumerate(value):
            if index >= _MAX_TRACE_LIST_ITEMS:
                sanitized_items.append(
                    {
                        "__truncated_items": len(value) - _MAX_TRACE_LIST_ITEMS,
                    }
                )
                break
            sanitized_items.append(_sanitize_value(item, depth=depth + 1))
        return sanitized_items

    if isinstance(value, tuple):
        return _sanitize_value(list(value), depth=depth)

    if isinstance(value, bytes):
        return f"<bytes {len(value)}>"

    return _truncate_text(_redact_inline_secrets(str(value)))


def _sanitize_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_value(payload, depth=0)
    if not isinstance(sanitized, dict):
        sanitized = {}

    serialized = json.dumps(sanitized, ensure_ascii=False)
    if len(serialized) <= _MAX_TRACE_PAYLOAD_CHARS:
        return sanitized

    preview_chars = max(400, _MAX_TRACE_PAYLOAD_CHARS - 400)
    preview = serialized[:preview_chars]
    return {
        "__truncated_payload": True,
        "__original_chars": len(serialized),
        "__max_chars": _MAX_TRACE_PAYLOAD_CHARS,
        "__preview": preview,
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
    run_id: str = "",
    step_order: int = 0,
    tool_name: str = "",
    stage: str = "",
    status: str = "",
    input_summary: str = "",
    output_summary: str = "",
    started_at: str = "",
    finished_at: str = "",
    response_payload: dict[str, Any] | None = None,
) -> RequestTraceRecord:
    safe_payload = _sanitize_request_payload(request_payload)
    safe_response_payload = _sanitize_request_payload(response_payload or {})
    normalized_step_order = max(0, int(step_order))
    record: RequestTraceRecord = {
        "trace_id": _new_id(),
        "person_id": person_id,
        "opportunity_id": opportunity_id.strip(),
        "run_id": run_id.strip(),
        "destination": destination.strip().lower(),
        "flow_key": flow_key.strip(),
        "step_order": normalized_step_order,
        "tool_name": tool_name.strip(),
        "stage": stage.strip(),
        "status": status.strip(),
        "input_summary": input_summary.strip(),
        "output_summary": output_summary.strip(),
        "started_at": started_at.strip(),
        "finished_at": finished_at.strip(),
        "request_payload": safe_payload,
        "response_payload": safe_response_payload,
        "created_at": _now_iso(),
    }
    return _save(record)


def list_request_traces(
    *,
    person_id: str,
    opportunity_id: str | None = None,
    destination: str | None = None,
    run_id: str | None = None,
    limit: int = 50,
) -> list[RequestTraceRecord]:
    normalized_destination = (destination or "").strip().lower()
    normalized_opportunity_id = (opportunity_id or "").strip()
    normalized_run_id = (run_id or "").strip()

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
    if normalized_run_id:
        items = [item for item in items if item["run_id"] == normalized_run_id]
    items = sorted(items, key=lambda item: item["created_at"], reverse=True)
    return items[: max(1, limit)]


def reset_request_traces() -> None:
    with _store_lock:
        _request_traces.clear()
