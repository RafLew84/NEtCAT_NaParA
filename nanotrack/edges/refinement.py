"""Helpers for refining a coarse step-edge polyline to a sharper final geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .hybrid import resample_polyline_xy

_SUBPIXEL_MODES = {"none", "parabolic", "step_tanh", "step_erf"}


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
    shift_std_px: float = 0.0
    max_shift_px: float = 0.0
    stability_score: float = 1.0
    subpixel_mode: str = "none"
    mean_subpixel_correction_px: float = 0.0
    profile_fit_success_rate: float = 0.0
    mean_step_height: float = 0.0
    mean_step_width_px: float = 0.0

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
        shift_std_px = float(self.shift_std_px)
        max_shift_px = float(self.max_shift_px)
        stability_score = float(self.stability_score)
        subpixel_mode = str(self.subpixel_mode)
        mean_subpixel_correction_px = float(self.mean_subpixel_correction_px)
        profile_fit_success_rate = float(self.profile_fit_success_rate)
        mean_step_height = float(self.mean_step_height)
        mean_step_width_px = float(self.mean_step_width_px)
        if not np.isfinite(shift_std_px) or shift_std_px < 0.0:
            raise ValueError("shift_std_px must be finite and non-negative.")
        if not np.isfinite(max_shift_px) or max_shift_px < 0.0:
            raise ValueError("max_shift_px must be finite and non-negative.")
        if not np.isfinite(stability_score):
            raise ValueError("stability_score must be finite.")
        if subpixel_mode not in _SUBPIXEL_MODES:
            raise ValueError("subpixel_mode must be one of: none, parabolic, step_tanh, step_erf.")
        if not np.isfinite(mean_subpixel_correction_px) or mean_subpixel_correction_px < 0.0:
            raise ValueError("mean_subpixel_correction_px must be finite and non-negative.")
        if not np.isfinite(profile_fit_success_rate):
            raise ValueError("profile_fit_success_rate must be finite.")
        if not np.isfinite(mean_step_height):
            raise ValueError("mean_step_height must be finite.")
        if not np.isfinite(mean_step_width_px) or mean_step_width_px < 0.0:
            raise ValueError("mean_step_width_px must be finite and non-negative.")
        object.__setattr__(self, "shift_std_px", shift_std_px)
        object.__setattr__(self, "max_shift_px", max_shift_px)
        object.__setattr__(self, "stability_score", float(np.clip(stability_score, 0.0, 1.0)))
        object.__setattr__(self, "subpixel_mode", subpixel_mode)
        object.__setattr__(self, "mean_subpixel_correction_px", mean_subpixel_correction_px)
        object.__setattr__(self, "profile_fit_success_rate", float(np.clip(profile_fit_success_rate, 0.0, 1.0)))
        object.__setattr__(self, "mean_step_height", mean_step_height)
        object.__setattr__(self, "mean_step_width_px", mean_step_width_px)


def refine_edge_polyline(
    coarse_polyline_xy: np.ndarray,
    *,
    edge_prob: np.ndarray,
    input_frame: np.ndarray,
    polygon_mask: np.ndarray,
    score_mode: str = "combined",
    search_radius_px: int = 4,
    max_points: int = 128,
    smoothness_lambda: float = 0.08,
    curvature_lambda: float = 0.04,
    prior_polyline_xy: np.ndarray | None = None,
    temporal_lambda: float = 0.0,
    subpixel_mode: str = "parabolic",
) -> EdgeRefinementResult:
    """Refine a coarse polyline by globally optimizing normal offsets.

    The coarse geometry is first resampled to a denser point set. Each point gets
    a stack of candidate positions along its local normal. Dynamic programming
    then chooses one coherent offset sequence, balancing local edge evidence
    against smoothness, curvature, and an optional temporal prior.
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
    if subpixel_mode not in _SUBPIXEL_MODES:
        raise ValueError("subpixel_mode must be one of: none, parabolic, step_tanh, step_erf.")
    if int(search_radius_px) <= 0:
        raise ValueError("search_radius_px must be positive.")
    if int(max_points) < 2:
        raise ValueError("max_points must be at least 2.")
    if float(smoothness_lambda) < 0.0:
        raise ValueError("smoothness_lambda must be non-negative.")
    if float(curvature_lambda) < 0.0:
        raise ValueError("curvature_lambda must be non-negative.")
    if float(temporal_lambda) < 0.0:
        raise ValueError("temporal_lambda must be non-negative.")

    target_point_count = min(
        int(max_points),
        max(len(coarse_polyline), int(np.ceil(_polyline_length(coarse_polyline))) + 1),
    )
    reference_polyline = (
        np.asarray(coarse_polyline, dtype=np.float64)
        if target_point_count == len(coarse_polyline)
        else resample_polyline_xy(coarse_polyline, target_point_count)
    )

    prior_polyline = None
    if prior_polyline_xy is not None:
        prior = np.asarray(prior_polyline_xy, dtype=np.float64)
        if prior.ndim != 2 or prior.shape[1] != 2:
            raise ValueError("prior_polyline_xy must have shape [N, 2].")
        if len(prior) < 2:
            raise ValueError("prior_polyline_xy must contain at least two points.")
        prior_polyline = (
            np.asarray(prior, dtype=np.float64)
            if len(prior) == len(reference_polyline)
            else resample_polyline_xy(prior, len(reference_polyline))
        )

    prob_norm = _normalize_map(edge_prob_f32, polygon_mask_bool)
    gradient_norm = _normalize_map(_gradient_magnitude(input_frame_f32), polygon_mask_bool)
    offsets = np.linspace(
        -float(search_radius_px),
        float(search_radius_px),
        num=min(97, max(9, int(search_radius_px) * 4 + 1)),
        dtype=np.float64,
    )

    candidates_xy, scores, valid_mask, normals_xy = _build_normal_candidate_grid(
        reference_polyline,
        offsets,
        prob_norm=prob_norm,
        gradient_norm=gradient_norm,
        polygon_mask=polygon_mask_bool,
        score_mode=score_mode,
    )
    selected_indices = _solve_normal_offset_dynamic_programming(
        scores,
        offsets,
        valid_mask,
        candidates_xy=candidates_xy,
        smoothness_lambda=float(smoothness_lambda),
        curvature_lambda=float(curvature_lambda),
        prior_polyline_xy=prior_polyline,
        temporal_lambda=float(temporal_lambda),
    )

    point_indices = np.arange(len(reference_polyline), dtype=np.int32)
    selected_offsets = offsets[selected_indices]
    profile_fit_success_rate = 0.0
    mean_step_height = 0.0
    mean_step_width_px = 0.0

    if subpixel_mode in {"parabolic", "step_tanh", "step_erf"}:
        base_offsets, parabolic_corrections = _parabolic_subpixel_offsets(
            scores,
            offsets,
            selected_indices,
            valid_mask,
        )
    else:
        base_offsets = selected_offsets
        parabolic_corrections = np.zeros_like(selected_offsets, dtype=np.float64)

    if subpixel_mode in {"step_tanh", "step_erf"}:
        refined_offsets, profile_corrections, step_heights, step_widths, fit_success_mask = _fit_step_profile_offsets(
            reference_polyline,
            normals_xy,
            base_offsets,
            input_frame_f32,
            polygon_mask_bool,
            search_radius_px=int(search_radius_px),
            model=subpixel_mode.removeprefix("step_"),
        )
        subpixel_corrections = np.abs(refined_offsets - selected_offsets)
        if fit_success_mask.size:
            profile_fit_success_rate = float(np.mean(fit_success_mask.astype(np.float64)))
        if np.any(fit_success_mask):
            mean_step_height = float(np.mean(step_heights[fit_success_mask]))
            mean_step_width_px = float(np.mean(step_widths[fit_success_mask]))
    else:
        refined_offsets = base_offsets
        subpixel_corrections = parabolic_corrections

    refined_points = reference_polyline + refined_offsets[:, None] * normals_xy
    selected_scores = scores[point_indices, selected_indices]
    selected_shifts = np.abs(refined_offsets)

    refined_polyline = _remove_duplicate_points(refined_points)
    if len(refined_polyline) < 2:
        refined_polyline = reference_polyline[[0, -1]]

    shift_std_px = float(np.std(selected_shifts)) if selected_shifts.size else 0.0
    max_shift_px = float(np.max(selected_shifts)) if selected_shifts.size else 0.0
    radius = max(float(search_radius_px), 1.0)
    shift_stability = 1.0 - np.clip(shift_std_px / radius, 0.0, 1.0)
    max_shift_stability = 1.0 - np.clip(max_shift_px / radius, 0.0, 1.0)
    mean_score = float(np.mean(selected_scores)) if selected_scores.size else 0.0
    stability_score = float(np.clip(0.55 * shift_stability + 0.25 * max_shift_stability + 0.20 * mean_score, 0.0, 1.0))

    return EdgeRefinementResult(
        polyline_xy=refined_polyline,
        point_count=len(refined_polyline),
        score_mode=score_mode,
        search_radius_px=int(search_radius_px),
        mean_score=mean_score,
        mean_shift_px=float(np.mean(selected_shifts)) if selected_shifts.size else 0.0,
        refinement_mode=f"normal_dp_{score_mode}",
        shift_std_px=shift_std_px,
        max_shift_px=max_shift_px,
        stability_score=stability_score,
        subpixel_mode=subpixel_mode,
        mean_subpixel_correction_px=float(np.mean(subpixel_corrections)) if subpixel_corrections.size else 0.0,
        profile_fit_success_rate=profile_fit_success_rate,
        mean_step_height=mean_step_height,
        mean_step_width_px=mean_step_width_px,
    )


def _build_normal_candidate_grid(
    reference_polyline: np.ndarray,
    offsets: np.ndarray,
    *,
    prob_norm: np.ndarray,
    gradient_norm: np.ndarray,
    polygon_mask: np.ndarray,
    score_mode: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    points = np.asarray(reference_polyline, dtype=np.float64)
    offset_values = np.asarray(offsets, dtype=np.float64)
    candidates_xy = np.empty((len(points), len(offset_values), 2), dtype=np.float64)
    scores = np.zeros((len(points), len(offset_values)), dtype=np.float32)
    valid_mask = np.zeros((len(points), len(offset_values)), dtype=bool)
    normals_xy = np.empty((len(points), 2), dtype=np.float64)
    zero_offset_index = int(np.argmin(np.abs(offset_values)))

    for point_index, point_xy in enumerate(points):
        tangent = _local_tangent(points, point_index)
        normal = np.asarray([-tangent[1], tangent[0]], dtype=np.float64)
        normals_xy[point_index] = normal
        point_candidates_xy = point_xy[None, :] + offset_values[:, None] * normal[None, :]
        point_valid_mask = _valid_candidate_mask(point_candidates_xy, polygon_mask)

        candidates_xy[point_index] = point_candidates_xy
        if not np.any(point_valid_mask):
            candidates_xy[point_index, zero_offset_index] = point_xy
            valid_mask[point_index, zero_offset_index] = True
            scores[point_index, zero_offset_index] = 0.0
            continue

        valid_candidates_xy = point_candidates_xy[point_valid_mask]
        prob_scores = _sample_bilinear(prob_norm, valid_candidates_xy)
        gradient_scores = _sample_bilinear(gradient_norm, valid_candidates_xy)
        valid_scores = _combine_scores(prob_scores, gradient_scores, score_mode)
        valid_mask[point_index] = point_valid_mask
        scores[point_index, point_valid_mask] = valid_scores

    return candidates_xy, scores, valid_mask, normals_xy


def _parabolic_subpixel_offsets(
    scores: np.ndarray,
    offsets: np.ndarray,
    selected_indices: np.ndarray,
    valid_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    score_grid = np.asarray(scores, dtype=np.float64)
    offset_values = np.asarray(offsets, dtype=np.float64)
    selected = np.asarray(selected_indices, dtype=np.int32)
    valid_grid = np.asarray(valid_mask, dtype=bool)

    refined_offsets = offset_values[selected].astype(np.float64, copy=True)
    corrections = np.zeros(len(selected), dtype=np.float64)
    if len(offset_values) < 3:
        return refined_offsets, corrections

    for point_index, selected_index in enumerate(selected):
        if selected_index <= 0 or selected_index >= len(offset_values) - 1:
            continue
        neighbor_slice = slice(selected_index - 1, selected_index + 2)
        if not np.all(valid_grid[point_index, neighbor_slice]):
            continue

        left_score, center_score, right_score = score_grid[point_index, neighbor_slice]
        denominator = left_score - (2.0 * center_score) + right_score
        if not np.isfinite(denominator) or denominator >= -1e-12:
            continue

        step = 0.5 * (offset_values[selected_index + 1] - offset_values[selected_index - 1])
        correction = 0.5 * step * (left_score - right_score) / denominator
        correction = float(np.clip(correction, -abs(step), abs(step)))
        if not np.isfinite(correction):
            continue
        refined_offsets[point_index] = offset_values[selected_index] + correction
        corrections[point_index] = abs(correction)

    return refined_offsets, corrections


def _fit_step_profile_offsets(
    reference_polyline: np.ndarray,
    normals_xy: np.ndarray,
    initial_offsets: np.ndarray,
    input_frame: np.ndarray,
    polygon_mask: np.ndarray,
    *,
    search_radius_px: int,
    model: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    points = np.asarray(reference_polyline, dtype=np.float64)
    normals = np.asarray(normals_xy, dtype=np.float64)
    offsets = np.asarray(initial_offsets, dtype=np.float64)
    frame = np.asarray(input_frame, dtype=np.float32)
    mask = np.asarray(polygon_mask, dtype=bool)

    refined_offsets = offsets.copy()
    corrections = np.zeros(len(offsets), dtype=np.float64)
    step_heights = np.zeros(len(offsets), dtype=np.float64)
    step_widths = np.zeros(len(offsets), dtype=np.float64)
    fit_success_mask = np.zeros(len(offsets), dtype=bool)

    fit_radius = float(np.clip(max(2.0, float(search_radius_px) + 1.0), 2.0, 6.0))
    sample_step = 0.25
    profile_offsets = np.arange(-fit_radius, fit_radius + (0.5 * sample_step), sample_step, dtype=np.float64)
    s0_extent = min(1.5, fit_radius * 0.5)
    s0_count = max(13, int(round((2.0 * s0_extent) / 0.125)) + 1)
    s0_candidates = np.linspace(-s0_extent, s0_extent, num=s0_count, dtype=np.float64)
    sigma_max = max(0.5, min(3.0, fit_radius))
    sigma_candidates = np.linspace(0.35, sigma_max, num=10, dtype=np.float64)

    for point_index, (point_xy, normal_xy, initial_offset) in enumerate(zip(points, normals, offsets)):
        sample_points = point_xy[None, :] + (initial_offset + profile_offsets)[:, None] * normal_xy[None, :]
        valid_mask = _valid_candidate_mask(sample_points, mask)
        if np.count_nonzero(valid_mask) < 9:
            continue

        profile_s = profile_offsets[valid_mask]
        profile_values = _sample_bilinear(frame, sample_points[valid_mask]).astype(np.float64, copy=False)
        finite_mask = np.isfinite(profile_values)
        if np.count_nonzero(finite_mask) < 9:
            continue
        profile_s = profile_s[finite_mask]
        profile_values = profile_values[finite_mask]

        fit = _fit_step_profile_1d(
            profile_s,
            profile_values,
            model=model,
            s0_candidates=s0_candidates,
            sigma_candidates=sigma_candidates,
        )
        if fit is None:
            continue

        s0, step_height, step_width = fit
        candidate_offset = float(initial_offset + s0)
        candidate_point = point_xy + candidate_offset * normal_xy
        if not bool(_valid_candidate_mask(candidate_point[None, :], mask)[0]):
            continue

        refined_offsets[point_index] = candidate_offset
        corrections[point_index] = abs(float(s0))
        step_heights[point_index] = float(step_height)
        step_widths[point_index] = float(step_width)
        fit_success_mask[point_index] = True

    return refined_offsets, corrections, step_heights, step_widths, fit_success_mask


def _fit_step_profile_1d(
    profile_s: np.ndarray,
    profile_values: np.ndarray,
    *,
    model: str,
    s0_candidates: np.ndarray,
    sigma_candidates: np.ndarray,
) -> tuple[float, float, float] | None:
    s_values = np.asarray(profile_s, dtype=np.float64)
    y_values = np.asarray(profile_values, dtype=np.float64)
    if s_values.ndim != 1 or y_values.ndim != 1 or len(s_values) != len(y_values):
        raise ValueError("profile_s and profile_values must be one-dimensional arrays with the same length.")
    value_range = float(np.ptp(y_values))
    if len(s_values) < 9 or value_range <= 1e-8:
        return None

    best_error = np.inf
    best_s0 = 0.0
    best_step_height = 0.0
    best_step_width = 0.0
    ones = np.ones_like(s_values)

    for sigma in np.asarray(sigma_candidates, dtype=np.float64):
        if sigma <= 0.0:
            continue
        for s0 in np.asarray(s0_candidates, dtype=np.float64):
            transition = _step_transition(s_values, float(s0), float(sigma), model)
            design = np.column_stack((ones, s_values, transition))
            try:
                coefficients, *_ = np.linalg.lstsq(design, y_values, rcond=None)
            except np.linalg.LinAlgError:
                continue
            fitted = design @ coefficients
            error = float(np.mean(np.square(y_values - fitted)))
            if error < best_error:
                best_error = error
                best_s0 = float(s0)
                best_step_height = float(coefficients[2])
                best_step_width = float(sigma)

    if not np.isfinite(best_error):
        return None
    if abs(best_step_height) < 0.10 * value_range:
        return None
    rmse = math.sqrt(best_error)
    if rmse > max(0.35 * value_range, 1e-8):
        return None
    return best_s0, best_step_height, best_step_width


def _step_transition(s_values: np.ndarray, s0: float, sigma: float, model: str) -> np.ndarray:
    scaled = (np.asarray(s_values, dtype=np.float64) - float(s0)) / max(float(sigma), 1e-6)
    if model == "tanh":
        return 0.5 * (1.0 + np.tanh(scaled))
    if model == "erf":
        erf_values = np.asarray([math.erf(float(value)) for value in scaled.ravel()], dtype=np.float64)
        return 0.5 * (1.0 + erf_values.reshape(scaled.shape))
    raise ValueError("model must be one of: tanh, erf.")


def _solve_normal_offset_dynamic_programming(
    scores: np.ndarray,
    offsets: np.ndarray,
    valid_mask: np.ndarray,
    *,
    candidates_xy: np.ndarray,
    smoothness_lambda: float,
    curvature_lambda: float,
    prior_polyline_xy: np.ndarray | None,
    temporal_lambda: float,
) -> np.ndarray:
    score_grid = np.asarray(scores, dtype=np.float64)
    offset_values = np.asarray(offsets, dtype=np.float64)
    valid_grid = np.asarray(valid_mask, dtype=bool)
    if score_grid.ndim != 2:
        raise ValueError("scores must have shape [N, K].")
    if valid_grid.shape != score_grid.shape:
        raise ValueError("valid_mask must match scores shape.")
    if candidates_xy.shape[:2] != score_grid.shape:
        raise ValueError("candidates_xy must have shape [N, K, 2].")

    point_count, candidate_count = score_grid.shape
    if point_count < 2:
        raise ValueError("At least two points are required for refinement DP.")
    if candidate_count < 1:
        raise ValueError("At least one candidate offset is required for refinement DP.")

    unary_cost = 1.0 - np.clip(score_grid, 0.0, 1.0)
    unary_cost[~valid_grid] = np.inf
    if prior_polyline_xy is not None and temporal_lambda > 0.0:
        prior = np.asarray(prior_polyline_xy, dtype=np.float64)
        if prior.shape != (point_count, 2):
            raise ValueError("prior_polyline_xy must match the resampled reference polyline shape.")
        prior_distance_sq = np.sum(np.square(np.asarray(candidates_xy, dtype=np.float64) - prior[:, None, :]), axis=2)
        unary_cost = unary_cost + float(temporal_lambda) * prior_distance_sq

    for point_index in range(point_count):
        if not np.any(np.isfinite(unary_cost[point_index])):
            zero_offset_index = int(np.argmin(np.abs(offset_values)))
            unary_cost[point_index, zero_offset_index] = 1.0

    offset_diff_sq = np.square(offset_values[None, :] - offset_values[:, None])
    if point_count == 2:
        pair_cost = unary_cost[0, :, None] + unary_cost[1, None, :] + float(smoothness_lambda) * offset_diff_sq
        first_index, second_index = np.unravel_index(int(np.argmin(pair_cost)), pair_cost.shape)
        return np.asarray([first_index, second_index], dtype=np.int32)

    dp_previous = unary_cost[0, :, None] + unary_cost[1, None, :] + float(smoothness_lambda) * offset_diff_sq
    backpointers: list[np.ndarray] = []
    prevprev_offsets = offset_values[:, None]
    prev_offsets = offset_values[None, :]

    for point_index in range(2, point_count):
        dp_next = np.full((candidate_count, candidate_count), np.inf, dtype=np.float64)
        backpointer = np.zeros((candidate_count, candidate_count), dtype=np.int32)
        for current_index, current_offset in enumerate(offset_values):
            smoothness_cost = float(smoothness_lambda) * np.square(current_offset - offset_values)
            curvature_cost = float(curvature_lambda) * np.square(current_offset - 2.0 * prev_offsets + prevprev_offsets)
            transition_cost = dp_previous + smoothness_cost[None, :] + curvature_cost
            best_prevprev_indices = np.argmin(transition_cost, axis=0)
            best_transition_cost = transition_cost[best_prevprev_indices, np.arange(candidate_count)]
            dp_next[:, current_index] = best_transition_cost + unary_cost[point_index, current_index]
            backpointer[:, current_index] = best_prevprev_indices.astype(np.int32, copy=False)
        backpointers.append(backpointer)
        dp_previous = dp_next

    final_prev_index, final_current_index = np.unravel_index(int(np.argmin(dp_previous)), dp_previous.shape)
    selected_indices = np.empty(point_count, dtype=np.int32)
    selected_indices[-2] = int(final_prev_index)
    selected_indices[-1] = int(final_current_index)

    for point_index in range(point_count - 1, 1, -1):
        backpointer = backpointers[point_index - 2]
        selected_indices[point_index - 2] = int(backpointer[selected_indices[point_index - 1], selected_indices[point_index]])

    return selected_indices


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
