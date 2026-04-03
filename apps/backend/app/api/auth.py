from fastapi import APIRouter


router = APIRouter()


@router.post("/login")
def login() -> dict[str, str]:
    return {"message": "login scaffold"}


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"message": "logout scaffold"}


@router.get("/session")
def session() -> dict[str, str]:
    return {"message": "session scaffold"}
