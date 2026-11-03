"""Materialize final, auditable lattice-domain metrics from seed/grow output."""

from __future__ import annotations

from collections.abc import Sequence
from math import atan2, cos, degrees, fsum, isfinite, pi, sin

import numpy as np

from ._coordinate_fingerprint import point_coordinate_fingerprint
from ._first_shell_graph_fingerprint import first_shell_graph_fingerprint
from .first_shell_graph import FirstShellGraph
from .lattice_domain_models import (
    LatticeDomain,
    LatticeDomainAnalysis,
    LatticeDomainAnalysisSettings,
    LatticeDomainDominantSymmetry,
    LatticeDomainGeometry,
    LatticeDomainInternalBond,
    LatticeDomainOrientationReferenceChannel,
    LatticeDomainQc,
    M3M6OrientationRelationStatus,
    lattice_domain_analysis_settings_fingerprint,
    lattice_domain_id_from_members,
)
from .lattice_domain_seed_growth_models import (
    LatticeDomainSeedComponent,
    LatticeDomainSeedGrowthResult,
    lattice_domain_seed_growth_result_fingerprint,
)
from .local_multisymmetry_bond_order import LocalMultiSymmetryBondOrderField
from .local_symmetry_evidence_models import LocalSymmetryEvidenceField


_CENTROID_ALIAS = "symmetry_alias_unresolvable_from_centroids"


def build_lattice_domain_analysis(
    points_xy_nm: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    seed_growth: LatticeDomainSeedGrowthResult,
    settings: LatticeDomainAnalysisSettings | None = None,
    point_footprint_area_nm2: Sequence[float | None] | None = None,
    point_footprint_clipped_by_fov: Sequence[bool] | None = None,
    valid_fov_area_nm2: float | None = None,
) -> LatticeDomainAnalysis:
    """Build final domains without changing the seed/grow partition."""

    if settings is None:
        settings = LatticeDomainAnalysisSettings()
    if not isinstance(settings, LatticeDomainAnalysisSettings):
        raise TypeError("settings must be LatticeDomainAnalysisSettings.")
    points = _validate_inputs(
        points_xy_nm,
        graph=first_shell_graph,
        local_order=local_order,
        local_evidence=local_evidence,
        seed_growth=seed_growth,
    )
    footprint_areas = _optional_footprint_areas(
        point_footprint_area_nm2,
        point_count=first_shell_graph.point_count,
    )
    footprint_clipped = _optional_boolean_values(
        point_footprint_clipped_by_fov,
        point_count=first_shell_graph.point_count,
    )
    valid_fov_area = _optional_positive_float(valid_fov_area_nm2, "valid_fov_area_nm2")
    if footprint_areas is None and valid_fov_area is not None:
        raise ValueError("valid_fov_area_nm2 requires point footprint areas.")
    if (
        footprint_areas is not None
        and valid_fov_area is not None
        and fsum(value for value in footprint_areas if value is not None)
        > valid_fov_area + 1e-10
    ):
        raise ValueError("Point footprint areas cannot exceed the valid FOV area.")
    valid_indices = tuple(
        index
        for index in range(first_shell_graph.point_count)
        if not first_shell_graph.physical_duplicate_qc[index]
        and not first_shell_graph.geometry_duplicate_qc[index]
        and local_order.computation_status[index] != "invalid_position"
    )
    valid_count = len(valid_indices)
    valid_set = set(valid_indices)
    boundary_indices = tuple(
        index
        for index, role in enumerate(seed_growth.point_role)
        if role == "boundary" and index in valid_set
    )
    components = tuple(
        _measure_component(
            component,
            points=points,
            graph=first_shell_graph,
            local_order=local_order,
            local_evidence=local_evidence,
            seed_growth=seed_growth,
            settings=settings,
            valid_representative_count=valid_count,
            footprint_areas=footprint_areas,
            footprint_clipped=footprint_clipped,
            valid_fov_area_nm2=valid_fov_area,
        )
        for component in seed_growth.components
        if component.seed_state != "proto_seed"
    )
    domains = tuple(
        sorted(
            (value for value in components if value.component_type == "full_domain"),
            key=lambda value: value.lattice_domain_id,
        )
    )
    islands = tuple(
        sorted(
            (
                value
                for value in components
                if value.component_type == "small_ordered_island"
            ),
            key=lambda value: value.lattice_domain_id,
        )
    )
    assignments: list[str | None] = [None] * first_shell_graph.point_count
    for component in domains + islands:
        for point_index in component.point_indices:
            assignments[point_index] = component.lattice_domain_id
    classified_count = sum(value.molecule_count for value in domains + islands)
    first_shell_bonds = _build_frame_first_shell_bonds(
        points,
        graph=first_shell_graph,
    )
    return LatticeDomainAnalysis(
        source_ids=first_shell_graph.point_ids,
        point_count=first_shell_graph.point_count,
        points_xy_nm=tuple((float(point[0]), float(point[1])) for point in points),
        valid_representative=tuple(
            index in valid_set for index in range(first_shell_graph.point_count)
        ),
        point_role=seed_growth.point_role,
        boundary_reason=seed_growth.boundary_reason,
        point_lattice_domain_id=tuple(assignments),
        first_shell_bonds=first_shell_bonds,
        domains=domains,
        small_ordered_islands=islands,
        valid_representative_count=valid_count,
        classified_molecule_count=classified_count,
        classified_molecule_fraction=(classified_count / valid_count if valid_count else 0.0),
        boundary_point_count=len(boundary_indices),
        boundary_point_fraction=(len(boundary_indices) / valid_count if valid_count else 0.0),
        settings=settings,
        coordinate_frame=first_shell_graph.coordinate_frame,
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
        local_order_analysis_fingerprint=(
            local_order.provenance.analysis_settings_fingerprint
        ),
        local_symmetry_evidence_settings_fingerprint=(
            local_evidence.settings_fingerprint
        ),
        local_symmetry_bond_evidence_fingerprint=(
            local_evidence.bond_evidence_fingerprint
        ),
        seed_growth_settings_fingerprint=seed_growth.settings_fingerprint,
        seed_growth_result_fingerprint=(
            lattice_domain_seed_growth_result_fingerprint(seed_growth)
        ),
        settings_fingerprint=lattice_domain_analysis_settings_fingerprint(settings),
    )


def _build_frame_first_shell_bonds(
    points_xy_nm: object,
    *,
    graph: FirstShellGraph,
) -> tuple[LatticeDomainInternalBond, ...]:
    points = np.asarray(points_xy_nm, dtype=np.float64).reshape((-1, 2))
    if points.shape != (graph.point_count, 2):
        raise ValueError("points_xy_nm must match the first-shell graph.")
    return tuple(
        sorted(
            (
                _internal_bond(
                    left,
                    right,
                    float(distance),
                    points=points,
                    graph=graph,
                )
                for (left, right), distance in zip(
                    graph.edges_ij,
                    graph.distances_nm,
                )
            ),
            key=lambda value: value.source_ids,
        )
    )


def _measure_component(
    component: LatticeDomainSeedComponent,
    *,
    points: np.ndarray,
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    seed_growth: LatticeDomainSeedGrowthResult,
    settings: LatticeDomainAnalysisSettings,
    valid_representative_count: int,
    footprint_areas: tuple[float | None, ...] | None,
    footprint_clipped: tuple[bool, ...] | None,
    valid_fov_area_nm2: float | None,
) -> LatticeDomain:
    member_indices = component.point_indices
    core_indices = component.core_point_indices
    halo_indices = component.halo_point_indices
    member_records = _canonical_members(member_indices, graph=graph)
    core_records = _canonical_members(core_indices, graph=graph)
    halo_records = _canonical_members(halo_indices, graph=graph)
    ordered_indices = tuple(record[0] for record in member_records)
    coordinates = points[np.asarray(ordered_indices, dtype=np.int64)]
    molecule_count = len(member_indices)
    centroid_x = fsum(float(points[index, 0]) for index in ordered_indices) / molecule_count
    centroid_y = fsum(float(points[index, 1]) for index in ordered_indices) / molecule_count
    member_set = set(member_indices)
    internal_bonds = tuple(
        sorted(
            (
                _internal_bond(left, right, float(distance), points=points, graph=graph)
                for (left, right), distance in zip(graph.edges_ij, graph.distances_nm)
                if left in member_set and right in member_set
            ),
            key=lambda value: value.source_ids,
        )
    )
    internal_distances = tuple(sorted(value.distance_nm for value in internal_bonds))
    bond_statistics = _bond_statistics(
        internal_distances,
        minimum_count=settings.min_bonds_for_length_stats,
    )
    graph_disconnected = not _is_connected(member_set, graph.edges_ij)
    adjacent_boundary_indices = {
        neighbor
        for left, right in graph.edges_ij
        for member, neighbor in ((left, right), (right, left))
        if member in member_set and seed_growth.point_role[neighbor] == "boundary"
    }
    alias_unresolvable = any(
        local_order.symmetry_resolvability_status[index] == _CENTROID_ALIAS
        for index in member_indices
    )
    dominant_symmetry: LatticeDomainDominantSymmetry = component.symmetry_model
    theta3_prototype = (
        _channel_prototype(core_records, local_order.theta3_lattice_deg)
        if component.core_theta3_deg is not None
        else None
    )
    theta6_prototype = (
        _channel_prototype(core_records, local_order.theta6_deg)
        if component.core_theta6_deg is not None
        else None
    )
    reference_channel, relation_status, relation_offset = _orientation_relation(
        dominant_symmetry,
        theta3=theta3_prototype,
        theta6=theta6_prototype,
    )
    footprint_area = _component_footprint_area(member_indices, footprint_areas)
    footprint_fraction = (
        footprint_area / valid_fov_area_nm2
        if footprint_area is not None and valid_fov_area_nm2 is not None
        else None
    )
    robust_cv = bond_statistics[3]
    geometry = LatticeDomainGeometry(
        centroid_x_nm=centroid_x,
        centroid_y_nm=centroid_y,
        min_x_nm=float(np.min(coordinates[:, 0])),
        min_y_nm=float(np.min(coordinates[:, 1])),
        max_x_nm=float(np.max(coordinates[:, 0])),
        max_y_nm=float(np.max(coordinates[:, 1])),
        internal_first_shell_bond_count=len(internal_distances),
        internal_first_shell_bonds=internal_bonds,
        median_bond_length_nm=bond_statistics[0],
        bond_length_mad_nm=bond_statistics[1],
        bond_length_iqr_nm=bond_statistics[2],
        bond_length_robust_cv=robust_cv,
        footprint_area_nm2=footprint_area,
        footprint_fraction_of_valid_fov=footprint_fraction,
    )
    qc = LatticeDomainQc(
        edge_truncated_neighborhood=any(
            local_order.edge_truncated_neighborhood[index] for index in member_indices
        ),
        graph_disconnected=graph_disconnected,
        insufficient_bonds_for_length_stats=bond_statistics[0] is None,
        bond_length_heterogeneity=(
            robust_cv is not None
            and robust_cv >= settings.bond_length_robust_cv_qc_threshold
        ),
        footprint_unavailable=footprint_area is None,
        footprint_clipped_by_fov=(
            any(footprint_clipped[index] for index in member_indices)
            if footprint_clipped is not None
            else False
        ),
        symmetry_alias_unresolvable_from_centroids=alias_unresolvable,
    )
    component_type = (
        "full_domain"
        if molecule_count >= settings.min_domain_size
        else "small_ordered_island"
    )
    domain_id = lattice_domain_id_from_members(
        tuple(
            (graph.point_ids[index], float(points[index, 0]), float(points[index, 1]))
            for index in ordered_indices
        ),
        coordinate_frame=graph.coordinate_frame,
    )
    return LatticeDomain(
        lattice_domain_id=domain_id,
        source_component_id=component.component_id,
        component_type=component_type,
        point_indices=ordered_indices,
        source_ids=tuple(record[1] for record in member_records),
        core_point_indices=tuple(record[0] for record in core_records),
        core_source_ids=tuple(record[1] for record in core_records),
        halo_point_indices=tuple(record[0] for record in halo_records),
        halo_source_ids=tuple(record[1] for record in halo_records),
        molecule_count=molecule_count,
        core_size=component.core_size,
        halo_size=component.halo_size,
        molecule_fraction_of_valid_representatives=(
            molecule_count / valid_representative_count
            if valid_representative_count
            else 0.0
        ),
        adjacent_boundary_point_count=len(adjacent_boundary_indices),
        adjacent_boundary_source_ids=tuple(
            sorted(graph.point_ids[index] for index in adjacent_boundary_indices)
        ),
        adjacent_boundary_point_fraction=(
            len(adjacent_boundary_indices)
            / (molecule_count + len(adjacent_boundary_indices))
            if adjacent_boundary_indices
            else 0.0
        ),
        theta3_lattice_prototype_deg=theta3_prototype,
        theta6_prototype_deg=theta6_prototype,
        theta3_lattice_spread_deg=component.assigned_theta3_spread_deg,
        theta6_spread_deg=component.assigned_theta6_spread_deg,
        dominant_symmetry=dominant_symmetry,
        orientation_reference_channel=reference_channel,
        m3_m6_orientation_relation_status=relation_status,
        m3_m6_orientation_offset_deg=relation_offset,
        confidence=_component_confidence(
            component,
            local_order=local_order,
            local_evidence=local_evidence,
            graph=graph,
        ),
        geometry=geometry,
        qc=qc,
    )


def _orientation_relation(
    symmetry: LatticeDomainDominantSymmetry,
    *,
    theta3: float | None,
    theta6: float | None,
) -> tuple[
    LatticeDomainOrientationReferenceChannel,
    M3M6OrientationRelationStatus,
    float | None,
]:
    if symmetry == "ambiguous":
        return "unavailable", "symmetry_alias_unresolvable_from_centroids", None
    if symmetry == "trifold":
        return "m3_lattice", "not_applicable", None
    if symmetry == "sixfold":
        return "m6", "not_applicable", None
    if theta3 is None or theta6 is None:
        return "unavailable", "unavailable", None
    difference = abs((theta3 % 60.0) - (theta6 % 60.0))
    return "joint", "available", min(difference, 60.0 - difference)


def _component_confidence(
    component: LatticeDomainSeedComponent,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    graph: FirstShellGraph,
) -> float:
    point_values: list[tuple[str, float]] = []
    for index in component.core_point_indices:
        classification = local_evidence.classification_confidence[index]
        model_score = _model_score(index, component.symmetry_model, local_evidence)
        orientation_values = _orientation_confidences(
            index,
            component.symmetry_model,
            local_order,
        )
        values = (classification, model_score) + orientation_values
        if any(value is None for value in values):
            point_confidence = 0.0
        else:
            point_confidence = min(float(value) for value in values if value is not None)
        point_values.append((graph.point_ids[index], point_confidence))
    ordered = tuple(value for _source_id, value in sorted(point_values))
    return fsum(ordered) / len(ordered)


def _model_score(
    point_index: int,
    symmetry: str,
    local_evidence: LocalSymmetryEvidenceField,
) -> float | None:
    if symmetry == "trifold":
        return local_evidence.trifold_model_score[point_index]
    if symmetry == "sixfold":
        return local_evidence.sixfold_model_score[point_index]
    return local_evidence.mixed_model_score[point_index]


def _orientation_confidences(
    point_index: int,
    symmetry: str,
    local_order: LocalMultiSymmetryBondOrderField,
) -> tuple[float | None, ...]:
    if symmetry == "trifold":
        return (local_order.m3_orientation_confidence[point_index],)
    if symmetry == "sixfold":
        return (local_order.m6_orientation_confidence[point_index],)
    return (
        local_order.m3_orientation_confidence[point_index],
        local_order.m6_orientation_confidence[point_index],
    )


def _validate_inputs(
    points_xy_nm: object,
    *,
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    seed_growth: LatticeDomainSeedGrowthResult,
) -> np.ndarray:
    if not isinstance(graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be FirstShellGraph.")
    if not isinstance(local_order, LocalMultiSymmetryBondOrderField):
        raise TypeError("local_order must be LocalMultiSymmetryBondOrderField.")
    if not isinstance(local_evidence, LocalSymmetryEvidenceField):
        raise TypeError("local_evidence must be LocalSymmetryEvidenceField.")
    if not isinstance(seed_growth, LatticeDomainSeedGrowthResult):
        raise TypeError("seed_growth must be LatticeDomainSeedGrowthResult.")
    points = np.asarray(points_xy_nm, dtype=np.float64)
    if points.size == 0:
        points = points.reshape((0, 2))
    if points.shape != (graph.point_count, 2):
        raise ValueError("points_xy_nm must have shape [point_count, 2].")
    if not bool(np.all(np.isfinite(points))):
        raise ValueError("points_xy_nm must contain finite values.")
    if (
        point_coordinate_fingerprint(points, graph.point_ids)
        != graph.point_coordinate_fingerprint
    ):
        raise ValueError("points_xy_nm must match the first-shell graph fingerprint.")
    if not (
        graph.point_ids == local_order.source_ids
        == local_evidence.source_ids
        == seed_growth.source_ids
    ):
        raise ValueError("Lattice-domain inputs must preserve graph point order.")
    graph_fingerprint = first_shell_graph_fingerprint(graph)
    if (
        seed_growth.first_shell_graph_fingerprint != graph_fingerprint
        or seed_growth.local_order_analysis_fingerprint
        != local_order.provenance.analysis_settings_fingerprint
        or seed_growth.local_symmetry_evidence_settings_fingerprint
        != local_evidence.settings_fingerprint
        or seed_growth.local_symmetry_bond_evidence_fingerprint
        != local_evidence.bond_evidence_fingerprint
    ):
        raise ValueError("Lattice-domain inputs must preserve seed/grow provenance.")
    return points


def _canonical_members(
    indices: tuple[int, ...],
    *,
    graph: FirstShellGraph,
) -> tuple[tuple[int, str], ...]:
    return tuple(
        sorted(
            ((index, graph.point_ids[index]) for index in indices),
            key=lambda value: value[1],
        )
    )


def _internal_bond(
    left: int,
    right: int,
    distance_nm: float,
    *,
    points: np.ndarray,
    graph: FirstShellGraph,
) -> LatticeDomainInternalBond:
    first, second = sorted((left, right), key=lambda index: graph.point_ids[index])
    delta_x = float(points[second, 0] - points[first, 0])
    delta_y = float(points[second, 1] - points[first, 1])
    return LatticeDomainInternalBond(
        source_ids=(graph.point_ids[first], graph.point_ids[second]),
        distance_nm=distance_nm,
        axial_angle_deg=degrees(atan2(delta_y, delta_x)) % 180.0,
    )


def _channel_prototype(
    member_records: tuple[tuple[int, str], ...],
    values: tuple[float | None, ...],
) -> float:
    angles = tuple(values[index] for index, _source_id in member_records)
    if any(value is None for value in angles):
        raise ValueError("A domain core orientation channel cannot contain missing angles.")
    phases = tuple(
        float(value) * 2.0 * pi / 60.0 for value in angles if value is not None
    )
    x = fsum(cos(value) for value in phases)
    y = fsum(sin(value) for value in phases)
    if abs(x) < 1e-12 and abs(y) < 1e-12:
        return min(float(value) % 60.0 for value in angles if value is not None)
    return degrees(atan2(y, x)) / 6.0 % 60.0


def _is_connected(
    members: set[int],
    edges: tuple[tuple[int, int], ...],
) -> bool:
    if len(members) <= 1:
        return True
    adjacency = {index: set() for index in members}
    for left, right in edges:
        if left in members and right in members:
            adjacency[left].add(right)
            adjacency[right].add(left)
    reached: set[int] = set()
    stack = [min(members)]
    while stack:
        current = stack.pop()
        if current in reached:
            continue
        reached.add(current)
        stack.extend(adjacency[current] - reached)
    return reached == members


def _bond_statistics(
    distances_nm: tuple[float, ...],
    *,
    minimum_count: int,
) -> tuple[float | None, float | None, float | None, float | None]:
    if len(distances_nm) < minimum_count:
        return None, None, None, None
    distances = np.asarray(distances_nm, dtype=np.float64)
    median = float(np.median(distances))
    if median <= 0.0:
        return None, None, None, None
    mad = float(np.median(np.abs(distances - median)))
    q25, q75 = np.percentile(distances, (25.0, 75.0))
    return median, mad, float(q75 - q25), 1.4826 * mad / median


def _component_footprint_area(
    member_indices: tuple[int, ...],
    footprint_areas: tuple[float | None, ...] | None,
) -> float | None:
    if footprint_areas is None or any(
        footprint_areas[index] is None for index in member_indices
    ):
        return None
    return fsum(
        float(footprint_areas[index])
        for index in member_indices
        if footprint_areas[index] is not None
    )


def _optional_footprint_areas(
    values: Sequence[float | None] | None,
    *,
    point_count: int,
) -> tuple[float | None, ...] | None:
    if values is None:
        return None
    normalized = tuple(
        None if value is None else _non_negative_float(value, "point_footprint_area_nm2")
        for value in values
    )
    if len(normalized) != point_count:
        raise ValueError("point_footprint_area_nm2 must contain one value per point.")
    return normalized


def _optional_boolean_values(
    values: Sequence[bool] | None,
    *,
    point_count: int,
) -> tuple[bool, ...] | None:
    if values is None:
        return None
    normalized = tuple(values)
    if len(normalized) != point_count or any(not isinstance(value, bool) for value in normalized):
        raise ValueError("point_footprint_clipped_by_fov must contain one boolean per point.")
    return normalized


def _optional_positive_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized
