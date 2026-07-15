from __future__ import annotations

from math import atan2, pi
from typing import Sequence

import numpy as np
from scipy.spatial import Delaunay, QhullError, cKDTree

from ._first_shell_deduplication import (
    _DeduplicationResult,
    _deduplicate_points,
    _normalize_point_quality,
)
from ._first_shell_filtering import _FirstShellDistancePolicy
from ._coordinate_fingerprint import point_coordinate_fingerprint
from .first_shell_graph import FirstShellGraph
from .m6_settings import MolecularM6OrientationAnalysisSettings


def build_first_shell_graph(
    points_xy_nm: object,
    *,
    point_ids: Sequence[str] | None = None,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    mask_blocking_qc: Sequence[bool] | None = None,
    segmentation_quality_scores: Sequence[float | None] | None = None,
    topography_peak_matches: Sequence[bool | None] | None = None,
    detection_confidences: Sequence[float | None] | None = None,
    orientation_reference: str = "+x_sample_axis",
    spatial_calibration_fingerprint: str = "unspecified_calibration",
    registration_fingerprint: str = "unregistered",
) -> FirstShellGraph:
    """Build a deterministic first-shell graph from calibrated sample positions."""

    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    points = np.array(points_xy_nm, dtype=np.float64, copy=True)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points_xy_nm must have shape [N, 2].")
    if not bool(np.all(np.isfinite(points))):
        raise ValueError("points_xy_nm must contain only finite coordinates.")
    count = int(points.shape[0])
    normalized_ids = _normalize_point_ids(point_ids, points)
    point_quality = _normalize_point_quality(
        count,
        mask_blocking_qc=mask_blocking_qc,
        segmentation_quality_scores=segmentation_quality_scores,
        topography_peak_matches=topography_peak_matches,
        detection_confidences=detection_confidences,
    )

    extent_x = float(np.ptp(points[:, 0])) if count else 0.0
    extent_y = float(np.ptp(points[:, 1])) if count else 0.0
    scale_nm = max(settings.first_shell_r_max_nm, extent_x, extent_y)
    geometry_epsilon_nm = max(
        settings.geometry_absolute_tolerance_nm,
        settings.geometry_relative_tolerance * scale_nm,
    )
    distance_policy = _FirstShellDistancePolicy(
        geometry_collision_epsilon_nm=geometry_epsilon_nm,
        duplicate_detection_enabled=settings.duplicate_detection_enabled,
        duplicate_max_distance_nm=settings.duplicate_max_distance_nm,
        first_shell_r_min_nm=settings.first_shell_r_min_nm,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
    )

    deduplication = _deduplicate_points(
        points,
        point_ids=normalized_ids,
        geometry_epsilon_nm=geometry_epsilon_nm,
        duplicate_max_distance_nm=settings.duplicate_max_distance_nm,
        physical_detection_enabled=settings.duplicate_detection_enabled,
        point_quality=point_quality,
    )
    representative_indices = deduplication.representative_indices
    ambiguous_edges: tuple[tuple[int, int], ...] = ()
    qc_status = "valid"
    if count < 2:
        return _make_graph(
            points=points,
            point_ids=normalized_ids,
            candidate_edges=(),
            geometry_epsilon_nm=geometry_epsilon_nm,
            settings=settings,
            distance_policy=distance_policy,
            orientation_reference=orientation_reference,
            spatial_calibration_fingerprint=spatial_calibration_fingerprint,
            registration_fingerprint=registration_fingerprint,
            construction_method="rank0_empty",
            deduplication=deduplication,
            ambiguous_edges=(),
            qc_status=qc_status,
        )

    representative_points = points[np.asarray(representative_indices, dtype=np.int64)]
    centered = representative_points - np.mean(representative_points, axis=0)
    _u, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    affine_rank = int(np.count_nonzero(singular_values > settings.geometry_relative_tolerance * scale_nm))
    if affine_rank == 0:
        candidate_edges: tuple[tuple[int, int], ...] = ()
        construction_method = "rank0_empty"
    elif affine_rank == 1:
        axis = np.array(vh[0], dtype=np.float64, copy=True)
        for component in axis:
            if abs(float(component)) > settings.geometry_relative_tolerance:
                if component < 0.0:
                    axis *= -1.0
                break
        projections = points @ axis
        ordered = sorted(
            representative_indices,
            key=lambda index: (float(projections[index]), normalized_ids[index]),
        )
        candidate_edges = tuple(
            tuple(sorted((left, right)))
            for left, right in zip(ordered, ordered[1:])
        )
        construction_method = "rank1_adjacent_projection"
    else:
        try:
            candidate_edges, ambiguous_edges = _delaunay_edges(
                points,
                representative_indices=representative_indices,
                point_ids=normalized_ids,
                geometry_relative_tolerance=settings.geometry_relative_tolerance,
            )
            construction_method = "delaunay_first_shell"
        except QhullError:
            candidate_edges = _rank2_radius_fallback_edges(
                points,
                representative_indices=representative_indices,
                radius_nm=settings.first_shell_r_max_nm,
            )
            construction_method = "rank2_radius_fallback"
            qc_status = "blocking_rank2_radius_fallback"

    return _make_graph(
        points=points,
        point_ids=normalized_ids,
        candidate_edges=candidate_edges,
        geometry_epsilon_nm=geometry_epsilon_nm,
        settings=settings,
        distance_policy=distance_policy,
        orientation_reference=orientation_reference,
        spatial_calibration_fingerprint=spatial_calibration_fingerprint,
        registration_fingerprint=registration_fingerprint,
        construction_method=construction_method,
        deduplication=deduplication,
        ambiguous_edges=ambiguous_edges,
        qc_status=qc_status,
    )


def _normalize_point_ids(point_ids: Sequence[str] | None, points: np.ndarray) -> tuple[str, ...]:
    point_count = int(points.shape[0])
    if point_ids is None:
        canonical_order = sorted(
            range(point_count),
            key=lambda index: (float(points[index, 0]), float(points[index, 1]), index),
        )
        generated = [""] * point_count
        for canonical_index, original_index in enumerate(canonical_order):
            generated[original_index] = f"point-{canonical_index}"
        return tuple(generated)
    normalized = tuple(point_ids)
    if len(normalized) != point_count:
        raise ValueError("point_ids must contain one value per point.")
    return normalized


def _make_graph(
    *,
    points: np.ndarray,
    point_ids: tuple[str, ...],
    candidate_edges: tuple[tuple[int, int], ...],
    geometry_epsilon_nm: float,
    settings: MolecularM6OrientationAnalysisSettings,
    distance_policy: _FirstShellDistancePolicy,
    orientation_reference: str,
    spatial_calibration_fingerprint: str,
    registration_fingerprint: str,
    construction_method: str,
    deduplication: _DeduplicationResult,
    ambiguous_edges: tuple[tuple[int, int], ...],
    qc_status: str,
) -> FirstShellGraph:
    candidate_records: list[tuple[tuple[int, int], float, float]] = []
    for i, j in candidate_edges:
        delta = points[j] - points[i]
        distance_nm = float(np.linalg.norm(delta))
        candidate_records.append(
            (
                (i, j),
                distance_nm,
                float(atan2(float(delta[1]), float(delta[0])) % (2.0 * pi)),
            )
        )
    candidate_records.sort(key=lambda record: record[0])
    retained = [
        record
        for record in candidate_records
        if distance_policy.classify(record[1]) == "first_shell"
    ]
    degree = [0] * len(point_ids)
    for (i, j), _distance, _angle in retained:
        degree[i] += 1
        degree[j] += 1
    short_pair_qc = [False] * len(point_ids)
    for (i, j), distance_nm, _angle in candidate_records:
        if distance_policy.classify(distance_nm) == "short_non_shell_pair":
            short_pair_qc[i] = True
            short_pair_qc[j] = True
    return FirstShellGraph(
        point_ids=point_ids,
        point_count=len(point_ids),
        edges_ij=tuple(record[0] for record in retained),
        distances_nm=tuple(record[1] for record in retained),
        angles_rad=tuple(record[2] for record in retained),
        degree=tuple(degree),
        geometry_collision_epsilon_nm=geometry_epsilon_nm,
        duplicate_max_distance_nm=settings.duplicate_max_distance_nm,
        first_shell_r_min_nm=settings.first_shell_r_min_nm,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference=orientation_reference,
        spatial_calibration_fingerprint=spatial_calibration_fingerprint,
        registration_fingerprint=registration_fingerprint,
        point_coordinate_fingerprint=point_coordinate_fingerprint(points, point_ids),
        construction_method=construction_method,
        qc_status=qc_status,
        duplicate_detection_enabled=settings.duplicate_detection_enabled,
        representative_source_ids=deduplication.representative_source_ids,
        duplicate_parent_component_ids=deduplication.parent_component_ids,
        duplicate_parent_component_diameters_nm=deduplication.parent_component_diameters_nm,
        duplicate_group_ids=deduplication.group_ids,
        duplicate_group_diameters_nm=deduplication.group_diameters_nm,
        duplicate_chain_qc=deduplication.chain_qc,
        physical_duplicate_qc=deduplication.physical_duplicate_qc,
        geometry_duplicate_qc=deduplication.geometry_duplicate_qc,
        short_non_shell_pair_qc=tuple(short_pair_qc),
        ambiguous_edges_ij=ambiguous_edges,
        delaunay_degeneracy_qc=bool(ambiguous_edges),
        candidate_edges_ij=tuple(record[0] for record in candidate_records),
        candidate_distances_nm=tuple(record[1] for record in candidate_records),
        candidate_angles_rad=tuple(record[2] for record in candidate_records),
    )


def _delaunay_edges(
    points: np.ndarray,
    *,
    representative_indices: tuple[int, ...],
    point_ids: tuple[str, ...],
    geometry_relative_tolerance: float,
) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    canonical_indices = tuple(
        sorted(
            representative_indices,
            key=lambda index: (
                float(points[index, 0]),
                float(points[index, 1]),
                point_ids[index],
            ),
        )
    )
    canonical_points = points[np.asarray(canonical_indices, dtype=np.int64)]
    triangulation = Delaunay(canonical_points)
    edge_opposites: dict[tuple[int, int], list[int]] = {}
    for simplex in triangulation.simplices:
        original = tuple(canonical_indices[int(index)] for index in simplex)
        for left, right, opposite in (
            (original[0], original[1], original[2]),
            (original[1], original[2], original[0]),
            (original[2], original[0], original[1]),
        ):
            edge = tuple(sorted((left, right)))
            edge_opposites.setdefault(edge, []).append(opposite)
    ambiguous: set[tuple[int, int]] = set()
    for edge, opposites in edge_opposites.items():
        if len(opposites) != 2:
            continue
        indices = (edge[0], edge[1], opposites[0], opposites[1])
        if _points_are_cocircular(
            points[np.asarray(indices, dtype=np.int64)],
            relative_tolerance=geometry_relative_tolerance,
        ):
            ambiguous.add(edge)
    retained = set(edge_opposites) - ambiguous
    return tuple(sorted(retained)), tuple(sorted(ambiguous))


def _points_are_cocircular(
    points: np.ndarray,
    *,
    relative_tolerance: float,
) -> bool:
    centered = points - np.mean(points, axis=0)
    scale = max(float(np.ptp(centered[:, 0])), float(np.ptp(centered[:, 1])))
    if scale == 0.0:
        return True
    normalized = centered / scale
    matrix = np.column_stack(
        (
            normalized[:, 0],
            normalized[:, 1],
            np.sum(normalized * normalized, axis=1),
            np.ones(4, dtype=np.float64),
        )
    )
    return abs(float(np.linalg.det(matrix))) <= relative_tolerance


def _rank2_radius_fallback_edges(
    points: np.ndarray,
    *,
    representative_indices: tuple[int, ...],
    radius_nm: float,
) -> tuple[tuple[int, int], ...]:
    selected = points[np.asarray(representative_indices, dtype=np.int64)]
    local_pairs = cKDTree(selected).query_pairs(radius_nm, output_type="set")
    return tuple(
        sorted(
            tuple(sorted((representative_indices[left], representative_indices[right])))
            for left, right in local_pairs
        )
    )
