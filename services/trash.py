import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from db.supabase import request_supabase
from services.trash_processing import process_trash_data

logger = logging.getLogger(__name__)

DEMO_BIN_ID = "550f05c2-438c-4dde-8b31-bbbb4f334b64"


def create_trash_session() -> dict[str, object]:
    bin_id = DEMO_BIN_ID

    try:
        bins = request_supabase(
            "GET", "bins", params={"select": "id", "id": f"eq.{bin_id}", "limit": 1}
        )
    except Exception as exc:
        logger.error("Trash session bin lookup failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to create trash session") from exc

    if not bins:
        logger.error("DEMO_BIN_ID does not reference an existing bin")
        raise HTTPException(
            status_code=500, detail="DEMO_BIN_ID does not reference an existing bin"
        )

    try:
        data = request_supabase(
            "POST",
            "trash_sessions",
            json={"bin_id": bin_id, "status": "waiting"},
            prefer="return=representation",
        )
        if not data:
            raise ValueError("Supabase returned no session")
        session = data[0]
        result = {
            "success": True,
            "session_id": session["id"],
            "bin_id": session["bin_id"],
            "status": session["status"],
        }
    except Exception as exc:
        # Avoid exposing database details or credentials in responses and logs.
        logger.error("Create trash session failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to create trash session") from exc

    logger.info("Created trash session %s", session["id"])
    return result


STATUS_TRANSITIONS = {
    "waiting": {"preparing", "failed"},
    "preparing": {"ready", "failed"},
    "ready": {"recognizing", "failed"},
    "recognizing": {"uploading", "failed"},
    "uploading": {"calculating", "failed"},
    "calculating": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}
PI_STATUSES = {"preparing", "ready", "recognizing", "uploading", "failed"}


def validate_status_transition(current_status: str, target_status: str) -> None:
    if target_status not in STATUS_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid trash session status transition: {current_status} -> {target_status}",
        )


def _get_session(session_id: str) -> dict[str, Any]:
    try:
        sessions = request_supabase(
            "GET", "trash_sessions",
            params={"select": "id,status", "id": f"eq.{session_id}", "limit": 1},
        )
    except Exception as exc:
        logger.exception("session_id=%s stage=lookup exception=%s", session_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to load trash session") from exc
    if not sessions:
        raise HTTPException(status_code=404, detail="Trash session not found")
    return sessions[0]


def _transition_session(
    session_id: str, current_status: str, target_status: str,
    values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_status_transition(current_status, target_status)
    # Compare-and-set prevents a stale request from overwriting a newer status.
    data = request_supabase(
        "PATCH", "trash_sessions",
        params={"id": f"eq.{session_id}", "status": f"eq.{current_status}"},
        json={**(values or {}), "status": target_status},
        prefer="return=representation",
    )
    if not data:
        raise HTTPException(status_code=409, detail="Trash session status changed; reload before retrying")
    logger.info("session_id=%s status=%s -> %s", session_id, current_status, target_status)
    return data[0]


def update_trash_session_status(session_id: UUID, target_status: str) -> dict[str, object]:
    session_id = str(session_id)
    if target_status not in PI_STATUSES:
        raise HTTPException(status_code=422, detail="Status is not writable by Raspberry Pi")
    session = _get_session(session_id)
    try:
        updated = _transition_session(session_id, session["status"], target_status)
    except HTTPException as exc:
        if exc.status_code == 409:
            raise
        logger.exception("session_id=%s stage=patch_status exception=%s", session_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to update trash session status") from exc
    except Exception as exc:
        logger.exception("session_id=%s stage=patch_status exception=%s", session_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to update trash session status") from exc
    return {"success": True, "session_id": session_id, "status": updated["status"]}


def upload_trash_raw_data(session_id: UUID, raw_data: dict[str, Any]) -> dict[str, object]:
    session_id = str(session_id)
    session = _get_session(session_id)
    validate_status_transition(session["status"], "calculating")
    stage = "insert_raw_data"
    current_status = "uploading"
    try:
        data = request_supabase(
            "POST", "trash_raw_data",
            json={**raw_data, "session_id": session_id},
            prefer="return=representation",
        )
        if not data:
            raise ValueError("Supabase returned no raw data")

        stage = "enter_calculating"
        _transition_session(session_id, "uploading", "calculating", {"completed_at": None})
        current_status = "calculating"
        stage = "process_trash_data"
        result = process_trash_data(
            raw_weight=raw_data.get("raw_weight"),
            ai_raw_result=raw_data.get("ai_raw_result"),
            sensor_data=raw_data.get("sensor_data"),
        )
        final_result = {
            "trash_type": result["trash_type"],
            "weight": result["weight"],
            "carbon": result["carbon"],
        }
        stage = "complete_session"
        _transition_session(session_id, "calculating", "completed", {
            **final_result,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.exception("session_id=%s stage=%s exception=%s", session_id, stage, type(exc).__name__)
        # A concurrent request owns the newer state. Do not mark its work failed.
        if isinstance(exc, HTTPException) and exc.status_code == 409:
            raise
        try:
            _transition_session(session_id, current_status, "failed", {"completed_at": None})
        except Exception as status_exc:
            logger.exception(
                "session_id=%s stage=mark_failed source_stage=%s exception=%s",
                session_id, stage, type(status_exc).__name__,
            )
        raise HTTPException(status_code=500, detail="Failed to process trash data") from exc

    return {"success": True, "session_id": session_id, "status": "completed", "result": final_result}
