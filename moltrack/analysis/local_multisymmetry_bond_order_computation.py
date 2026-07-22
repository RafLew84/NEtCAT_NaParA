"""Parallel local M3/M6 observations from one retained first-shell graph."""

from __future__ import annotations

import json
from cmath import phase
from collections.abc import Sequence
from hashlib import sha256
from math import degrees, isfinite

from ._first_shell_graph_fingerprint import first_shell_graph_fingerprint
from ._local_harmonic_bond_order import (
    LocalHarmonicOrderChannel,
    compute_local_harmonic_bond_order_core,
)
from .first_shell_graph import FirstShellGraph
from .local_multisymmetry_bond_order import (
    LocalMultiSymmetryBondOrderField,
    LocalMultiSymmetryBondOrderProvenance,
    LocalMultiSymmetryOrientationStatus,
    SymmetryResolvabilityStatus,
)
from .local_sixfold_bond_order import LocalOrderComputationStatus
from .m3_sublattice_gauge import build_m3_sublattice_gauge_assignment
from .m6_settings import MolecularM6OrientationAnalysisSettings


def compute_local_multisymmetry_bond_order(
    first_shell_graph: FirstShellGraph,
    *,
    distance_to_valid_fov_boundary_nm: Sequence[float | None],
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    m3_orientation_zero_tolerance: float | None = None,
    m6_orientation_zero_tolerance: float | None = None,
    qualified_trifold_point_indices: Sequence[int] = (),
    ambiguous_trifold_point_indices: Sequence[int] = (),
    trifold_edge_qualified: Sequence[bool] | None = None,
) -> LocalMultiSymmetryBondOrderField:
    """Compute uniform M3 and M6 channels with shared incidence and QC."""

    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    m3_tolerance = _orientation_tolerance(
        settings.orientation_zero_tolerance
        if m3_orientation_zero_tolerance is None
        else m3_orientation_zero_tolerance,
        field_name="m3_orientation_zero_tolerance",
    )
    m6_tolerance = _orientation_tolerance(
        settings.orientation_zero_tolerance
        if m6_orientation_zero_tolerance is None
        else m6_orientation_zero_tolerance,
        field_name="m6_orientation_zero_tolerance",
    )
    core = compute_local_harmonic_bond_order_core(
        first_shell_graph,
        harmonics=(3, 6),
        distance_to_valid_fov_boundary_nm=distance_to_valid_fov_boundary_nm,
        settings=settings,
    )
    m3_channel = core.channel(3)
    m6_channel = core.channel(6)
    m3_status, m3_confidence = _orientation_context(
        m3_channel,
        computation_status=core.computation_status,
        tolerance=m3_tolerance,
    )
    m6_status, m6_confidence = _orientation_context(
        m6_channel,
        computation_status=core.computation_status,
        tolerance=m6_tolerance,
    )
    theta3_polar = _channel_angles(
        m3_channel.psi,
        orientation_status=m3_status,
        harmonic=3,
        period_deg=120.0,
    )
    theta3_lattice = _channel_angles(
        tuple(
            None if value is None else value * value
            for value in m3_channel.psi
        ),
        orientation_status=m3_status,
        harmonic=6,
        period_deg=60.0,
    )
    theta6 = _channel_angles(
        m6_channel.psi,
        orientation_status=m6_status,
        harmonic=6,
        period_deg=60.0,
    )

    gauge = build_m3_sublattice_gauge_assignment(
        first_shell_graph=first_shell_graph,
        m3_orientation_status=m3_status,
        qualified_trifold_point_indices=tuple(qualified_trifold_point_indices),
        ambiguous_trifold_point_indices=tuple(ambiguous_trifold_point_indices),
        trifold_edge_qualified=(
            None if trifold_edge_qualified is None else tuple(trifold_edge_qualified)
        ),
    )
    analysis_fingerprint = _analysis_settings_fingerprint(
        settings=settings,
        m3_orientation_zero_tolerance=m3_tolerance,
        m6_orientation_zero_tolerance=m6_tolerance,
    )
    provenance = LocalMultiSymmetryBondOrderProvenance(
        coordinate_frame="sample_nm",
        orientation_reference=first_shell_graph.orientation_reference,
        spatial_calibration_fingerprint=(
            first_shell_graph.spatial_calibration_fingerprint
        ),
        registration_fingerprint=first_shell_graph.registration_fingerprint,
        point_coordinate_fingerprint=(
            first_shell_graph.point_coordinate_fingerprint
        ),
        first_shell_graph_fingerprint=first_shell_graph_fingerprint(
            first_shell_graph
        ),
        qualified_trifold_subgraph_fingerprint=(
            gauge.qualified_trifold_subgraph_fingerprint
        ),
        m3_phase_assignment_fingerprint=gauge.m3_phase_assignment_fingerprint,
        analysis_settings_fingerprint=analysis_fingerprint,
    )
    symmetry_resolvability_status: tuple[SymmetryResolvabilityStatus, ...] = tuple(
        "not_evaluated" if status == "valid_order" else "unavailable"
        for status in core.computation_status
    )
    return LocalMultiSymmetryBondOrderField(
        source_ids=first_shell_graph.point_ids,
        point_count=first_shell_graph.point_count,
        psi3=m3_channel.psi,
        q3=m3_channel.magnitude,
        theta3_polar_deg=theta3_polar,
        theta3_lattice_deg=theta3_lattice,
        m3_orientation_status=m3_status,
        m3_orientation_confidence=m3_confidence,
        psi6=m6_channel.psi,
        q6=m6_channel.magnitude,
        theta6_deg=theta6,
        m6_orientation_status=m6_status,
        m6_orientation_confidence=m6_confidence,
        neighbor_count=core.neighbor_count,
        computation_status=core.computation_status,
        m3_sublattice_phase=gauge.m3_sublattice_phase,
        m3_sublattice_phase_status=gauge.m3_sublattice_phase_status,
        m3_phase_gauge_anchor=gauge.m3_phase_gauge_anchor,
        m3_qualified_trifold=gauge.m3_qualified_trifold,
        m3_sublattice_assignment_ambiguous=(
            gauge.m3_sublattice_assignment_ambiguous
        ),
        m3_gauge_inconsistent_cycle=gauge.m3_gauge_inconsistent_cycle,
        m3_gauge_frustration_qc=gauge.m3_gauge_frustration_qc,
        symmetry_resolvability_status=symmetry_resolvability_status,
        physical_duplicate_qc=first_shell_graph.physical_duplicate_qc,
        geometry_duplicate_qc=first_shell_graph.geometry_duplicate_qc,
        edge_truncated_neighborhood=core.edge_truncated_neighborhood,
        distance_to_valid_fov_boundary_nm=(
            core.distance_to_valid_fov_boundary_nm
        ),
        first_shell_r_max_nm=first_shell_graph.first_shell_r_max_nm,
        provenance=provenance,
        min_neighbors_for_local_order=settings.min_neighbors_for_local_order,
        m3_orientation_zero_tolerance=m3_tolerance,
        m6_orientation_zero_tolerance=m6_tolerance,
        bond_weighting=settings.bond_weighting,
    )


def _orientation_context(
    channel: LocalHarmonicOrderChannel,
    *,
    computation_status: tuple[LocalOrderComputationStatus, ...],
    tolerance: float,
) -> tuple[
    tuple[LocalMultiSymmetryOrientationStatus, ...],
    tuple[float | None, ...],
]:
    statuses: list[LocalMultiSymmetryOrientationStatus] = []
    confidence: list[float | None] = []
    for point_status, magnitude in zip(computation_status, channel.magnitude):
        if point_status == "insufficient_neighbors":
            statuses.append("insufficient_neighbors")
            confidence.append(None)
        elif point_status != "valid_order":
            statuses.append("invalid_geometry")
            confidence.append(None)
        elif magnitude is None:
            raise RuntimeError("Valid harmonic magnitude is unexpectedly unavailable.")
        elif magnitude <= tolerance:
            statuses.append("undefined_low_amplitude")
            confidence.append(None)
        else:
            statuses.append("defined")
            confidence.append(magnitude)
    return tuple(statuses), tuple(confidence)


def _channel_angles(
    psi: tuple[complex | None, ...],
    *,
    orientation_status: tuple[LocalMultiSymmetryOrientationStatus, ...],
    harmonic: int,
    period_deg: float,
) -> tuple[float | None, ...]:
    angles: list[float | None] = []
    for point_psi, status in zip(psi, orientation_status):
        if status != "defined":
            angles.append(None)
        elif point_psi is None:
            raise RuntimeError("Defined harmonic orientation is unexpectedly unavailable.")
        else:
            angles.append(degrees(phase(point_psi) / harmonic) % period_deg)
    return tuple(angles)


def _orientation_tolerance(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _analysis_settings_fingerprint(
    *,
    settings: MolecularM6OrientationAnalysisSettings,
    m3_orientation_zero_tolerance: float,
    m6_orientation_zero_tolerance: float,
) -> str:
    payload = {
        "schema": "moltrack-local-m3-m6-computation-v1",
        "graph_and_m6_settings": settings.to_dict(),
        "harmonics": (3, 6),
        "bond_weighting": "uniform",
        "orientation_confidence": "q_magnitude",
        "m3_orientation_zero_tolerance": m3_orientation_zero_tolerance,
        "m6_orientation_zero_tolerance": m6_orientation_zero_tolerance,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded).hexdigest()
