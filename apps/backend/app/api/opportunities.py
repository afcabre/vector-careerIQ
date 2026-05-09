import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.core.security import SessionData, require_operator_session
from app.core.settings import Settings, get_settings
from app.services.ai_run_store import (
    ACTION_ANALYZE_CULTURAL_FIT,
    ACTION_ANALYZE_PROFILE_MATCH,
    ACTION_INTERVIEW_BRIEF,
    ACTION_PREPARE_COVER_LETTER,
    ACTION_PREPARE_EXPERIENCE_SUMMARY,
    ACTION_PREPARE_GUIDANCE,
    AI_ACTION_KEYS,
    get_current_ai_run,
    list_ai_runs,
    new_ai_run_id,
    upsert_current_ai_run,
)
from app.services.artifact_store import ARTIFACT_TYPES, list_current_artifacts, upsert_current_artifact
from app.services.conversation_store import append_message, get_or_create_conversation
from app.services.opportunity_ai_service import (
    PREPARE_TARGET_COVER_LETTER,
    PREPARE_TARGET_EXPERIENCE_SUMMARY,
    PREPARE_TARGET_GUIDANCE,
    PREPARE_TARGETS,
    analyze_cultural_fit,
    analyze_profile_match,
    analyze_opportunity,
    interview_brief,
    prepare_application_materials,
    prepare_selected_materials,
    stream_analyze_cultural_fit_text,
    stream_analyze_profile_match_text,
    stream_analyze_text,
    stream_interview_brief_text,
    stream_prepare_sections,
)
from app.services.opportunity_store import (
    OPPORTUNITY_STATUSES,
    VACANCY_PROFILE_STATUSES,
    VACANCY_V2_ARTIFACT_STATUSES,
    create_opportunity,
    find_opportunity,
    import_text_opportunity,
    import_url_opportunity,
    list_opportunities as list_saved_opportunities,
    save_from_search,
    update_opportunity as update_saved_opportunity,
)
from app.services.opportunity_profile_service import extract_structured_opportunity_profile
from app.services.person_store import get_person
from app.services.vacancy_v2_consistency_gate import (
    build_vacancy_v2_consistency_report,
    evaluate_vacancy_v2_consistency_report,
)
from app.services.vacancy_blocks_service import (
    VacancyBlocksExtractionError,
    extract_vacancy_blocks,
)
from app.services.vacancy_dimensions_service import (
    VacancyDimensionsExtractionError,
    extract_vacancy_dimensions,
)
from app.services.vacancy_salary_service import (
    VacancySalaryNormalizationError,
    extract_vacancy_salary_normalization,
)
from app.services.vacancy_comparable_conditions_service import (
    VacancyComparableConditionsBuildError,
    build_vacancy_comparable_conditions,
)
from app.services.vacancy_dimensions_enrichment_service import (
    VacancyDimensionsEnrichmentError,
    enrich_vacancy_dimensions_artifact,
)
from app.services.vacancy_retrieval_queries_service import (
    VacancyRetrievalQueriesExtractionError,
    extract_vacancy_retrieval_queries,
)
from app.services.vacancy_retrieval_evidence_service import (
    VacancyRetrievalEvidenceBuildError,
    build_vacancy_retrieval_evidence,
)
from app.services.vacancy_evidence_analysis_service import (
    VacancyEvidenceAnalysisBuildError,
    build_vacancy_evidence_analysis,
)
from app.services.vacancy_evidence_adjudication_service import (
    VacancyEvidenceAdjudicationBuildError,
    build_vacancy_evidence_adjudication,
)
from app.services.vacancy_alignment_summary_service import (
    VacancyAlignmentSummaryBuildError,
    build_vacancy_alignment_summary,
)
from app.services.vacancy_alignment_summary_v2_service import (
    VacancyAlignmentSummaryV2BuildError,
    build_vacancy_alignment_summary_v2,
)
from app.services.vacancy_alignment_report_service import (
    VacancyAlignmentReportBuildError,
    extract_vacancy_alignment_report,
)
from app.services.vacancy_alignment_report_v2_service import (
    VacancyAlignmentReportV2BuildError,
    extract_vacancy_alignment_report_v2,
)


router = APIRouter()


class OpportunityResponse(BaseModel):
    opportunity_id: str
    person_id: str
    source_type: str
    source_provider: str
    source_url: str
    source_label: str
    title: str
    company: str
    location: str
    status: str
    notes: str
    snapshot_raw_text: str
    snapshot_payload: dict[str, Any]
    vacancy_profile: dict[str, Any]
    vacancy_profile_status: str
    vacancy_profile_updated_at: str
    vacancy_blocks_artifact: dict[str, Any]
    vacancy_blocks_status: str
    vacancy_blocks_generated_at: str
    vacancy_dimensions_artifact: dict[str, Any]
    vacancy_dimensions_status: str
    vacancy_dimensions_generated_at: str
    vacancy_salary_artifact: dict[str, Any]
    vacancy_salary_status: str
    vacancy_salary_generated_at: str
    vacancy_comparable_conditions_artifact: dict[str, Any]
    vacancy_comparable_conditions_status: str
    vacancy_comparable_conditions_generated_at: str
    vacancy_dimensions_enriched_artifact: dict[str, Any]
    vacancy_dimensions_enriched_status: str
    vacancy_dimensions_enriched_generated_at: str
    vacancy_retrieval_queries_artifact: dict[str, Any]
    vacancy_retrieval_queries_status: str
    vacancy_retrieval_queries_generated_at: str
    vacancy_retrieval_evidence_artifact: dict[str, Any]
    vacancy_retrieval_evidence_status: str
    vacancy_retrieval_evidence_generated_at: str
    vacancy_evidence_analysis_artifact: dict[str, Any]
    vacancy_evidence_analysis_status: str
    vacancy_evidence_analysis_generated_at: str
    vacancy_evidence_adjudication_artifact: dict[str, Any]
    vacancy_evidence_adjudication_status: str
    vacancy_evidence_adjudication_generated_at: str
    vacancy_alignment_summary_v2_artifact: dict[str, Any]
    vacancy_alignment_summary_v2_status: str
    vacancy_alignment_summary_v2_generated_at: str
    vacancy_alignment_report_v2_artifact: dict[str, Any]
    vacancy_alignment_report_v2_status: str
    vacancy_alignment_report_v2_generated_at: str
    vacancy_alignment_summary_artifact: dict[str, Any]
    vacancy_alignment_summary_status: str
    vacancy_alignment_summary_generated_at: str
    vacancy_alignment_report_artifact: dict[str, Any]
    vacancy_alignment_report_status: str
    vacancy_alignment_report_generated_at: str
    created_at: str
    updated_at: str


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    person_id: str


class VacancyV2ConsistencyIssueResponse(BaseModel):
    opportunity_id: str
    title: str
    company: str
    vacancy_blocks_status: str
    vacancy_dimensions_status: str
    issues: list[str]


class VacancyV2ConsistencyResponse(BaseModel):
    person_id: str
    total_opportunities: int
    opportunities_with_step2: int
    opportunities_with_step3: int
    salary_transfer_eligible: int
    salary_transfer_ok: int
    salary_transfer_missing: int
    salary_transfer_rate: float
    salary_signal_in_step2_benefits: int
    salary_signal_in_step2_benefits_rate: float
    gate_passed: bool
    failed_checks: list[str]
    thresholds: dict[str, float | int]
    issue_samples: list[VacancyV2ConsistencyIssueResponse]


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
    source_label: str = Field(default="")
    title: str = Field(default="")
    company: str = Field(default="")
    location: str = Field(default="")
    raw_text: str = Field(min_length=8)


class ImportTextRequest(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(default="")
    location: str = Field(default="")
    source_label: str = Field(default="")
    raw_text: str = Field(min_length=8)


class CreateOpportunityRequest(BaseModel):
    source_type: str = Field(default="manual_text")
    source_provider: str = Field(default="manual")
    source_url: str = Field(default="")
    source_label: str = Field(default="")
    title: str = Field(min_length=1)
    company: str = Field(default="")
    location: str = Field(default="")
    snapshot_raw_text: str = Field(default="")
    snapshot_payload: dict[str, Any] = Field(default_factory=dict)


class UpdateOpportunityRequest(BaseModel):
    status: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    vacancy_profile: dict[str, Any] | None = Field(default=None)
    vacancy_profile_status: str | None = Field(default=None)
    vacancy_blocks_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_blocks_status: str | None = Field(default=None)
    vacancy_dimensions_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_dimensions_status: str | None = Field(default=None)
    vacancy_salary_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_salary_status: str | None = Field(default=None)
    vacancy_comparable_conditions_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_comparable_conditions_status: str | None = Field(default=None)
    vacancy_dimensions_enriched_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_dimensions_enriched_status: str | None = Field(default=None)
    vacancy_retrieval_queries_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_retrieval_queries_status: str | None = Field(default=None)
    vacancy_retrieval_evidence_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_retrieval_evidence_status: str | None = Field(default=None)
    vacancy_evidence_analysis_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_evidence_analysis_status: str | None = Field(default=None)
    vacancy_evidence_adjudication_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_evidence_adjudication_status: str | None = Field(default=None)
    vacancy_alignment_summary_v2_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_alignment_summary_v2_status: str | None = Field(default=None)
    vacancy_alignment_report_v2_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_alignment_report_v2_status: str | None = Field(default=None)
    vacancy_alignment_summary_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_alignment_summary_status: str | None = Field(default=None)
    vacancy_alignment_report_artifact: dict[str, Any] | None = Field(default=None)
    vacancy_alignment_report_status: str | None = Field(default=None)


class ActionRequest(BaseModel):
    force_recompute: bool = False


class PrepareRequest(BaseModel):
    targets: list[str] | None = None
    force_recompute: bool = False


class CulturalSignalResponse(BaseModel):
    source_provider: str
    source_url: str
    title: str
    snippet: str
    captured_at: str


class SemanticEvidenceResponse(BaseModel):
    source: str
    query: str
    top_k: int
    snippets: list[str]


class InterviewIterationResponse(BaseModel):
    step_order: int
    topic_key: str
    topic_label: str
    query: str
    status: str
    results_count: int
    top_urls: list[str]
    warning: str


class AnalyzeResponse(BaseModel):
    opportunity: OpportunityResponse
    analysis_text: str
    cultural_confidence: str
    cultural_warnings: list[str]
    cultural_signals: list[CulturalSignalResponse]
    semantic_evidence: SemanticEvidenceResponse


class AnalyzeProfileMatchResponse(BaseModel):
    opportunity: OpportunityResponse
    analysis_text: str
    semantic_evidence: SemanticEvidenceResponse
    served_from_cache: bool


class AnalyzeCulturalFitResponse(BaseModel):
    opportunity: OpportunityResponse
    analysis_text: str
    cultural_confidence: str
    cultural_warnings: list[str]
    cultural_signals: list[CulturalSignalResponse]
    served_from_cache: bool


class InterviewBriefResponse(BaseModel):
    opportunity: OpportunityResponse
    analysis_text: str
    interview_warnings: list[str]
    interview_sources: list[CulturalSignalResponse]
    interview_iterations: list[InterviewIterationResponse]
    semantic_evidence: SemanticEvidenceResponse
    served_from_cache: bool
    assistant_message_id: str


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
    semantic_evidence: SemanticEvidenceResponse
    served_from_cache: bool


class AIRunResponse(BaseModel):
    run_id: str
    person_id: str
    opportunity_id: str
    action_key: str
    result_payload: dict[str, Any]
    is_current: bool
    created_at: str
    updated_at: str


class AIRunsResponse(BaseModel):
    items: list[AIRunResponse]


def _serialize_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _require_person(person_id: str) -> dict[str, Any]:
    person = get_person(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return person


def _to_response(item: dict[str, Any]) -> OpportunityResponse:
    return OpportunityResponse(**item)


def _as_semantic_evidence(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"source": "unknown", "query": "", "top_k": 0, "snippets": []}
    return {
        "source": str(payload.get("source", "")),
        "query": str(payload.get("query", "")),
        "top_k": int(payload.get("top_k", 0)),
        "snippets": [str(item) for item in payload.get("snippets", []) if str(item).strip()],
    }


def _prepare_action_key(target: str) -> str:
    mapping = {
        PREPARE_TARGET_GUIDANCE: ACTION_PREPARE_GUIDANCE,
        PREPARE_TARGET_COVER_LETTER: ACTION_PREPARE_COVER_LETTER,
        PREPARE_TARGET_EXPERIENCE_SUMMARY: ACTION_PREPARE_EXPERIENCE_SUMMARY,
    }
    value = mapping.get(target)
    if not value:
        raise ValueError("Invalid prepare target")
    return value


def _as_cultural_warnings(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if str(item).strip()]


def _as_cultural_signals(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        return []
    items: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "source_provider": str(item.get("source_provider", "")),
                "source_url": str(item.get("source_url", "")),
                "title": str(item.get("title", "")),
                "snippet": str(item.get("snippet", "")),
                "captured_at": str(item.get("captured_at", "")),
            }
        )
    return items


def _as_interview_iterations(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    items: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        raw_urls = item.get("top_urls", [])
        top_urls = [str(url) for url in raw_urls if str(url).strip()] if isinstance(raw_urls, list) else []
        items.append(
            {
                "step_order": int(item.get("step_order", 0) or 0),
                "topic_key": str(item.get("topic_key", "")),
                "topic_label": str(item.get("topic_label", "")),
                "query": str(item.get("query", "")),
                "status": str(item.get("status", "")),
                "results_count": int(item.get("results_count", 0) or 0),
                "top_urls": top_urls,
                "warning": str(item.get("warning", "")),
            }
        )
    return items


def _append_assistant_message_dedup(person_id: str, content: str) -> str:
    normalized = content.strip()
    if not normalized:
        return ""
    conversation = get_or_create_conversation(person_id)
    messages = conversation.get("messages", [])
    if messages:
        last = messages[-1]
        if (
            str(last.get("role", "")).strip() == "assistant"
            and str(last.get("content", "")).strip() == normalized
        ):
            return str(last.get("message_id", ""))
    updated = append_message(person_id, "assistant", normalized)
    if not updated.get("messages"):
        return ""
    return str(updated["messages"][-1].get("message_id", ""))


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
    settings: Settings = Depends(get_settings),
) -> FromSearchResponse:
    _require_person(person_id)
    item, created = import_url_opportunity(
        person_id=person_id,
        source_url=payload.source_url,
        source_label=payload.source_label,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        raw_text=payload.raw_text,
    )
    if created:
        structured = extract_structured_opportunity_profile(item, settings)
        updated = update_saved_opportunity(
            person_id=person_id,
            opportunity_id=item["opportunity_id"],
            status=None,
            notes=None,
            vacancy_profile=structured,
            vacancy_profile_status="draft",
        )
        if updated:
            item = updated
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
        source_label=payload.source_label,
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
        source_label=payload.source_label,
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
    if (
        payload.vacancy_profile_status is not None
        and payload.vacancy_profile_status not in VACANCY_PROFILE_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_profile_status",
        )
    if (
        payload.vacancy_blocks_status is not None
        and payload.vacancy_blocks_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_blocks_status",
        )
    if (
        payload.vacancy_dimensions_status is not None
        and payload.vacancy_dimensions_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_dimensions_status",
        )
    if (
        payload.vacancy_salary_status is not None
        and payload.vacancy_salary_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_salary_status",
        )
    if (
        payload.vacancy_comparable_conditions_status is not None
        and payload.vacancy_comparable_conditions_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_comparable_conditions_status",
        )
    if (
        payload.vacancy_dimensions_enriched_status is not None
        and payload.vacancy_dimensions_enriched_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_dimensions_enriched_status",
        )
    if (
        payload.vacancy_retrieval_queries_status is not None
        and payload.vacancy_retrieval_queries_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_retrieval_queries_status",
        )
    if (
        payload.vacancy_retrieval_evidence_status is not None
        and payload.vacancy_retrieval_evidence_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_retrieval_evidence_status",
        )
    if (
        payload.vacancy_evidence_analysis_status is not None
        and payload.vacancy_evidence_analysis_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_evidence_analysis_status",
        )
    if (
        payload.vacancy_evidence_adjudication_status is not None
        and payload.vacancy_evidence_adjudication_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_evidence_adjudication_status",
        )
    if (
        payload.vacancy_alignment_summary_v2_status is not None
        and payload.vacancy_alignment_summary_v2_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_alignment_summary_v2_status",
        )
    if (
        payload.vacancy_alignment_report_v2_status is not None
        and payload.vacancy_alignment_report_v2_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_alignment_report_v2_status",
        )
    if (
        payload.vacancy_alignment_summary_status is not None
        and payload.vacancy_alignment_summary_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_alignment_summary_status",
        )
    if (
        payload.vacancy_alignment_report_status is not None
        and payload.vacancy_alignment_report_status not in VACANCY_V2_ARTIFACT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vacancy_alignment_report_status",
        )

    item = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=payload.status,
        notes=payload.notes,
        vacancy_profile=payload.vacancy_profile,
        vacancy_profile_status=payload.vacancy_profile_status,
        vacancy_blocks_artifact=payload.vacancy_blocks_artifact,
        vacancy_blocks_status=payload.vacancy_blocks_status,
        vacancy_dimensions_artifact=payload.vacancy_dimensions_artifact,
        vacancy_dimensions_status=payload.vacancy_dimensions_status,
        vacancy_salary_artifact=payload.vacancy_salary_artifact,
        vacancy_salary_status=payload.vacancy_salary_status,
        vacancy_comparable_conditions_artifact=payload.vacancy_comparable_conditions_artifact,
        vacancy_comparable_conditions_status=payload.vacancy_comparable_conditions_status,
        vacancy_dimensions_enriched_artifact=payload.vacancy_dimensions_enriched_artifact,
        vacancy_dimensions_enriched_status=payload.vacancy_dimensions_enriched_status,
        vacancy_retrieval_queries_artifact=payload.vacancy_retrieval_queries_artifact,
        vacancy_retrieval_queries_status=payload.vacancy_retrieval_queries_status,
        vacancy_retrieval_evidence_artifact=payload.vacancy_retrieval_evidence_artifact,
        vacancy_retrieval_evidence_status=payload.vacancy_retrieval_evidence_status,
        vacancy_evidence_analysis_artifact=payload.vacancy_evidence_analysis_artifact,
        vacancy_evidence_analysis_status=payload.vacancy_evidence_analysis_status,
        vacancy_evidence_adjudication_artifact=payload.vacancy_evidence_adjudication_artifact,
        vacancy_evidence_adjudication_status=payload.vacancy_evidence_adjudication_status,
        vacancy_alignment_summary_v2_artifact=payload.vacancy_alignment_summary_v2_artifact,
        vacancy_alignment_summary_v2_status=payload.vacancy_alignment_summary_v2_status,
        vacancy_alignment_report_v2_artifact=payload.vacancy_alignment_report_v2_artifact,
        vacancy_alignment_report_v2_status=payload.vacancy_alignment_report_v2_status,
        vacancy_alignment_summary_artifact=payload.vacancy_alignment_summary_artifact,
        vacancy_alignment_summary_status=payload.vacancy_alignment_summary_status,
        vacancy_alignment_report_artifact=payload.vacancy_alignment_report_artifact,
        vacancy_alignment_report_status=payload.vacancy_alignment_report_status,
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


@router.post("/{opportunity_id}/vacancy-profile/recompute")
def recompute_vacancy_profile(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    structured = extract_structured_opportunity_profile(opportunity, settings)
    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_profile=structured,
        vacancy_profile_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy profile",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-profile/recompute/stream")
async def recompute_vacancy_profile_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_profile_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_profile_extracting",
                },
            )
            await asyncio.sleep(0)

            structured = extract_structured_opportunity_profile(opportunity, settings)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_profile_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_profile=structured,
                vacancy_profile_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy profile")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-blocks/recompute")
def recompute_vacancy_blocks(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    try:
        artifact = extract_vacancy_blocks(opportunity, settings)
    except VacancyBlocksExtractionError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_blocks_artifact=artifact,
        vacancy_blocks_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy blocks",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-blocks/recompute/stream")
async def recompute_vacancy_blocks_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_blocks_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_blocks_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = extract_vacancy_blocks(opportunity, settings)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_blocks_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_blocks_artifact=artifact,
                vacancy_blocks_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy blocks")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyBlocksExtractionError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_blocks_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-dimensions/recompute")
def recompute_vacancy_dimensions(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = extract_vacancy_dimensions(
            opportunity=opportunity,
            vacancy_blocks_artifact=opportunity.get("vacancy_blocks_artifact", {}),
            settings=settings,
        )
    except VacancyDimensionsExtractionError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_dimensions_artifact=artifact,
        vacancy_dimensions_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy dimensions",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-salary/recompute")
def recompute_vacancy_salary(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = extract_vacancy_salary_normalization(
            opportunity=opportunity,
            vacancy_dimensions_artifact=opportunity.get("vacancy_dimensions_artifact", {}),
            settings=settings,
        )
    except VacancySalaryNormalizationError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_salary_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_salary_artifact=artifact,
        vacancy_salary_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy salary",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-salary/recompute/stream")
async def recompute_vacancy_salary_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_salary_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_salary_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = extract_vacancy_salary_normalization(
                opportunity=opportunity,
                vacancy_dimensions_artifact=opportunity.get("vacancy_dimensions_artifact", {}),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_salary_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_salary_artifact=artifact,
                vacancy_salary_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy salary")

            yield _serialize_sse(
                "message_complete",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "vacancy_salary_status": "draft",
                    "artifact": artifact,
                },
            )
        except VacancySalaryNormalizationError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_salary_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-comparable-conditions/recompute")
def recompute_vacancy_comparable_conditions(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = build_vacancy_comparable_conditions(
            opportunity=opportunity,
            vacancy_dimensions_artifact=opportunity.get("vacancy_dimensions_artifact", {}),
            vacancy_salary_artifact=opportunity.get("vacancy_salary_artifact", {}),
        )
    except VacancyComparableConditionsBuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_comparable_conditions_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_comparable_conditions_artifact=artifact,
        vacancy_comparable_conditions_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy comparable conditions",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-comparable-conditions/recompute/stream")
async def recompute_vacancy_comparable_conditions_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_comparable_conditions_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_comparable_conditions_building",
                },
            )
            await asyncio.sleep(0)

            artifact = build_vacancy_comparable_conditions(
                opportunity=opportunity,
                vacancy_dimensions_artifact=opportunity.get("vacancy_dimensions_artifact", {}),
                vacancy_salary_artifact=opportunity.get("vacancy_salary_artifact", {}),
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_comparable_conditions_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_comparable_conditions_artifact=artifact,
                vacancy_comparable_conditions_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy comparable conditions")

            yield _serialize_sse(
                "message_complete",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "opportunity": updated,
                },
            )
        except VacancyComparableConditionsBuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_comparable_conditions_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-dimensions-enriched/recompute")
def recompute_vacancy_dimensions_enriched(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = enrich_vacancy_dimensions_artifact(
            opportunity=opportunity,
            vacancy_dimensions_artifact=opportunity.get("vacancy_dimensions_artifact", {}),
        )
    except VacancyDimensionsEnrichmentError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_dimensions_enriched_artifact=artifact,
        vacancy_dimensions_enriched_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy dimensions enriched artifact",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-retrieval-queries/recompute")
def recompute_vacancy_retrieval_queries(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = extract_vacancy_retrieval_queries(
            opportunity=opportunity,
            vacancy_dimensions_enriched_artifact=opportunity.get("vacancy_dimensions_enriched_artifact", {}),
            vacancy_salary_artifact=opportunity.get("vacancy_salary_artifact", {}),
            settings=settings,
        )
    except VacancyRetrievalQueriesExtractionError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_retrieval_queries_artifact=artifact,
        vacancy_retrieval_queries_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy retrieval queries",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-retrieval-queries/recompute/stream")
async def recompute_vacancy_retrieval_queries_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_retrieval_queries_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_retrieval_queries_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = extract_vacancy_retrieval_queries(
                opportunity=opportunity,
                vacancy_dimensions_enriched_artifact=opportunity.get(
                    "vacancy_dimensions_enriched_artifact", {}
                ),
                vacancy_salary_artifact=opportunity.get("vacancy_salary_artifact", {}),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_retrieval_queries_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_retrieval_queries_artifact=artifact,
                vacancy_retrieval_queries_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy retrieval queries")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyRetrievalQueriesExtractionError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_retrieval_queries_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-retrieval-evidence/recompute")
def recompute_vacancy_retrieval_evidence(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = build_vacancy_retrieval_evidence(
            opportunity=opportunity,
            vacancy_retrieval_queries_artifact=opportunity.get("vacancy_retrieval_queries_artifact", {}),
            settings=settings,
        )
    except VacancyRetrievalEvidenceBuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_retrieval_evidence_artifact=artifact,
        vacancy_retrieval_evidence_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy retrieval evidence",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-retrieval-evidence/recompute/stream")
async def recompute_vacancy_retrieval_evidence_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_retrieval_evidence_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_retrieval_evidence_building",
                },
            )
            await asyncio.sleep(0)

            artifact = build_vacancy_retrieval_evidence(
                opportunity=opportunity,
                vacancy_retrieval_queries_artifact=opportunity.get("vacancy_retrieval_queries_artifact", {}),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_retrieval_evidence_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_retrieval_evidence_artifact=artifact,
                vacancy_retrieval_evidence_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy retrieval evidence")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyRetrievalEvidenceBuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_retrieval_evidence_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-evidence-analysis/recompute")
def recompute_vacancy_evidence_analysis(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = build_vacancy_evidence_analysis(
            opportunity=opportunity,
            vacancy_retrieval_evidence_artifact=opportunity.get("vacancy_retrieval_evidence_artifact", {}),
        )
    except VacancyEvidenceAnalysisBuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_evidence_analysis_artifact=artifact,
        vacancy_evidence_analysis_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy evidence analysis",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-evidence-analysis/recompute/stream")
async def recompute_vacancy_evidence_analysis_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_evidence_analysis_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_evidence_analysis_building",
                },
            )
            await asyncio.sleep(0)

            artifact = build_vacancy_evidence_analysis(
                opportunity=opportunity,
                vacancy_retrieval_evidence_artifact=opportunity.get("vacancy_retrieval_evidence_artifact", {}),
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_evidence_analysis_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_evidence_analysis_artifact=artifact,
                vacancy_evidence_analysis_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy evidence analysis")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyEvidenceAnalysisBuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_evidence_analysis_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-alignment-summary/recompute")
def recompute_vacancy_alignment_summary(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = build_vacancy_alignment_summary(
            opportunity=opportunity,
            vacancy_evidence_analysis_artifact=opportunity.get(
                "vacancy_evidence_analysis_artifact",
                {},
            ),
        )
    except VacancyAlignmentSummaryBuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_alignment_summary_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_alignment_summary_artifact=artifact,
        vacancy_alignment_summary_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy alignment summary",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-alignment-summary/recompute/stream")
async def recompute_vacancy_alignment_summary_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_summary_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_summary_building",
                },
            )
            await asyncio.sleep(0)

            artifact = build_vacancy_alignment_summary(
                opportunity=opportunity,
                vacancy_evidence_analysis_artifact=opportunity.get(
                    "vacancy_evidence_analysis_artifact",
                    {},
                ),
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_summary_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_summary_artifact=artifact,
                vacancy_alignment_summary_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy alignment summary")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyAlignmentSummaryBuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_summary_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-evidence-adjudication/recompute")
def recompute_vacancy_evidence_adjudication(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    person = _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = build_vacancy_evidence_adjudication(
            person=person,
            opportunity=opportunity,
            vacancy_dimensions_enriched_artifact=opportunity.get(
                "vacancy_dimensions_enriched_artifact",
                {},
            ),
            vacancy_evidence_analysis_artifact=opportunity.get(
                "vacancy_evidence_analysis_artifact",
                {},
            ),
            settings=settings,
        )
    except VacancyEvidenceAdjudicationBuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_evidence_adjudication_artifact=artifact,
        vacancy_evidence_adjudication_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy evidence adjudication",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-evidence-adjudication/recompute/stream")
async def recompute_vacancy_evidence_adjudication_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    person = _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_evidence_adjudication_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_evidence_adjudication_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = build_vacancy_evidence_adjudication(
                person=person,
                opportunity=opportunity,
                vacancy_dimensions_enriched_artifact=opportunity.get(
                    "vacancy_dimensions_enriched_artifact",
                    {},
                ),
                vacancy_evidence_analysis_artifact=opportunity.get(
                    "vacancy_evidence_analysis_artifact",
                    {},
                ),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_evidence_adjudication_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_evidence_adjudication_artifact=artifact,
                vacancy_evidence_adjudication_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy evidence adjudication")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyEvidenceAdjudicationBuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_evidence_adjudication_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-alignment-summary-v2/recompute")
def recompute_vacancy_alignment_summary_v2(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> OpportunityResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = build_vacancy_alignment_summary_v2(
            opportunity=opportunity,
            vacancy_evidence_adjudication_artifact=opportunity.get(
                "vacancy_evidence_adjudication_artifact",
                {},
            ),
        )
    except VacancyAlignmentSummaryV2BuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_alignment_summary_v2_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_alignment_summary_v2_artifact=artifact,
        vacancy_alignment_summary_v2_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy alignment summary v2",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-alignment-summary-v2/recompute/stream")
async def recompute_vacancy_alignment_summary_v2_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_summary_v2_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_summary_v2_building",
                },
            )
            await asyncio.sleep(0)

            artifact = build_vacancy_alignment_summary_v2(
                opportunity=opportunity,
                vacancy_evidence_adjudication_artifact=opportunity.get(
                    "vacancy_evidence_adjudication_artifact",
                    {},
                ),
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_summary_v2_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_summary_v2_artifact=artifact,
                vacancy_alignment_summary_v2_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy alignment summary v2")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyAlignmentSummaryV2BuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_summary_v2_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-alignment-report-v2/recompute")
def recompute_vacancy_alignment_report_v2(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    person = _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = extract_vacancy_alignment_report_v2(
            person=person,
            opportunity=opportunity,
            vacancy_evidence_adjudication_artifact=opportunity.get(
                "vacancy_evidence_adjudication_artifact",
                {},
            ),
            vacancy_alignment_summary_v2_artifact=opportunity.get(
                "vacancy_alignment_summary_v2_artifact",
                {},
            ),
            vacancy_evidence_analysis_artifact=opportunity.get(
                "vacancy_evidence_analysis_artifact",
                {},
            ),
            settings=settings,
        )
    except VacancyAlignmentReportV2BuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_alignment_report_v2_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_alignment_report_v2_artifact=artifact,
        vacancy_alignment_report_v2_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy alignment report v2",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-alignment-report-v2/recompute/stream")
async def recompute_vacancy_alignment_report_v2_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    person = _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_report_v2_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_report_v2_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = extract_vacancy_alignment_report_v2(
                person=person,
                opportunity=opportunity,
                vacancy_evidence_adjudication_artifact=opportunity.get(
                    "vacancy_evidence_adjudication_artifact",
                    {},
                ),
                vacancy_alignment_summary_v2_artifact=opportunity.get(
                    "vacancy_alignment_summary_v2_artifact",
                    {},
                ),
                vacancy_evidence_analysis_artifact=opportunity.get(
                    "vacancy_evidence_analysis_artifact",
                    {},
                ),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_report_v2_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_report_v2_artifact=artifact,
                vacancy_alignment_report_v2_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy alignment report v2")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyAlignmentReportV2BuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_report_v2_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-alignment-report/recompute")
def recompute_vacancy_alignment_report(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    person = _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    try:
        artifact = extract_vacancy_alignment_report(
            person=person,
            opportunity=opportunity,
            vacancy_alignment_summary_artifact=opportunity.get(
                "vacancy_alignment_summary_artifact",
                {},
            ),
            vacancy_evidence_analysis_artifact=opportunity.get(
                "vacancy_evidence_analysis_artifact",
                {},
            ),
            settings=settings,
        )
    except VacancyAlignmentReportBuildError as exc:
        update_saved_opportunity(
            person_id=person_id,
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_alignment_report_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status=None,
        notes=None,
        vacancy_alignment_report_artifact=artifact,
        vacancy_alignment_report_status="draft",
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not recompute vacancy alignment report",
        )
    return _to_response(updated)


@router.post("/{opportunity_id}/vacancy-alignment-report/recompute/stream")
async def recompute_vacancy_alignment_report_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    person = _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_report_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_report_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = extract_vacancy_alignment_report(
                person=person,
                opportunity=opportunity,
                vacancy_alignment_summary_artifact=opportunity.get(
                    "vacancy_alignment_summary_artifact",
                    {},
                ),
                vacancy_evidence_analysis_artifact=opportunity.get(
                    "vacancy_evidence_analysis_artifact",
                    {},
                ),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_alignment_report_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_report_artifact=artifact,
                vacancy_alignment_report_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy alignment report")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyAlignmentReportBuildError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_alignment_report_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-dimensions-enriched/recompute/stream")
async def recompute_vacancy_dimensions_enriched_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_dimensions_enriched_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_dimensions_enriched_building",
                },
            )
            await asyncio.sleep(0)

            artifact = enrich_vacancy_dimensions_artifact(
                opportunity=opportunity,
                vacancy_dimensions_artifact=opportunity.get("vacancy_dimensions_artifact", {}),
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_dimensions_enriched_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_dimensions_enriched_artifact=artifact,
                vacancy_dimensions_enriched_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy dimensions enriched artifact")

            yield _serialize_sse(
                "message_complete",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "vacancy_dimensions_enriched_status": "draft",
                    "artifact": artifact,
                },
            )
        except VacancyDimensionsEnrichmentError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_dimensions_enriched_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/vacancy-dimensions/recompute/stream")
async def recompute_vacancy_dimensions_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _require_person(person_id)
    opportunity = find_opportunity(person_id, opportunity_id)
    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    async def event_generator():
        try:
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_dimensions_recompute_started",
                },
            )
            await asyncio.sleep(0)

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_dimensions_extracting",
                },
            )
            await asyncio.sleep(0)

            artifact = extract_vacancy_dimensions(
                opportunity=opportunity,
                vacancy_blocks_artifact=opportunity.get("vacancy_blocks_artifact", {}),
                settings=settings,
            )

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "vacancy_dimensions_saving",
                },
            )
            await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_dimensions_artifact=artifact,
                vacancy_dimensions_status="draft",
            )
            if not updated:
                raise RuntimeError("Could not recompute vacancy dimensions")

            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": updated,
                },
            )
        except VacancyDimensionsExtractionError as exc:
            update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status=None,
                notes=None,
                vacancy_dimensions_status="error",
            )
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )
        except Exception as exc:  # pragma: no cover - stream runtime path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/vacancy-v2/consistency")
def get_vacancy_v2_consistency_report(
    person_id: str,
    sample_limit: int = Query(default=20, ge=1, le=100),
    min_salary_transfer_rate: float = Query(default=0.8, ge=0.0, le=1.0),
    max_salary_signal_in_step2_benefits_rate: float = Query(default=0.05, ge=0.0, le=1.0),
    min_salary_transfer_eligible: int = Query(default=1, ge=1, le=100),
    _: SessionData = Depends(require_operator_session),
) -> VacancyV2ConsistencyResponse:
    _require_person(person_id)
    items = list_saved_opportunities(person_id)
    report = build_vacancy_v2_consistency_report(
        items,
        issue_sample_limit=sample_limit,
    )
    evaluation = evaluate_vacancy_v2_consistency_report(
        report,
        min_salary_transfer_rate=min_salary_transfer_rate,
        max_salary_signal_in_step2_benefits_rate=max_salary_signal_in_step2_benefits_rate,
        min_salary_transfer_eligible=min_salary_transfer_eligible,
    )
    return VacancyV2ConsistencyResponse(
        person_id=person_id,
        total_opportunities=report["total_opportunities"],
        opportunities_with_step2=report["opportunities_with_step2"],
        opportunities_with_step3=report["opportunities_with_step3"],
        salary_transfer_eligible=report["salary_transfer_eligible"],
        salary_transfer_ok=report["salary_transfer_ok"],
        salary_transfer_missing=report["salary_transfer_missing"],
        salary_transfer_rate=report["salary_transfer_rate"],
        salary_signal_in_step2_benefits=report["salary_signal_in_step2_benefits"],
        salary_signal_in_step2_benefits_rate=report["salary_signal_in_step2_benefits_rate"],
        gate_passed=evaluation["gate_passed"],
        failed_checks=evaluation["failed_checks"],
        thresholds=evaluation["thresholds"],
        issue_samples=[
            VacancyV2ConsistencyIssueResponse(
                opportunity_id=issue["opportunity_id"],
                title=issue["title"],
                company=issue["company"],
                vacancy_blocks_status=issue["vacancy_blocks_status"],
                vacancy_dimensions_status=issue["vacancy_dimensions_status"],
                issues=issue["issues"],
            )
            for issue in report["issue_samples"]
        ],
    )


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


@router.get("/{opportunity_id}/ai-runs")
def list_action_runs(
    person_id: str,
    opportunity_id: str,
    action_key: str | None = Query(default=None),
    _: SessionData = Depends(require_operator_session),
) -> AIRunsResponse:
    _require_person(person_id)
    item = find_opportunity(person_id, opportunity_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    normalized_action_key = action_key.strip() if isinstance(action_key, str) else None
    if normalized_action_key and normalized_action_key not in AI_ACTION_KEYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid action_key",
        )

    runs = list_ai_runs(
        person_id=person_id,
        opportunity_id=opportunity_id,
        action_key=normalized_action_key,
        current_only=False,
    )
    return AIRunsResponse(items=[AIRunResponse(**record) for record in runs])


@router.post("/{opportunity_id}/analyze/profile-match")
def analyze_profile_match_action(
    person_id: str,
    opportunity_id: str,
    payload: ActionRequest,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> AnalyzeProfileMatchResponse:
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

    if not payload.force_recompute:
        cached = get_current_ai_run(
            person_id=person_id,
            opportunity_id=opportunity_id,
            action_key=ACTION_ANALYZE_PROFILE_MATCH,
        )
        if cached:
            cached_payload = cached.get("result_payload", {})
            if isinstance(cached_payload, dict):
                text = str(cached_payload.get("analysis_text", "")).strip()
                evidence = _as_semantic_evidence(cached_payload.get("semantic_evidence"))
                if text:
                    return AnalyzeProfileMatchResponse(
                        opportunity=_to_response(opportunity),
                        analysis_text=text,
                        semantic_evidence=evidence,
                        served_from_cache=True,
                    )

    run_id = new_ai_run_id()
    result = analyze_profile_match(person, opportunity, settings, run_id=run_id)
    upsert_current_ai_run(
        person_id=person_id,
        opportunity_id=opportunity_id,
        action_key=ACTION_ANALYZE_PROFILE_MATCH,
        run_id=run_id,
        result_payload={
            "analysis_text": result["analysis_text"],
            "semantic_evidence": result["semantic_evidence"],
            "input_snapshot": result.get("input_snapshot", {}),
            "parse_validation": result.get("parse_validation", {}),
            "normalized_candidate_profile": result.get("normalized_candidate_profile", {}),
            "mapped_criteria": result.get("mapped_criteria", {}),
            "criterion_evidence": result.get("criterion_evidence", []),
            "criteria_evaluation": result.get("criteria_evaluation", []),
            "consolidated_assessment": result.get("consolidated_assessment", {}),
            "rendered_output": result.get("rendered_output", {}),
            "prompt_meta": result.get("prompt_meta", {}),
        },
    )
    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status="analyzed",
        notes=opportunity.get("notes", ""),
    )
    final_item = updated or opportunity
    return AnalyzeProfileMatchResponse(
        opportunity=_to_response(final_item),
        analysis_text=result["analysis_text"],
        semantic_evidence=result["semantic_evidence"],
        served_from_cache=False,
    )


@router.post("/{opportunity_id}/analyze/cultural-fit")
def analyze_cultural_fit_action(
    person_id: str,
    opportunity_id: str,
    payload: ActionRequest,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> AnalyzeCulturalFitResponse:
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

    if not payload.force_recompute:
        cached = get_current_ai_run(
            person_id=person_id,
            opportunity_id=opportunity_id,
            action_key=ACTION_ANALYZE_CULTURAL_FIT,
        )
        if cached:
            cached_payload = cached.get("result_payload", {})
            if isinstance(cached_payload, dict):
                text = str(cached_payload.get("analysis_text", "")).strip()
                confidence = str(cached_payload.get("cultural_confidence", "")).strip()
                warnings = _as_cultural_warnings(cached_payload.get("cultural_warnings"))
                signals = _as_cultural_signals(cached_payload.get("cultural_signals"))
                if text:
                    return AnalyzeCulturalFitResponse(
                        opportunity=_to_response(opportunity),
                        analysis_text=text,
                        cultural_confidence=confidence,
                        cultural_warnings=warnings,
                        cultural_signals=[CulturalSignalResponse(**item) for item in signals],
                        served_from_cache=True,
                    )

    run_id = new_ai_run_id()
    result = analyze_cultural_fit(person, opportunity, settings, run_id=run_id)
    upsert_current_ai_run(
        person_id=person_id,
        opportunity_id=opportunity_id,
        action_key=ACTION_ANALYZE_CULTURAL_FIT,
        run_id=run_id,
        result_payload={
            "analysis_text": result["analysis_text"],
            "cultural_confidence": result["cultural_confidence"],
            "cultural_warnings": result["cultural_warnings"],
            "cultural_signals": result["cultural_signals"],
        },
    )
    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status="analyzed",
        notes=opportunity.get("notes", ""),
    )
    final_item = updated or opportunity
    return AnalyzeCulturalFitResponse(
        opportunity=_to_response(final_item),
        analysis_text=result["analysis_text"],
        cultural_confidence=result["cultural_confidence"],
        cultural_warnings=result["cultural_warnings"],
        cultural_signals=result["cultural_signals"],
        served_from_cache=False,
    )


@router.post("/{opportunity_id}/interview/brief")
def interview_brief_action(
    person_id: str,
    opportunity_id: str,
    payload: ActionRequest,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> InterviewBriefResponse:
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

    if not payload.force_recompute:
        cached = get_current_ai_run(
            person_id=person_id,
            opportunity_id=opportunity_id,
            action_key=ACTION_INTERVIEW_BRIEF,
        )
        if cached:
            cached_payload = cached.get("result_payload", {})
            if isinstance(cached_payload, dict):
                text = str(cached_payload.get("analysis_text", "")).strip()
                warnings = _as_cultural_warnings(cached_payload.get("interview_warnings"))
                sources = _as_cultural_signals(cached_payload.get("interview_sources"))
                iterations = _as_interview_iterations(cached_payload.get("interview_iterations"))
                evidence = _as_semantic_evidence(cached_payload.get("semantic_evidence"))
                if text:
                    return InterviewBriefResponse(
                        opportunity=_to_response(opportunity),
                        analysis_text=text,
                        interview_warnings=warnings,
                        interview_sources=[CulturalSignalResponse(**item) for item in sources],
                        interview_iterations=[InterviewIterationResponse(**item) for item in iterations],
                        semantic_evidence=evidence,
                        served_from_cache=True,
                        assistant_message_id="",
                    )

    run_id = new_ai_run_id()
    result = interview_brief(person, opportunity, settings, run_id=run_id)
    upsert_current_ai_run(
        person_id=person_id,
        opportunity_id=opportunity_id,
        action_key=ACTION_INTERVIEW_BRIEF,
        run_id=run_id,
        result_payload={
            "analysis_text": result["analysis_text"],
            "interview_warnings": result["interview_warnings"],
            "interview_sources": result["interview_sources"],
            "interview_iterations": result["interview_iterations"],
            "semantic_evidence": result["semantic_evidence"],
            "prompt_meta": result.get("prompt_meta", {}),
        },
    )
    assistant_message_id = _append_assistant_message_dedup(
        person_id,
        result["analysis_text"],
    )
    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status="analyzed",
        notes=opportunity.get("notes", ""),
    )
    final_item = updated or opportunity
    return InterviewBriefResponse(
        opportunity=_to_response(final_item),
        analysis_text=result["analysis_text"],
        interview_warnings=result["interview_warnings"],
        interview_sources=result["interview_sources"],
        interview_iterations=result["interview_iterations"],
        semantic_evidence=result["semantic_evidence"],
        served_from_cache=False,
        assistant_message_id=assistant_message_id,
    )


@router.post("/{opportunity_id}/analyze/profile-match/stream")
async def analyze_profile_match_stream(
    person_id: str,
    opportunity_id: str,
    payload: ActionRequest | None = None,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
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

    async def event_generator():
        try:
            request_payload = payload or ActionRequest()
            yield _serialize_sse(
                "message_start",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "channel": "analysis_text",
                },
            )
            if not request_payload.force_recompute:
                cached = get_current_ai_run(
                    person_id=person_id,
                    opportunity_id=opportunity_id,
                    action_key=ACTION_ANALYZE_PROFILE_MATCH,
                )
                if cached and isinstance(cached.get("result_payload"), dict):
                    cached_payload = cached["result_payload"]
                    text = str(cached_payload.get("analysis_text", "")).strip()
                    evidence = _as_semantic_evidence(cached_payload.get("semantic_evidence"))
                    if text:
                        yield _serialize_sse(
                            "tool_status",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "stage": "analyze_profile_match_cached",
                            },
                        )
                        yield _serialize_sse(
                            "message_delta",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "channel": "analysis_text",
                                "delta": text,
                            },
                        )
                        yield _serialize_sse(
                            "message_complete",
                            {
                                "opportunity": opportunity,
                                "analysis_text": text,
                                "semantic_evidence": evidence,
                                "served_from_cache": True,
                            },
                        )
                        return

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "analyze_profile_match_running",
                },
            )
            run_id = new_ai_run_id()
            (
                semantic_evidence,
                input_snapshot,
                parse_validation,
                normalized_candidate_profile,
                mapped_criteria,
                criterion_evidence,
                criteria_evaluation,
                consolidated_assessment,
                rendered_output,
                prompt_meta,
                stream,
            ) = stream_analyze_profile_match_text(
                person,
                opportunity,
                settings,
                run_id=run_id,
            )
            analysis_text = ""
            for delta in stream:
                analysis_text += delta
                yield _serialize_sse(
                    "message_delta",
                    {
                        "person_id": person_id,
                        "opportunity_id": opportunity_id,
                        "channel": "analysis_text",
                        "delta": delta,
                    },
                )
                await asyncio.sleep(0)

            upsert_current_ai_run(
                person_id=person_id,
                opportunity_id=opportunity_id,
                action_key=ACTION_ANALYZE_PROFILE_MATCH,
                run_id=run_id,
                result_payload={
                    "analysis_text": analysis_text,
                    "semantic_evidence": semantic_evidence,
                    "input_snapshot": input_snapshot,
                    "parse_validation": parse_validation,
                    "normalized_candidate_profile": normalized_candidate_profile,
                    "mapped_criteria": mapped_criteria,
                    "criterion_evidence": criterion_evidence,
                    "criteria_evaluation": criteria_evaluation,
                    "consolidated_assessment": consolidated_assessment,
                    "rendered_output": rendered_output,
                    "prompt_meta": prompt_meta,
                },
            )
            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status="analyzed",
                notes=opportunity.get("notes", ""),
            )
            final_item = updated or opportunity
            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": final_item,
                    "analysis_text": analysis_text,
                    "semantic_evidence": semantic_evidence,
                    "served_from_cache": False,
                },
            )
        except Exception as exc:  # pragma: no cover - network stream path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/analyze/cultural-fit/stream")
async def analyze_cultural_fit_stream(
    person_id: str,
    opportunity_id: str,
    payload: ActionRequest | None = None,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
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

    async def event_generator():
        try:
            request_payload = payload or ActionRequest()
            yield _serialize_sse(
                "message_start",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "channel": "analysis_text",
                },
            )
            if not request_payload.force_recompute:
                cached = get_current_ai_run(
                    person_id=person_id,
                    opportunity_id=opportunity_id,
                    action_key=ACTION_ANALYZE_CULTURAL_FIT,
                )
                if cached and isinstance(cached.get("result_payload"), dict):
                    cached_payload = cached["result_payload"]
                    text = str(cached_payload.get("analysis_text", "")).strip()
                    confidence = str(cached_payload.get("cultural_confidence", "")).strip()
                    warnings = _as_cultural_warnings(cached_payload.get("cultural_warnings"))
                    signals = _as_cultural_signals(cached_payload.get("cultural_signals"))
                    if text:
                        yield _serialize_sse(
                            "tool_status",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "stage": "analyze_cultural_fit_cached",
                            },
                        )
                        yield _serialize_sse(
                            "message_delta",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "channel": "analysis_text",
                                "delta": text,
                            },
                        )
                        yield _serialize_sse(
                            "message_complete",
                            {
                                "opportunity": opportunity,
                                "analysis_text": text,
                                "cultural_confidence": confidence,
                                "cultural_warnings": warnings,
                                "cultural_signals": signals,
                                "served_from_cache": True,
                            },
                        )
                        return

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "analyze_cultural_fit_running",
                },
            )
            run_id = new_ai_run_id()
            confidence, warnings, signals, prompt_meta, stream = stream_analyze_cultural_fit_text(
                person,
                opportunity,
                settings,
                run_id=run_id,
            )
            analysis_text = ""
            for delta in stream:
                analysis_text += delta
                yield _serialize_sse(
                    "message_delta",
                    {
                        "person_id": person_id,
                        "opportunity_id": opportunity_id,
                        "channel": "analysis_text",
                        "delta": delta,
                    },
                )
                await asyncio.sleep(0)

            upsert_current_ai_run(
                person_id=person_id,
                opportunity_id=opportunity_id,
                action_key=ACTION_ANALYZE_CULTURAL_FIT,
                run_id=run_id,
                result_payload={
                    "analysis_text": analysis_text,
                    "cultural_confidence": confidence,
                    "cultural_warnings": warnings,
                    "cultural_signals": signals,
                    "prompt_meta": prompt_meta,
                },
            )
            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status="analyzed",
                notes=opportunity.get("notes", ""),
            )
            final_item = updated or opportunity
            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": final_item,
                    "analysis_text": analysis_text,
                    "cultural_confidence": confidence,
                    "cultural_warnings": warnings,
                    "cultural_signals": signals,
                    "served_from_cache": False,
                },
            )
        except Exception as exc:  # pragma: no cover - network stream path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/interview/brief/stream")
async def interview_brief_stream(
    person_id: str,
    opportunity_id: str,
    payload: ActionRequest | None = None,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
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

    async def event_generator():
        try:
            request_payload = payload or ActionRequest()
            yield _serialize_sse(
                "message_start",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "channel": "analysis_text",
                },
            )
            if not request_payload.force_recompute:
                cached = get_current_ai_run(
                    person_id=person_id,
                    opportunity_id=opportunity_id,
                    action_key=ACTION_INTERVIEW_BRIEF,
                )
                if cached and isinstance(cached.get("result_payload"), dict):
                    cached_payload = cached["result_payload"]
                    text = str(cached_payload.get("analysis_text", "")).strip()
                    warnings = _as_cultural_warnings(cached_payload.get("interview_warnings"))
                    sources = _as_cultural_signals(cached_payload.get("interview_sources"))
                    iterations = _as_interview_iterations(cached_payload.get("interview_iterations"))
                    evidence = _as_semantic_evidence(cached_payload.get("semantic_evidence"))
                    if text:
                        yield _serialize_sse(
                            "tool_status",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "stage": "interview_brief_cached",
                            },
                        )
                        yield _serialize_sse(
                            "message_delta",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "channel": "analysis_text",
                                "delta": text,
                            },
                        )
                        yield _serialize_sse(
                            "message_complete",
                            {
                                "opportunity": opportunity,
                                "analysis_text": text,
                                "interview_warnings": warnings,
                                "interview_sources": sources,
                                "interview_iterations": iterations,
                                "semantic_evidence": evidence,
                                "served_from_cache": True,
                                "assistant_message_id": "",
                            },
                        )
                        return

            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "interview_brief_running",
                },
            )
            run_id = new_ai_run_id()
            (
                semantic_evidence,
                interview_sources,
                interview_warnings,
                interview_iterations,
                prompt_meta,
                stream,
            ) = stream_interview_brief_text(
                person,
                opportunity,
                settings,
                run_id=run_id,
            )
            analysis_text = ""
            for delta in stream:
                analysis_text += delta
                yield _serialize_sse(
                    "message_delta",
                    {
                        "person_id": person_id,
                        "opportunity_id": opportunity_id,
                        "channel": "analysis_text",
                        "delta": delta,
                    },
                )
                await asyncio.sleep(0)

            upsert_current_ai_run(
                person_id=person_id,
                opportunity_id=opportunity_id,
                action_key=ACTION_INTERVIEW_BRIEF,
                run_id=run_id,
                result_payload={
                    "analysis_text": analysis_text,
                    "interview_warnings": interview_warnings,
                    "interview_sources": interview_sources,
                    "interview_iterations": interview_iterations,
                    "semantic_evidence": semantic_evidence,
                    "prompt_meta": prompt_meta,
                },
            )
            assistant_message_id = _append_assistant_message_dedup(
                person_id,
                analysis_text,
            )
            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status="analyzed",
                notes=opportunity.get("notes", ""),
            )
            final_item = updated or opportunity
            yield _serialize_sse(
                "message_complete",
                {
                    "opportunity": final_item,
                    "analysis_text": analysis_text,
                    "interview_warnings": interview_warnings,
                    "interview_sources": interview_sources,
                    "interview_iterations": interview_iterations,
                    "semantic_evidence": semantic_evidence,
                    "served_from_cache": False,
                    "assistant_message_id": assistant_message_id,
                },
            )
        except Exception as exc:  # pragma: no cover - network stream path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
        cultural_confidence=result["cultural_confidence"],
        cultural_warnings=result["cultural_warnings"],
        cultural_signals=result["cultural_signals"],
        semantic_evidence=result["semantic_evidence"],
    )


@router.post("/{opportunity_id}/analyze/stream")
async def analyze_stream(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
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

    async def event_generator():
        try:
            yield _serialize_sse(
                "message_start",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "channel": "analysis_text",
                },
            )
            yield _serialize_sse(
                "tool_status",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "stage": "analyze_running",
                },
            )

            bundle, stream = stream_analyze_text(person, opportunity, settings)
            analysis_text = ""
            for delta in stream:
                analysis_text += delta
                yield _serialize_sse(
                    "message_delta",
                    {
                        "person_id": person_id,
                        "opportunity_id": opportunity_id,
                        "channel": "analysis_text",
                        "delta": delta,
                    },
                )
                await asyncio.sleep(0)

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status="analyzed",
                notes=opportunity.get("notes", ""),
            )
            final_item = updated or opportunity
            payload = {
                "opportunity": final_item,
                "analysis_text": analysis_text,
                "cultural_confidence": bundle["cultural_confidence"],
                "cultural_warnings": bundle["cultural_warnings"],
                "cultural_signals": bundle["cultural_signals"],
                "semantic_evidence": bundle["semantic_evidence"],
            }
            yield _serialize_sse("message_complete", payload)
        except Exception as exc:  # pragma: no cover - network stream path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{opportunity_id}/prepare")
def prepare(
    person_id: str,
    opportunity_id: str,
    payload: PrepareRequest | None = None,
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

    if payload is None:
        legacy_payload = prepare_application_materials(person, opportunity, settings)
        cover = upsert_current_artifact(
            person_id=person_id,
            opportunity_id=opportunity_id,
            artifact_type="cover_letter",
            content=legacy_payload["cover_letter"],
        )
        summary = upsert_current_artifact(
            person_id=person_id,
            opportunity_id=opportunity_id,
            artifact_type="experience_summary",
            content=legacy_payload["experience_summary"],
        )
        upsert_current_ai_run(
            person_id=person_id,
            opportunity_id=opportunity_id,
            action_key=ACTION_PREPARE_GUIDANCE,
            result_payload={
                "content": legacy_payload["guidance_text"],
                "semantic_evidence": legacy_payload["semantic_evidence"],
            },
        )
        upsert_current_ai_run(
            person_id=person_id,
            opportunity_id=opportunity_id,
            action_key=ACTION_PREPARE_COVER_LETTER,
            result_payload={
                "content": legacy_payload["cover_letter"],
                "semantic_evidence": legacy_payload["semantic_evidence"],
            },
        )
        upsert_current_ai_run(
            person_id=person_id,
            opportunity_id=opportunity_id,
            action_key=ACTION_PREPARE_EXPERIENCE_SUMMARY,
            result_payload={
                "content": legacy_payload["experience_summary"],
                "semantic_evidence": legacy_payload["semantic_evidence"],
            },
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
            guidance_text=legacy_payload["guidance_text"],
            artifacts=[ArtifactResponse(**cover), ArtifactResponse(**summary)],
            semantic_evidence=legacy_payload["semantic_evidence"],
            served_from_cache=False,
        )

    request_payload = payload
    targets = request_payload.targets or [*PREPARE_TARGETS]
    targets = [item for item in targets if item in PREPARE_TARGETS]
    if not targets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid prepare targets",
        )

    served_from_cache = True
    outputs: dict[str, str] = {}
    semantic_evidence: dict[str, Any] = {"source": "unknown", "query": "", "top_k": 0, "snippets": []}

    for target in targets:
        action_key = _prepare_action_key(target)
        cached = None
        if not request_payload.force_recompute:
            cached = get_current_ai_run(
                person_id=person_id,
                opportunity_id=opportunity_id,
                action_key=action_key,
            )
        if cached and isinstance(cached.get("result_payload"), dict):
            cached_payload = cached["result_payload"]
            content = str(cached_payload.get("content", "")).strip()
            if content:
                outputs[target] = content
                semantic_evidence = _as_semantic_evidence(cached_payload.get("semantic_evidence"))
                continue
        served_from_cache = False

    missing_targets = [target for target in targets if target not in outputs]
    if missing_targets:
        run_ids_by_target = {target: new_ai_run_id() for target in missing_targets}
        generated = prepare_selected_materials(
            person=person,
            opportunity=opportunity,
            settings=settings,
            targets=missing_targets,
            run_ids_by_target=run_ids_by_target,
        )
        semantic_evidence = generated["semantic_evidence"]
        for target, content in generated["outputs"].items():
            cleaned = content.strip()
            outputs[target] = cleaned
            upsert_current_ai_run(
                person_id=person_id,
                opportunity_id=opportunity_id,
                action_key=_prepare_action_key(target),
                run_id=run_ids_by_target.get(target, ""),
                result_payload={
                    "content": cleaned,
                    "semantic_evidence": semantic_evidence,
                    "prompt_meta": generated.get("prompt_meta", {}),
                },
            )

    if PREPARE_TARGET_COVER_LETTER in outputs:
        upsert_current_artifact(
            person_id=person_id,
            opportunity_id=opportunity_id,
            artifact_type="cover_letter",
            content=outputs[PREPARE_TARGET_COVER_LETTER],
        )
    if PREPARE_TARGET_EXPERIENCE_SUMMARY in outputs:
        upsert_current_artifact(
            person_id=person_id,
            opportunity_id=opportunity_id,
            artifact_type="experience_summary",
            content=outputs[PREPARE_TARGET_EXPERIENCE_SUMMARY],
        )

    current_items = list_current_artifacts(person_id, opportunity_id)
    allowed_types = set(ARTIFACT_TYPES)
    selected_artifact_types: set[str] = set()
    if PREPARE_TARGET_COVER_LETTER in targets:
        selected_artifact_types.add("cover_letter")
    if PREPARE_TARGET_EXPERIENCE_SUMMARY in targets:
        selected_artifact_types.add("experience_summary")
    filtered_items = [
        item
        for item in current_items
        if item["artifact_type"] in allowed_types and item["artifact_type"] in selected_artifact_types
    ]

    updated = update_saved_opportunity(
        person_id=person_id,
        opportunity_id=opportunity_id,
        status="application_prepared",
        notes=opportunity.get("notes", ""),
    )
    final_item = updated or opportunity
    return PrepareResponse(
        opportunity=_to_response(final_item),
        guidance_text=outputs.get(PREPARE_TARGET_GUIDANCE, ""),
        artifacts=[ArtifactResponse(**item) for item in filtered_items],
        semantic_evidence=semantic_evidence,
        served_from_cache=served_from_cache,
    )


@router.post("/{opportunity_id}/prepare/stream")
async def prepare_stream(
    person_id: str,
    opportunity_id: str,
    payload: PrepareRequest | None = None,
    _: SessionData = Depends(require_operator_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
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

    async def event_generator():
        try:
            request_payload = payload or PrepareRequest()
            targets = request_payload.targets or [*PREPARE_TARGETS]
            targets = [item for item in targets if item in PREPARE_TARGETS]
            if not targets:
                yield _serialize_sse(
                    "error",
                    {
                        "person_id": person_id,
                        "opportunity_id": opportunity_id,
                        "detail": "Invalid prepare targets",
                    },
                )
                return

            yield _serialize_sse(
                "message_start",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "channel": targets[0],
                },
            )

            served_from_cache = True
            outputs: dict[str, str] = {}
            semantic_evidence: dict[str, Any] = {
                "source": "unknown",
                "query": "",
                "top_k": 0,
                "snippets": [],
            }

            if not request_payload.force_recompute:
                for target in targets:
                    action_key = _prepare_action_key(target)
                    cached = get_current_ai_run(
                        person_id=person_id,
                        opportunity_id=opportunity_id,
                        action_key=action_key,
                    )
                    if not cached or not isinstance(cached.get("result_payload"), dict):
                        served_from_cache = False
                        continue
                    cached_payload = cached["result_payload"]
                    content = str(cached_payload.get("content", ""))
                    if not content.strip():
                        served_from_cache = False
                        continue
                    outputs[target] = content
                    semantic_evidence = _as_semantic_evidence(
                        cached_payload.get("semantic_evidence")
                    )
            else:
                served_from_cache = False

            missing_targets = [target for target in targets if target not in outputs]
            if missing_targets:
                served_from_cache = False
                run_ids_by_target = {
                    target: new_ai_run_id() for target in missing_targets
                }
                (
                    bundle,
                    guidance_stream,
                    cover_stream,
                    summary_stream,
                ) = stream_prepare_sections(
                    person,
                    opportunity,
                    settings,
                    run_ids_by_target=run_ids_by_target,
                )
                semantic_evidence = bundle["semantic_evidence"]
                stream_by_target = {
                    PREPARE_TARGET_GUIDANCE: guidance_stream,
                    PREPARE_TARGET_COVER_LETTER: cover_stream,
                    PREPARE_TARGET_EXPERIENCE_SUMMARY: summary_stream,
                }
                for target in missing_targets:
                    stream = stream_by_target[target]
                    outputs[target] = ""
                    yield _serialize_sse(
                        "tool_status",
                        {
                            "person_id": person_id,
                            "opportunity_id": opportunity_id,
                            "stage": f"prepare_{target}",
                        },
                    )
                    for delta in stream:
                        outputs[target] += delta
                        yield _serialize_sse(
                            "message_delta",
                            {
                                "person_id": person_id,
                                "opportunity_id": opportunity_id,
                                "channel": target,
                                "delta": delta,
                            },
                        )
                        await asyncio.sleep(0)
                    upsert_current_ai_run(
                        person_id=person_id,
                        opportunity_id=opportunity_id,
                        action_key=_prepare_action_key(target),
                        run_id=run_ids_by_target.get(target, ""),
                        result_payload={
                            "content": outputs[target],
                            "semantic_evidence": semantic_evidence,
                        },
                    )

            if served_from_cache:
                for target in targets:
                    content = outputs.get(target, "")
                    if not content:
                        continue
                    yield _serialize_sse(
                        "tool_status",
                        {
                            "person_id": person_id,
                            "opportunity_id": opportunity_id,
                            "stage": f"prepare_{target}_cached",
                        },
                    )
                    yield _serialize_sse(
                        "message_delta",
                        {
                            "person_id": person_id,
                            "opportunity_id": opportunity_id,
                            "channel": target,
                            "delta": content,
                        },
                    )
                    await asyncio.sleep(0)

            if PREPARE_TARGET_COVER_LETTER in outputs:
                upsert_current_artifact(
                    person_id=person_id,
                    opportunity_id=opportunity_id,
                    artifact_type="cover_letter",
                    content=outputs[PREPARE_TARGET_COVER_LETTER],
                )
            if PREPARE_TARGET_EXPERIENCE_SUMMARY in outputs:
                upsert_current_artifact(
                    person_id=person_id,
                    opportunity_id=opportunity_id,
                    artifact_type="experience_summary",
                    content=outputs[PREPARE_TARGET_EXPERIENCE_SUMMARY],
                )

            current_items = list_current_artifacts(person_id, opportunity_id)
            selected_artifact_types: set[str] = set()
            if PREPARE_TARGET_COVER_LETTER in targets:
                selected_artifact_types.add("cover_letter")
            if PREPARE_TARGET_EXPERIENCE_SUMMARY in targets:
                selected_artifact_types.add("experience_summary")
            filtered_artifacts = [
                item for item in current_items if item["artifact_type"] in selected_artifact_types
            ]

            updated = update_saved_opportunity(
                person_id=person_id,
                opportunity_id=opportunity_id,
                status="application_prepared",
                notes=opportunity.get("notes", ""),
            )
            final_item = updated or opportunity
            complete_payload = {
                "opportunity": final_item,
                "guidance_text": outputs.get(PREPARE_TARGET_GUIDANCE, ""),
                "artifacts": filtered_artifacts,
                "semantic_evidence": semantic_evidence,
                "served_from_cache": served_from_cache,
            }
            yield _serialize_sse("message_complete", complete_payload)
        except Exception as exc:  # pragma: no cover - network stream path
            yield _serialize_sse(
                "error",
                {
                    "person_id": person_id,
                    "opportunity_id": opportunity_id,
                    "detail": str(exc),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
