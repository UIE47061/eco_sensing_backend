from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from services.auth import get_current_employee
from services.crud import (
    create_record,
    delete_record,
    find_one,
    get_record,
    list_records,
    update_record,
)

router = APIRouter(prefix="/api", tags=["Eco Records"])


def dump_payload(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(exclude_none=True, mode="json")


class EmissionFactorCreate(BaseModel):
    category: str = Field(..., examples=["travel"])
    key: str = Field(..., examples=["mrt"])
    value: float = Field(..., examples=[0.035])
    unit: str = Field(..., examples=["kgCO2e/km"])
    source: str | None = Field(default=None, examples=["EPA"])
    valid_from: date


class EmissionFactorUpdate(BaseModel):
    category: str | None = None
    key: str | None = None
    value: float | None = None
    unit: str | None = None
    source: str | None = None
    valid_from: date | None = None


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


class DeviceCreate(BaseModel):
    type: str = Field(..., examples=["camera"])
    status: str = Field(default="active", examples=["active"])
    last_seen: datetime | None = None


class DeviceUpdate(BaseModel):
    type: str | None = None
    status: str | None = None
    last_seen: datetime | None = None


class ElevatorTripCreate(BaseModel):
    factor_id: UUID | None = None
    ts_in: datetime
    ts_out: datetime | None = None
    floor_in: int
    floor_out: int
    co2e_kg: float | None = None


class ElevatorTripUpdate(BaseModel):
    factor_id: UUID | None = None
    ts_in: datetime | None = None
    ts_out: datetime | None = None
    floor_in: int | None = None
    floor_out: int | None = None
    co2e_kg: float | None = None


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


@router.get("/emission-factors")
def list_emission_factors(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("emission_factor", limit=limit, offset=offset)


@router.post("/emission-factors", status_code=201)
def create_emission_factor(payload: EmissionFactorCreate) -> dict[str, Any]:
    return create_record("emission_factor", dump_payload(payload))


@router.get("/emission-factors/{record_id}")
def get_emission_factor(record_id: UUID) -> dict[str, Any]:
    return get_record("emission_factor", record_id)


@router.patch("/emission-factors/{record_id}")
def update_emission_factor(record_id: UUID, payload: EmissionFactorUpdate) -> dict[str, Any]:
    return update_record("emission_factor", record_id, dump_payload(payload))


@router.delete("/emission-factors/{record_id}")
def delete_emission_factor(record_id: UUID) -> dict[str, Any]:
    return delete_record("emission_factor", record_id)


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


@router.get("/devices")
def list_devices(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("device", limit=limit, offset=offset)


@router.post("/devices", status_code=201)
def create_device(payload: DeviceCreate) -> dict[str, Any]:
    return create_record("device", dump_payload(payload))


@router.get("/devices/{record_id}")
def get_device(record_id: UUID) -> dict[str, Any]:
    return get_record("device", record_id)


@router.patch("/devices/{record_id}")
def update_device(record_id: UUID, payload: DeviceUpdate) -> dict[str, Any]:
    return update_record("device", record_id, dump_payload(payload))


@router.delete("/devices/{record_id}")
def delete_device(record_id: UUID) -> dict[str, Any]:
    return delete_record("device", record_id)


@router.get("/elevator-trips")
def list_elevator_trips(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("elevator_trip", limit=limit, offset=offset)


@router.post("/elevator-trips", status_code=201)
def create_elevator_trip(
    payload: ElevatorTripCreate,
    employee_id: UUID = Depends(get_current_employee),
) -> dict[str, Any]:
    data = dump_payload(payload)
    data["employee_id"] = str(employee_id)
    return create_record("elevator_trip", data)


@router.get("/elevator-trips/{record_id}")
def get_elevator_trip(record_id: UUID) -> dict[str, Any]:
    return get_record("elevator_trip", record_id)


@router.patch("/elevator-trips/{record_id}")
def update_elevator_trip(
    record_id: UUID,
    payload: ElevatorTripUpdate,
    _: UUID = Depends(get_current_employee),
) -> dict[str, Any]:
    return update_record("elevator_trip", record_id, dump_payload(payload))


@router.delete("/elevator-trips/{record_id}")
def delete_elevator_trip(record_id: UUID) -> dict[str, Any]:
    return delete_record("elevator_trip", record_id)


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
