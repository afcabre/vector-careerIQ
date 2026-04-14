from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.core.security import (
    SessionData,
    create_session,
    destroy_session,
    require_operator_session,
    verify_password,
)
from app.core.settings import Settings, get_settings
from app.services.login_rate_limit_store import (
    clear_failed_attempts,
    get_blocked_until,
    register_failed_attempt,
)
from app.services.operator_store import get_password_hash_for_operator


router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class SessionResponse(BaseModel):
    authenticated: bool
    username: str
    expires_at: str


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    client_host = ""
    if request.client and request.client.host:
        client_host = request.client.host.strip()
    rate_limit_key = f"{payload.username}|{client_host or 'unknown'}"

    blocked_until = get_blocked_until(rate_limit_key, settings)
    if blocked_until:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again after {blocked_until.astimezone(UTC).isoformat()}",
        )

    operator_password_hash = get_password_hash_for_operator(payload.username)
    if not operator_password_hash or not verify_password(
        payload.password,
        operator_password_hash,
    ):
        new_block = register_failed_attempt(rate_limit_key, settings)
        if new_block:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Try again after {new_block.astimezone(UTC).isoformat()}",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    clear_failed_attempts(rate_limit_key, settings)

    session_id, session = create_session(payload.username, settings)
    cookie_samesite = "none" if settings.session_cookie_secure else "lax"
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=cookie_samesite,
        max_age=settings.session_ttl_minutes * 60,
    )

    return SessionResponse(
        authenticated=True,
        username=session.username,
        expires_at=session.expires_at.astimezone(UTC).isoformat(),
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        destroy_session(session_id, settings)
    response.delete_cookie(key=settings.session_cookie_name)
    return {"message": "logged out"}


@router.get("/session")
def session(
    session_data: SessionData = Depends(require_operator_session),
) -> SessionResponse:
    return SessionResponse(
        authenticated=True,
        username=session_data.username,
        expires_at=session_data.expires_at.astimezone(UTC).isoformat(),
    )
