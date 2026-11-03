"""Unit-aware finite quantities shared by the text-based input formats."""

import math
import re

_NUMBER_UNIT = re.compile(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)")
LENGTH_NM = {"m": 1e9, "mm": 1e6, "um": 1e3, "µm": 1e3, "μm": 1e3,
              "nm": 1.0, "pm": 1e-3, "Å": 0.1, "angstrom": 0.1}
VOLTAGE_V = {"V": 1.0, "mV": 1e-3, "uV": 1e-6, "µV": 1e-6, "μV": 1e-6}
CURRENT_A = {"A": 1.0, "mA": 1e-3, "uA": 1e-6, "µA": 1e-6, "μA": 1e-6,
            "nA": 1e-9, "pA": 1e-12}


def parse_quantity(text: str) -> tuple[float, str] | None:
    match = _NUMBER_UNIT.fullmatch(text.strip())
    if match is None:
        return None
    value = float(match[1])
    return (value, match[2]) if math.isfinite(value) else None


def scaled_quantity(text: str, factors: dict[str, float], *, positive: bool = False) -> float | None:
    quantity = parse_quantity(text)
    if quantity is None or quantity[1] not in factors:
        return None
    value = quantity[0] * factors[quantity[1]]
    if not math.isfinite(value) or (positive and value <= 0):
        return None
    return value

