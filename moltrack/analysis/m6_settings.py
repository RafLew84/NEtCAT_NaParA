from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
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
    "lattice_edge_trifold_orientation_tolerance_deg",
    "lattice_edge_sixfold_orientation_tolerance_deg",
    "lattice_edge_mixed_model_profile_tolerance",
    "lattice_edge_conditional_channel_minimum_score",
    "lattice_edge_minimum_classification_confidence",
    "lattice_edge_minimum_orientation_confidence",
    "lattice_seed_min_model_score",
    "lattice_halo_min_model_score",
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

MAX_PAIR_CORRELATION_BIN_COUNT = 10_000

_LATTICE_EDGE_MIGRATION_FIELDS = {
    "lattice_edge_trifold_orientation_tolerance_deg",
    "lattice_edge_sixfold_orientation_tolerance_deg",
    "lattice_edge_mixed_model_profile_tolerance",
    "lattice_edge_conditional_channel_minimum_score",
    "lattice_edge_minimum_classification_confidence",
    "lattice_edge_minimum_orientation_confidence",
    "lattice_seed_min_model_score",
    "lattice_halo_min_model_score",
}


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
    lattice_edge_trifold_orientation_tolerance_deg: float = 8.0
    lattice_edge_sixfold_orientation_tolerance_deg: float = 8.0
    lattice_edge_mixed_model_profile_tolerance: float = 0.2
    lattice_edge_conditional_channel_minimum_score: float = 0.5
    lattice_edge_minimum_classification_confidence: float = 0.5
    lattice_edge_minimum_orientation_confidence: float = 0.5
    lattice_seed_min_model_score: float = 0.65
    lattice_halo_min_model_score: float = 0.25
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
        pair_correlation_bin_count = self.gr_max_nm / self.gr_bin_width_nm
        if (
            not isfinite(pair_correlation_bin_count)
            or pair_correlation_bin_count > MAX_PAIR_CORRELATION_BIN_COUNT
        ):
            raise ValueError(
                "Pair-correlation bin count must not exceed "
                f"{MAX_PAIR_CORRELATION_BIN_COUNT}."
            )
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
        for field_name in (
            "lattice_edge_trifold_orientation_tolerance_deg",
            "lattice_edge_sixfold_orientation_tolerance_deg",
        ):
            if not 0.0 <= getattr(self, field_name) <= 30.0:
                raise ValueError(f"{field_name} must be between 0 and 30.")
        for field_name in (
            "lattice_edge_mixed_model_profile_tolerance",
            "lattice_edge_conditional_channel_minimum_score",
            "lattice_edge_minimum_classification_confidence",
            "lattice_edge_minimum_orientation_confidence",
            "lattice_seed_min_model_score",
            "lattice_halo_min_model_score",
        ):
            if not 0.0 <= getattr(self, field_name) <= 1.0:
                raise ValueError(f"{field_name} must lie between 0 and 1.")
        if self.lattice_halo_min_model_score > self.lattice_seed_min_model_score:
            raise ValueError(
                "lattice_halo_min_model_score must not exceed "
                "lattice_seed_min_model_score."
            )
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
        missing_fields = field_names - set(payload)
        unsupported_missing_fields = sorted(
            missing_fields - _LATTICE_EDGE_MIGRATION_FIELDS
        )
        if unsupported_missing_fields:
            raise ValueError(
                f"Missing M6 setting fields: {', '.join(unsupported_missing_fields)}"
            )
        values = dict(payload)
        if missing_fields:
            defaults = cls()
            for field_name in missing_fields:
                values[field_name] = getattr(defaults, field_name)
        return cls(**values)


@dataclass(frozen=True)
class MolecularM6ViewSettings:
    """Serializable choices controlling M6 point overlays."""

    show_domain_overlay: bool = True
    overlay_mode: Literal[
        "q6",
        "orientation",
        "q3",
        "m3_orientation",
        "symmetry_evidence",
        "domain_id",
        "domain_type",
    ] = (
        "domain_id"
    )
    show_first_shell_graph: bool = False
    show_unassigned_points: bool = True
    overlay_opacity_percent: int = 60

    def __post_init__(self) -> None:
        opacity = int(self.overlay_opacity_percent)
        if not 0 <= opacity <= 100:
            raise ValueError("overlay_opacity_percent must be between 0 and 100.")
        mode = str(self.overlay_mode).strip().lower()
        if mode not in {
            "q6",
            "orientation",
            "q3",
            "m3_orientation",
            "symmetry_evidence",
            "domain_id",
            "domain_type",
        }:
            raise ValueError(f"Unsupported M6 overlay_mode: {self.overlay_mode!r}.")
        object.__setattr__(self, "show_domain_overlay", bool(self.show_domain_overlay))
        object.__setattr__(self, "overlay_mode", mode)
        object.__setattr__(self, "show_first_shell_graph", bool(self.show_first_shell_graph))
        object.__setattr__(self, "show_unassigned_points", bool(self.show_unassigned_points))
        object.__setattr__(self, "overlay_opacity_percent", opacity)


@dataclass(frozen=True)
class MolecularM6SessionState:
    """Serializable M6 analysis configuration independent of derived results."""

    enabled: bool = False
    source_view: str = "raw"
    use_segmentation_centroids: bool = True
    settings: MolecularM6OrientationAnalysisSettings = field(
        default_factory=MolecularM6OrientationAnalysisSettings
    )
    view_settings: MolecularM6ViewSettings = field(
        default_factory=MolecularM6ViewSettings
    )

    def __post_init__(self) -> None:
        source_view = str(self.source_view).strip()
        if source_view not in {"raw", "expanded_aligned"}:
            raise ValueError("Unsupported M6 source_view.")
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        if not isinstance(self.view_settings, MolecularM6ViewSettings):
            raise TypeError("view_settings must be MolecularM6ViewSettings.")
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(
            self,
            "use_segmentation_centroids",
            bool(self.use_segmentation_centroids),
        )


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
