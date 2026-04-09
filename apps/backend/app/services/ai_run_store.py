from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


ACTION_ANALYZE_PROFILE_MATCH = "analyze_profile_match"
ACTION_ANALYZE_CULTURAL_FIT = "analyze_cultural_fit"
ACTION_INTERVIEW_BRIEF = "interview_brief"
ACTION_PREPARE_GUIDANCE = "prepare_guidance_text"
ACTION_PREPARE_COVER_LETTER = "prepare_cover_letter"
ACTION_PREPARE_EXPERIENCE_SUMMARY = "prepare_experience_summary"

AI_ACTION_KEYS = [
    ACTION_ANALYZE_PROFILE_MATCH,
    ACTION_ANALYZE_CULTURAL_FIT,
    ACTION_INTERVIEW_BRIEF,
    ACTION_PREPARE_GUIDANCE,
    ACTION_PREPARE_COVER_LETTER,
    ACTION_PREPARE_EXPERIENCE_SUMMARY,
]


class AIRunRecord(TypedDict):
    run_id: str
    person_id: str
    opportunity_id: str
    action_key: str
    result_payload: dict[str, Any]
    is_current: bool
    created_at: str
    updated_at: str


_store_lock = Lock()
_ai_runs: dict[str, AIRunRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"r-{uuid.uuid4().hex[:10]}"


def new_ai_run_id() -> str:
    return _new_id()


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _normalize(payload: dict[str, Any] | None) -> AIRunRecord:
    source = payload or {}
    result_payload = source.get("result_payload", {})
    if not isinstance(result_payload, dict):
        result_payload = {}
    return {
        "run_id": str(source.get("run_id", "")),
        "person_id": str(source.get("person_id", "")),
        "opportunity_id": str(source.get("opportunity_id", "")),
        "action_key": str(source.get("action_key", "")),
        "result_payload": result_payload,
        "is_current": bool(source.get("is_current", False)),
        "created_at": str(source.get("created_at", "")),
        "updated_at": str(source.get("updated_at", "")),
    }


def _list_for_scope(person_id: str, opportunity_id: str) -> list[AIRunRecord]:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items = [
            _normalize(doc.to_dict())
            for doc in client.collection("ai_action_runs").where("person_id", "==", person_id).stream()
        ]
    else:
        with _store_lock:
            items = [item for item in _ai_runs.values() if item["person_id"] == person_id]

    filtered = [item for item in items if item["opportunity_id"] == opportunity_id]
    return sorted(
        filtered,
        key=lambda item: (
            bool(item.get("is_current", False)),
            str(item.get("updated_at", "")),
            str(item.get("created_at", "")),
        ),
        reverse=True,
    )


def list_ai_runs(
    person_id: str,
    opportunity_id: str,
    *,
    action_key: str | None = None,
    current_only: bool = False,
) -> list[AIRunRecord]:
    items = _list_for_scope(person_id, opportunity_id)
    if action_key:
        items = [item for item in items if item["action_key"] == action_key]
    if current_only:
        items = [item for item in items if item["is_current"]]
    return items


def get_current_ai_run(
    person_id: str,
    opportunity_id: str,
    action_key: str,
) -> AIRunRecord | None:
    for item in list_ai_runs(
        person_id,
        opportunity_id,
        action_key=action_key,
        current_only=True,
    ):
        return item
    return None


def _save(record: AIRunRecord) -> AIRunRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("ai_action_runs").document(record["run_id"]).set(record)
        return record

    with _store_lock:
        _ai_runs[record["run_id"]] = record
    return record


def upsert_current_ai_run(
    person_id: str,
    opportunity_id: str,
    action_key: str,
    result_payload: dict[str, Any],
    run_id: str | None = None,
) -> AIRunRecord:
    if action_key not in AI_ACTION_KEYS:
        raise ValueError("Invalid action_key")

    now = _now_iso()
    current_items = list_ai_runs(
        person_id,
        opportunity_id,
        action_key=action_key,
        current_only=True,
    )
    for item in current_items:
        item["is_current"] = False
        item["updated_at"] = now
        _save(item)

    record: AIRunRecord = {
        "run_id": run_id.strip() if isinstance(run_id, str) and run_id.strip() else _new_id(),
        "person_id": person_id,
        "opportunity_id": opportunity_id,
        "action_key": action_key,
        "result_payload": result_payload,
        "is_current": True,
        "created_at": now,
        "updated_at": now,
    }
    return _save(record)


def reset_ai_runs() -> None:
    with _store_lock:
        _ai_runs.clear()
