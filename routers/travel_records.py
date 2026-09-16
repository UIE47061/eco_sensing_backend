from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from services.auth import get_current_employee
from services.crud import create_record, delete_record, get_record, list_records, update_record

router = APIRouter(prefix="/api", tags=["Travel Records"])


def dump_payload(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(exclude_none=True, mode="json")


# 差旅稽核確認送出的最終欄位（context v28 §4.1 [D2]）。
# co2e_kg／factor_id 一律由後端計算,不接受 client 指定(同 [A3]／[D5]「關鍵計算量 client 不直寫」)；
# 實際計算與 entry_source 標記為後續實作(§4.1 [D2](5) preview 端點),此處先鎖定輸入欄位形狀,
# 故 co2e_kg 於計算引擎完成前恆為 null。
# distance_km 正常情形亦由後端計算覆寫,僅 TDX／Maps 換算失敗(degraded)時作為人工填寫 fallback 採用。
class TravelRecordCreate(BaseModel):
    transport_mode: str = Field(
        ...,
        examples=["高鐵電子票"],
        description="票據類型：高鐵電子票／App乘車截圖／計程車紙本收據／其他",
    )
    travel_date: date
    origin: str | None = None
    destination: str | None = None
    amount: float = Field(..., examples=[700])
    distance_km: float | None = Field(
        default=None, description="僅 degraded fallback 時之人工填寫值"
    )
    receipt_id: str | None = None
    status: str = "pending"


class TravelRecordUpdate(BaseModel):
    transport_mode: str | None = None
    travel_date: date | None = None
    origin: str | None = None
    destination: str | None = None
    amount: float | None = None
    distance_km: float | None = None
    receipt_id: str | None = None
    status: str | None = None


@router.get("/travel-records")
def list_travel_records(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("travel_record", limit=limit, offset=offset)


@router.post("/travel-records", status_code=201)
def create_travel_record(
    payload: TravelRecordCreate,
    employee_id: UUID = Depends(get_current_employee),
) -> dict[str, Any]:
    data = dump_payload(payload)
    data["employee_id"] = str(employee_id)
    return create_record("travel_record", data)


@router.get("/travel-records/{record_id}")
def get_travel_record(record_id: UUID) -> dict[str, Any]:
    return get_record("travel_record", record_id)


@router.patch("/travel-records/{record_id}")
def update_travel_record(
    record_id: UUID,
    payload: TravelRecordUpdate,
    _: UUID = Depends(get_current_employee),
) -> dict[str, Any]:
    return update_record("travel_record", record_id, dump_payload(payload))


@router.delete("/travel-records/{record_id}")
def delete_travel_record(record_id: UUID) -> dict[str, Any]:
    return delete_record("travel_record", record_id)
