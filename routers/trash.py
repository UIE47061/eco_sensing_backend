from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.trash import create_trash_session, upload_trash_raw_data, update_trash_session_status

router = APIRouter(prefix="/trash", tags=["Trash"])


class TrashSessionStatusRequest(BaseModel):
    status: Literal["preparing", "ready", "recognizing", "uploading", "failed"]


class TrashSessionStatusResponse(BaseModel):
    success: Literal[True]
    session_id: UUID
    status: Literal["preparing", "ready", "recognizing", "uploading", "failed"]


@router.patch("/{session_id}/status", response_model=TrashSessionStatusResponse)
def patch_status(session_id: UUID, request: TrashSessionStatusRequest) -> dict[str, object]:
    return update_trash_session_status(session_id, request.status)


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
