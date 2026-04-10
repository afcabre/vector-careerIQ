from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import SessionData, require_operator_session
from app.services.person_store import (
    create_person as create_person_record,
    get_person as get_person_record,
    list_persons as list_person_records,
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
