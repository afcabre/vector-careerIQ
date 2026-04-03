from fastapi import APIRouter

from app.api import auth, chat, cv, opportunities, persons, search


router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(persons.router, prefix="/persons", tags=["persons"])
router.include_router(cv.router, prefix="/persons/{person_id}/cv", tags=["cv"])
router.include_router(chat.router, prefix="/persons/{person_id}/chat", tags=["chat"])
router.include_router(search.router, prefix="/persons/{person_id}/search", tags=["search"])
router.include_router(
    opportunities.router,
    prefix="/persons/{person_id}/opportunities",
    tags=["opportunities"],
)
