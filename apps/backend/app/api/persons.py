from fastapi import APIRouter


router = APIRouter()


@router.get("")
def list_persons() -> dict[str, list[dict[str, str]]]:
    return {
        "items": [
            {"person_id": "p-001", "full_name": "Camila Torres"},
            {"person_id": "p-002", "full_name": "Mateo Rojas"},
        ]
    }


@router.post("")
def create_person() -> dict[str, str]:
    return {"message": "create person scaffold"}


@router.get("/{person_id}")
def get_person(person_id: str) -> dict[str, str]:
    return {"person_id": person_id}


@router.patch("/{person_id}")
def update_person(person_id: str) -> dict[str, str]:
    return {"message": f"update person scaffold {person_id}"}
