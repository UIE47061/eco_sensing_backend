from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.sensors import create_sensor_reading, get_sensor_readings

router = APIRouter(prefix="/api/sensors", tags=["Sensors"])


class SensorReadingCreate(BaseModel):
    device_id: str = Field(..., examples=["sensor-001"])
    temperature: float | None = Field(default=None, examples=[26.5])
    humidity: float | None = Field(default=None, examples=[72.3])
    co2: float | None = Field(default=None, examples=[420.0])


class SensorReading(SensorReadingCreate):
    id: int


@router.get("", response_model=list[SensorReading])
def list_sensor_readings() -> list[SensorReading]:
    return get_sensor_readings()


@router.post("", response_model=SensorReading, status_code=201)
def add_sensor_reading(payload: SensorReadingCreate) -> SensorReading:
    return create_sensor_reading(payload)
