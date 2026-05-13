from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


class AlignmentStepTelemetry(TypedDict):
    step_key: str
    status: str
    started_at: str
    ended_at: str
    duration_ms: int | None
    attempt_index: int
    attempt_count: int
    retry_reason: str | None
    provider: str | None
    model: str | None
    input_size_hints: dict[str, Any]
    output_size_hints: dict[str, Any]
    params_effective: dict[str, Any]
    warnings: list[str]


class AlignmentRunSummary(TypedDict):
    total_duration_ms: int | None
    slowest_steps: list[dict[str, Any]]
    total_retries: int
    llm_calls_count: int
    retrieval_summary: dict[str, Any]
    warnings: list[str]


class AlignmentRunTelemetryRecord(TypedDict):
    run_id: str
    person_id: str
    opportunity_id: str
    status: str
    current_stage: str
    started_at: str
    ended_at: str
    steps: list[AlignmentStepTelemetry]
    summary: AlignmentRunSummary
    created_at: str
    updated_at: str


_store_lock = Lock()
_alignment_runs: dict[str, AlignmentRunTelemetryRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"ar-{uuid.uuid4().hex[:10]}"


def new_alignment_run_id() -> str:
    return _new_id()


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_step(source: dict[str, Any]) -> AlignmentStepTelemetry:
    return {
        "step_key": str(source.get("step_key", "")).strip(),
        "status": str(source.get("status", "running")).strip().lower(),
        "started_at": str(source.get("started_at", "")),
        "ended_at": str(source.get("ended_at", "")),
        "duration_ms": (
            int(source["duration_ms"])
            if isinstance(source.get("duration_ms"), int)
            else None
        ),
        "attempt_index": int(source.get("attempt_index", 1) or 1),
        "attempt_count": int(source.get("attempt_count", 1) or 1),
        "retry_reason": (
            str(source.get("retry_reason", "")).strip() or None
            if source.get("retry_reason") is not None
            else None
        ),
        "provider": (
            str(source.get("provider", "")).strip() or None
            if source.get("provider") is not None
            else None
        ),
        "model": (
            str(source.get("model", "")).strip() or None
            if source.get("model") is not None
            else None
        ),
        "input_size_hints": _as_dict(source.get("input_size_hints")),
        "output_size_hints": _as_dict(source.get("output_size_hints")),
        "params_effective": _as_dict(source.get("params_effective")),
        "warnings": [str(item) for item in _as_list(source.get("warnings")) if str(item).strip()],
    }


def _empty_summary() -> AlignmentRunSummary:
    return {
        "total_duration_ms": None,
        "slowest_steps": [],
        "total_retries": 0,
        "llm_calls_count": 0,
        "retrieval_summary": {
            "criteria_count": None,
            "queries_per_item_effective": None,
            "top_k_effective": None,
            "total_hits_retrieved": None,
        },
        "warnings": [],
    }


def _normalize(payload: dict[str, Any] | None) -> AlignmentRunTelemetryRecord:
    source = payload or {}
    summary = source.get("summary")
    summary_dict = _as_dict(summary)
    retrieval = _as_dict(summary_dict.get("retrieval_summary"))
    return {
        "run_id": str(source.get("run_id", "")).strip(),
        "person_id": str(source.get("person_id", "")).strip(),
        "opportunity_id": str(source.get("opportunity_id", "")).strip(),
        "status": str(source.get("status", "running")).strip().lower() or "running",
        "current_stage": str(source.get("current_stage", "")).strip(),
        "started_at": str(source.get("started_at", "")),
        "ended_at": str(source.get("ended_at", "")),
        "steps": [_normalize_step(item) for item in _as_list(source.get("steps")) if isinstance(item, dict)],
        "summary": {
            "total_duration_ms": (
                int(summary_dict["total_duration_ms"])
                if isinstance(summary_dict.get("total_duration_ms"), int)
                else None
            ),
            "slowest_steps": [
                item for item in _as_list(summary_dict.get("slowest_steps")) if isinstance(item, dict)
            ],
            "total_retries": int(summary_dict.get("total_retries", 0) or 0),
            "llm_calls_count": int(summary_dict.get("llm_calls_count", 0) or 0),
            "retrieval_summary": {
                "criteria_count": retrieval.get("criteria_count"),
                "queries_per_item_effective": retrieval.get("queries_per_item_effective"),
                "top_k_effective": retrieval.get("top_k_effective"),
                "total_hits_retrieved": retrieval.get("total_hits_retrieved"),
            },
            "warnings": [
                str(item)
                for item in _as_list(summary_dict.get("warnings"))
                if str(item).strip()
            ],
        },
        "created_at": str(source.get("created_at", "")),
        "updated_at": str(source.get("updated_at", "")),
    }


def _save(record: AlignmentRunTelemetryRecord) -> AlignmentRunTelemetryRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("alignment_runtime_runs").document(record["run_id"]).set(record)
        return record
    with _store_lock:
        _alignment_runs[record["run_id"]] = record
    return record


def create_alignment_run(person_id: str, opportunity_id: str, *, run_id: str | None = None) -> AlignmentRunTelemetryRecord:
    now = _now_iso()
    record: AlignmentRunTelemetryRecord = {
        "run_id": run_id.strip() if isinstance(run_id, str) and run_id.strip() else _new_id(),
        "person_id": person_id,
        "opportunity_id": opportunity_id,
        "status": "running",
        "current_stage": "",
        "started_at": now,
        "ended_at": "",
        "steps": [],
        "summary": _empty_summary(),
        "created_at": now,
        "updated_at": now,
    }
    return _save(record)


def get_alignment_run(person_id: str, opportunity_id: str, run_id: str) -> AlignmentRunTelemetryRecord | None:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        snapshot = client.collection("alignment_runtime_runs").document(run_id).get()
        if not snapshot.exists:
            return None
        data = _normalize(snapshot.to_dict())
        if data["person_id"] != person_id or data["opportunity_id"] != opportunity_id:
            return None
        return data
    with _store_lock:
        record = _alignment_runs.get(run_id)
    if not record:
        return None
    if record["person_id"] != person_id or record["opportunity_id"] != opportunity_id:
        return None
    return _normalize(record)


def list_alignment_runs(person_id: str, opportunity_id: str, *, limit: int = 2) -> list[AlignmentRunTelemetryRecord]:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items = [
            _normalize(doc.to_dict())
            for doc in client.collection("alignment_runtime_runs").where("person_id", "==", person_id).stream()
        ]
    else:
        with _store_lock:
            items = [_normalize(item) for item in _alignment_runs.values()]
    filtered = [item for item in items if item["opportunity_id"] == opportunity_id]
    filtered.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return filtered[: max(1, limit)]


def upsert_alignment_step(
    person_id: str,
    opportunity_id: str,
    run_id: str,
    step_payload: dict[str, Any],
    *,
    current_stage: str | None = None,
) -> AlignmentRunTelemetryRecord:
    record = get_alignment_run(person_id, opportunity_id, run_id)
    if not record:
        raise ValueError("Alignment run not found")
    now = _now_iso()
    step = _normalize_step(step_payload)
    if not step["step_key"]:
        raise ValueError("step_key is required")
    steps = [item for item in record["steps"] if item["step_key"] != step["step_key"]]
    steps.append(step)
    record["steps"] = sorted(steps, key=lambda item: item.get("started_at", ""))
    record["current_stage"] = (current_stage or step["step_key"]).strip()
    record["updated_at"] = now
    return _save(record)


def complete_alignment_run(
    person_id: str,
    opportunity_id: str,
    run_id: str,
    *,
    status: str,
    summary: dict[str, Any] | None = None,
    ended_at: str | None = None,
) -> AlignmentRunTelemetryRecord:
    record = get_alignment_run(person_id, opportunity_id, run_id)
    if not record:
        raise ValueError("Alignment run not found")
    now = _now_iso()
    record["status"] = status.strip().lower() if status.strip() else "done"
    record["ended_at"] = ended_at.strip() if isinstance(ended_at, str) and ended_at.strip() else now
    if isinstance(summary, dict):
        normalized = _normalize({"summary": summary})["summary"]
        record["summary"] = normalized
    record["updated_at"] = now
    return _save(record)


def reset_alignment_runtime_runs() -> None:
    with _store_lock:
        _alignment_runs.clear()
