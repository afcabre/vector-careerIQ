from fastapi import APIRouter

from app.api import auth, chat, opportunities, persons


router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(persons.router, prefix="/persons", tags=["persons"])
router.include_router(chat.router, prefix="/persons/{person_id}/chat", tags=["chat"])
router.include_router(
    opportunities.router,
    prefix="/persons/{person_id}/opportunities",
    tags=["opportunities"],
)
