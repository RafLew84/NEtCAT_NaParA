"""Helpers for refining a coarse step-edge polyline to a sharper final geometry."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .hybrid import resample_polyline_xy


@dataclass(frozen=True)
class EdgeRefinementResult:
    """Refined edge geometry produced from a coarse polyline."""

    polyline_xy: np.ndarray
    point_count: int
    score_mode: str
    search_radius_px: int
    mean_score: float
    mean_shift_px: float
    refinement_mode: str

    def __post_init__(self) -> None:
        polyline = np.asarray(self.polyline_xy, dtype=np.float64)
        if polyline.ndim != 2 or polyline.shape[1] != 2:
            raise ValueError("polyline_xy must have shape [N, 2].")
        if len(polyline) < 2:
            raise ValueError("polyline_xy must contain at least two points.")
        object.__setattr__(self, "polyline_xy", polyline)
        object.__setattr__(self, "point_count", int(self.point_count))
        object.__setattr__(self, "score_mode", str(self.score_mode))
        object.__setattr__(self, "search_radius_px", int(self.search_radius_px))
        object.__setattr__(self, "mean_score", float(self.mean_score))
        object.__setattr__(self, "mean_shift_px", float(self.mean_shift_px))
        object.__setattr__(self, "refinement_mode", str(self.refinement_mode))


def refine_edge_polyline(
    coarse_polyline_xy: np.ndarray,
    *,
    edge_prob: np.ndarray,
    input_frame: np.ndarray,
    polygon_mask: np.ndarray,
    score_mode: str = "combined",
    search_radius_px: int = 4,
    max_points: int = 128,
) -> EdgeRefinementResult:
    """Refine a coarse polyline by searching along local normals.

    The coarse geometry is first resampled to a denser point set. For each point,
    the method probes candidate positions along the local normal and chooses the
    position with the strongest edge evidence according to the requested score:
    `edge_prob`, `gradient`, or `combined`.
    """

    coarse_polyline = np.asarray(coarse_polyline_xy, dtype=np.float64)
    edge_prob_f32 = np.asarray(edge_prob, dtype=np.float32)
    input_frame_f32 = np.asarray(input_frame, dtype=np.float32)
    polygon_mask_bool = np.asarray(polygon_mask, dtype=bool)

    if coarse_polyline.ndim != 2 or coarse_polyline.shape[1] != 2:
        raise ValueError("coarse_polyline_xy must have shape [N, 2].")
    if len(coarse_polyline) < 2:
        raise ValueError("coarse_polyline_xy must contain at least two points.")
    if edge_prob_f32.ndim != 2:
        raise ValueError("edge_prob must have shape [H, W].")
    if input_frame_f32.shape != edge_prob_f32.shape:
        raise ValueError("input_frame must match edge_prob shape.")
    if polygon_mask_bool.shape != edge_prob_f32.shape:
        raise ValueError("polygon_mask must match edge_prob shape.")
    if not np.any(polygon_mask_bool):
        raise ValueError("polygon_mask must contain at least one True pixel.")
    if score_mode not in {"edge_prob", "gradient", "combined"}:
        raise ValueError("score_mode must be one of: edge_prob, gradient, combined.")
    if int(search_radius_px) <= 0:
        raise ValueError("search_radius_px must be positive.")
    if int(max_points) < 2:
        raise ValueError("max_points must be at least 2.")

    target_point_count = min(
        int(max_points),
        max(len(coarse_polyline), int(np.ceil(_polyline_length(coarse_polyline))) + 1),
    )
    reference_polyline = (
        np.asarray(coarse_polyline, dtype=np.float64)
        if target_point_count == len(coarse_polyline)
        else resample_polyline_xy(coarse_polyline, target_point_count)
    )

    prob_norm = _normalize_map(edge_prob_f32, polygon_mask_bool)
    gradient_norm = _normalize_map(_gradient_magnitude(input_frame_f32), polygon_mask_bool)
    offsets = np.linspace(
        -float(search_radius_px),
        float(search_radius_px),
        num=max(9, int(search_radius_px) * 4 + 1),
        dtype=np.float64,
    )

    refined_points = np.empty_like(reference_polyline)
    selected_scores: list[float] = []
    selected_shifts: list[float] = []

    for point_index, point_xy in enumerate(reference_polyline):
        tangent = _local_tangent(reference_polyline, point_index)
        normal = np.asarray([-tangent[1], tangent[0]], dtype=np.float64)
        candidates_xy = point_xy[None, :] + offsets[:, None] * normal[None, :]
        valid_mask = _valid_candidate_mask(candidates_xy, polygon_mask_bool)

        if not np.any(valid_mask):
            refined_points[point_index] = point_xy
            selected_scores.append(0.0)
            selected_shifts.append(0.0)
            continue

        valid_candidates_xy = candidates_xy[valid_mask]
        valid_offsets = offsets[valid_mask]
        prob_scores = _sample_bilinear(prob_norm, valid_candidates_xy)
        gradient_scores = _sample_bilinear(gradient_norm, valid_candidates_xy)
        scores = _combine_scores(prob_scores, gradient_scores, score_mode)
        best_index = _pick_best_candidate(scores, valid_offsets)
        refined_points[point_index] = valid_candidates_xy[best_index]
        selected_scores.append(float(scores[best_index]))
        selected_shifts.append(float(abs(valid_offsets[best_index])))

    refined_polyline = _remove_duplicate_points(refined_points)
    if len(refined_polyline) < 2:
        refined_polyline = reference_polyline[[0, -1]]

    return EdgeRefinementResult(
        polyline_xy=refined_polyline,
        point_count=len(refined_polyline),
        score_mode=score_mode,
        search_radius_px=int(search_radius_px),
        mean_score=0.0 if not selected_scores else float(np.mean(selected_scores)),
        mean_shift_px=0.0 if not selected_shifts else float(np.mean(selected_shifts)),
        refinement_mode=f"normal_search_{score_mode}",
    )


def _polyline_length(polyline_xy: np.ndarray) -> float:
    deltas = np.diff(np.asarray(polyline_xy, dtype=np.float64), axis=0)
    if deltas.size == 0:
        return 0.0
    return float(np.sum(np.linalg.norm(deltas, axis=1)))


def _normalize_map(image: np.ndarray, polygon_mask: np.ndarray) -> np.ndarray:
    image_f32 = np.asarray(image, dtype=np.float32)
    roi_values = image_f32[polygon_mask]
    if roi_values.size == 0:
        return np.zeros_like(image_f32, dtype=np.float32)
    finite_values = roi_values[np.isfinite(roi_values)]
    if finite_values.size == 0:
        return np.zeros_like(image_f32, dtype=np.float32)
    min_value = float(np.min(finite_values))
    max_value = float(np.max(finite_values))
    if max_value - min_value <= 1e-6:
        return np.zeros_like(image_f32, dtype=np.float32)
    normalized = (image_f32 - min_value) / (max_value - min_value)
    normalized = np.clip(normalized, 0.0, 1.0)
    normalized[~polygon_mask] = 0.0
    return normalized.astype(np.float32, copy=False)


def _gradient_magnitude(input_frame: np.ndarray) -> np.ndarray:
    frame = np.asarray(input_frame, dtype=np.float32)
    grad_y, grad_x = np.gradient(frame)
    return np.hypot(grad_x, grad_y).astype(np.float32, copy=False)


def _local_tangent(polyline_xy: np.ndarray, point_index: int) -> np.ndarray:
    points = np.asarray(polyline_xy, dtype=np.float64)
    if point_index <= 0:
        tangent = points[1] - points[0]
    elif point_index >= len(points) - 1:
        tangent = points[-1] - points[-2]
    else:
        tangent = points[point_index + 1] - points[point_index - 1]
    tangent_norm = float(np.linalg.norm(tangent))
    if tangent_norm <= 1e-12:
        return np.asarray([1.0, 0.0], dtype=np.float64)
    return tangent / tangent_norm


def _valid_candidate_mask(candidates_xy: np.ndarray, polygon_mask: np.ndarray) -> np.ndarray:
    height, width = polygon_mask.shape
    x_coords = candidates_xy[:, 0]
    y_coords = candidates_xy[:, 1]
    inside = (x_coords >= 0.0) & (x_coords <= width - 1) & (y_coords >= 0.0) & (y_coords <= height - 1)
    if not np.any(inside):
        return inside
    nearest_x = np.clip(np.rint(x_coords[inside]).astype(np.int32), 0, width - 1)
    nearest_y = np.clip(np.rint(y_coords[inside]).astype(np.int32), 0, height - 1)
    valid = np.zeros(len(candidates_xy), dtype=bool)
    valid_indices = np.flatnonzero(inside)
    valid[valid_indices] = polygon_mask[nearest_y, nearest_x]
    return valid


def _sample_bilinear(image: np.ndarray, points_xy: np.ndarray) -> np.ndarray:
    image_f32 = np.asarray(image, dtype=np.float32)
    points = np.asarray(points_xy, dtype=np.float64)
    height, width = image_f32.shape

    x = np.clip(points[:, 0], 0.0, width - 1.0)
    y = np.clip(points[:, 1], 0.0, height - 1.0)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)

    wa = (x1 - x) * (y1 - y)
    wb = (x - x0) * (y1 - y)
    wc = (x1 - x) * (y - y0)
    wd = (x - x0) * (y - y0)

    sampled = (
        wa * image_f32[y0, x0]
        + wb * image_f32[y0, x1]
        + wc * image_f32[y1, x0]
        + wd * image_f32[y1, x1]
    )
    exact_x = x0 == x1
    exact_y = y0 == y1
    sampled[exact_x & exact_y] = image_f32[y0[exact_x & exact_y], x0[exact_x & exact_y]]
    sampled[exact_x & ~exact_y] = (
        (y1[exact_x & ~exact_y] - y[exact_x & ~exact_y]) * image_f32[y0[exact_x & ~exact_y], x0[exact_x & ~exact_y]]
        + (y[exact_x & ~exact_y] - y0[exact_x & ~exact_y]) * image_f32[y1[exact_x & ~exact_y], x0[exact_x & ~exact_y]]
    )
    sampled[~exact_x & exact_y] = (
        (x1[~exact_x & exact_y] - x[~exact_x & exact_y]) * image_f32[y0[~exact_x & exact_y], x0[~exact_x & exact_y]]
        + (x[~exact_x & exact_y] - x0[~exact_x & exact_y]) * image_f32[y0[~exact_x & exact_y], x1[~exact_x & exact_y]]
    )
    return sampled.astype(np.float32, copy=False)


def _combine_scores(prob_scores: np.ndarray, gradient_scores: np.ndarray, score_mode: str) -> np.ndarray:
    if score_mode == "edge_prob":
        return np.asarray(prob_scores, dtype=np.float32)
    if score_mode == "gradient":
        return np.asarray(gradient_scores, dtype=np.float32)
    return (0.5 * np.asarray(prob_scores, dtype=np.float32)) + (0.5 * np.asarray(gradient_scores, dtype=np.float32))


def _pick_best_candidate(scores: np.ndarray, offsets: np.ndarray) -> int:
    score_array = np.asarray(scores, dtype=np.float32)
    offset_array = np.asarray(offsets, dtype=np.float64)
    best_score = float(np.max(score_array))
    best_indices = np.flatnonzero(np.isclose(score_array, best_score, atol=1e-6))
    if len(best_indices) == 1:
        return int(best_indices[0])
    tied_offsets = np.abs(offset_array[best_indices])
    return int(best_indices[int(np.argmin(tied_offsets))])


def _remove_duplicate_points(polyline_xy: np.ndarray) -> np.ndarray:
    polyline = np.asarray(polyline_xy, dtype=np.float64)
    if len(polyline) <= 1:
        return polyline
    keep_mask = np.ones(len(polyline), dtype=bool)
    segment_lengths = np.linalg.norm(np.diff(polyline, axis=0), axis=1)
    keep_mask[1:] = segment_lengths > 1e-6
    filtered = polyline[keep_mask]
    if len(filtered) >= 2:
        return filtered
    return polyline[[0, -1]]
