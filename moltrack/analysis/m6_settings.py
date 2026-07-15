from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from math import isfinite
from typing import Literal


_FLOAT_FIELDS = (
    "duplicate_max_distance_nm",
    "first_shell_r_min_nm",
    "first_shell_r_max_nm",
    "geometry_absolute_tolerance_nm",
    "geometry_relative_tolerance",
    "domain_conflict_margin",
    "domain_merge_angle_tolerance_deg",
    "footprint_support_radius_nm",
    "q_seed",
    "q_grow",
    "seed_angle_tolerance_deg",
    "grow_angle_tolerance_deg",
    "gr_bin_width_nm",
    "gr_max_nm",
    "gr_min_expected_pair_exposure",
    "gr_smoothing_width",
    "gr_peak_prominence",
    "domain_bond_length_robust_cv_qc_threshold",
    "orientation_zero_tolerance",
)

_INTEGER_FIELDS = (
    "symmetry_m",
    "min_neighbors_for_local_order",
    "min_neighbors_for_seed",
    "min_ordered_component_size",
    "min_seed_size",
    "min_domain_size",
    "gr_min_contributing_frames",
    "min_bonds_for_domain_length_stats",
)

_TOKEN_FIELDS = (
    "bond_weighting",
    "duplicate_policy",
    "duplicate_chain_policy",
    "geometry_collision_policy",
    "delaunay_degeneracy_policy",
    "gr_smoothing_method",
)

_FIXED_VALUES = {
    "symmetry_m": 6,
    "bond_weighting": "uniform",
    "duplicate_policy": "best_quality_representative",
    "duplicate_chain_policy": "deterministic_complete_linkage",
    "geometry_collision_policy": "always_deduplicate_with_tolerance",
    "delaunay_degeneracy_policy": "exclude_ambiguous_edges",
}

_POSITIVE_DISTANCE_FIELDS = (
    "duplicate_max_distance_nm",
    "first_shell_r_min_nm",
    "first_shell_r_max_nm",
    "geometry_absolute_tolerance_nm",
    "geometry_relative_tolerance",
    "footprint_support_radius_nm",
)

_POSITIVE_INTEGER_FIELDS = tuple(
    field_name for field_name in _INTEGER_FIELDS if field_name != "symmetry_m"
)

_POSITIVE_GR_FIELDS = (
    "gr_bin_width_nm",
    "gr_max_nm",
    "gr_min_expected_pair_exposure",
    "gr_smoothing_width",
)


@dataclass(frozen=True)
class MolecularM6OrientationAnalysisSettings:
    """Immutable settings shared by every M6 orientation analysis surface."""

    duplicate_detection_enabled: bool = True
    duplicate_max_distance_nm: float = 0.5
    first_shell_r_min_nm: float = 1.0
    first_shell_r_max_nm: float = 2.6
    symmetry_m: Literal[6] = 6
    bond_weighting: Literal["uniform"] = "uniform"
    duplicate_policy: Literal["best_quality_representative"] = "best_quality_representative"
    duplicate_chain_policy: Literal["deterministic_complete_linkage"] = "deterministic_complete_linkage"
    geometry_collision_policy: Literal[
        "always_deduplicate_with_tolerance"
    ] = "always_deduplicate_with_tolerance"
    geometry_absolute_tolerance_nm: float = 1e-12
    geometry_relative_tolerance: float = 1e-10
    min_neighbors_for_local_order: int = 3
    min_neighbors_for_seed: int = 5
    min_ordered_component_size: int = 3
    min_seed_size: int = 5
    min_domain_size: int = 8
    domain_conflict_margin: float = 0.05
    domain_merge_angle_tolerance_deg: float = 8.0
    footprint_support_radius_nm: float = 1.3
    q_seed: float = 0.65
    q_grow: float = 0.25
    seed_angle_tolerance_deg: float = 8.0
    grow_angle_tolerance_deg: float = 12.0
    delaunay_degeneracy_policy: Literal[
        "exclude_ambiguous_edges"
    ] = "exclude_ambiguous_edges"
    gr_bin_width_nm: float = 0.1
    gr_max_nm: float = 10.0
    gr_min_expected_pair_exposure: float = 5.0
    gr_min_contributing_frames: int = 1
    gr_smoothing_method: str = "gaussian_bins"
    gr_smoothing_width: float = 2.0
    gr_peak_prominence: float = 0.1
    min_bonds_for_domain_length_stats: int = 5
    domain_bond_length_robust_cv_qc_threshold: float = 0.2
    orientation_zero_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "duplicate_detection_enabled",
            _normalize_bool(self.duplicate_detection_enabled, "duplicate_detection_enabled"),
        )
        for field_name in _FLOAT_FIELDS:
            object.__setattr__(
                self,
                field_name,
                _normalize_float(getattr(self, field_name), field_name),
            )
        for field_name in _INTEGER_FIELDS:
            object.__setattr__(
                self,
                field_name,
                _normalize_integer(getattr(self, field_name), field_name),
            )
        for field_name in _TOKEN_FIELDS:
            object.__setattr__(
                self,
                field_name,
                str(getattr(self, field_name)).strip().lower(),
            )
        for field_name, expected in _FIXED_VALUES.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} must be {expected!r}.")
        if not self.gr_smoothing_method:
            raise ValueError("gr_smoothing_method must not be empty.")
        for field_name in _POSITIVE_DISTANCE_FIELDS:
            if getattr(self, field_name) <= 0.0:
                raise ValueError(f"{field_name} must be positive.")
        for field_name in _POSITIVE_INTEGER_FIELDS:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive.")
        for field_name in _POSITIVE_GR_FIELDS:
            if getattr(self, field_name) <= 0.0:
                raise ValueError(f"{field_name} must be positive.")
        if self.first_shell_r_min_nm >= self.first_shell_r_max_nm:
            raise ValueError("first_shell_r_min_nm must be less than first_shell_r_max_nm.")
        if self.duplicate_detection_enabled and not (
            self.geometry_absolute_tolerance_nm
            < self.duplicate_max_distance_nm
            < self.first_shell_r_min_nm
        ):
            raise ValueError(
                "Active duplicate detection requires geometry_absolute_tolerance_nm "
                "< duplicate_max_distance_nm < first_shell_r_min_nm."
            )
        if not 0.0 <= self.q_grow <= self.q_seed <= 1.0:
            raise ValueError("q thresholds must satisfy 0 <= q_grow <= q_seed <= 1.")
        if not 0.0 <= self.seed_angle_tolerance_deg <= 30.0:
            raise ValueError("seed_angle_tolerance_deg must be between 0 and 30.")
        if not 0.0 <= self.grow_angle_tolerance_deg <= 30.0:
            raise ValueError("grow_angle_tolerance_deg must be between 0 and 30.")
        if not 0.0 <= self.domain_merge_angle_tolerance_deg <= 30.0:
            raise ValueError("domain_merge_angle_tolerance_deg must be between 0 and 30.")
        if self.domain_conflict_margin < 0.0:
            raise ValueError("domain_conflict_margin must be non-negative.")
        if self.orientation_zero_tolerance < 0.0:
            raise ValueError("orientation_zero_tolerance must be non-negative.")
        if not 0 < self.min_ordered_component_size <= self.min_seed_size <= self.min_domain_size:
            raise ValueError(
                "Component sizes must satisfy 0 < min_ordered_component_size "
                "<= min_seed_size <= min_domain_size."
            )
        if self.gr_peak_prominence < 0.0:
            raise ValueError("gr_peak_prominence must be non-negative.")
        if self.domain_bond_length_robust_cv_qc_threshold < 0.0:
            raise ValueError(
                "domain_bond_length_robust_cv_qc_threshold must be non-negative."
            )

    def to_dict(self) -> dict[str, bool | int | float | str]:
        """Return fields in declaration order using JSON-compatible scalars."""

        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MolecularM6OrientationAnalysisSettings":
        """Restore settings while applying the same normalization and validation."""

        if not isinstance(payload, Mapping):
            raise TypeError("M6 settings payload must be a mapping.")
        field_names = {field.name for field in fields(cls)}
        non_string_keys = [key for key in payload if not isinstance(key, str)]
        if non_string_keys:
            raise ValueError("M6 setting field names must be strings.")
        unknown_fields = sorted(set(payload) - field_names)
        if unknown_fields:
            raise ValueError(f"Unknown M6 setting fields: {', '.join(unknown_fields)}")
        missing_fields = sorted(field_names - set(payload))
        if missing_fields:
            raise ValueError(f"Missing M6 setting fields: {', '.join(missing_fields)}")
        return cls(**dict(payload))


def _normalize_bool(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "false"):
            return normalized == "true"
    raise ValueError(f"{field_name} must be a boolean value.")


def _normalize_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a numeric value.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a numeric value.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _normalize_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer value.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field_name} must be an integer value.") from exc
    if not isfinite(numeric) or numeric != normalized:
        raise ValueError(f"{field_name} must be an integer value.")
    return normalized
