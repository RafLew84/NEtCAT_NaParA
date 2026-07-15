from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Sequence

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class _DeduplicationResult:
    representative_indices: tuple[int, ...]
    representative_source_ids: tuple[str, ...]
    parent_component_ids: tuple[str | None, ...]
    parent_component_diameters_nm: tuple[float | None, ...]
    group_ids: tuple[str | None, ...]
    group_diameters_nm: tuple[float | None, ...]
    chain_qc: tuple[bool, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]


@dataclass(frozen=True)
class _PointQuality:
    mask_blocking_qc: tuple[bool, ...]
    segmentation_quality_scores: tuple[float | None, ...]
    topography_peak_matches: tuple[bool | None, ...]
    detection_confidences: tuple[float | None, ...]


def _normalize_point_quality(
    point_count: int,
    *,
    mask_blocking_qc: Sequence[bool] | None,
    segmentation_quality_scores: Sequence[float | None] | None,
    topography_peak_matches: Sequence[bool | None] | None,
    detection_confidences: Sequence[float | None] | None,
) -> _PointQuality:
    blocking = _aligned_values(mask_blocking_qc, point_count, False, "mask_blocking_qc")
    if any(not isinstance(value, bool) for value in blocking):
        raise TypeError("mask_blocking_qc values must be booleans.")
    segmentation = _optional_finite_values(
        segmentation_quality_scores,
        point_count,
        "segmentation_quality_scores",
    )
    topography = _aligned_values(
        topography_peak_matches,
        point_count,
        None,
        "topography_peak_matches",
    )
    if any(value is not None and not isinstance(value, bool) for value in topography):
        raise TypeError("topography_peak_matches values must be booleans or None.")
    confidence = _optional_finite_values(
        detection_confidences,
        point_count,
        "detection_confidences",
    )
    return _PointQuality(
        mask_blocking_qc=tuple(blocking),
        segmentation_quality_scores=segmentation,
        topography_peak_matches=tuple(topography),
        detection_confidences=confidence,
    )


def _deduplicate_points(
    points: np.ndarray,
    *,
    point_ids: tuple[str, ...],
    geometry_epsilon_nm: float,
    duplicate_max_distance_nm: float,
    physical_detection_enabled: bool,
    point_quality: _PointQuality,
) -> _DeduplicationResult:
    point_count = len(point_ids)
    if point_count == 0:
        return _empty_deduplication_result(())
    tree = cKDTree(points)
    collision_pairs = tree.query_pairs(geometry_epsilon_nm, output_type="set")
    geometry_clusters = list(_connected_components(point_count, collision_pairs))
    geometry_representatives: dict[int, int] = {}
    for cluster in geometry_clusters:
        representative = _best_quality_representative(cluster, point_ids, point_quality)
        for index in cluster:
            geometry_representatives[index] = representative

    parent_pairs = (
        tree.query_pairs(duplicate_max_distance_nm, output_type="set")
        if physical_detection_enabled
        else collision_pairs
    )
    parent_components = _connected_components(point_count, parent_pairs)
    representative_ids = list(point_ids)
    parent_ids: list[str | None] = [None] * point_count
    parent_diameters: list[float | None] = [None] * point_count
    group_ids: list[str | None] = [None] * point_count
    group_diameters: list[float | None] = [None] * point_count
    chain_qc = [False] * point_count
    geometry_qc = [False] * point_count
    physical_qc = [False] * point_count
    representatives: list[int] = []

    for component in parent_components:
        if len(component) == 1:
            representatives.append(component[0])
            continue
        parent_diameter = _cluster_diameter(points, component)
        parent_id = _stable_component_id("duplicate-parent", point_ids, component)
        component_set = set(component)
        initial_clusters = [
            cluster for cluster in geometry_clusters if set(cluster).issubset(component_set)
        ]
        clusters = (
            _merge_complete_linkage_clusters(
                points,
                initial_clusters,
                max_diameter_nm=duplicate_max_distance_nm,
                point_ids=point_ids,
            )
            if physical_detection_enabled
            else tuple(initial_clusters)
        )
        is_chain = physical_detection_enabled and parent_diameter > duplicate_max_distance_nm
        for index in component:
            parent_ids[index] = parent_id
            parent_diameters[index] = parent_diameter
            chain_qc[index] = is_chain
        for cluster in clusters:
            geometry_cluster_representatives = tuple(
                sorted({geometry_representatives[index] for index in cluster})
            )
            representative = _best_quality_representative(
                geometry_cluster_representatives,
                point_ids,
                point_quality,
            )
            representatives.append(representative)
            group_id = _stable_component_id("duplicate-group", point_ids, cluster)
            group_diameter = _cluster_diameter(points, cluster)
            for index in cluster:
                representative_ids[index] = point_ids[representative]
                group_ids[index] = group_id
                group_diameters[index] = group_diameter
                if index != geometry_representatives[index]:
                    geometry_qc[index] = True
                elif index != representative:
                    physical_qc[index] = True

    representatives.sort(
        key=lambda index: (
            float(points[index, 0]),
            float(points[index, 1]),
            point_ids[index],
        )
    )
    return _DeduplicationResult(
        representative_indices=tuple(representatives),
        representative_source_ids=tuple(representative_ids),
        parent_component_ids=tuple(parent_ids),
        parent_component_diameters_nm=tuple(parent_diameters),
        group_ids=tuple(group_ids),
        group_diameters_nm=tuple(group_diameters),
        chain_qc=tuple(chain_qc),
        physical_duplicate_qc=tuple(physical_qc),
        geometry_duplicate_qc=tuple(geometry_qc),
    )


def _aligned_values(
    values: Sequence[object] | None,
    point_count: int,
    default: object,
    field_name: str,
) -> tuple[object, ...]:
    if values is None:
        return (default,) * point_count
    normalized = tuple(values)
    if len(normalized) != point_count:
        raise ValueError(f"{field_name} must contain one value per point.")
    return normalized


def _optional_finite_values(
    values: Sequence[float | None] | None,
    point_count: int,
    field_name: str,
) -> tuple[float | None, ...]:
    normalized = _aligned_values(values, point_count, None, field_name)
    result: list[float | None] = []
    for value in normalized:
        if value is None:
            result.append(None)
            continue
        numeric = float(value)
        if not np.isfinite(numeric):
            raise ValueError(f"{field_name} values must be finite or None.")
        result.append(numeric)
    return tuple(result)


def _best_quality_representative(
    indices: Sequence[int],
    point_ids: tuple[str, ...],
    quality: _PointQuality,
) -> int:
    def rank(index: int) -> tuple[object, ...]:
        segmentation = quality.segmentation_quality_scores[index]
        confidence = quality.detection_confidences[index]
        return (
            quality.mask_blocking_qc[index],
            segmentation is None,
            0.0 if segmentation is None else -segmentation,
            quality.topography_peak_matches[index] is not True,
            confidence is None,
            0.0 if confidence is None else -confidence,
            point_ids[index],
        )

    return min(indices, key=rank)


def _empty_deduplication_result(point_ids: tuple[str, ...]) -> _DeduplicationResult:
    point_count = len(point_ids)
    return _DeduplicationResult(
        representative_indices=tuple(range(point_count)),
        representative_source_ids=point_ids,
        parent_component_ids=(None,) * point_count,
        parent_component_diameters_nm=(None,) * point_count,
        group_ids=(None,) * point_count,
        group_diameters_nm=(None,) * point_count,
        chain_qc=(False,) * point_count,
        physical_duplicate_qc=(False,) * point_count,
        geometry_duplicate_qc=(False,) * point_count,
    )


def _connected_components(
    point_count: int,
    pairs: set[tuple[int, int]],
) -> tuple[tuple[int, ...], ...]:
    adjacency = [set() for _ in range(point_count)]
    for left, right in pairs:
        adjacency[left].add(right)
        adjacency[right].add(left)
    unseen = set(range(point_count))
    components: list[tuple[int, ...]] = []
    while unseen:
        start = min(unseen)
        stack = [start]
        members: set[int] = set()
        while stack:
            current = stack.pop()
            if current in members:
                continue
            members.add(current)
            unseen.discard(current)
            stack.extend(adjacency[current] - members)
        components.append(tuple(sorted(members)))
    return tuple(components)


def _merge_complete_linkage_clusters(
    points: np.ndarray,
    initial_clusters: Sequence[tuple[int, ...]],
    *,
    max_diameter_nm: float,
    point_ids: tuple[str, ...],
) -> tuple[tuple[int, ...], ...]:
    clusters = list(initial_clusters)
    while True:
        choices: list[tuple[float, tuple[str, ...], int, int, tuple[int, ...]]] = []
        for left_index in range(len(clusters)):
            for right_index in range(left_index + 1, len(clusters)):
                merged = tuple(sorted(clusters[left_index] + clusters[right_index]))
                if _cluster_diameter(points, merged) <= max_diameter_nm:
                    linkage_distance = _complete_linkage_distance(
                        points,
                        clusters[left_index],
                        clusters[right_index],
                    )
                    stable_ids = tuple(sorted(point_ids[index] for index in merged))
                    choices.append((linkage_distance, stable_ids, left_index, right_index, merged))
        if not choices:
            break
        _distance, _ids, left_index, right_index, merged = min(choices)
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in (left_index, right_index)
        ]
        clusters.append(merged)
    return tuple(
        sorted(
            clusters,
            key=lambda cluster: tuple(sorted(point_ids[index] for index in cluster)),
        )
    )


def _complete_linkage_distance(
    points: np.ndarray,
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> float:
    left_points = points[np.asarray(left, dtype=np.int64)]
    right_points = points[np.asarray(right, dtype=np.int64)]
    deltas = left_points[:, None, :] - right_points[None, :, :]
    return float(np.max(np.linalg.norm(deltas, axis=2)))


def _cluster_diameter(points: np.ndarray, indices: tuple[int, ...]) -> float:
    if len(indices) < 2:
        return 0.0
    selected = points[np.asarray(indices, dtype=np.int64)]
    deltas = selected[:, None, :] - selected[None, :, :]
    return float(np.max(np.linalg.norm(deltas, axis=2)))


def _stable_component_id(
    prefix: str,
    point_ids: tuple[str, ...],
    indices: tuple[int, ...],
) -> str:
    encoded_ids = json.dumps(
        sorted(point_ids[index] for index in indices),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return f"{prefix}:{encoded_ids}"
