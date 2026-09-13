from fastapi import APIRouter

from services.trash import create_trash_session

router = APIRouter(prefix="/trash", tags=["Trash"])


@router.post("/session")
def create_session() -> dict[str, object]:
    return create_trash_session()
