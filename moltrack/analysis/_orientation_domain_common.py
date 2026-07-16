from __future__ import annotations

from cmath import phase
from dataclasses import dataclass
from math import cos, degrees, fsum, pi

import numpy as np

from ._coordinate_fingerprint import point_coordinate_fingerprint
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .orientation_domain_models import M6AssignmentStatus


@dataclass(frozen=True)
class NormalizedM6PointState:
    point_count: int
    source_ids: tuple[str, ...]
    seed_eligible: tuple[bool, ...]
    ordered_component_id: tuple[int, ...]
    component_types: tuple[str, ...]
    assignment_status: tuple[M6AssignmentStatus, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]


def normalize_m6_point_state(
    *,
    point_count: object,
    source_ids: object,
    seed_eligible: object,
    ordered_component_id: object,
    component_types: object,
    component_type_field_name: str,
    assignment_status: object,
    edge_truncated_neighborhood: object,
    physical_duplicate_qc: object,
    geometry_duplicate_qc: object,
) -> NormalizedM6PointState:
    """Normalize the shared point-level invariants of seed and growth results."""

    normalized_count = _non_negative_integer(point_count, "point_count")
    normalized_source_ids = _per_point_values(
        source_ids,
        normalized_count,
        "source_ids",
    )
    if (
        len(set(normalized_source_ids)) != normalized_count
        or any(not isinstance(value, str) or not value for value in normalized_source_ids)
    ):
        raise ValueError("source_ids must contain one unique non-empty ID per point.")
    eligible = _boolean_values(seed_eligible, normalized_count, "seed_eligible")
    ordered_ids = tuple(
        _point_label(value, f"ordered_component_id[{index}]")
        for index, value in enumerate(
            _per_point_values(
                ordered_component_id,
                normalized_count,
                "ordered_component_id",
            )
        )
    )
    normalized_component_types = _per_point_values(
        component_types,
        normalized_count,
        component_type_field_name,
    )
    if any(
        value not in {"growth_seed", "small_ordered_island", "unassigned"}
        for value in normalized_component_types
    ):
        raise ValueError(f"{component_type_field_name} contains an unsupported value.")
    statuses = _per_point_values(
        assignment_status,
        normalized_count,
        "assignment_status",
    )
    if any(
        value
        not in {
            "assigned",
            "boundary_or_disordered",
            "insufficient_neighbors",
            "duplicate_excluded",
            "invalid_position",
        }
        for value in statuses
    ):
        raise ValueError("assignment_status contains an unsupported value.")
    edge_qc = _boolean_values(
        edge_truncated_neighborhood,
        normalized_count,
        "edge_truncated_neighborhood",
    )
    physical_qc = _boolean_values(
        physical_duplicate_qc,
        normalized_count,
        "physical_duplicate_qc",
    )
    geometry_qc = _boolean_values(
        geometry_duplicate_qc,
        normalized_count,
        "geometry_duplicate_qc",
    )
    for index, status in enumerate(statuses):
        if physical_qc[index] and geometry_qc[index]:
            raise ValueError("A point cannot have both duplicate QC flags.")
        if (physical_qc[index] or geometry_qc[index]) != (
            status == "duplicate_excluded"
        ):
            raise ValueError("Duplicate QC must correspond to duplicate_excluded status.")
    return NormalizedM6PointState(
        point_count=normalized_count,
        source_ids=normalized_source_ids,  # type: ignore[arg-type]
        seed_eligible=eligible,
        ordered_component_id=ordered_ids,
        component_types=normalized_component_types,  # type: ignore[arg-type]
        assignment_status=statuses,  # type: ignore[arg-type]
        edge_truncated_neighborhood=edge_qc,
        physical_duplicate_qc=physical_qc,
        geometry_duplicate_qc=geometry_qc,
    )


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


def _per_point_values(
    values: object,
    point_count: int,
    field_name: str,
) -> tuple[object, ...]:
    try:
        normalized = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must be an iterable.") from exc
    if len(normalized) != point_count:
        raise ValueError(f"{field_name} must contain one value per point.")
    return normalized


def _boolean_values(
    values: object,
    point_count: int,
    field_name: str,
) -> tuple[bool, ...]:
    normalized = _per_point_values(values, point_count, field_name)
    if any(not isinstance(value, bool) for value in normalized):
        raise TypeError(f"{field_name} must contain only booleans.")
    return normalized  # type: ignore[return-value]


def _point_label(value: object, field_name: str) -> int:
    normalized = _integer(value, field_name)
    if normalized < -1:
        raise ValueError(f"{field_name} must be -1 or a non-negative ID.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    normalized = _integer(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not np.isfinite(numeric) or numeric != normalized:
        raise ValueError(f"{field_name} must be an integer.")
    return normalized
