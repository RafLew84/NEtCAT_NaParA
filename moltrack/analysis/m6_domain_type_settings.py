from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from math import isfinite
from numbers import Real
from typing import Literal


BondLengthToleranceMode = Literal["relative_percent", "absolute_nm"]

@dataclass(frozen=True)
class M6DomainTypeClassificationSettings:
    """Starting analytical defaults, not a validated TTMAPP preset."""

    orientation_tolerance_deg: float = 5.0
    bond_length_tolerance_mode: BondLengthToleranceMode = "relative_percent"
    bond_length_tolerance_value: float = 10.0
    minimum_observations_per_type: int = 3
    include_small_ordered_islands: bool = False
    exclude_bond_length_heterogeneity_qc: bool = True

    def __post_init__(self) -> None:
        orientation_tolerance_deg = _finite_number(
            self.orientation_tolerance_deg,
            "orientation_tolerance_deg",
        )
        if not 0.0 < orientation_tolerance_deg <= 30.0:
            raise ValueError(
                "orientation_tolerance_deg must be greater than 0 and at most 30."
            )

        mode = self.bond_length_tolerance_mode
        if not isinstance(mode, str):
            raise TypeError("bond_length_tolerance_mode must be a string.")
        if mode not in {"relative_percent", "absolute_nm"}:
            raise ValueError(
                "bond_length_tolerance_mode must be 'relative_percent' or "
                "'absolute_nm'."
            )

        bond_length_tolerance_value = _finite_number(
            self.bond_length_tolerance_value,
            "bond_length_tolerance_value",
        )
        if bond_length_tolerance_value <= 0.0:
            raise ValueError("bond_length_tolerance_value must be positive.")

        minimum_observations_per_type = self.minimum_observations_per_type
        if (
            isinstance(minimum_observations_per_type, bool)
            or not isinstance(minimum_observations_per_type, int)
        ):
            raise TypeError("minimum_observations_per_type must be an integer.")
        if minimum_observations_per_type <= 0:
            raise ValueError("minimum_observations_per_type must be positive.")

        for field_name in (
            "include_small_ordered_islands",
            "exclude_bond_length_heterogeneity_qc",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean.")

        object.__setattr__(
            self,
            "orientation_tolerance_deg",
            orientation_tolerance_deg,
        )
        object.__setattr__(
            self,
            "bond_length_tolerance_value",
            bond_length_tolerance_value,
        )

    def to_dict(self) -> dict[str, bool | int | float | str]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "M6DomainTypeClassificationSettings":
        if not isinstance(payload, Mapping):
            raise TypeError("M6 domain type settings payload must be a mapping.")
        if any(not isinstance(key, str) for key in payload):
            raise ValueError("M6 domain type setting field names must be strings.")
        field_names = tuple(field.name for field in fields(cls))
        payload_fields = set(payload)
        required = set(field_names)
        unknown = sorted(payload_fields - required)
        if unknown:
            raise ValueError(
                f"Unknown M6 domain type setting fields: {', '.join(unknown)}"
            )
        missing = sorted(required - payload_fields)
        if missing:
            raise ValueError(
                f"Missing M6 domain type setting fields: {', '.join(missing)}"
            )
        return cls(**{field_name: payload[field_name] for field_name in field_names})


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized
