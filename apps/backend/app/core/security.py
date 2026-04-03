from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from threading import Lock

from fastapi import Depends, HTTPException, Request, status

from app.core.settings import Settings, get_settings


@dataclass
class SessionData:
    username: str
    expires_at: datetime


_sessions: dict[str, SessionData] = {}
_sessions_lock = Lock()


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def verify_password(raw_password: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(raw_password), expected_hash)


def create_session(username: str, settings: Settings) -> tuple[str, SessionData]:
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.session_ttl_minutes)
    session = SessionData(username=username, expires_at=expires_at)
    with _sessions_lock:
        _sessions[session_id] = session
    return session_id, session


def get_session(session_id: str) -> SessionData | None:
    with _sessions_lock:
        session = _sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at <= datetime.now(tz=UTC):
            _sessions.pop(session_id, None)
            return None
    return session


def destroy_session(session_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(session_id, None)


def require_operator_session(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> SessionData:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session = get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )
    return session
