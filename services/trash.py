import logging

from fastapi import HTTPException

from db.supabase import request_supabase

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
