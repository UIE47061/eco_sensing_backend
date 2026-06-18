from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class SensorReadingCreate(BaseModel):
    device_id: str = Field(..., examples=["sensor-001"])
    temperature: float | None = Field(default=None, examples=[26.5])
    humidity: float | None = Field(default=None, examples=[72.3])
    co2: float | None = Field(default=None, examples=[420.0])


class SensorReading(SensorReadingCreate):
    id: int


@router.get("", response_model=list[SensorReading])
def list_sensor_readings() -> list[SensorReading]:
    return [
        SensorReading(
            id=1,
            device_id="sensor-001",
            temperature=26.5,
            humidity=72.3,
            co2=420.0,
        )
    ]


@router.post("", response_model=SensorReading, status_code=201)
def create_sensor_reading(payload: SensorReadingCreate) -> SensorReading:
    return SensorReading(id=1, **payload.model_dump())
