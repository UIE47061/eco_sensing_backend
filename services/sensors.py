from typing import Any


def get_sensor_readings() -> list[dict[str, str | float | int | None]]:
    return [
        {
            "id": 1,
            "device_id": "sensor-001",
            "temperature": 26.5,
            "humidity": 72.3,
            "co2": 420.0,
        }
    ]


def create_sensor_reading(payload: Any) -> dict[str, object]:
    return {"id": 1, **payload.model_dump()}
