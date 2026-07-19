from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import atan2, cos, degrees, fsum, hypot, radians, sin
from typing import Literal

from ._m6_domain_type_validation import (
    non_negative_float as _non_negative_float,
    normalize_m6_orientation as _normalize_m6_orientation,
    positive_float as _positive_float,
)
from .m6_domain_type_settings import (
    BondLengthToleranceMode,
    M6DomainTypeClassificationSettings,
)


BondLengthDifferenceUnit = Literal["percent", "nm"]


@dataclass(frozen=True)
class M6DomainTypeDistance:
    """Auditable orientation and bond-length distance under two tolerances."""

    orientation_difference_deg: float
    orientation_tolerance_deg: float
    bond_length_difference: float
    bond_length_tolerance_mode: BondLengthToleranceMode
    bond_length_tolerance_value: float

    def __post_init__(self) -> None:
        orientation_difference = _non_negative_float(
            self.orientation_difference_deg,
            "orientation_difference_deg",
        )
        if orientation_difference > 30.0:
            raise ValueError("orientation_difference_deg must not exceed 30.")
        orientation_tolerance = _positive_float(
            self.orientation_tolerance_deg,
            "orientation_tolerance_deg",
        )
        if orientation_tolerance > 30.0:
            raise ValueError("orientation_tolerance_deg must not exceed 30.")
        bond_length_difference = _non_negative_float(
            self.bond_length_difference,
            "bond_length_difference",
        )
        mode = _bond_length_tolerance_mode(self.bond_length_tolerance_mode)
        bond_length_tolerance = _positive_float(
            self.bond_length_tolerance_value,
            "bond_length_tolerance_value",
        )
        object.__setattr__(
            self,
            "orientation_difference_deg",
            orientation_difference,
        )
        object.__setattr__(
            self,
            "orientation_tolerance_deg",
            orientation_tolerance,
        )
        object.__setattr__(self, "bond_length_difference", bond_length_difference)
        object.__setattr__(self, "bond_length_tolerance_mode", mode)
        object.__setattr__(
            self,
            "bond_length_tolerance_value",
            bond_length_tolerance,
        )

    @property
    def bond_length_difference_unit(self) -> BondLengthDifferenceUnit:
        if self.bond_length_tolerance_mode == "relative_percent":
            return "percent"
        return "nm"

    @property
    def normalized_orientation_distance(self) -> float:
        return self.orientation_difference_deg / self.orientation_tolerance_deg

    @property
    def normalized_bond_length_distance(self) -> float:
        return self.bond_length_difference / self.bond_length_tolerance_value

    @property
    def normalized_distance(self) -> float:
        return max(
            self.normalized_orientation_distance,
            self.normalized_bond_length_distance,
        )

    @property
    def is_compatible(self) -> bool:
        return self.normalized_distance <= 1.0


def m6_orientation_distance_deg(first_deg: object, second_deg: object) -> float:
    """Return the shortest angular distance for an orientation modulo 60 degrees."""

    first = _normalize_m6_orientation(first_deg, "first_orientation_deg")
    second = _normalize_m6_orientation(second_deg, "second_orientation_deg")
    direct_distance = abs(first - second)
    return min(direct_distance, 60.0 - direct_distance)


def mean_m6_orientation_deg(orientations_deg: Iterable[object]) -> float:
    """Return the circular M6 mean obtained from cos(6 theta) and sin(6 theta)."""

    try:
        orientations = tuple(orientations_deg)
    except TypeError as exc:
        raise TypeError("orientations_deg must be an iterable of real numbers.") from exc
    if not orientations:
        raise ValueError("orientations_deg must contain at least one value.")
    normalized = tuple(
        _normalize_m6_orientation(value, "orientation_deg")
        for value in orientations
    )
    angles_rad = tuple(radians(6.0 * value) for value in normalized)
    cosine_sum = fsum(cos(value) for value in angles_rad)
    sine_sum = fsum(sin(value) for value in angles_rad)
    if hypot(cosine_sum, sine_sum) <= len(normalized) * 1e-12:
        raise ValueError("Mean M6 orientation is undefined for a zero resultant.")
    mean_deg = degrees(atan2(sine_sum, cosine_sum)) / 6.0
    return _normalize_m6_orientation(mean_deg, "mean_orientation_deg")


def m6_bond_length_difference(
    first_nm: object,
    second_nm: object,
    *,
    mode: BondLengthToleranceMode,
) -> float:
    """Return symmetric relative-percent or absolute-nanometre difference."""

    first = _positive_float(first_nm, "first_bond_length_nm")
    second = _positive_float(second_nm, "second_bond_length_nm")
    normalized_mode = _bond_length_tolerance_mode(mode)
    absolute_difference = abs(first - second)
    if normalized_mode == "relative_percent":
        return 200.0 * absolute_difference / (first + second)
    return absolute_difference


def compute_m6_domain_type_distance(
    first_orientation_deg: object,
    first_bond_length_nm: object,
    second_orientation_deg: object,
    second_bond_length_nm: object,
    *,
    settings: M6DomainTypeClassificationSettings,
) -> M6DomainTypeDistance:
    """Compare two domain observations using the configured independent tolerances."""

    if not isinstance(settings, M6DomainTypeClassificationSettings):
        raise TypeError("settings must be M6DomainTypeClassificationSettings.")
    return M6DomainTypeDistance(
        orientation_difference_deg=m6_orientation_distance_deg(
            first_orientation_deg,
            second_orientation_deg,
        ),
        orientation_tolerance_deg=settings.orientation_tolerance_deg,
        bond_length_difference=m6_bond_length_difference(
            first_bond_length_nm,
            second_bond_length_nm,
            mode=settings.bond_length_tolerance_mode,
        ),
        bond_length_tolerance_mode=settings.bond_length_tolerance_mode,
        bond_length_tolerance_value=settings.bond_length_tolerance_value,
    )


def _bond_length_tolerance_mode(value: object) -> BondLengthToleranceMode:
    if not isinstance(value, str):
        raise TypeError("bond-length tolerance mode must be a string.")
    if value not in {"relative_percent", "absolute_nm"}:
        raise ValueError("Unsupported bond-length tolerance mode.")
    return value
