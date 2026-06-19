from typing import Any
from uuid import UUID

from fastapi import HTTPException

from db.supabase import request_supabase


def list_records(table: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return request_supabase(
        "GET",
        table,
        params={
            "select": "*",
            "order": "created_at.desc",
            "limit": limit,
            "offset": offset,
        },
    )


def get_record(table: str, record_id: UUID) -> dict[str, Any]:
    data = request_supabase(
        "GET",
        table,
        params={
            "select": "*",
            "id": f"eq.{record_id}",
            "limit": 1,
        },
    )
    if not data:
        raise HTTPException(status_code=404, detail=f"{table} record not found")
    return data[0]


def create_record(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = request_supabase(
        "POST",
        table,
        json=payload,
        prefer="return=representation",
    )
    return data[0]


def update_record(table: str, record_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    data = request_supabase(
        "PATCH",
        table,
        params={"id": f"eq.{record_id}"},
        json=payload,
        prefer="return=representation",
    )
    if not data:
        raise HTTPException(status_code=404, detail=f"{table} record not found")
    return data[0]


def delete_record(table: str, record_id: UUID) -> dict[str, Any]:
    data = request_supabase(
        "DELETE",
        table,
        params={"id": f"eq.{record_id}"},
        prefer="return=representation",
    )
    if not data:
        raise HTTPException(status_code=404, detail=f"{table} record not found")
    return data[0]
