"""Versioned local M3/M6 observations in calibrated sample coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, get_args

from ._local_multisymmetry_validation import (
    as_non_negative_integer as _as_non_negative_integer,
    as_positive_float as _as_positive_float,
    as_positive_integer as _as_positive_integer,
    as_unit_interval_float as _as_unit_interval_float,
    boolean_tuple as _boolean_tuple,
    normalize_m3_sublattice_gauge as _normalize_m3_sublattice_gauge,
    normalized_optional_angles as _normalized_optional_angles,
    optional_complex_tuple as _optional_complex_tuple,
    optional_float_tuple as _optional_float_tuple,
    per_point_tuple as _per_point_tuple,
    status_tuple as _status_tuple,
    validate_m3_gauge_component_qc as _validate_m3_gauge_component_qc,
    validate_order_channel as _validate_order_channel,
    validate_periodic_angle_consistency as _validate_periodic_angle_consistency,
    validate_point_context as _validate_point_context,
)
from .first_shell_graph import OrientationReference
from .local_sixfold_bond_order import LocalOrderComputationStatus


LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION = 1

LocalMultiSymmetryOrientationStatus = Literal[
    "defined",
    "undefined_low_amplitude",
    "insufficient_neighbors",
    "invalid_geometry",
]
M3SublatticePhaseStatus = Literal[
    "defined",
    "ambiguous",
    "unavailable",
    "not_applicable",
    "inconsistent",
]
SymmetryResolvabilityStatus = Literal[
    "not_evaluated",
    "resolvable",
    "symmetry_alias_unresolvable_from_centroids",
    "unavailable",
]


_ORIENTATION_STATUSES = set(get_args(LocalMultiSymmetryOrientationStatus))
_M3_SUBLATTICE_PHASE_STATUSES = set(get_args(M3SublatticePhaseStatus))
_SYMMETRY_RESOLVABILITY_STATUSES = set(get_args(SymmetryResolvabilityStatus))
_COMPUTATION_STATUSES = set(get_args(LocalOrderComputationStatus))
_ORIENTATION_REFERENCES = set(get_args(OrientationReference))


def m3_lattice_orientation_distance_deg(first_deg: float, second_deg: float) -> float:
    """Return the shortest M3 lattice-orientation distance modulo 60 degrees."""

    normalized: list[float] = []
    for value in (first_deg, second_deg):
        if isinstance(value, bool):
            raise TypeError("M3 lattice orientations must be finite numbers.")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError("M3 lattice orientations must be finite numbers.") from exc
        if not isfinite(number):
            raise ValueError("M3 lattice orientations must be finite numbers.")
        normalized.append(number % 60.0)
    difference = abs(normalized[0] - normalized[1])
    return min(difference, 60.0 - difference)


@dataclass(frozen=True)
class LocalMultiSymmetryBondOrderProvenance:
    """Shared coordinate, graph, and settings provenance for M3 and M6."""

    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str
    first_shell_graph_fingerprint: str
    qualified_trifold_subgraph_fingerprint: str
    m3_phase_assignment_fingerprint: str
    analysis_settings_fingerprint: str

    def __post_init__(self) -> None:
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.orientation_reference not in _ORIENTATION_REFERENCES:
            raise ValueError(
                f"Unsupported orientation_reference: {self.orientation_reference!r}."
            )
        for field_name in (
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
            "point_coordinate_fingerprint",
            "first_shell_graph_fingerprint",
            "qualified_trifold_subgraph_fingerprint",
            "m3_phase_assignment_fingerprint",
            "analysis_settings_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field_name} must be a non-empty string.")


@dataclass(frozen=True)
class LocalMultiSymmetryBondOrderField:
    """Immutable per-molecule M3/M6 observations from one first-shell graph.

    M3 lattice angles and sublattice phases describe centroid geometry, not
    molecular orientation or stacking. Phases are component-relative topology
    labels. Both channels share one point order, graph fingerprint, coordinate
    transform provenance, neighbor count, and QC context.
    """

    source_ids: tuple[str, ...]
    point_count: int
    psi3: tuple[complex | None, ...]
    q3: tuple[float | None, ...]
    theta3_polar_deg: tuple[float | None, ...]
    theta3_lattice_deg: tuple[float | None, ...]
    m3_orientation_status: tuple[LocalMultiSymmetryOrientationStatus, ...]
    m3_orientation_confidence: tuple[float | None, ...]
    psi6: tuple[complex | None, ...]
    q6: tuple[float | None, ...]
    theta6_deg: tuple[float | None, ...]
    m6_orientation_status: tuple[LocalMultiSymmetryOrientationStatus, ...]
    m6_orientation_confidence: tuple[float | None, ...]
    neighbor_count: tuple[int, ...]
    computation_status: tuple[LocalOrderComputationStatus, ...]
    m3_sublattice_phase: tuple[int | None, ...]
    m3_sublattice_phase_status: tuple[M3SublatticePhaseStatus, ...]
    m3_phase_gauge_anchor: tuple[str | None, ...]
    m3_qualified_trifold: tuple[bool, ...]
    m3_sublattice_assignment_ambiguous: tuple[bool, ...]
    m3_gauge_inconsistent_cycle: tuple[bool, ...]
    m3_gauge_frustration_qc: tuple[bool, ...]
    symmetry_resolvability_status: tuple[SymmetryResolvabilityStatus, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    distance_to_valid_fov_boundary_nm: tuple[float | None, ...]
    first_shell_r_max_nm: float
    provenance: LocalMultiSymmetryBondOrderProvenance
    min_neighbors_for_local_order: int = 3
    m3_orientation_zero_tolerance: float = 1e-12
    m6_orientation_zero_tolerance: float = 1e-12
    schema_version: int = LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION
    symmetry_channels: tuple[Literal[3], Literal[6]] = (3, 6)
    m3_phase_gauge_scope: Literal["connected_component_relative"] = (
        "connected_component_relative"
    )
    bond_weighting: Literal["uniform"] = "uniform"

    def __post_init__(self) -> None:
        point_count = _as_non_negative_integer(self.point_count, "point_count")
        source_ids = _per_point_tuple(
            self.source_ids,
            point_count=point_count,
            field_name="source_ids",
        )
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")
        if (
            isinstance(self.schema_version, bool)
            or self.schema_version != LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION
        ):
            raise ValueError(f"Unsupported schema_version: {self.schema_version!r}.")
        if self.symmetry_channels != (3, 6):
            raise ValueError("symmetry_channels must be (3, 6).")
        if self.m3_phase_gauge_scope != "connected_component_relative":
            raise ValueError(
                "m3_phase_gauge_scope must be 'connected_component_relative'."
            )
        if self.bond_weighting != "uniform":
            raise ValueError("bond_weighting must be 'uniform'.")
        if not isinstance(self.provenance, LocalMultiSymmetryBondOrderProvenance):
            raise TypeError(
                "provenance must be LocalMultiSymmetryBondOrderProvenance."
            )
        minimum_neighbors = _as_positive_integer(
            self.min_neighbors_for_local_order,
            "min_neighbors_for_local_order",
        )
        first_shell_r_max_nm = _as_positive_float(
            self.first_shell_r_max_nm,
            "first_shell_r_max_nm",
        )
        m3_orientation_zero_tolerance = _as_unit_interval_float(
            self.m3_orientation_zero_tolerance,
            "m3_orientation_zero_tolerance",
        )
        m6_orientation_zero_tolerance = _as_unit_interval_float(
            self.m6_orientation_zero_tolerance,
            "m6_orientation_zero_tolerance",
        )
        object.__setattr__(
            self,
            "m3_orientation_zero_tolerance",
            m3_orientation_zero_tolerance,
        )
        object.__setattr__(
            self,
            "m6_orientation_zero_tolerance",
            m6_orientation_zero_tolerance,
        )

        per_point_fields = (
            "psi3",
            "q3",
            "theta3_polar_deg",
            "theta3_lattice_deg",
            "m3_orientation_status",
            "m3_orientation_confidence",
            "psi6",
            "q6",
            "theta6_deg",
            "m6_orientation_status",
            "m6_orientation_confidence",
            "neighbor_count",
            "computation_status",
            "m3_sublattice_phase",
            "m3_sublattice_phase_status",
            "m3_phase_gauge_anchor",
            "m3_qualified_trifold",
            "m3_sublattice_assignment_ambiguous",
            "m3_gauge_inconsistent_cycle",
            "m3_gauge_frustration_qc",
            "symmetry_resolvability_status",
            "physical_duplicate_qc",
            "geometry_duplicate_qc",
            "edge_truncated_neighborhood",
            "distance_to_valid_fov_boundary_nm",
        )
        for field_name in per_point_fields:
            object.__setattr__(
                self,
                field_name,
                _per_point_tuple(
                    getattr(self, field_name),
                    point_count=point_count,
                    field_name=field_name,
                ),
            )

        self._normalize_scalar_fields()
        normalized_phases, normalized_anchors = _normalize_m3_sublattice_gauge(
            source_ids=source_ids,
            phases=self.m3_sublattice_phase,
            statuses=self.m3_sublattice_phase_status,
            anchors=self.m3_phase_gauge_anchor,
        )
        object.__setattr__(self, "m3_sublattice_phase", normalized_phases)
        object.__setattr__(self, "m3_phase_gauge_anchor", normalized_anchors)
        self._normalize_angles()
        self._validate_channels()
        _validate_point_context(
            computation_status=self.computation_status,
            psi3=self.psi3,
            psi6=self.psi6,
            m3_orientation_status=self.m3_orientation_status,
            m6_orientation_status=self.m6_orientation_status,
            m3_sublattice_phase_status=self.m3_sublattice_phase_status,
            m3_qualified_trifold=self.m3_qualified_trifold,
            m3_sublattice_assignment_ambiguous=(
                self.m3_sublattice_assignment_ambiguous
            ),
            m3_gauge_inconsistent_cycle=self.m3_gauge_inconsistent_cycle,
            m3_gauge_frustration_qc=self.m3_gauge_frustration_qc,
            symmetry_resolvability_status=self.symmetry_resolvability_status,
            neighbor_count=self.neighbor_count,
            physical_duplicate_qc=self.physical_duplicate_qc,
            geometry_duplicate_qc=self.geometry_duplicate_qc,
            edge_truncated_neighborhood=self.edge_truncated_neighborhood,
            boundary_distances=self.distance_to_valid_fov_boundary_nm,
            first_shell_r_max_nm=first_shell_r_max_nm,
            min_neighbors_for_local_order=minimum_neighbors,
        )
        _validate_m3_gauge_component_qc(
            anchors=self.m3_phase_gauge_anchor,
            ambiguity_flags=self.m3_sublattice_assignment_ambiguous,
        )
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "first_shell_r_max_nm", first_shell_r_max_nm)
        object.__setattr__(self, "min_neighbors_for_local_order", minimum_neighbors)

    def _normalize_scalar_fields(self) -> None:
        object.__setattr__(self, "psi3", _optional_complex_tuple(self.psi3, field_name="psi3"))
        object.__setattr__(self, "q3", _optional_float_tuple(self.q3, field_name="q3"))
        object.__setattr__(
            self,
            "m3_orientation_status",
            _status_tuple(
                self.m3_orientation_status,
                field_name="m3_orientation_status",
                supported=_ORIENTATION_STATUSES,
            ),
        )
        object.__setattr__(
            self,
            "m3_orientation_confidence",
            _optional_float_tuple(
                self.m3_orientation_confidence,
                field_name="m3_orientation_confidence",
            ),
        )
        object.__setattr__(self, "psi6", _optional_complex_tuple(self.psi6, field_name="psi6"))
        object.__setattr__(self, "q6", _optional_float_tuple(self.q6, field_name="q6"))
        object.__setattr__(
            self,
            "m6_orientation_status",
            _status_tuple(
                self.m6_orientation_status,
                field_name="m6_orientation_status",
                supported=_ORIENTATION_STATUSES,
            ),
        )
        object.__setattr__(
            self,
            "m6_orientation_confidence",
            _optional_float_tuple(
                self.m6_orientation_confidence,
                field_name="m6_orientation_confidence",
            ),
        )
        object.__setattr__(
            self,
            "m3_sublattice_phase_status",
            _status_tuple(
                self.m3_sublattice_phase_status,
                field_name="m3_sublattice_phase_status",
                supported=_M3_SUBLATTICE_PHASE_STATUSES,
            ),
        )
        object.__setattr__(
            self,
            "neighbor_count",
            tuple(
                _as_non_negative_integer(value, f"neighbor_count[{index}]")
                for index, value in enumerate(self.neighbor_count)
            ),
        )
        object.__setattr__(
            self,
            "computation_status",
            _status_tuple(
                self.computation_status,
                field_name="computation_status",
                supported=_COMPUTATION_STATUSES,
            ),
        )
        object.__setattr__(
            self,
            "symmetry_resolvability_status",
            _status_tuple(
                self.symmetry_resolvability_status,
                field_name="symmetry_resolvability_status",
                supported=_SYMMETRY_RESOLVABILITY_STATUSES,
            ),
        )
        for field_name in (
            "m3_qualified_trifold",
            "m3_sublattice_assignment_ambiguous",
            "m3_gauge_inconsistent_cycle",
            "m3_gauge_frustration_qc",
            "physical_duplicate_qc",
            "geometry_duplicate_qc",
            "edge_truncated_neighborhood",
        ):
            object.__setattr__(
                self,
                field_name,
                _boolean_tuple(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "distance_to_valid_fov_boundary_nm",
            _optional_float_tuple(
                self.distance_to_valid_fov_boundary_nm,
                field_name="distance_to_valid_fov_boundary_nm",
            ),
        )

    def _normalize_angles(self) -> None:
        object.__setattr__(
            self,
            "theta3_polar_deg",
            _normalized_optional_angles(self.theta3_polar_deg, period_deg=120.0),
        )
        object.__setattr__(
            self,
            "theta3_lattice_deg",
            _normalized_optional_angles(self.theta3_lattice_deg, period_deg=60.0),
        )
        object.__setattr__(
            self,
            "theta6_deg",
            _normalized_optional_angles(self.theta6_deg, period_deg=60.0),
        )

    def _validate_channels(self) -> None:
        _validate_order_channel(
            channel_name="M3",
            psi=self.psi3,
            magnitude=self.q3,
            angles=(self.theta3_polar_deg, self.theta3_lattice_deg),
            statuses=self.m3_orientation_status,
            confidence=self.m3_orientation_confidence,
            orientation_zero_tolerance=self.m3_orientation_zero_tolerance,
        )
        _validate_order_channel(
            channel_name="M6",
            psi=self.psi6,
            magnitude=self.q6,
            angles=(self.theta6_deg,),
            statuses=self.m6_orientation_status,
            confidence=self.m6_orientation_confidence,
            orientation_zero_tolerance=self.m6_orientation_zero_tolerance,
        )
        _validate_periodic_angle_consistency(
            field_name="theta3_polar_deg",
            psi=self.psi3,
            angles=self.theta3_polar_deg,
            statuses=self.m3_orientation_status,
            harmonic=3,
            period_deg=120.0,
        )
        _validate_periodic_angle_consistency(
            field_name="theta3_lattice_deg",
            psi=tuple(None if value is None else value * value for value in self.psi3),
            angles=self.theta3_lattice_deg,
            statuses=self.m3_orientation_status,
            harmonic=6,
            period_deg=60.0,
        )
        _validate_periodic_angle_consistency(
            field_name="theta6_deg",
            psi=self.psi6,
            angles=self.theta6_deg,
            statuses=self.m6_orientation_status,
            harmonic=6,
            period_deg=60.0,
        )

    def index_for_source_id(self, source_id: str) -> int:
        """Return the input-order index linked to a molecular source ID."""

        try:
            return self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc
