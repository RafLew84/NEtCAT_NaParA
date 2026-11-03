"""Shared uniform harmonic bond-order computation on one first-shell graph."""

from __future__ import annotations

from cmath import exp
from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, isclose, pi

import numpy as np

from ._boundary_distances import normalize_boundary_distances
from ._m6_settings_fingerprint import m6_settings_fingerprint
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import LocalOrderComputationStatus
from .m6_settings import MolecularM6OrientationAnalysisSettings


@dataclass(frozen=True)
class LocalHarmonicOrderChannel:
    harmonic: int
    psi: tuple[complex | None, ...]
    magnitude: tuple[float | None, ...]


@dataclass(frozen=True)
class LocalHarmonicBondOrderCoreResult:
    channels: tuple[LocalHarmonicOrderChannel, ...]
    neighbor_count: tuple[int, ...]
    computation_status: tuple[LocalOrderComputationStatus, ...]
    local_median_bond_length_nm: tuple[float | None, ...]
    local_bond_length_mad_nm: tuple[float | None, ...]
    local_bond_length_iqr_nm: tuple[float | None, ...]
    local_bond_length_robust_cv: tuple[float | None, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    distance_to_valid_fov_boundary_nm: tuple[float | None, ...]

    def channel(self, harmonic: int) -> LocalHarmonicOrderChannel:
        for channel in self.channels:
            if channel.harmonic == harmonic:
                return channel
        raise KeyError(f"Harmonic {harmonic} was not computed.")


def compute_local_harmonic_bond_order_core(
    first_shell_graph: FirstShellGraph,
    *,
    harmonics: Sequence[int],
    distance_to_valid_fov_boundary_nm: Sequence[float | None],
    settings: MolecularM6OrientationAnalysisSettings,
) -> LocalHarmonicBondOrderCoreResult:
    """Compute selected uniform harmonics with shared graph incidence and QC."""

    if not isinstance(first_shell_graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be a FirstShellGraph.")
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    normalized_harmonics = _normalize_harmonics(harmonics)
    _validate_graph_settings(first_shell_graph, settings)
    boundary_distances = normalize_boundary_distances(
        distance_to_valid_fov_boundary_nm,
        point_count=first_shell_graph.point_count,
    )

    phase_contributions = {
        harmonic: [[] for _ in range(first_shell_graph.point_count)]
        for harmonic in normalized_harmonics
    }
    bond_lengths: list[list[float]] = [
        [] for _ in range(first_shell_graph.point_count)
    ]
    for (left, right), distance_nm, angle_rad in zip(
        first_shell_graph.edges_ij,
        first_shell_graph.distances_nm,
        first_shell_graph.angles_rad,
    ):
        for harmonic in normalized_harmonics:
            phase_contributions[harmonic][left].append(
                exp(harmonic * 1j * angle_rad)
            )
            phase_contributions[harmonic][right].append(
                exp(harmonic * 1j * (angle_rad + pi))
            )
        bond_lengths[left].append(distance_nm)
        bond_lengths[right].append(distance_nm)

    psi_by_harmonic: dict[int, list[complex | None]] = {
        harmonic: [] for harmonic in normalized_harmonics
    }
    q_by_harmonic: dict[int, list[float | None]] = {
        harmonic: [] for harmonic in normalized_harmonics
    }
    computation_statuses: list[LocalOrderComputationStatus] = []
    medians: list[float | None] = []
    mads: list[float | None] = []
    iqrs: list[float | None] = []
    robust_cvs: list[float | None] = []

    for index in range(first_shell_graph.point_count):
        neighbors = first_shell_graph.degree[index]
        lengths = bond_lengths[index]
        if len(lengths) != neighbors:
            raise ValueError("first_shell_graph degree must match retained edge incidence.")
        if any(
            len(phase_contributions[harmonic][index]) != neighbors
            for harmonic in normalized_harmonics
        ):
            raise ValueError("All harmonics must use the same retained edge incidence.")

        point_median, point_mad, point_iqr, point_robust_cv = (
            _bond_length_statistics(lengths)
        )
        medians.append(point_median)
        mads.append(point_mad)
        iqrs.append(point_iqr)
        robust_cvs.append(point_robust_cv)

        status = _point_computation_status(
            first_shell_graph,
            index=index,
            boundary_distance_nm=boundary_distances[index],
            min_neighbors=settings.min_neighbors_for_local_order,
        )
        computation_statuses.append(status)
        for harmonic in normalized_harmonics:
            if status != "valid_order":
                psi_by_harmonic[harmonic].append(None)
                q_by_harmonic[harmonic].append(None)
                continue
            point_psi = _mean_complex(phase_contributions[harmonic][index])
            point_q = abs(point_psi)
            if point_q > 1.0:
                if not isclose(point_q, 1.0, rel_tol=0.0, abs_tol=1e-12):
                    raise ArithmeticError(
                        f"Computed q{harmonic} exceeds its unit upper bound."
                    )
                point_psi /= point_q
                point_q = 1.0
            psi_by_harmonic[harmonic].append(point_psi)
            q_by_harmonic[harmonic].append(point_q)

    edge_truncated = tuple(
        distance is not None and distance < first_shell_graph.first_shell_r_max_nm
        for distance in boundary_distances
    )
    return LocalHarmonicBondOrderCoreResult(
        channels=tuple(
            LocalHarmonicOrderChannel(
                harmonic=harmonic,
                psi=tuple(psi_by_harmonic[harmonic]),
                magnitude=tuple(q_by_harmonic[harmonic]),
            )
            for harmonic in normalized_harmonics
        ),
        neighbor_count=first_shell_graph.degree,
        computation_status=tuple(computation_statuses),
        local_median_bond_length_nm=tuple(medians),
        local_bond_length_mad_nm=tuple(mads),
        local_bond_length_iqr_nm=tuple(iqrs),
        local_bond_length_robust_cv=tuple(robust_cvs),
        edge_truncated_neighborhood=edge_truncated,
        distance_to_valid_fov_boundary_nm=boundary_distances,
    )


def _normalize_harmonics(values: Sequence[int]) -> tuple[int, ...]:
    normalized = tuple(values)
    if not normalized:
        raise ValueError("harmonics must contain at least one value.")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in normalized):
        raise TypeError("harmonics must contain positive integers.")
    if any(value <= 0 for value in normalized):
        raise ValueError("harmonics must contain positive integers.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("harmonics must be unique.")
    return normalized


def _point_computation_status(
    graph: FirstShellGraph,
    *,
    index: int,
    boundary_distance_nm: float | None,
    min_neighbors: int,
) -> LocalOrderComputationStatus:
    is_duplicate = (
        graph.physical_duplicate_qc[index] or graph.geometry_duplicate_qc[index]
    )
    neighbors = graph.degree[index]
    if is_duplicate:
        return "duplicate_excluded"
    if boundary_distance_nm is None:
        if neighbors:
            raise ValueError(
                "A point without a valid FOV boundary distance cannot retain graph edges."
            )
        return "invalid_position"
    if neighbors < min_neighbors:
        return "insufficient_neighbors"
    return "valid_order"


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
