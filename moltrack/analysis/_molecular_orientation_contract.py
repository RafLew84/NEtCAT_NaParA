"""Shared strict-validation helpers for molecular-orientation contracts."""

from __future__ import annotations

from math import isfinite
from typing import Mapping


def require_exact_fields(
    payload: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{label} must be an object.")
    actual = set(payload)
    if actual == expected:
        return
    missing = sorted(expected.difference(actual))
    unknown = sorted(actual.difference(expected))
    details = []
    if missing:
        details.append("missing " + ", ".join(missing))
    if unknown:
        details.append("unknown " + ", ".join(unknown))
    raise ValueError(f"Invalid {label} fields: {'; '.join(details)}.")


def strict_string(
    value: object,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not allow_empty and not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value


def optional_strict_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return strict_string(value, field_name)


def non_empty_string(value: object, field_name: str) -> str:
    return strict_string(value, field_name).strip()


def optional_non_empty_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return non_empty_string(value, field_name)


def supported_string(
    value: object,
    supported: set[str],
    field_name: str,
) -> str:
    normalized = non_empty_string(value, field_name)
    if normalized not in supported:
        raise ValueError(f"Unsupported {field_name}: {normalized!r}.")
    return normalized


def sha256_digest(value: object, field_name: str) -> str:
    normalized = non_empty_string(value, field_name).casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{field_name} must be a SHA-256 hexadecimal digest.")
    return normalized


def strict_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def non_negative_integer(value: object, field_name: str) -> int:
    normalized = strict_integer(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return normalized


def strict_boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean.")
    return value


def strict_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be a finite number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def optional_strict_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return strict_float(value, field_name)


def strict_integer_tuple(
    value: object,
    length: int,
    field_name: str,
) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise TypeError(f"{field_name} must contain {length} integers.")
    return tuple(
        strict_integer(item, f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def strict_float_tuple(
    value: object,
    length: int,
    field_name: str,
) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise TypeError(f"{field_name} must contain {length} numbers.")
    return tuple(
        strict_float(item, f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def positive_shape(value: object, field_name: str) -> tuple[int, int]:
    dimensions = strict_integer_tuple(value, 2, field_name)
    if any(dimension <= 0 for dimension in dimensions):
        raise ValueError(f"{field_name} dimensions must be positive integers.")
    return dimensions[0], dimensions[1]


def bbox_xyxy(
    value: object,
    field_name: str,
) -> tuple[float, float, float, float]:
    normalized = strict_float_tuple(value, 4, field_name)
    if normalized[2] <= normalized[0] or normalized[3] <= normalized[1]:
        raise ValueError(f"{field_name} must have positive width and height.")
    return normalized
