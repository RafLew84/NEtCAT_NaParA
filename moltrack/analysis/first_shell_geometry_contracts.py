"""Small shared value objects for first-shell geometry calibration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal


FirstShellSymmetry = Literal["trifold", "sixfold"]


@dataclass(frozen=True, order=True)
class FirstShellStratumIdentity:
    """One measurement-group and symmetry stratum in Calibration."""

    measurement_group_id: str
    symmetry_class: FirstShellSymmetry

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "measurement_group_id",
            _text(self.measurement_group_id, "measurement_group_id"),
        )
        object.__setattr__(
            self,
            "symmetry_class",
            first_shell_symmetry(self.symmetry_class),
        )


@dataclass(frozen=True)
class FirstShellGraphSettings:
    """Graph-construction inputs kept separate from classification sweeps."""

    duplicate_max_distance_nm: float
    duplicate_detection_enabled: bool = True
    geometry_absolute_tolerance_nm: float = 1e-12
    geometry_relative_tolerance: float = 1e-10

    def __post_init__(self) -> None:
        if not isinstance(self.duplicate_detection_enabled, bool):
            raise TypeError("duplicate_detection_enabled must be boolean.")
        duplicate_distance = _positive_float(
            self.duplicate_max_distance_nm,
            "duplicate_max_distance_nm",
        )
        absolute_tolerance = _positive_float(
            self.geometry_absolute_tolerance_nm,
            "geometry_absolute_tolerance_nm",
        )
        if duplicate_distance <= absolute_tolerance:
            raise ValueError(
                "duplicate_max_distance_nm must exceed geometry_absolute_tolerance_nm."
            )
        object.__setattr__(self, "duplicate_max_distance_nm", duplicate_distance)
        object.__setattr__(
            self,
            "geometry_absolute_tolerance_nm",
            absolute_tolerance,
        )
        object.__setattr__(
            self,
            "geometry_relative_tolerance",
            _positive_float(
                self.geometry_relative_tolerance,
                "geometry_relative_tolerance",
            ),
        )


def first_shell_symmetry(value: object) -> FirstShellSymmetry:
    if value not in {"trifold", "sixfold"}:
        raise ValueError(f"Unsupported first-shell symmetry: {value!r}.")
    return value  # type: ignore[return-value]


def _positive_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive and finite.")
    return normalized


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "FirstShellGraphSettings",
    "FirstShellStratumIdentity",
    "FirstShellSymmetry",
    "first_shell_symmetry",
]
