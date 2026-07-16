from __future__ import annotations

from cmath import phase
from math import cos, degrees, fsum, pi

import numpy as np

from ._coordinate_fingerprint import point_coordinate_fingerprint
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .orientation_domain_models import M6AssignmentStatus


def validate_m6_domain_analysis_inputs(
    points_xy_nm: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings,
) -> np.ndarray:
    """Validate and normalize the shared graph/local-order domain contract."""

    if not isinstance(first_shell_graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be a FirstShellGraph.")
    if not isinstance(local_order, LocalSixfoldBondOrderField):
        raise TypeError("local_order must be a LocalSixfoldBondOrderField.")
    points = np.array(points_xy_nm, dtype=np.float64, copy=True)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points_xy_nm must have shape [N, 2].")
    if not bool(np.all(np.isfinite(points))):
        raise ValueError("points_xy_nm must contain only finite coordinates.")
    if len(points) != first_shell_graph.point_count:
        raise ValueError("points_xy_nm must contain one coordinate per graph point.")
    if (
        point_coordinate_fingerprint(points, first_shell_graph.point_ids)
        != first_shell_graph.point_coordinate_fingerprint
    ):
        raise ValueError("first_shell_graph coordinate fingerprint must match points_xy_nm.")
    if first_shell_graph.qc_status.startswith("blocking_"):
        raise ValueError("first_shell_graph has blocking QC and cannot construct domains.")

    graph_settings = (
        first_shell_graph.duplicate_detection_enabled,
        first_shell_graph.duplicate_max_distance_nm,
        first_shell_graph.first_shell_r_min_nm,
        first_shell_graph.first_shell_r_max_nm,
    )
    requested_settings = (
        settings.duplicate_detection_enabled,
        settings.duplicate_max_distance_nm,
        settings.first_shell_r_min_nm,
        settings.first_shell_r_max_nm,
    )
    if graph_settings != requested_settings:
        raise ValueError("first_shell_graph must use the supplied settings.")
    if (
        local_order.source_ids != first_shell_graph.point_ids
        or local_order.point_count != first_shell_graph.point_count
        or local_order.neighbor_count != first_shell_graph.degree
        or local_order.physical_duplicate_qc
        != first_shell_graph.physical_duplicate_qc
        or local_order.geometry_duplicate_qc
        != first_shell_graph.geometry_duplicate_qc
    ):
        raise ValueError("local_order must match first_shell_graph point order and QC.")
    local_context = (
        local_order.coordinate_frame,
        local_order.orientation_reference,
        local_order.spatial_calibration_fingerprint,
        local_order.registration_fingerprint,
        local_order.first_shell_r_max_nm,
        local_order.min_neighbors_for_local_order,
        local_order.symmetry_m,
        local_order.bond_weighting,
    )
    expected_context = (
        first_shell_graph.coordinate_frame,
        first_shell_graph.orientation_reference,
        first_shell_graph.spatial_calibration_fingerprint,
        first_shell_graph.registration_fingerprint,
        first_shell_graph.first_shell_r_max_nm,
        settings.min_neighbors_for_local_order,
        settings.symmetry_m,
        settings.bond_weighting,
    )
    if local_context != expected_context:
        raise ValueError("local_order metadata must match graph and settings.")
    return points


def initial_m6_assignment_status(status: str) -> M6AssignmentStatus:
    if status == "duplicate_excluded":
        return "duplicate_excluded"
    if status == "invalid_position":
        return "invalid_position"
    if status == "insufficient_neighbors":
        return "insufficient_neighbors"
    return "boundary_or_disordered"


def m6_similarity_threshold(tolerance_deg: float) -> float:
    return cos(6.0 * tolerance_deg * pi / 180.0)


def point_pair_m6_similarity(
    local_order: LocalSixfoldBondOrderField,
    left: int,
    right: int,
) -> float:
    left_vector = point_m6_unit_orientation(left, local_order)
    right_vector = point_m6_unit_orientation(right, local_order)
    similarity = (left_vector * right_vector.conjugate()).real
    return min(1.0, max(-1.0, float(similarity)))


def point_domain_m6_similarity(
    point_index: int,
    domain_vector: complex,
    local_order: LocalSixfoldBondOrderField,
) -> float:
    point_vector = point_m6_unit_orientation(point_index, local_order)
    similarity = (point_vector * domain_vector.conjugate()).real
    return min(1.0, max(-1.0, float(similarity)))


def point_m6_unit_orientation(
    point_index: int,
    local_order: LocalSixfoldBondOrderField,
) -> complex:
    value = local_order.psi6[point_index]
    magnitude = local_order.q6[point_index]
    if value is None or magnitude is None or magnitude <= 0.0:
        raise ValueError("A compared M6 orientation must be defined and non-zero.")
    return value / magnitude


def component_m6_orientation_deg(
    members: tuple[int, ...],
    local_order: LocalSixfoldBondOrderField,
) -> float:
    vector = component_m6_unit_orientation(members, local_order)
    return degrees(phase(vector) / 6.0) % 60.0


def component_m6_unit_orientation(
    members: tuple[int, ...],
    local_order: LocalSixfoldBondOrderField,
) -> complex:
    vector = component_m6_complex_sum(members, local_order)
    magnitude = abs(vector)
    if magnitude > 1e-15:
        return vector / magnitude
    return _canonical_m6_medoid_orientation(members, local_order)


def component_m6_complex_sum(
    members: tuple[int, ...],
    local_order: LocalSixfoldBondOrderField,
) -> complex:
    ordered_members = sorted(members, key=lambda index: local_order.source_ids[index])
    values = tuple(local_order.psi6[index] for index in ordered_members)
    if any(value is None for value in values):
        raise ValueError("M6 component points require psi6 values.")
    return complex(
        fsum(value.real for value in values if value is not None),
        fsum(value.imag for value in values if value is not None),
    )


def _canonical_m6_medoid_orientation(
    members: tuple[int, ...],
    local_order: LocalSixfoldBondOrderField,
) -> complex:
    """Resolve an exactly cancelling mean by a deterministic component medoid."""

    ordered_members = sorted(members, key=lambda index: local_order.source_ids[index])
    vectors = {
        index: point_m6_unit_orientation(index, local_order)
        for index in ordered_members
    }
    scores = {
        index: fsum(
            float((vectors[index] * vectors[other].conjugate()).real)
            for other in ordered_members
        )
        for index in ordered_members
    }
    best_index = min(
        ordered_members,
        key=lambda index: (-scores[index], local_order.source_ids[index]),
    )
    return vectors[best_index]
