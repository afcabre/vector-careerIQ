from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.security import SessionData, require_operator_session
from app.services.cv_store import get_active_cv, upsert_active_cv
from app.services.person_store import get_person


router = APIRouter()

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
PREVIEW_CHARS = 1600


class CVResponse(BaseModel):
    cv_id: str
    person_id: str
    source_filename: str
    mime_type: str
    extraction_status: str
    vector_index_status: str
    vector_chunks_indexed: int
    vector_last_indexed_at: str
    text_length: int
    text_truncated: bool
    extracted_text_preview: str
    is_active: bool
    created_at: str
    updated_at: str


class CVTextResponse(BaseModel):
    cv_id: str
    person_id: str
    text_length: int
    text_truncated: bool
    extracted_text: str


def _require_person(person_id: str) -> None:
    if get_person(person_id):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Person not found",
    )


def _to_response(record: dict) -> CVResponse:
    return CVResponse(
        cv_id=str(record.get("cv_id", "")),
        person_id=str(record.get("person_id", "")),
        source_filename=str(record.get("source_filename", "")),
        mime_type=str(record.get("mime_type", "")),
        extraction_status=str(record.get("extraction_status", "")),
        vector_index_status=str(record.get("vector_index_status", "")),
        vector_chunks_indexed=int(record.get("vector_chunks_indexed", 0)),
        vector_last_indexed_at=str(record.get("vector_last_indexed_at", "")),
        text_length=int(record.get("text_length", 0)),
        text_truncated=bool(record.get("text_truncated", False)),
        extracted_text_preview=str(record.get("extracted_text", ""))[:PREVIEW_CHARS],
        is_active=bool(record.get("is_active", False)),
        created_at=str(record.get("created_at", "")),
        updated_at=str(record.get("updated_at", "")),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_cv(
    person_id: str,
    file: UploadFile = File(...),
    _: SessionData = Depends(require_operator_session),
) -> CVResponse:
    _require_person(person_id)
    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty file",
        )
    if len(raw) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large for V1 limit (5MB)",
        )

    record = upsert_active_cv(
        person_id=person_id,
        source_filename=file.filename or "cv-upload",
        mime_type=file.content_type or "application/octet-stream",
        payload=raw,
    )
    return _to_response(record)


@router.get("/active")
def get_active(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> CVResponse:
    _require_person(person_id)
    record = get_active_cv(person_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active CV",
        )
    return _to_response(record)


@router.get("/active/text")
def get_active_text(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> CVTextResponse:
    _require_person(person_id)
    record = get_active_cv(person_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active CV",
        )
    return CVTextResponse(
        cv_id=str(record.get("cv_id", "")),
        person_id=str(record.get("person_id", "")),
        text_length=int(record.get("text_length", 0)),
        text_truncated=bool(record.get("text_truncated", False)),
        extracted_text=str(record.get("extracted_text", "")),
    )
