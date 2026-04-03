from datetime import UTC, datetime
from io import BytesIO
from threading import Lock
from typing import TypedDict
import uuid

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency fallback.
    PdfReader = None  # type: ignore[assignment]


MAX_TEXT_CHARS = 200_000


class CVRecord(TypedDict):
    cv_id: str
    person_id: str
    source_filename: str
    mime_type: str
    extracted_text: str
    text_length: int
    text_truncated: bool
    extraction_status: str
    is_active: bool
    created_at: str
    updated_at: str


_store_lock = Lock()
_cvs: dict[str, CVRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id() -> str:
    return f"cv-{uuid.uuid4().hex[:10]}"


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _to_text(payload: bytes) -> str:
    if not payload:
        return ""
    return payload.decode("utf-8", errors="ignore").strip()


def _extract_pdf_text(payload: bytes) -> tuple[str, str]:
    if PdfReader is None:
        return "", "pdf_parser_missing"
    try:
        reader = PdfReader(BytesIO(payload))
        pages: list[str] = []
        for page in reader.pages:
            pages.append((page.extract_text() or "").strip())
        text = "\n\n".join([item for item in pages if item]).strip()
        if not text:
            return "", "pdf_no_text"
        return text, "ok"
    except Exception:
        return "", "pdf_parse_error"


def _extract_text(source_filename: str, mime_type: str, payload: bytes) -> tuple[str, str]:
    if not payload:
        return "", "empty_file"

    filename = source_filename.lower()
    content_type = (mime_type or "").lower()
    is_pdf = filename.endswith(".pdf") or content_type == "application/pdf"
    if is_pdf:
        text, status = _extract_pdf_text(payload)
        if text:
            return text, status
        fallback = _to_text(payload)
        if fallback:
            return fallback, f"{status}_fallback_text"
        return "", status

    text = _to_text(payload)
    if not text:
        return "", "unsupported_or_empty"
    return text, "ok"


def _normalize(record: dict | None) -> CVRecord:
    source = record or {}
    return {
        "cv_id": str(source.get("cv_id", "")),
        "person_id": str(source.get("person_id", "")),
        "source_filename": str(source.get("source_filename", "")),
        "mime_type": str(source.get("mime_type", "")),
        "extracted_text": str(source.get("extracted_text", "")),
        "text_length": int(source.get("text_length", 0)),
        "text_truncated": bool(source.get("text_truncated", False)),
        "extraction_status": str(source.get("extraction_status", "unknown")),
        "is_active": bool(source.get("is_active", False)),
        "created_at": str(source.get("created_at", "")),
        "updated_at": str(source.get("updated_at", "")),
    }


def _deactivate_current_cv(person_id: str, now: str) -> None:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        active_docs = (
            client.collection("cvs")
            .where("person_id", "==", person_id)
            .where("is_active", "==", True)
            .stream()
        )
        for doc in active_docs:
            payload = _normalize(doc.to_dict())
            payload["is_active"] = False
            payload["updated_at"] = now
            client.collection("cvs").document(doc.id).set(payload)
        return

    with _store_lock:
        for cv_id, record in _cvs.items():
            if record["person_id"] != person_id or not record["is_active"]:
                continue
            record["is_active"] = False
            record["updated_at"] = now
            _cvs[cv_id] = record


def _save(record: CVRecord) -> CVRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("cvs").document(record["cv_id"]).set(record)
        return record

    with _store_lock:
        _cvs[record["cv_id"]] = record
    return record


def upsert_active_cv(
    person_id: str,
    source_filename: str,
    mime_type: str,
    payload: bytes,
) -> CVRecord:
    now = _now_iso()
    _deactivate_current_cv(person_id, now)

    extracted_text, extraction_status = _extract_text(source_filename, mime_type, payload)
    original_length = len(extracted_text)
    text_truncated = original_length > MAX_TEXT_CHARS
    if text_truncated:
        extracted_text = extracted_text[:MAX_TEXT_CHARS]

    record: CVRecord = {
        "cv_id": _new_id(),
        "person_id": person_id,
        "source_filename": source_filename,
        "mime_type": mime_type,
        "extracted_text": extracted_text,
        "text_length": original_length,
        "text_truncated": text_truncated,
        "extraction_status": extraction_status,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    return _save(record)


def get_active_cv(person_id: str) -> CVRecord | None:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        query = (
            client.collection("cvs")
            .where("person_id", "==", person_id)
            .where("is_active", "==", True)
            .limit(1)
            .stream()
        )
        for doc in query:
            return _normalize(doc.to_dict())
        return None

    with _store_lock:
        for item in _cvs.values():
            if item["person_id"] == person_id and item["is_active"]:
                return item
    return None
