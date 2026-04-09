from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import SessionData, require_operator_session
from app.services.ai_runtime_config_store import (
    AI_RUNTIME_TOP_K_MAX,
    AI_RUNTIME_TOP_K_MIN,
    get_ai_runtime_config,
    update_ai_runtime_config,
)


router = APIRouter()


class AIRuntimeConfigResponse(BaseModel):
    config_key: str
    top_k_semantic_analysis: int
    top_k_semantic_interview: int
    updated_by: str
    created_at: str
    updated_at: str


class UpdateAIRuntimeConfigRequest(BaseModel):
    top_k_semantic_analysis: int | None = Field(
        default=None,
        ge=AI_RUNTIME_TOP_K_MIN,
        le=AI_RUNTIME_TOP_K_MAX,
    )
    top_k_semantic_interview: int | None = Field(
        default=None,
        ge=AI_RUNTIME_TOP_K_MIN,
        le=AI_RUNTIME_TOP_K_MAX,
    )


@router.get("")
def get_config(
    _: SessionData = Depends(require_operator_session),
) -> AIRuntimeConfigResponse:
    return AIRuntimeConfigResponse(**get_ai_runtime_config())


@router.patch("")
def patch_config(
    payload: UpdateAIRuntimeConfigRequest,
    session: SessionData = Depends(require_operator_session),
) -> AIRuntimeConfigResponse:
    if payload.top_k_semantic_analysis is None and payload.top_k_semantic_interview is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )
    try:
        updated = update_ai_runtime_config(
            top_k_semantic_analysis=payload.top_k_semantic_analysis,
            top_k_semantic_interview=payload.top_k_semantic_interview,
            updated_by=session.username,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return AIRuntimeConfigResponse(**updated)
