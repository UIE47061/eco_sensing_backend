from typing import Any


def process_trash_data(
    raw_weight: float | None,
    ai_raw_result: dict[str, Any] | None,
    sensor_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Placeholder only: raw weight is not calibrated; carbon is not calculated."""
    return {"weight": raw_weight, "trash_type": "unknown", "carbon": 0.0}
