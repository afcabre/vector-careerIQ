from datetime import UTC, datetime
from io import BytesIO
import re
from threading import Lock
from typing import TypedDict
import uuid

from app.core.settings import get_settings
from app.services.ai_runtime_config_store import get_ai_runtime_config
from app.services.firestore_client import get_firestore_client
from app.services.cv_vector_service import (
    CHUNKING_STRATEGY_TOKEN_WINDOW,
    CHUNKING_VERSION,
    upsert_cv_vectors,
)

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
    extraction_format: str
    vector_index_status: str
    vector_chunks_indexed: int
    vector_last_indexed_at: str
    vector_chunking_strategy: str
    vector_chunking_version: str
    vector_source_format: str
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


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip(" :.-").strip()
    if not stripped:
        return False
    if len(stripped) > 72:
        return False
    lower = stripped.lower()
    heading_hints = (
        "experience",
        "experiencia",
        "education",
        "educacion",
        "skills",
        "habilidades",
        "summary",
        "resumen",
        "projects",
        "proyectos",
        "languages",
        "idiomas",
        "certifications",
        "certificaciones",
    )
    if any(keyword in lower for keyword in heading_hints):
        return True
    if stripped.endswith((".", ";", ",")):
        return False
    words = [word for word in re.split(r"\s+", stripped) if word]
    if not words or len(words) > 8:
        return False
    title_case_words = [word for word in words if word[:1].isupper()]
    uppercase_ratio = len(title_case_words) / max(1, len(words))
    return uppercase_ratio >= 0.7


def _build_structured_markdown(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        return ""
    md_lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if md_lines and md_lines[-1] != "":
                md_lines.append("")
            continue
        if _looks_like_heading(line):
            if md_lines and md_lines[-1] != "":
                md_lines.append("")
            md_lines.append(f"## {line.strip(' :.-')}")
            continue
        if re.match(r"^[-*•]\s+", line):
            md_lines.append(f"- {re.sub(r'^[-*•]\s+', '', line).strip()}")
            continue
        if re.match(r"^\d+[\.\)]\s+", line):
            md_lines.append(f"- {re.sub(r'^\d+[.)]\s+', '', line).strip()}")
            continue
        md_lines.append(line)

    markdown = "\n".join(md_lines).strip()
    if len(markdown) > MAX_TEXT_CHARS:
        return markdown[:MAX_TEXT_CHARS]
    return markdown


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
        "extraction_format": str(source.get("extraction_format", "plain_text")),
        "vector_index_status": str(source.get("vector_index_status", "not_indexed")),
        "vector_chunks_indexed": int(source.get("vector_chunks_indexed", 0)),
        "vector_last_indexed_at": str(source.get("vector_last_indexed_at", "")),
        "vector_chunking_strategy": str(
            source.get("vector_chunking_strategy", CHUNKING_STRATEGY_TOKEN_WINDOW)
        ),
        "vector_chunking_version": str(source.get("vector_chunking_version", CHUNKING_VERSION)),
        "vector_source_format": str(source.get("vector_source_format", "plain_text")),
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
    structured_markdown = _build_structured_markdown(extracted_text)

    record: CVRecord = {
        "cv_id": _new_id(),
        "person_id": person_id,
        "source_filename": source_filename,
        "mime_type": mime_type,
        "extracted_text": extracted_text,
        "text_length": original_length,
        "text_truncated": text_truncated,
        "extraction_status": extraction_status,
        "extraction_format": "plain_text",
        "vector_index_status": "pending",
        "vector_chunks_indexed": 0,
        "vector_last_indexed_at": "",
        "vector_chunking_strategy": CHUNKING_STRATEGY_TOKEN_WINDOW,
        "vector_chunking_version": CHUNKING_VERSION,
        "vector_source_format": "plain_text",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    saved = _save(record)

    settings = get_settings()
    runtime_config = get_ai_runtime_config()
    vector_status, chunks_indexed, applied_strategy, chunking_version, source_format = (
        upsert_cv_vectors(
            {
                **saved,
                "structured_markdown": structured_markdown,
            },
            settings,
            chunking_strategy=runtime_config.get("cv_chunking_strategy", CHUNKING_STRATEGY_TOKEN_WINDOW),
        )
    )
    saved["vector_index_status"] = vector_status
    saved["vector_chunks_indexed"] = chunks_indexed
    saved["vector_chunking_strategy"] = applied_strategy
    saved["vector_chunking_version"] = chunking_version
    saved["vector_source_format"] = source_format
    if vector_status == "indexed":
        saved["vector_last_indexed_at"] = _now_iso()
    saved["updated_at"] = _now_iso()
    return _save(saved)


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
