from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Literal, cast

from .backend_contract import NativeEvidenceKind


GeometryPolicyMode = Literal["fixed", "adaptive"]
GeometryParameter = bool | int | float | str


def geometry_parameters(
    values: tuple[tuple[str, GeometryParameter], ...],
) -> tuple[tuple[str, GeometryParameter], ...]:
    normalized = tuple(sorted(
        (text(name, "adaptive parameter name"), parameter(value))
        for name, value in values
    ))
    if len({name for name, _ in normalized}) != len(normalized):
        raise ValueError("Adaptive parameter names must be unique.")
    return normalized


def mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise TypeError(f"{name} must be a string-keyed mapping.")
    return MappingProxyType(dict(value))


def sequence(value: object) -> list[object] | tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("Expected a list or tuple.")
    return value


def text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text.")
    return value.strip()


def optional_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("description must be text.")
    return value.strip()


def number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    return float(value)


def positive_float(value: object, name: str) -> float:
    result = number(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive.")
    return result


def parameter(value: object) -> GeometryParameter:
    if not isinstance(value, (bool, int, float, str)):
        raise TypeError("Adaptive parameter values must be JSON scalars.")
    return value


def geometry_mode(value: object) -> GeometryPolicyMode:
    if value not in {"fixed", "adaptive"}:
        raise ValueError(f"Unsupported first-shell policy mode: {value!r}.")
    return cast(GeometryPolicyMode, value)


def native_evidence_kind(value: object) -> NativeEvidenceKind:
    if value not in {"m6_orientation_evidence_v1", "m3_m6_lattice_evidence_v1"}:
        raise ValueError(f"Unsupported native evidence kind: {value!r}.")
    return cast(NativeEvidenceKind, value)


def timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be a timezone-aware datetime.")
    return value.astimezone(timezone.utc)


def timestamp_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_timestamp(value: object, name: str) -> datetime:
    value_text = text(value, name)
    try:
        return timestamp(
            datetime.fromisoformat(value_text.replace("Z", "+00:00")),
            name,
        )
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp.") from error
