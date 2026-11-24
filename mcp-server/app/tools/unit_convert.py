"""Unit conversion tool — pure computation, no external dependencies or secrets."""

import json

# (from_unit, to_unit) -> factor to multiply `from` value by to get `to` value.
# Length base: meter; Mass base: gram.
_LENGTH_TO_METER = {
    "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
    "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
}
_MASS_TO_GRAM = {
    "mg": 0.001, "g": 1.0, "kg": 1000.0, "t": 1_000_000.0,
    "oz": 28.349523125, "lb": 453.59237,
}

CONVERT_SCHEMA = {
    "name": "unit_convert",
    "description": (
        "Convert a numeric value between units of length (mm/cm/m/km/in/ft/yd/mi) "
        "or mass (mg/g/kg/t/oz/lb), or convert temperature between C/F/K. "
        "Use when a question asks to convert a measurement from one unit to another."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "value": {
                "type": "number",
                "description": "The numeric value to convert.",
            },
            "from_unit": {
                "type": "string",
                "description": "Source unit symbol (e.g. m, kg, C).",
            },
            "to_unit": {
                "type": "string",
                "description": "Target unit symbol (e.g. cm, g, F).",
            },
        },
        "required": ["value", "from_unit", "to_unit"],
    },
}


def _convert_temp(value: float, src: str, dst: str) -> float:
    celsius = {"C": value, "F": (value - 32) * 5 / 9, "K": value - 273.15}.get(src.upper())
    if celsius is None:
        raise ValueError(f"unsupported temperature unit: {src}")
    return {"C": celsius, "F": celsius * 9 / 5 + 32, "K": celsius + 273.15}[dst.upper()]


def unit_convert(value: float = 0, from_unit: str = "", to_unit: str = "") -> str:
    """Convert value between units and return a JSON string with the result."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return json.dumps({"error": "value must be a number"}, ensure_ascii=False)
    src = (from_unit or "").strip().lower()
    dst = (to_unit or "").strip().lower()
    if not src or not dst:
        return json.dumps({"error": "from_unit and to_unit are required"}, ensure_ascii=False)

    try:
        if src.upper() in ("C", "F", "K") and dst.upper() in ("C", "F", "K"):
            result = _convert_temp(float(value), src, dst)
        elif src in _LENGTH_TO_METER and dst in _LENGTH_TO_METER:
            result = float(value) * _LENGTH_TO_METER[src] / _LENGTH_TO_METER[dst]
        elif src in _MASS_TO_GRAM and dst in _MASS_TO_GRAM:
            result = float(value) * _MASS_TO_GRAM[src] / _MASS_TO_GRAM[dst]
        else:
            return json.dumps(
                {"error": f"cannot convert between incompatible units: {from_unit} -> {to_unit}"},
                ensure_ascii=False,
            )
    except (KeyError, ValueError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return json.dumps(
        {"value": float(value), "from_unit": from_unit, "to_unit": to_unit, "result": result},
        ensure_ascii=False,
    )
