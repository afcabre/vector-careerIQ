from fastapi import APIRouter, Depends

from app.core.security import SessionData, require_operator_session


router = APIRouter()


@router.post("/from-search")
def create_from_search(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> dict[str, str]:
    return {"message": f"save search result scaffold for {person_id}"}


@router.post("/import-url")
def import_url(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> dict[str, str]:
    return {"message": f"import url scaffold for {person_id}"}


@router.post("/import-text")
def import_text(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> dict[str, str]:
    return {"message": f"import text scaffold for {person_id}"}


@router.get("")
def list_opportunities(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> dict[str, list[dict[str, str]]]:
    return {"items": [], "person_id": person_id}


@router.post("")
def create_opportunity(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> dict[str, str]:
    return {"message": f"create opportunity scaffold for {person_id}"}


@router.patch("/{opportunity_id}")
def update_opportunity(
    person_id: str,
    opportunity_id: str,
    _: SessionData = Depends(require_operator_session),
) -> dict[str, str]:
    return {
        "message": f"update opportunity scaffold {opportunity_id}",
        "person_id": person_id,
    }
