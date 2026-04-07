from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import SessionData, require_operator_session
from app.services.prompt_config_store import (
    get_prompt_config,
    list_prompt_config_versions,
    list_prompt_configs,
    rollback_prompt_config,
    update_prompt_config,
)


router = APIRouter()


class PromptConfigResponse(BaseModel):
    config_id: str
    scope: str
    flow_key: str
    template_text: str
    target_sources: list[str]
    is_active: bool
    updated_by: str
    created_at: str
    updated_at: str


class PromptConfigListResponse(BaseModel):
    items: list[PromptConfigResponse]


class PromptConfigVersionResponse(BaseModel):
    version_id: str
    flow_key: str
    template_text: str
    target_sources: list[str]
    is_active: bool
    source_updated_by: str
    source_updated_at: str
    reason: str
    created_by: str
    created_at: str


class PromptConfigVersionListResponse(BaseModel):
    items: list[PromptConfigVersionResponse]


class UpdatePromptConfigRequest(BaseModel):
    template_text: str | None = Field(default=None, min_length=1)
    target_sources: list[str] | None = None
    is_active: bool | None = None


class RollbackPromptConfigRequest(BaseModel):
    version_id: str = Field(min_length=1)


@router.get("")
def list_configs(
    _: SessionData = Depends(require_operator_session),
) -> PromptConfigListResponse:
    items = [PromptConfigResponse(**item) for item in list_prompt_configs()]
    return PromptConfigListResponse(items=items)


@router.get("/{flow_key}")
def get_config(
    flow_key: str,
    _: SessionData = Depends(require_operator_session),
) -> PromptConfigResponse:
    try:
        item = get_prompt_config(flow_key)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt flow not found",
        ) from exc
    return PromptConfigResponse(**item)


@router.get("/{flow_key}/versions")
def list_versions(
    flow_key: str,
    limit: int = Query(default=20, ge=1, le=100),
    _: SessionData = Depends(require_operator_session),
) -> PromptConfigVersionListResponse:
    try:
        items = list_prompt_config_versions(flow_key, limit=limit)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt flow not found",
        ) from exc
    return PromptConfigVersionListResponse(
        items=[PromptConfigVersionResponse(**item) for item in items]
    )


@router.patch("/{flow_key}")
def patch_config(
    flow_key: str,
    payload: UpdatePromptConfigRequest,
    session: SessionData = Depends(require_operator_session),
) -> PromptConfigResponse:
    if (
        payload.template_text is None
        and payload.target_sources is None
        and payload.is_active is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    try:
        item = update_prompt_config(
            flow_key=flow_key,
            updated_by=session.username,
            template_text=payload.template_text,
            target_sources=payload.target_sources,
            is_active=payload.is_active,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt flow not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return PromptConfigResponse(**item)


@router.post("/{flow_key}/rollback")
def rollback_config(
    flow_key: str,
    payload: RollbackPromptConfigRequest,
    session: SessionData = Depends(require_operator_session),
) -> PromptConfigResponse:
    try:
        item = rollback_prompt_config(
            flow_key=flow_key,
            version_id=payload.version_id,
            updated_by=session.username,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt flow/version not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return PromptConfigResponse(**item)
