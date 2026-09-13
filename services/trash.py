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


def _update_session(session_id: str, values: dict[str, Any]) -> None:
    data = request_supabase(
        "PATCH",
        "trash_sessions",
        params={"id": f"eq.{session_id}"},
        json=values,
        prefer="return=representation",
    )
    if not data:
        raise ValueError("Supabase updated no session")


def upload_trash_raw_data(session_id: UUID, raw_data: dict[str, Any]) -> dict[str, object]:
    session_id = str(session_id)
    try:
        sessions = request_supabase(
            "GET", "trash_sessions",
            params={"select": "id", "id": f"eq.{session_id}", "limit": 1},
        )
    except Exception as exc:
        logger.error("Trash session lookup failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to load trash session") from exc

    if not sessions:
        raise HTTPException(status_code=404, detail="Trash session not found")

    try:
        data = request_supabase(
            "POST", "trash_raw_data",
            json={**raw_data, "session_id": session_id},
            prefer="return=representation",
        )
        if not data:
            raise ValueError("Supabase returned no raw data")

        _update_session(session_id, {"status": "processing", "completed_at": None})
        logger.info("Processing trash session %s", session_id)
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
        _update_session(session_id, {
            **final_result,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.error("Trash session %s processing failed (%s)", session_id, type(exc).__name__)
        try:
            _update_session(session_id, {"status": "failed", "completed_at": None})
        except Exception as status_exc:
            logger.error(
                "Could not mark trash session %s failed (%s)",
                session_id, type(status_exc).__name__,
            )
        raise HTTPException(status_code=500, detail="Failed to process trash data") from exc

    logger.info("Completed trash session %s", session_id)
    return {"success": True, "session_id": session_id, "status": "completed", "result": final_result}
