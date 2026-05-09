from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.core.security import SessionData, require_operator_session
from app.services.candidate_preference_profile_service import build_candidate_preference_profile
from app.services.person_store import (
    create_person as create_person_record,
    get_person as get_person_record,
    list_persons as list_person_records,
    update_candidate_preference_profile as update_candidate_preference_profile_record,
    update_person as update_person_record,
)


router = APIRouter()


class CulturalFieldPreference(BaseModel):
    enabled: bool = False
    selected_values: list[str] = Field(default_factory=list)
    criticality: str = Field(default="normal")


class PersonSummary(BaseModel):
    person_id: str
    full_name: str
    target_roles: list[str]
    location: str
    years_experience: int
    skills: list[str]
    salary_expectation_min: int | None = None
    salary_expectation_max: int | None = None
    salary_currency: str = ""
    salary_period: str = ""
    culture_preferences: list[str]
    cultural_fit_preferences: dict[str, CulturalFieldPreference]
    culture_preferences_notes: str
    candidate_preference_profile_status: str = "none"
    candidate_preference_profile_generated_at: str = ""
    created_at: str
    updated_at: str


class PersonListResponse(BaseModel):
    items: list[PersonSummary]


class CreatePersonRequest(BaseModel):
    full_name: str = Field(min_length=1)
    target_roles: list[str] = Field(min_length=1)
    location: str = Field(min_length=1)
    years_experience: int = Field(ge=0, le=80)
    skills: list[str] = Field(min_length=1)
    salary_expectation_min: int | None = Field(default=None, ge=0, le=1_000_000_000)
    salary_expectation_max: int | None = Field(default=None, ge=0, le=1_000_000_000)
    salary_currency: str = Field(default="", max_length=8)
    salary_period: str = Field(default="", max_length=12)
    culture_preferences: list[str] = Field(default_factory=list)
    cultural_fit_preferences: dict[str, CulturalFieldPreference] = Field(
        default_factory=dict
    )
    culture_preferences_notes: str = Field(default="")


class UpdatePersonRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    target_roles: list[str] | None = None
    location: str | None = Field(default=None, min_length=1)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    skills: list[str] | None = None
    salary_expectation_min: int | None = Field(default=None, ge=0, le=1_000_000_000)
    salary_expectation_max: int | None = Field(default=None, ge=0, le=1_000_000_000)
    salary_currency: str | None = Field(default=None, max_length=8)
    salary_period: str | None = Field(default=None, max_length=12)
    culture_preferences: list[str] | None = None
    cultural_fit_preferences: dict[str, CulturalFieldPreference] | None = None
    culture_preferences_notes: str | None = None


class CandidatePreferenceProfileEnvelope(BaseModel):
    artifact: dict[str, Any]
    status: str
    generated_at: str


def _serialize_sse(event: str, payload: dict[str, Any]) -> str:
    import json

    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.get("")
def list_persons(
    _: SessionData = Depends(require_operator_session),
) -> PersonListResponse:
    return PersonListResponse(items=[PersonSummary(**item) for item in list_person_records()])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_person(
    payload: CreatePersonRequest,
    _: SessionData = Depends(require_operator_session),
) -> PersonSummary:
    record = create_person_record(
        full_name=payload.full_name,
        target_roles=payload.target_roles,
        location=payload.location,
        years_experience=payload.years_experience,
        skills=payload.skills,
        salary_expectation_min=payload.salary_expectation_min,
        salary_expectation_max=payload.salary_expectation_max,
        salary_currency=payload.salary_currency,
        salary_period=payload.salary_period,
        culture_preferences=payload.culture_preferences,
        cultural_fit_preferences={
            field_id: value.model_dump()
            for field_id, value in payload.cultural_fit_preferences.items()
        },
        culture_preferences_notes=payload.culture_preferences_notes,
    )
    return PersonSummary(**record)


@router.get("/{person_id}")
def get_person(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> PersonSummary:
    person = get_person_record(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return PersonSummary(**person)


@router.get("/{person_id}/candidate-preference-profile")
def get_candidate_preference_profile(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> CandidatePreferenceProfileEnvelope:
    person = get_person_record(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return CandidatePreferenceProfileEnvelope(
        artifact=dict(person.get("candidate_preference_profile_artifact", {})),
        status=str(person.get("candidate_preference_profile_status", "none")),
        generated_at=str(person.get("candidate_preference_profile_generated_at", "")),
    )


@router.post("/{person_id}/candidate-preference-profile/recompute")
def recompute_candidate_preference_profile(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> CandidatePreferenceProfileEnvelope:
    person = get_person_record(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )

    artifact = build_candidate_preference_profile(person)
    updated = update_candidate_preference_profile_record(
        person_id,
        artifact=artifact,
        status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return CandidatePreferenceProfileEnvelope(
        artifact=dict(updated.get("candidate_preference_profile_artifact", {})),
        status=str(updated.get("candidate_preference_profile_status", "none")),
        generated_at=str(updated.get("candidate_preference_profile_generated_at", "")),
    )


@router.post("/{person_id}/candidate-preference-profile/recompute/stream")
async def recompute_candidate_preference_profile_stream(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    async def event_generator():
        person = get_person_record(person_id)
        if not person:
            yield _serialize_sse(
                "error",
                {
                    "error": "Person not found",
                    "detail": "Person not found",
                },
            )
            return
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "stage": "candidate_preference_profile_recompute_started",
                    "message": "Iniciando recomputo de P0",
                },
            )
            yield _serialize_sse(
                "tool_status",
                {
                    "stage": "candidate_preference_profile_building",
                    "message": "Normalizando perfil comparable",
                },
            )
            artifact = build_candidate_preference_profile(person)
            yield _serialize_sse(
                "tool_status",
                {
                    "stage": "candidate_preference_profile_saving",
                    "message": "Guardando artefacto P0",
                },
            )
            updated = update_candidate_preference_profile_record(
                person_id,
                artifact=artifact,
                status="draft",
            )
            if not updated:
                yield _serialize_sse(
                    "error",
                    {
                        "error": "Person not found",
                        "detail": "Person not found",
                    },
                )
                return
            payload = {
                "artifact": dict(updated.get("candidate_preference_profile_artifact", {})),
                "status": str(updated.get("candidate_preference_profile_status", "none")),
                "generated_at": str(
                    updated.get("candidate_preference_profile_generated_at", "")
                ),
            }
            yield _serialize_sse("message_complete", payload)
        except Exception as exc:
            updated = update_candidate_preference_profile_record(person_id, status="error")
            generated_at = ""
            if updated:
                generated_at = str(updated.get("candidate_preference_profile_generated_at", ""))
            yield _serialize_sse(
                "error",
                {
                    "error": str(exc),
                    "detail": str(exc),
                    "generated_at": generated_at,
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.patch("/{person_id}")
def update_person(
    person_id: str,
    payload: UpdatePersonRequest,
    _: SessionData = Depends(require_operator_session),
) -> PersonSummary:
    person = update_person_record(
        person_id=person_id,
        full_name=payload.full_name,
        target_roles=payload.target_roles,
        location=payload.location,
        years_experience=payload.years_experience,
        skills=payload.skills,
        salary_expectation_min=payload.salary_expectation_min,
        salary_expectation_max=payload.salary_expectation_max,
        salary_currency=payload.salary_currency,
        salary_period=payload.salary_period,
        culture_preferences=payload.culture_preferences,
        cultural_fit_preferences=(
            {
                field_id: value.model_dump()
                for field_id, value in payload.cultural_fit_preferences.items()
            }
            if payload.cultural_fit_preferences is not None
            else None
        ),
        culture_preferences_notes=payload.culture_preferences_notes,
    )
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return PersonSummary(**person)
