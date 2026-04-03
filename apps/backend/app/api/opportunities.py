from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import SessionData, require_operator_session
from app.core.settings import Settings, get_settings
from app.services.artifact_store import ARTIFACT_TYPES, list_current_artifacts, upsert_current_artifact
from app.services.opportunity_ai_service import analyze_opportunity, prepare_application_materials
from app.services.opportunity_store import (
    OPPORTUNITY_STATUSES,
    create_opportunity,
    find_opportunity,
    import_text_opportunity,
    import_url_opportunity,
    list_opportunities as list_saved_opportunities,
    save_from_search,
    update_opportunity as update_saved_opportunity,
)
from app.services.person_store import get_person


router = APIRouter()


class OpportunityResponse(BaseModel):
    opportunity_id: str
    person_id: str
    source_type: str
    source_provider: str
    source_url: str
    title: str
    company: str
    location: str
    status: str
    notes: str
    snapshot_raw_text: str
    snapshot_payload: dict[str, Any]
    created_at: str
    updated_at: str


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    person_id: str


class FromSearchRequest(BaseModel):
    source_provider: str = Field(default="tavily", min_length=1)
    source_url: str = Field(default="")
    title: str = Field(min_length=1)
    company: str = Field(default="")
    location: str = Field(default="")
    snippet: str = Field(default="")
    normalized_payload: dict[str, Any] = Field(default_factory=dict)


class FromSearchResponse(BaseModel):
    item: OpportunityResponse
    created: bool


class ImportUrlRequest(BaseModel):
    source_url: str = Field(min_length=5)
    title: str = Field(default="")
    company: str = Field(default="")
    location: str = Field(default="")
    raw_text: str = Field(default="")


class ImportTextRequest(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(default="")
    location: str = Field(default="")
    raw_text: str = Field(min_length=8)


class CreateOpportunityRequest(BaseModel):
    source_type: str = Field(default="manual_text")
    source_provider: str = Field(default="manual")
    source_url: str = Field(default="")
    title: str = Field(min_length=1)
    company: str = Field(default="")
    location: str = Field(default="")
    snapshot_raw_text: str = Field(default="")
    snapshot_payload: dict[str, Any] = Field(default_factory=dict)


class UpdateOpportunityRequest(BaseModel):
    status: str | None = Field(default=None)
    notes: str | None = Field(default=None)


class AnalyzeResponse(BaseModel):
    opportunity: OpportunityResponse
    analysis_text: str


class ArtifactResponse(BaseModel):
    artifact_id: str
    person_id: str
    opportunity_id: str
    artifact_type: str
    content: str
    is_current: bool
    created_at: str
    updated_at: str


class ArtifactsResponse(BaseModel):
    items: list[ArtifactResponse]


class PrepareResponse(BaseModel):
    opportunity: OpportunityResponse
    guidance_text: str
    artifacts: list[ArtifactResponse]


def _require_person(person_id: str) -> None:
    if not get_person(person_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )


def _to_response(item: dict[str, Any]) -> OpportunityResponse:
    return OpportunityResponse(**item)


@router.post("/from-search")
def create_from_search(
    person_id: str,
    payload: FromSearchRequest,
    _: SessionData = Depends(require_operator_session),
) -> FromSearchResponse:
    _require_person(person_id)
    item, created = save_from_search(
        person_id=person_id,
        source_provider=payload.source_provider,
        source_url=payload.source_url,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        snippet=payload.snippet,
        normalized_payload=payload.normalized_payload,
    )
    return FromSearchResponse(item=_to_response(item), created=created)


@router.post("/import-url")
def import_url(
    person_id: str,
    payload: ImportUrlRequest,
    _: SessionData = Depends(require_operator_session),
) -> FromSearchResponse:
    _require_person(person_id)
    item, created = import_url_opportunity(
        person_id=person_id,
        source_url=payload.source_url,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        raw_text=payload.raw_text,
    )
    return FromSearchResponse(item=_to_response(item), created=created)


@router.post("/import-text", status_code=status.HTTP_201_CREATED)
def import_text(
    person_id: str,
    payload: ImportTextRequest,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    item = import_text_opportunity(
        person_id=person_id,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        raw_text=payload.raw_text,
    )
    return _to_response(item)


@router.get("")
def list_opportunities(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityListResponse:
    _require_person(person_id)
    items = list_saved_opportunities(person_id)
    return OpportunityListResponse(
        items=[_to_response(item) for item in items],
        person_id=person_id,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_manual_opportunity(
    person_id: str,
    payload: CreateOpportunityRequest,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    item = create_opportunity(
        person_id=person_id,
        source_type=payload.source_type,
        source_provider=payload.source_provider,
        source_url=payload.source_url,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        snapshot_raw_text=payload.snapshot_raw_text,
        snapshot_payload=payload.snapshot_payload,
    )
    return _to_response(item)


@router.patch("/{opportunity_id}")
def update_opportunity(
    person_id: str,
    opportunity_id: str,
    payload: UpdateOpportunityRequest,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    if payload.status is not None and payload.status not in OPPORTUNITY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid status",
        )

    item = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=payload.status,
        notes=payload.notes,
    )
    if not item:
        existing = find_opportunity(person_id, opportunity_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Opportunity not found",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid status transition",
        )
    return _to_response(item)


@router.get("/{opportunity_id}")
def get_opportunity(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    item = find_opportunity(person_id, opportunity_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    return _to_response(item)


@router.post("/{opportunity_id}/analyze")
def analyze(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> AnalyzeResponse:
    person = get_person(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    result = analyze_opportunity(person, opportunity, settings)
    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status="analyzed",
        notes=opportunity.get("notes", ""),
    )
    final_item = updated or opportunity
    return AnalyzeResponse(
        opportunity=_to_response(final_item),
        analysis_text=result["analysis_text"],
    )


@router.post("/{opportunity_id}/prepare")
def prepare(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> PrepareResponse:
    person = get_person(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    payload = prepare_application_materials(person, opportunity, settings)
    cover = upsert_current_artifact(
        person_id=person_id,
        opportunity_id=opportunity_id,
        artifact_type="cover_letter",
        content=payload["cover_letter"],
    )
    summary = upsert_current_artifact(
        person_id=person_id,
        opportunity_id=opportunity_id,
        artifact_type="experience_summary",
        content=payload["experience_summary"],
    )

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status="application_prepared",
        notes=opportunity.get("notes", ""),
    )
    final_item = updated or opportunity
    return PrepareResponse(
        opportunity=_to_response(final_item),
        guidance_text=payload["guidance_text"],
        artifacts=[ArtifactResponse(**cover), ArtifactResponse(**summary)],
    )


@router.get("/{opportunity_id}/artifacts")
def list_artifacts(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> ArtifactsResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    items = list_current_artifacts(person_id, opportunity_id)
    filtered = [item for item in items if item["artifact_type"] in ARTIFACT_TYPES]
    return ArtifactsResponse(items=[ArtifactResponse(**item) for item in filtered])
