from datetime import UTC, datetime
from threading import Lock
from typing import TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


class MessageRecord(TypedDict):
    message_id: str
    role: str
    content: str
    created_at: str


class ConversationRecord(TypedDict):
    conversation_id: str
    person_id: str
    status: str
    last_message_at: str
    messages: list[MessageRecord]


_store_lock = Lock()
_conversations: dict[str, ConversationRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_message_id() -> str:
    return f"m-{uuid.uuid4().hex[:10]}"


def _new_conversation(person_id: str) -> ConversationRecord:
    now = _now_iso()
    return {
        "conversation_id": f"c-{person_id}",
        "person_id": person_id,
        "status": "active",
        "last_message_at": now,
        "messages": [],
    }


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _normalize_message(payload: dict | None) -> MessageRecord:
    source = payload or {}
    return {
        "message_id": str(source.get("message_id", _new_message_id())),
        "role": str(source.get("role", "assistant")),
        "content": str(source.get("content", "")),
        "created_at": str(source.get("created_at", _now_iso())),
    }


def _normalize_conversation(person_id: str, payload: dict | None) -> ConversationRecord:
    source = payload or {}
    messages = [_normalize_message(item) for item in source.get("messages", [])]
    return {
        "conversation_id": str(source.get("conversation_id", f"c-{person_id}")),
        "person_id": person_id,
        "status": str(source.get("status", "active")),
        "last_message_at": str(source.get("last_message_at", _now_iso())),
        "messages": messages,
    }


def _save_firestore(record: ConversationRecord) -> None:
    settings = get_settings()
    client = get_firestore_client(settings)
    client.collection("conversations").document(record["person_id"]).set(record)


def get_or_create_conversation(person_id: str) -> ConversationRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        ref = client.collection("conversations").document(person_id)
        snapshot = ref.get()
        if snapshot.exists:
            return _normalize_conversation(person_id, snapshot.to_dict())
        record = _new_conversation(person_id)
        ref.set(record)
        return record

    with _store_lock:
        existing = _conversations.get(person_id)
        if existing:
            return existing
        record = _new_conversation(person_id)
        _conversations[person_id] = record
        return record


def append_message(person_id: str, role: str, content: str) -> ConversationRecord:
    message: MessageRecord = {
        "message_id": _new_message_id(),
        "role": role,
        "content": content,
        "created_at": _now_iso(),
    }

    if _is_firestore_backend():
        record = get_or_create_conversation(person_id)
        record["messages"].append(message)
        record["last_message_at"] = message["created_at"]
        _save_firestore(record)
        return record

    with _store_lock:
        record = _conversations.get(person_id)
        if not record:
            record = _new_conversation(person_id)
        record["messages"].append(message)
        record["last_message_at"] = message["created_at"]
        _conversations[person_id] = record
        return record
