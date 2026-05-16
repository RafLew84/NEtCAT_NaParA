"""Helpers for reducing a dominant edge mask to a centerline polyline."""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
from skimage import measure
from skimage.morphology import skeletonize

from .selection import EdgeComponentCandidate


@dataclass(frozen=True)
class EdgePolylineExtraction:
    """Polyline extracted from one dominant edge component."""

    polyline_xy: np.ndarray
    point_count: int
    axis_length_px: float
    extraction_mode: str

    def __post_init__(self) -> None:
        polyline = np.asarray(self.polyline_xy, dtype=np.float64)
        if polyline.ndim != 2 or polyline.shape[1] != 2:
            raise ValueError("polyline_xy must have shape [N, 2].")
        if len(polyline) < 2:
            raise ValueError("polyline_xy must contain at least two points.")
        object.__setattr__(self, "polyline_xy", polyline)
        object.__setattr__(self, "point_count", int(self.point_count))
        object.__setattr__(self, "axis_length_px", float(self.axis_length_px))
        object.__setattr__(self, "extraction_mode", str(self.extraction_mode))


@dataclass(frozen=True)
class EdgePolylineCandidate:
    """One component group with extracted polyline and geometry quality score."""

    edge_mask: np.ndarray
    components: tuple[EdgeComponentCandidate, ...]
    extraction: EdgePolylineExtraction
    geometry_score: float
    polyline_length_px: float
    straightness: float
    segment_length_cv: float
    turn_rms_rad: float
    selection_mode: str
    reason: str

    def __post_init__(self) -> None:
        edge_mask = np.asarray(self.edge_mask, dtype=bool)
        if edge_mask.ndim != 2:
            raise ValueError("edge_mask must have shape [H, W].")
        object.__setattr__(self, "edge_mask", edge_mask)
        object.__setattr__(self, "components", tuple(self.components))
        object.__setattr__(self, "geometry_score", float(self.geometry_score))
        object.__setattr__(self, "polyline_length_px", float(self.polyline_length_px))
        object.__setattr__(self, "straightness", float(self.straightness))
        object.__setattr__(self, "segment_length_cv", float(self.segment_length_cv))
        object.__setattr__(self, "turn_rms_rad", float(self.turn_rms_rad))
        object.__setattr__(self, "selection_mode", str(self.selection_mode))
        object.__setattr__(self, "reason", str(self.reason))


def _weighted_principal_axis(coords_xy: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    weight_sum = float(np.sum(weights))
    center = np.sum(coords_xy * weights[:, None], axis=0) / weight_sum
    centered = coords_xy - center
    covariance = (centered * weights[:, None]).T @ centered / weight_sum
    eigvals, eigvecs = np.linalg.eigh(covariance)
    order = np.argsort(eigvals)
    primary = eigvecs[:, order[-1]]
    secondary = eigvecs[:, order[0]]
    if primary[0] < 0 or (np.isclose(primary[0], 0.0) and primary[1] < 0):
        primary = -primary
        secondary = -secondary
    return center, primary, secondary


def _validate_polyline_inputs(
    edge_mask: np.ndarray,
    edge_prob: np.ndarray | None,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    mask = np.asarray(edge_mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("edge_mask must have shape [H, W].")
    if not np.any(mask):
        raise ValueError("edge_mask must contain at least one True pixel.")
    if max_points < 2:
        raise ValueError("max_points must be at least 2.")

    edge_prob_f32: np.ndarray | None = None
    if edge_prob is not None:
        edge_prob_f32 = np.asarray(edge_prob, dtype=np.float32)
        if edge_prob_f32.shape != mask.shape:
            raise ValueError("edge_prob must match edge_mask shape.")
        if not np.all(np.isfinite(edge_prob_f32[mask])):
            raise ValueError("edge_prob values must be finite on edge_mask.")

    return mask, edge_prob_f32


def _dominant_edge_to_polyline_pca(
    mask: np.ndarray,
    *,
    edge_prob: np.ndarray | None,
    max_points: int,
) -> EdgePolylineExtraction:
    coords_yx = np.argwhere(mask)
    coords_xy = np.column_stack([coords_yx[:, 1], coords_yx[:, 0]]).astype(np.float64, copy=False)

    if edge_prob is None:
        weights = np.ones(len(coords_xy), dtype=np.float64)
    else:
        weights = np.asarray(edge_prob[mask], dtype=np.float64)
        if float(np.sum(weights)) <= 0:
            weights = np.ones(len(coords_xy), dtype=np.float64)

    if len(coords_xy) == 1:
        repeated = np.repeat(coords_xy, 2, axis=0)
        return EdgePolylineExtraction(
            polyline_xy=repeated,
            point_count=2,
            axis_length_px=0.0,
            extraction_mode="single_pixel",
        )

    center, primary_axis, _secondary_axis = _weighted_principal_axis(coords_xy, weights)
    axis_projection = (coords_xy - center) @ primary_axis
    t_min = float(np.min(axis_projection))
    t_max = float(np.max(axis_projection))
    axis_length = float(t_max - t_min)

    if axis_length <= 1e-6:
        order = np.argsort(coords_xy[:, 0], kind="mergesort")
        endpoints = coords_xy[order[[0, -1]]]
        return EdgePolylineExtraction(
            polyline_xy=endpoints,
            point_count=2,
            axis_length_px=0.0,
            extraction_mode="degenerate",
        )

    bin_count = min(int(max_points), max(2, int(np.ceil(axis_length)) + 1))
    bin_edges = np.linspace(t_min, t_max, bin_count + 1, dtype=np.float64)
    bin_indices = np.clip(np.digitize(axis_projection, bin_edges[1:-1], right=False), 0, bin_count - 1)

    polyline_points: list[np.ndarray] = []
    for bin_index in range(bin_count):
        in_bin = bin_indices == bin_index
        if not np.any(in_bin):
            continue
        bin_weights = weights[in_bin]
        point = np.sum(coords_xy[in_bin] * bin_weights[:, None], axis=0) / float(np.sum(bin_weights))
        polyline_points.append(point)

    if len(polyline_points) < 2:
        order = np.argsort(axis_projection, kind="mergesort")
        endpoints = coords_xy[order[[0, -1]]]
        return EdgePolylineExtraction(
            polyline_xy=endpoints,
            point_count=2,
            axis_length_px=axis_length,
            extraction_mode="endpoints",
        )

    polyline = np.asarray(polyline_points, dtype=np.float64)
    segment_lengths = np.linalg.norm(np.diff(polyline, axis=0), axis=1)
    if segment_lengths.size:
        keep = np.concatenate([[True], segment_lengths > 1e-6])
        polyline = polyline[keep]

    if len(polyline) < 2:
        order = np.argsort(axis_projection, kind="mergesort")
        polyline = coords_xy[order[[0, -1]]]
        mode = "endpoints"
    else:
        mode = "binned_pca"

    return EdgePolylineExtraction(
        polyline_xy=polyline,
        point_count=len(polyline),
        axis_length_px=axis_length,
        extraction_mode=mode,
    )


def _skeleton_endpoint_indices(coords_yx: np.ndarray, adjacency: list[list[tuple[int, float]]]) -> list[int]:
    endpoints = [index for index, neighbors in enumerate(adjacency) if len(neighbors) <= 1]
    if len(endpoints) >= 2:
        return endpoints

    coords_xy = np.column_stack([coords_yx[:, 1], coords_yx[:, 0]]).astype(np.float64, copy=False)
    weights = np.ones(len(coords_xy), dtype=np.float64)
    center, primary_axis, _secondary_axis = _weighted_principal_axis(coords_xy, weights)
    projection = (coords_xy - center) @ primary_axis
    return [int(np.argmin(projection)), int(np.argmax(projection))]


def _build_skeleton_graph(coords_yx: np.ndarray) -> list[list[tuple[int, float]]]:
    coord_to_index = {tuple(coord): index for index, coord in enumerate(coords_yx.tolist())}
    adjacency: list[list[tuple[int, float]]] = [[] for _ in range(len(coords_yx))]
    for index, (y, x) in enumerate(coords_yx):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                neighbor_index = coord_to_index.get((int(y + dy), int(x + dx)))
                if neighbor_index is None or neighbor_index <= index:
                    continue
                distance = float(np.hypot(dy, dx))
                adjacency[index].append((neighbor_index, distance))
                adjacency[neighbor_index].append((index, distance))
    return adjacency


def _bridge_nearby_skeleton_components(
    coords_yx: np.ndarray,
    component_labels: np.ndarray,
    adjacency: list[list[tuple[int, float]]],
    *,
    max_gap_px: float,
) -> None:
    labels = [int(label_id) for label_id in np.unique(component_labels) if int(label_id) > 0]
    if len(labels) < 2:
        return

    endpoints_by_label: dict[int, list[int]] = {}
    for label_id in labels:
        component_indices = np.flatnonzero(component_labels == label_id)
        endpoint_indices = [int(index) for index in component_indices if len(adjacency[int(index)]) <= 1]
        if len(endpoint_indices) < 2 and len(component_indices) >= 2:
            component_coords_xy = np.column_stack(
                [coords_yx[component_indices, 1], coords_yx[component_indices, 0]]
            ).astype(np.float64, copy=False)
            center, primary_axis, _secondary_axis = _weighted_principal_axis(
                component_coords_xy,
                np.ones(len(component_coords_xy), dtype=np.float64),
            )
            projection = (component_coords_xy - center) @ primary_axis
            endpoint_indices = [
                int(component_indices[int(np.argmin(projection))]),
                int(component_indices[int(np.argmax(projection))]),
            ]
        endpoints_by_label[label_id] = endpoint_indices

    for left_offset, left_label in enumerate(labels[:-1]):
        left_endpoints = endpoints_by_label.get(left_label, [])
        if not left_endpoints:
            continue
        for right_label in labels[left_offset + 1 :]:
            right_endpoints = endpoints_by_label.get(right_label, [])
            if not right_endpoints:
                continue

            best_pair: tuple[int, int] | None = None
            best_distance = np.inf
            for left_index in left_endpoints:
                left_yx = coords_yx[left_index].astype(np.float64)
                for right_index in right_endpoints:
                    distance = float(np.linalg.norm(left_yx - coords_yx[right_index].astype(np.float64)))
                    if distance < best_distance:
                        best_distance = distance
                        best_pair = (left_index, right_index)

            if best_pair is None or best_distance > max_gap_px:
                continue

            left_index, right_index = best_pair
            bridge_cost = best_distance * 1.5
            adjacency[left_index].append((right_index, bridge_cost))
            adjacency[right_index].append((left_index, bridge_cost))


def _shortest_path_indices(
    adjacency: list[list[tuple[int, float]]],
    start_index: int,
    end_index: int,
) -> list[int]:
    distances = [np.inf] * len(adjacency)
    previous = [-1] * len(adjacency)
    distances[start_index] = 0.0
    queue: list[tuple[float, int]] = [(0.0, start_index)]

    while queue:
        current_distance, current_index = heapq.heappop(queue)
        if current_index == end_index:
            break
        if current_distance > distances[current_index]:
            continue
        for neighbor_index, edge_distance in adjacency[current_index]:
            next_distance = current_distance + edge_distance
            if next_distance < distances[neighbor_index]:
                distances[neighbor_index] = next_distance
                previous[neighbor_index] = current_index
                heapq.heappush(queue, (next_distance, neighbor_index))

    if not np.isfinite(distances[end_index]):
        return []

    path = [end_index]
    current = end_index
    while current != start_index:
        current = previous[current]
        if current < 0:
            return []
        path.append(current)
    path.reverse()
    return path


def _resample_polyline_by_arc_length(polyline_xy: np.ndarray, max_points: int) -> np.ndarray:
    polyline = np.asarray(polyline_xy, dtype=np.float64)
    if len(polyline) <= 2:
        return polyline

    segment_lengths = np.linalg.norm(np.diff(polyline, axis=0), axis=1)
    total_length = float(np.sum(segment_lengths))
    if total_length <= 1e-9:
        return polyline[[0, -1]]

    target_count = min(int(max_points), max(2, int(np.ceil(total_length)) + 1))
    distances = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    sample_distances = np.linspace(0.0, total_length, target_count, dtype=np.float64)
    resampled_x = np.interp(sample_distances, distances, polyline[:, 0])
    resampled_y = np.interp(sample_distances, distances, polyline[:, 1])
    return np.column_stack([resampled_x, resampled_y])


def _orient_polyline_stably(polyline_xy: np.ndarray) -> np.ndarray:
    polyline = np.asarray(polyline_xy, dtype=np.float64)
    first = polyline[0]
    last = polyline[-1]
    if first[0] > last[0] or (np.isclose(first[0], last[0]) and first[1] > last[1]):
        return polyline[::-1]
    return polyline


def _score_graph_path(path_indices: list[int], coords_yx: np.ndarray, probability_map: np.ndarray) -> tuple[float, np.ndarray, float]:
    path_yx = coords_yx[np.asarray(path_indices, dtype=np.int64)]
    path_xy = np.column_stack([path_yx[:, 1], path_yx[:, 0]]).astype(np.float64, copy=False)
    polyline_length, straightness, segment_length_cv, turn_rms = _polyline_geometry_metrics(path_xy)
    path_probability = float(np.mean(probability_map[path_yx[:, 0], path_yx[:, 1]]))
    score = (
        2.0 * np.log1p(polyline_length)
        + 2.0 * straightness
        + 1.5 * path_probability
        - 0.6 * segment_length_cv
        - 0.8 * turn_rms
    )
    return float(score), path_xy, polyline_length


def _dominant_edge_to_polyline_graph(
    mask: np.ndarray,
    *,
    edge_prob: np.ndarray | None,
    max_points: int,
) -> EdgePolylineExtraction:
    probability_map = np.ones(mask.shape, dtype=np.float32) if edge_prob is None else np.asarray(edge_prob, dtype=np.float32)
    skeleton = skeletonize(mask)
    coords_yx = np.argwhere(skeleton)
    if len(coords_yx) <= 2:
        raise ValueError("Skeleton is too small for graph extraction.")

    adjacency = _build_skeleton_graph(coords_yx)
    labels = measure.label(skeleton, connectivity=2)
    component_labels = labels[coords_yx[:, 0], coords_yx[:, 1]]
    max_gap_px = max(3.0, min(24.0, 0.08 * float(max(mask.shape))))
    _bridge_nearby_skeleton_components(
        coords_yx,
        component_labels,
        adjacency,
        max_gap_px=max_gap_px,
    )
    if not any(adjacency):
        raise ValueError("Skeleton graph has no connected edges.")

    endpoints = _skeleton_endpoint_indices(coords_yx, adjacency)
    best_path_xy: np.ndarray | None = None
    best_path_length = 0.0
    best_score = -np.inf
    for start_offset, start_index in enumerate(endpoints[:-1]):
        for end_index in endpoints[start_offset + 1 :]:
            if start_index == end_index:
                continue
            path_indices = _shortest_path_indices(adjacency, start_index, end_index)
            if len(path_indices) < 2:
                continue
            path_score, path_xy, path_length = _score_graph_path(path_indices, coords_yx, probability_map)
            if path_score > best_score:
                best_score = path_score
                best_path_xy = path_xy
                best_path_length = path_length

    if best_path_xy is None:
        raise ValueError("No valid skeleton path could be extracted.")

    polyline = _orient_polyline_stably(_resample_polyline_by_arc_length(best_path_xy, max_points))
    if len(polyline) < 2:
        raise ValueError("Graph path collapsed to fewer than two points.")

    return EdgePolylineExtraction(
        polyline_xy=polyline,
        point_count=len(polyline),
        axis_length_px=best_path_length,
        extraction_mode="graph_path",
    )


def dominant_edge_to_polyline(
    edge_mask: np.ndarray,
    *,
    edge_prob: np.ndarray | None = None,
    max_points: int = 64,
    method: str = "graph",
) -> EdgePolylineExtraction:
    """Approximate one dominant edge component by a centerline polyline.

    The default method skeletonizes the component, builds an 8-neighborhood
    graph over skeleton pixels, picks the best endpoint-to-endpoint path, and
    resamples it by arc length. ``method="pca_bins"`` keeps the previous
    weighted PCA/binning behavior for fallback and regression comparisons.
    """

    mask, edge_prob_f32 = _validate_polyline_inputs(edge_mask, edge_prob, max_points)
    normalized_method = str(method).strip().lower()
    if normalized_method in {"pca", "pca_bins", "binned_pca"}:
        return _dominant_edge_to_polyline_pca(mask, edge_prob=edge_prob_f32, max_points=max_points)
    if normalized_method != "graph":
        raise ValueError("method must be 'graph' or 'pca_bins'.")

    try:
        return _dominant_edge_to_polyline_graph(mask, edge_prob=edge_prob_f32, max_points=max_points)
    except ValueError:
        return _dominant_edge_to_polyline_pca(mask, edge_prob=edge_prob_f32, max_points=max_points)


def _polyline_geometry_metrics(polyline_xy: np.ndarray) -> tuple[float, float, float, float]:
    polyline = np.asarray(polyline_xy, dtype=np.float64)
    segment_vectors = np.diff(polyline, axis=0)
    segment_lengths = np.linalg.norm(segment_vectors, axis=1)
    polyline_length = float(np.sum(segment_lengths))
    if polyline_length <= 1e-9:
        return 0.0, 0.0, 0.0, 0.0

    direct_distance = float(np.linalg.norm(polyline[-1] - polyline[0]))
    straightness = float(np.clip(direct_distance / polyline_length, 0.0, 1.0))
    mean_segment = float(np.mean(segment_lengths)) if segment_lengths.size else 0.0
    segment_length_cv = 0.0
    if mean_segment > 1e-9 and segment_lengths.size > 1:
        segment_length_cv = float(np.std(segment_lengths) / mean_segment)

    turn_rms = 0.0
    if len(segment_vectors) >= 2:
        unit_vectors = segment_vectors / np.maximum(segment_lengths[:, None], 1e-9)
        dot_products = np.sum(unit_vectors[:-1] * unit_vectors[1:], axis=1)
        turn_angles = np.arccos(np.clip(dot_products, -1.0, 1.0))
        turn_rms = float(np.sqrt(np.mean(np.square(turn_angles)))) if turn_angles.size else 0.0

    return polyline_length, straightness, segment_length_cv, turn_rms


def _combined_component_mask(components: tuple[EdgeComponentCandidate, ...], shape: tuple[int, int]) -> np.ndarray:
    edge_mask = np.zeros(shape, dtype=bool)
    for component in components:
        component_mask = np.asarray(component.edge_mask, dtype=bool)
        if component_mask.shape != shape:
            raise ValueError("component edge_mask must match edge_prob shape.")
        edge_mask |= component_mask
    return edge_mask


def _component_group_reason(
    components: tuple[EdgeComponentCandidate, ...],
    *,
    polyline_length: float,
    straightness: float,
    segment_length_cv: float,
    turn_rms: float,
) -> str:
    component_score = float(sum(component.score for component in components))
    mean_probability = float(np.mean([component.mean_probability for component in components]))
    return (
        f"components={len(components)}; component_score={component_score:.3f}; "
        f"mean_probability={mean_probability:.3f}; polyline_length={polyline_length:.3f}; "
        f"straightness={straightness:.3f}; segment_cv={segment_length_cv:.3f}; turn_rms={turn_rms:.3f}"
    )


def rank_edge_polyline_candidates(
    edge_prob: np.ndarray,
    component_candidates: tuple[EdgeComponentCandidate, ...] | list[EdgeComponentCandidate],
    *,
    candidate_limit: int = 3,
    include_merged: bool = True,
    max_points: int = 64,
    polyline_method: str = "graph",
) -> list[EdgePolylineCandidate]:
    """Build polylines from ranked components and rank them by geometry quality."""

    edge_prob_f32 = np.asarray(edge_prob, dtype=np.float32)
    if edge_prob_f32.ndim != 2:
        raise ValueError("edge_prob must have shape [H, W].")
    if int(candidate_limit) <= 0:
        raise ValueError("candidate_limit must be positive.")

    pool = tuple(component_candidates[: int(candidate_limit)])
    if not pool:
        return []

    component_groups: list[tuple[EdgeComponentCandidate, ...]] = [(component,) for component in pool]
    if include_merged and len(pool) > 1:
        component_groups.extend(tuple(pool[:count]) for count in range(2, len(pool) + 1))

    polyline_candidates: list[EdgePolylineCandidate] = []
    for components in component_groups:
        edge_mask = _combined_component_mask(components, edge_prob_f32.shape)
        if not np.any(edge_mask):
            continue
        try:
            extraction = dominant_edge_to_polyline(
                edge_mask,
                edge_prob=edge_prob_f32,
                max_points=max_points,
                method=polyline_method,
            )
        except ValueError:
            continue

        polyline_length, straightness, segment_length_cv, turn_rms = _polyline_geometry_metrics(extraction.polyline_xy)
        component_score = float(sum(component.score for component in components))
        mean_probability = float(np.mean([component.mean_probability for component in components]))
        geometry_score = (
            0.15 * component_score
            + 1.75 * np.log1p(polyline_length)
            + 3.0 * straightness
            + 0.2 * float(extraction.point_count)
            + 1.5 * mean_probability
            - 2.0 * segment_length_cv
            - 2.5 * turn_rms
            - 0.6 * float(max(0, len(components) - 1))
        )
        selection_mode = "geometry_component" if len(components) == 1 else f"geometry_top_{len(components)}_components"
        polyline_candidates.append(
            EdgePolylineCandidate(
                edge_mask=edge_mask,
                components=components,
                extraction=extraction,
                geometry_score=geometry_score,
                polyline_length_px=polyline_length,
                straightness=straightness,
                segment_length_cv=segment_length_cv,
                turn_rms_rad=turn_rms,
                selection_mode=selection_mode,
                reason=_component_group_reason(
                    components,
                    polyline_length=polyline_length,
                    straightness=straightness,
                    segment_length_cv=segment_length_cv,
                    turn_rms=turn_rms,
                ),
            )
        )

    polyline_candidates.sort(
        key=lambda candidate: (
            candidate.geometry_score,
            candidate.polyline_length_px,
            candidate.straightness,
            -candidate.segment_length_cv,
        ),
        reverse=True,
    )
    return polyline_candidates


def select_best_edge_polyline_candidate(
    edge_prob: np.ndarray,
    component_candidates: tuple[EdgeComponentCandidate, ...] | list[EdgeComponentCandidate],
    *,
    candidate_limit: int = 3,
    include_merged: bool = True,
    max_points: int = 64,
    polyline_method: str = "graph",
) -> EdgePolylineCandidate:
    """Return the component group that yields the highest-quality coarse polyline."""

    polyline_candidates = rank_edge_polyline_candidates(
        edge_prob,
        component_candidates,
        candidate_limit=candidate_limit,
        include_merged=include_merged,
        max_points=max_points,
        polyline_method=polyline_method,
    )
    if not polyline_candidates:
        raise ValueError("No edge polyline candidates could be extracted.")
    return polyline_candidates[0]
