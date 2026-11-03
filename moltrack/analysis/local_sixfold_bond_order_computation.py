from __future__ import annotations

from cmath import phase
from collections.abc import Sequence
from math import degrees

from ._local_harmonic_bond_order import compute_local_harmonic_bond_order_core
from ._m6_settings_fingerprint import m6_settings_fingerprint
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import (
    LocalOrientationStatus,
    LocalSixfoldBondOrderField,
)
from .m6_settings import MolecularM6OrientationAnalysisSettings


def compute_local_sixfold_bond_order(
    first_shell_graph: FirstShellGraph,
    *,
    distance_to_valid_fov_boundary_nm: Sequence[float | None],
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> LocalSixfoldBondOrderField:
    """Compute local uniform M6 order from a retained first-shell graph."""

    if not isinstance(first_shell_graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be a FirstShellGraph.")
    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    core = compute_local_harmonic_bond_order_core(
        first_shell_graph,
        harmonics=(6,),
        distance_to_valid_fov_boundary_nm=distance_to_valid_fov_boundary_nm,
        settings=settings,
    )
    channel = core.channel(6)

    orientations: list[float | None] = []
    orientation_statuses: list[LocalOrientationStatus] = []
    for status, point_psi6, point_q6 in zip(
        core.computation_status,
        channel.psi,
        channel.magnitude,
    ):
        if status != "valid_order":
            orientations.append(None)
            orientation_statuses.append("not_available")
            continue
        if point_psi6 is None or point_q6 is None:
            raise RuntimeError("Valid M6 order is unexpectedly unavailable.")
        if point_q6 <= settings.orientation_zero_tolerance:
            orientations.append(None)
            orientation_statuses.append("undefined_zero_magnitude")
        else:
            orientations.append(degrees(phase(point_psi6) / 6.0) % 60.0)
            orientation_statuses.append("defined")

    return LocalSixfoldBondOrderField(
        source_ids=first_shell_graph.point_ids,
        point_count=first_shell_graph.point_count,
        psi6=channel.psi,
        q6=channel.magnitude,
        lattice_orientation_deg=tuple(orientations),
        orientation_status=tuple(orientation_statuses),
        neighbor_count=core.neighbor_count,
        computation_status=core.computation_status,
        local_median_bond_length_nm=core.local_median_bond_length_nm,
        local_bond_length_mad_nm=core.local_bond_length_mad_nm,
        local_bond_length_iqr_nm=core.local_bond_length_iqr_nm,
        local_bond_length_robust_cv=core.local_bond_length_robust_cv,
        physical_duplicate_qc=first_shell_graph.physical_duplicate_qc,
        geometry_duplicate_qc=first_shell_graph.geometry_duplicate_qc,
        edge_truncated_neighborhood=core.edge_truncated_neighborhood,
        distance_to_valid_fov_boundary_nm=core.distance_to_valid_fov_boundary_nm,
        first_shell_r_max_nm=first_shell_graph.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference=first_shell_graph.orientation_reference,
        spatial_calibration_fingerprint=first_shell_graph.spatial_calibration_fingerprint,
        registration_fingerprint=first_shell_graph.registration_fingerprint,
        min_neighbors_for_local_order=settings.min_neighbors_for_local_order,
        symmetry_m=settings.symmetry_m,
        bond_weighting=settings.bond_weighting,
        analysis_settings_fingerprint=m6_settings_fingerprint(settings),
    )
