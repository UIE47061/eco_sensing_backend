from typing import Any

def process_trash_data(
    raw_weight: float | None,
    ai_raw_result: dict[str, Any] | None,
    sensor_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return estimated grams and the AI class; carbon remains a placeholder.

    grams = (raw - zero) * reference_grams / (reference_raw - zero).
    This provisional single-point calibration assumes a zero empty reading.
    """
    weight = None
    if raw_weight is not None:
        grams = (abs(raw_weight) * 10 / 4771.5)
        weight = round(max(0.0, grams), 2)

    class_name = (ai_raw_result or {}).get("class_name")
    trash_type = class_name.strip() if isinstance(class_name, str) else ""
    # confidence/class_name_zh remain in raw data; no confidence threshold yet.
    return {"weight": weight, "trash_type": trash_type or "unknown", "carbon": 0.0}
