from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.crud import (
    create_record,
    delete_record,
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


class TravelRecordCreate(BaseModel):
    employee_id: UUID
    factor_id: UUID | None = None
    track_type: str | None = Field(default=None, examples=["manual"])
    transport_mode: str = Field(..., examples=["mrt"])
    origin: str | None = None
    destination: str | None = None
    travel_date: date
    amount: float | None = None
    distance_km: float | None = None
    co2e_kg: float | None = None
    receipt_id: str | None = None
    status: str = "pending"


class TravelRecordUpdate(BaseModel):
    employee_id: UUID | None = None
    factor_id: UUID | None = None
    track_type: str | None = None
    transport_mode: str | None = None
    origin: str | None = None
    destination: str | None = None
    travel_date: date | None = None
    amount: float | None = None
    distance_km: float | None = None
    co2e_kg: float | None = None
    receipt_id: str | None = None
    status: str | None = None


class WasteBinCreate(BaseModel):
    qr_code: str = Field(..., examples=["BIN-001"])
    location: str | None = Field(default=None, examples=["1F pantry"])


class WasteBinUpdate(BaseModel):
    qr_code: str | None = None
    location: str | None = None


class DeviceCreate(BaseModel):
    type: str = Field(..., examples=["camera"])
    status: str = Field(default="active", examples=["active"])
    last_seen: datetime | None = None


class DeviceUpdate(BaseModel):
    type: str | None = None
    status: str | None = None
    last_seen: datetime | None = None


class WasteSessionCreate(BaseModel):
    employee_id: UUID
    bin_id: UUID
    scan_at: datetime | None = None
    confirm_at: datetime | None = None
    status: str = "open"
    lock_held: bool = False


class WasteSessionUpdate(BaseModel):
    employee_id: UUID | None = None
    bin_id: UUID | None = None
    scan_at: datetime | None = None
    confirm_at: datetime | None = None
    status: str | None = None
    lock_held: bool | None = None


class WasteEventCreate(BaseModel):
    bin_id: UUID
    session_id: UUID | None = None
    device_id: UUID | None = None
    factor_id: UUID | None = None
    event_at: datetime | None = None
    waste_type: str = Field(..., examples=["paper"])
    confidence: float | None = Field(default=None, examples=[0.98])
    weight_g: float | None = Field(default=None, examples=[120.5])
    co2e_kg: float | None = None


class WasteEventUpdate(BaseModel):
    bin_id: UUID | None = None
    session_id: UUID | None = None
    device_id: UUID | None = None
    factor_id: UUID | None = None
    event_at: datetime | None = None
    waste_type: str | None = None
    confidence: float | None = None
    weight_g: float | None = None
    co2e_kg: float | None = None


class ElevatorTripCreate(BaseModel):
    employee_id: UUID
    factor_id: UUID | None = None
    ts_in: datetime
    ts_out: datetime | None = None
    floor_in: int
    floor_out: int
    co2e_kg: float | None = None


class ElevatorTripUpdate(BaseModel):
    employee_id: UUID | None = None
    factor_id: UUID | None = None
    ts_in: datetime | None = None
    ts_out: datetime | None = None
    floor_in: int | None = None
    floor_out: int | None = None
    co2e_kg: float | None = None


class DigitalUsageCreate(BaseModel):
    employee_id: UUID
    factor_id: UUID | None = None
    usage_date: date
    pc_active_hours: float = 0
    print_pages: int = 0
    drive_usage_gb: float = 0
    co2e_kg: float | None = None


class DigitalUsageUpdate(BaseModel):
    employee_id: UUID | None = None
    factor_id: UUID | None = None
    usage_date: date | None = None
    pc_active_hours: float | None = None
    print_pages: int | None = None
    drive_usage_gb: float | None = None
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
def create_travel_record(payload: TravelRecordCreate) -> dict[str, Any]:
    return create_record("travel_record", dump_payload(payload))


@router.get("/travel-records/{record_id}")
def get_travel_record(record_id: UUID) -> dict[str, Any]:
    return get_record("travel_record", record_id)


@router.patch("/travel-records/{record_id}")
def update_travel_record(record_id: UUID, payload: TravelRecordUpdate) -> dict[str, Any]:
    return update_record("travel_record", record_id, dump_payload(payload))


@router.delete("/travel-records/{record_id}")
def delete_travel_record(record_id: UUID) -> dict[str, Any]:
    return delete_record("travel_record", record_id)


@router.get("/waste-bins")
def list_waste_bins(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("waste_bin", limit=limit, offset=offset)


@router.post("/waste-bins", status_code=201)
def create_waste_bin(payload: WasteBinCreate) -> dict[str, Any]:
    return create_record("waste_bin", dump_payload(payload))


@router.get("/waste-bins/{record_id}")
def get_waste_bin(record_id: UUID) -> dict[str, Any]:
    return get_record("waste_bin", record_id)


@router.patch("/waste-bins/{record_id}")
def update_waste_bin(record_id: UUID, payload: WasteBinUpdate) -> dict[str, Any]:
    return update_record("waste_bin", record_id, dump_payload(payload))


@router.delete("/waste-bins/{record_id}")
def delete_waste_bin(record_id: UUID) -> dict[str, Any]:
    return delete_record("waste_bin", record_id)


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


@router.get("/waste-sessions")
def list_waste_sessions(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("waste_session", limit=limit, offset=offset)


@router.post("/waste-sessions", status_code=201)
def create_waste_session(payload: WasteSessionCreate) -> dict[str, Any]:
    return create_record("waste_session", dump_payload(payload))


@router.get("/waste-sessions/{record_id}")
def get_waste_session(record_id: UUID) -> dict[str, Any]:
    return get_record("waste_session", record_id)


@router.patch("/waste-sessions/{record_id}")
def update_waste_session(record_id: UUID, payload: WasteSessionUpdate) -> dict[str, Any]:
    return update_record("waste_session", record_id, dump_payload(payload))


@router.delete("/waste-sessions/{record_id}")
def delete_waste_session(record_id: UUID) -> dict[str, Any]:
    return delete_record("waste_session", record_id)


@router.get("/waste-events")
def list_waste_events(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("waste_event", limit=limit, offset=offset)


@router.post("/waste-events", status_code=201)
def create_waste_event(payload: WasteEventCreate) -> dict[str, Any]:
    return create_record("waste_event", dump_payload(payload))


@router.get("/waste-events/{record_id}")
def get_waste_event(record_id: UUID) -> dict[str, Any]:
    return get_record("waste_event", record_id)


@router.patch("/waste-events/{record_id}")
def update_waste_event(record_id: UUID, payload: WasteEventUpdate) -> dict[str, Any]:
    return update_record("waste_event", record_id, dump_payload(payload))


@router.delete("/waste-events/{record_id}")
def delete_waste_event(record_id: UUID) -> dict[str, Any]:
    return delete_record("waste_event", record_id)


@router.get("/elevator-trips")
def list_elevator_trips(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("elevator_trip", limit=limit, offset=offset)


@router.post("/elevator-trips", status_code=201)
def create_elevator_trip(payload: ElevatorTripCreate) -> dict[str, Any]:
    return create_record("elevator_trip", dump_payload(payload))


@router.get("/elevator-trips/{record_id}")
def get_elevator_trip(record_id: UUID) -> dict[str, Any]:
    return get_record("elevator_trip", record_id)


@router.patch("/elevator-trips/{record_id}")
def update_elevator_trip(record_id: UUID, payload: ElevatorTripUpdate) -> dict[str, Any]:
    return update_record("elevator_trip", record_id, dump_payload(payload))


@router.delete("/elevator-trips/{record_id}")
def delete_elevator_trip(record_id: UUID) -> dict[str, Any]:
    return delete_record("elevator_trip", record_id)


@router.get("/digital-usages")
def list_digital_usages(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return list_records("digital_usage", limit=limit, offset=offset)


@router.post("/digital-usages", status_code=201)
def create_digital_usage(payload: DigitalUsageCreate) -> dict[str, Any]:
    return create_record("digital_usage", dump_payload(payload))


@router.get("/digital-usages/{record_id}")
def get_digital_usage(record_id: UUID) -> dict[str, Any]:
    return get_record("digital_usage", record_id)


@router.patch("/digital-usages/{record_id}")
def update_digital_usage(record_id: UUID, payload: DigitalUsageUpdate) -> dict[str, Any]:
    return update_record("digital_usage", record_id, dump_payload(payload))


@router.delete("/digital-usages/{record_id}")
def delete_digital_usage(record_id: UUID) -> dict[str, Any]:
    return delete_record("digital_usage", record_id)
