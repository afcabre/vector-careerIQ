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
    response: Response,
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    if payload.username != settings.tutor_username or not verify_password(
        payload.password,
        settings.tutor_password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    session_id, session = create_session(settings.tutor_username, settings)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
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
        destroy_session(session_id)
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
