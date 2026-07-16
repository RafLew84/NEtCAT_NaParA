from __future__ import annotations

from cmath import exp, phase
from collections.abc import Sequence
from math import degrees, fsum, isclose, pi

import numpy as np

from ._boundary_distances import normalize_boundary_distances
from ._m6_settings_fingerprint import m6_settings_fingerprint
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import (
    LocalOrderComputationStatus,
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
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    _validate_graph_settings(first_shell_graph, settings)
    boundary_distances = normalize_boundary_distances(
        distance_to_valid_fov_boundary_nm,
        point_count=first_shell_graph.point_count,
    )

    phase_contributions: list[list[complex]] = [
        [] for _ in range(first_shell_graph.point_count)
    ]
    bond_lengths: list[list[float]] = [
        [] for _ in range(first_shell_graph.point_count)
    ]
    for (left, right), distance_nm, angle_rad in zip(
        first_shell_graph.edges_ij,
        first_shell_graph.distances_nm,
        first_shell_graph.angles_rad,
    ):
        phase_contributions[left].append(exp(6j * angle_rad))
        phase_contributions[right].append(exp(6j * (angle_rad + pi)))
        bond_lengths[left].append(distance_nm)
        bond_lengths[right].append(distance_nm)

    psi6: list[complex | None] = []
    q6: list[float | None] = []
    orientations: list[float | None] = []
    orientation_statuses: list[LocalOrientationStatus] = []
    computation_statuses: list[LocalOrderComputationStatus] = []
    medians: list[float | None] = []
    mads: list[float | None] = []
    iqrs: list[float | None] = []
    robust_cvs: list[float | None] = []

    for index in range(first_shell_graph.point_count):
        neighbors = first_shell_graph.degree[index]
        contributions = phase_contributions[index]
        lengths = bond_lengths[index]
        if len(contributions) != neighbors or len(lengths) != neighbors:
            raise ValueError("first_shell_graph degree must match retained edge incidence.")

        point_median, point_mad, point_iqr, point_robust_cv = _bond_length_statistics(
            lengths
        )
        medians.append(point_median)
        mads.append(point_mad)
        iqrs.append(point_iqr)
        robust_cvs.append(point_robust_cv)

        is_duplicate = (
            first_shell_graph.physical_duplicate_qc[index]
            or first_shell_graph.geometry_duplicate_qc[index]
        )
        boundary_distance = boundary_distances[index]
        if is_duplicate:
            status: LocalOrderComputationStatus = "duplicate_excluded"
        elif boundary_distance is None:
            if neighbors:
                raise ValueError(
                    "A point without a valid FOV boundary distance cannot retain graph edges."
                )
            status = "invalid_position"
        elif neighbors < settings.min_neighbors_for_local_order:
            status = "insufficient_neighbors"
        else:
            status = "valid_order"
        computation_statuses.append(status)

        if status != "valid_order":
            psi6.append(None)
            q6.append(None)
            orientations.append(None)
            orientation_statuses.append("not_available")
            continue

        point_psi6 = _mean_complex(contributions)
        point_q6 = abs(point_psi6)
        if point_q6 > 1.0:
            if not isclose(point_q6, 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise ArithmeticError("Computed q6 exceeds its unit upper bound.")
            point_psi6 /= point_q6
            point_q6 = 1.0
        psi6.append(point_psi6)
        q6.append(point_q6)
        if point_q6 <= settings.orientation_zero_tolerance:
            orientations.append(None)
            orientation_statuses.append("undefined_zero_magnitude")
        else:
            orientations.append(degrees(phase(point_psi6) / 6.0) % 60.0)
            orientation_statuses.append("defined")

    edge_truncated = tuple(
        distance is not None and distance < first_shell_graph.first_shell_r_max_nm
        for distance in boundary_distances
    )
    return LocalSixfoldBondOrderField(
        source_ids=first_shell_graph.point_ids,
        point_count=first_shell_graph.point_count,
        psi6=tuple(psi6),
        q6=tuple(q6),
        lattice_orientation_deg=tuple(orientations),
        orientation_status=tuple(orientation_statuses),
        neighbor_count=first_shell_graph.degree,
        computation_status=tuple(computation_statuses),
        local_median_bond_length_nm=tuple(medians),
        local_bond_length_mad_nm=tuple(mads),
        local_bond_length_iqr_nm=tuple(iqrs),
        local_bond_length_robust_cv=tuple(robust_cvs),
        physical_duplicate_qc=first_shell_graph.physical_duplicate_qc,
        geometry_duplicate_qc=first_shell_graph.geometry_duplicate_qc,
        edge_truncated_neighborhood=edge_truncated,
        distance_to_valid_fov_boundary_nm=boundary_distances,
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


def _mean_complex(values: Sequence[complex]) -> complex:
    count = len(values)
    if count == 0:
        raise ValueError("Cannot compute a complex mean without values.")
    return complex(
        fsum(value.real for value in values) / count,
        fsum(value.imag for value in values) / count,
    )


def _bond_length_statistics(
    values: Sequence[float],
) -> tuple[float | None, float | None, float | None, float | None]:
    if not values:
        return None, None, None, None
    distances = np.asarray(values, dtype=np.float64)
    median = float(np.median(distances))
    mad = float(np.median(np.abs(distances - median)))
    quartile_25, quartile_75 = np.percentile(distances, (25.0, 75.0))
    iqr = float(quartile_75 - quartile_25)
    return median, mad, iqr, 1.4826 * mad / median


def _validate_graph_settings(
    graph: FirstShellGraph,
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    graph_contract = (
        graph.duplicate_detection_enabled,
        graph.duplicate_max_distance_nm,
        graph.first_shell_r_min_nm,
        graph.first_shell_r_max_nm,
    )
    settings_contract = (
        settings.duplicate_detection_enabled,
        settings.duplicate_max_distance_nm,
        settings.first_shell_r_min_nm,
        settings.first_shell_r_max_nm,
    )
    if graph_contract != settings_contract:
        raise ValueError("first_shell_graph must use the supplied settings.")
    expected_fingerprint = m6_settings_fingerprint(settings)
    if graph.analysis_settings_fingerprint not in {
        "unspecified_settings",
        expected_fingerprint,
    }:
        raise ValueError("first_shell_graph must use the complete supplied settings.")
