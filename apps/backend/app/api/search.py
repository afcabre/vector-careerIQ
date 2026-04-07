from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import SessionData, require_operator_session
from app.core.settings import Settings, get_settings
from app.services.person_store import get_person
from app.services.search_service import search_opportunities


router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=240)
    max_results: int = Field(default=6, ge=1, le=20)


class SearchResultResponse(BaseModel):
    search_result_id: str
    source_provider: str
    source_url: str
    title: str
    company: str
    location: str
    snippet: str
    captured_at: str
    normalized_payload: dict


class SearchProviderStatusResponse(BaseModel):
    provider_key: Literal["adzuna", "remotive", "tavily"]
    enabled: bool
    attempted: bool
    status: Literal["ok", "error", "skipped"]
    reason: str
    reason_detail: str = ""
    http_status: int | None = None
    error_class: str = "not_applicable"
    results_count: int
    query_truncated: bool = False


class SearchResponse(BaseModel):
    items: list[SearchResultResponse]
    warnings: list[str]
    provider_status: list[dict[str, Any]]


@router.post("")
def search(
    person_id: str,
    payload: SearchRequest,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    person = get_person(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )

    result = search_opportunities(
        person=person,
        query=payload.query,
        max_results=payload.max_results,
        settings=settings,
    )
    return SearchResponse(
        items=[SearchResultResponse(**item) for item in result["items"]],
        warnings=result["warnings"],
        provider_status=[
            SearchProviderStatusResponse(**item).model_dump()
            for item in result.get("provider_status", [])
        ],
    )
