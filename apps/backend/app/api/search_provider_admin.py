from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import SessionData, require_operator_session
from app.services.search_provider_store import (
    get_search_provider_config,
    list_search_provider_configs,
    update_search_provider_config,
)


router = APIRouter()


class SearchProviderConfigResponse(BaseModel):
    provider_key: str
    is_enabled: bool
    updated_by: str
    created_at: str
    updated_at: str


class SearchProviderConfigListResponse(BaseModel):
    items: list[SearchProviderConfigResponse]


class UpdateSearchProviderConfigRequest(BaseModel):
    is_enabled: bool


@router.get("")
def list_configs(
    _: SessionData = Depends(require_operator_session),
) -> SearchProviderConfigListResponse:
    items = [SearchProviderConfigResponse(**item) for item in list_search_provider_configs()]
    return SearchProviderConfigListResponse(items=items)


@router.get("/{provider_key}")
def get_config(
    provider_key: str,
    _: SessionData = Depends(require_operator_session),
) -> SearchProviderConfigResponse:
    try:
        item = get_search_provider_config(provider_key)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search provider not found",
        ) from exc
    return SearchProviderConfigResponse(**item)


@router.patch("/{provider_key}")
def patch_config(
    provider_key: str,
    payload: UpdateSearchProviderConfigRequest,
    session: SessionData = Depends(require_operator_session),
) -> SearchProviderConfigResponse:
    try:
        item = update_search_provider_config(
            provider_key=provider_key,
            is_enabled=payload.is_enabled,
            updated_by=session.username,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search provider not found",
        ) from exc
    return SearchProviderConfigResponse(**item)
