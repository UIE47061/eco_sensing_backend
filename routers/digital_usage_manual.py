from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from services.auth import get_current_employee
from services.crud import create_record, delete_record, find_one, get_record, update_record, list_records

router = APIRouter(prefix="/api", tags=["Digital Usage"])


def dump_payload(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(exclude_none=True, mode="json")


# App 手動上傳用紙量(共用印表機補位路徑,context 文件 v26 §4.4 [D16])。
# path_type/sensing_mode/employee_id 一律由後端固定寫入,不接受 client 指定。
class DigitalUsageCreate(BaseModel):
    usage_date: date
    print_pages: int = Field(..., ge=0, examples=[42])
    collected_at: datetime | None = None
    factor_id: UUID | None = None
    co2e_kg: float | None = None


class DigitalUsageUpdate(BaseModel):
    print_pages: int | None = None
    collected_at: datetime | None = None
    factor_id: UUID | None = None
    co2e_kg: float | None = None


@router.get("/digital-usages")
def list_digital_usages(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("digital_usage", limit=limit, offset=offset)


@router.post("/digital-usages", status_code=201)
def create_digital_usage(
    payload: DigitalUsageCreate,
    response: Response,
    employee_id: UUID = Depends(get_current_employee),
) -> dict[str, Any]:
    collected_at = payload.collected_at or datetime.now(timezone.utc)
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=timezone.utc)

    existing = find_one(
        "digital_usage",
        {
            "employee_id": f"eq.{employee_id}",
            "usage_date": f"eq.{payload.usage_date}",
            "path_type": "eq.printer",
            "sensing_mode": "eq.manual",
        },
    )

    data: dict[str, Any] = {
        "usage_date": payload.usage_date.isoformat(),
        "print_pages": payload.print_pages,
        "collected_at": collected_at.isoformat(),
    }
    if payload.factor_id is not None:
        data["factor_id"] = str(payload.factor_id)
    if payload.co2e_kg is not None:
        data["co2e_kg"] = payload.co2e_kg

    if existing is None:
        data["employee_id"] = str(employee_id)
        data["path_type"] = "printer"
        data["sensing_mode"] = "manual"
        return create_record("digital_usage", data)

    response.status_code = 200
    existing_collected_at = datetime.fromisoformat(existing["collected_at"])
    if collected_at <= existing_collected_at:
        # 較舊的重送封包,依 [D16]/[D14] 勝出規則不覆蓋既有較新值
        return existing

    return update_record("digital_usage", UUID(existing["id"]), data)


@router.get("/digital-usages/{record_id}")
def get_digital_usage(record_id: UUID) -> dict[str, Any]:
    return get_record("digital_usage", record_id)


@router.patch("/digital-usages/{record_id}")
def update_digital_usage(
    record_id: UUID,
    payload: DigitalUsageUpdate,
    _: UUID = Depends(get_current_employee),
) -> dict[str, Any]:
    return update_record("digital_usage", record_id, dump_payload(payload))


@router.delete("/digital-usages/{record_id}")
def delete_digital_usage(record_id: UUID) -> dict[str, Any]:
    return delete_record("digital_usage", record_id)
