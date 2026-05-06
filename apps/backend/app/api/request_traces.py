from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.security import SessionData, require_operator_session
from app.services.person_store import get_person
from app.services.request_trace_store import list_request_traces


router = APIRouter()


class RequestTraceResponse(BaseModel):
    trace_id: str
    person_id: str
    opportunity_id: str
    run_id: str
    destination: str
    flow_key: str
    step_order: int
    tool_name: str
    stage: str
    status: str
    input_summary: str
    output_summary: str
    started_at: str
    finished_at: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    created_at: str


class RequestTraceListResponse(BaseModel):
    items: list[RequestTraceResponse]


@router.get("")
def list_person_request_traces(
    person_id: str,
    opportunity_id: str | None = Query(default=None),
    destination: str | None = Query(default=None),
    flow_key: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: SessionData = Depends(require_operator_session),
) -> RequestTraceListResponse:
    person = get_person(person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    normalized_opportunity_id = opportunity_id if isinstance(opportunity_id, str) else None
    normalized_destination = destination if isinstance(destination, str) else None
    normalized_flow_key = flow_key if isinstance(flow_key, str) else None
    normalized_run_id = run_id if isinstance(run_id, str) else None
    items = list_request_traces(
        person_id=person_id,
        opportunity_id=normalized_opportunity_id,
        destination=normalized_destination,
        flow_key=normalized_flow_key,
        run_id=normalized_run_id,
        limit=limit,
    )
    return RequestTraceListResponse(items=[RequestTraceResponse(**item) for item in items])
