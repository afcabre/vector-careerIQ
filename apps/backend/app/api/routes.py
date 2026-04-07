from fastapi import APIRouter

from app.api import (
    auth,
    chat,
    cv,
    opportunities,
    persons,
    prompt_admin,
    request_traces,
    search,
    search_provider_admin,
)


router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(persons.router, prefix="/persons", tags=["persons"])
router.include_router(cv.router, prefix="/persons/{person_id}/cv", tags=["cv"])
router.include_router(chat.router, prefix="/persons/{person_id}/chat", tags=["chat"])
router.include_router(search.router, prefix="/persons/{person_id}/search", tags=["search"])
router.include_router(
    request_traces.router,
    prefix="/persons/{person_id}/request-traces",
    tags=["request-traces"],
)
router.include_router(prompt_admin.router, prefix="/admin/prompt-configs", tags=["prompt-admin"])
router.include_router(
    search_provider_admin.router,
    prefix="/admin/search-providers",
    tags=["search-provider-admin"],
)
router.include_router(
    opportunities.router,
    prefix="/persons/{person_id}/opportunities",
    tags=["opportunities"],
)
