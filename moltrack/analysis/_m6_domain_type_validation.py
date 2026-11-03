from __future__ import annotations

from math import isclose, isfinite
from numbers import Real


def non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value.strip()


def non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def positive_int(value: object, field_name: str) -> int:
    normalized = non_negative_int(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def positive_float(value: object, field_name: str) -> float:
    normalized = finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def non_negative_float(value: object, field_name: str) -> float:
    normalized = finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def unit_float(value: object, field_name: str) -> float:
    normalized = finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1.")
    return normalized


def optional_unit_float(value: object, field_name: str) -> float | None:
    return None if value is None else unit_float(value, field_name)


def optional_non_negative_float(value: object, field_name: str) -> float | None:
    return None if value is None else non_negative_float(value, field_name)


def normalize_m6_orientation(
    value: object,
    field_name: str = "orientation_deg",
) -> float:
    orientation = finite_float(value, field_name) % 60.0
    if isclose(orientation, 0.0, abs_tol=1e-12) or isclose(
        orientation,
        60.0,
        abs_tol=1e-12,
    ):
        return 0.0
    return orientation
