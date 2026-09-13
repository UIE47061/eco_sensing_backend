from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.trash import create_trash_session, upload_trash_raw_data

router = APIRouter(prefix="/trash", tags=["Trash"])


@router.post("/session")
def create_session() -> dict[str, object]:
    return create_trash_session()


class TrashRawDataRequest(BaseModel):
    raw_weight: float | None = Field(default=None, allow_inf_nan=False)
    image_url: str | None = None
    ai_raw_result: dict[str, Any] | None = None
    sensor_data: dict[str, Any] | None = None


@router.post("/{session_id}/raw-data")
def upload_raw_data(session_id: UUID, request: TrashRawDataRequest) -> dict[str, object]:
    return upload_trash_raw_data(session_id, request.model_dump(mode="json"))
