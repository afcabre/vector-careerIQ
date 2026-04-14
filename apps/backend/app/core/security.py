from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request, status

from app.core.settings import Settings, get_settings
from app.services.session_store import (
    delete_session,
    get_session as get_session_record,
    upsert_session,
)


@dataclass
class SessionData:
    username: str
    expires_at: datetime

def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def verify_password(raw_password: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(raw_password), expected_hash)


def create_session(username: str, settings: Settings) -> tuple[str, SessionData]:
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.session_ttl_minutes)
    session = SessionData(username=username, expires_at=expires_at)
    upsert_session(
        session_id=session_id,
        username=username,
        expires_at=expires_at.isoformat(),
        settings=settings,
    )
    return session_id, session


def get_session(session_id: str, settings: Settings) -> SessionData | None:
    record = get_session_record(session_id=session_id, settings=settings)
    if not record:
        return None
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return SessionData(
        username=record["username"],
        expires_at=expires_at,
    )


def destroy_session(session_id: str, settings: Settings) -> None:
    delete_session(session_id=session_id, settings=settings)


def require_operator_session(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionData:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        session_id = request.headers.get("x-session-id", "").strip() or None
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session = get_session(session_id, settings)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )
    return session
