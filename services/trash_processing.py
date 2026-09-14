from typing import Any

# Arbitrary DEMO value only, not a verified emissions factor.
# Units: kgCO2e per kg of waste. Replace with real factors after the demo.
DEMO_CARBON_FACTOR = 2.5


def process_trash_data(
    raw_weight: float | None,
    ai_raw_result: dict[str, Any] | None,
    sensor_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return estimated grams, the AI class, and synthetic demo carbon.

    grams = abs(raw_weight) * 10 / 4771.5 (assumes a zero empty reading).
    Demo carbon (kgCO2e) = weight (g) / 1000 * DEMO_CARBON_FACTOR.
    """
    weight = None
    if raw_weight is not None:
        grams = (abs(raw_weight) * 10 / 4771.5)
        weight = round(max(0.0, grams), 2)

    class_name = (ai_raw_result or {}).get("class_name")
    trash_type = class_name.strip() if isinstance(class_name, str) else ""
    carbon = round(weight / 1000 * DEMO_CARBON_FACTOR, 6) if weight is not None else 0.0
    # confidence/class_name_zh remain in raw data; no confidence threshold yet.
    return {"weight": weight, "trash_type": trash_type or "unknown", "carbon": carbon}
