"""Helpers for hybrid edge tracking that combine DexiNed geometry with tracked control points."""

from __future__ import annotations

import numpy as np


def resample_polyline_xy(polyline_xy: np.ndarray, point_count: int) -> np.ndarray:
    """Resample a polyline to a fixed number of points using arc-length interpolation."""

    polyline = np.asarray(polyline_xy, dtype=np.float64)
    if polyline.ndim != 2 or polyline.shape[1] != 2:
        raise ValueError("polyline_xy must have shape [N, 2].")
    if len(polyline) < 2:
        raise ValueError("polyline_xy must contain at least two points.")
    if point_count < 2:
        raise ValueError("point_count must be at least 2.")

    segment_vectors = np.diff(polyline, axis=0)
    segment_lengths = np.linalg.norm(segment_vectors, axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = float(cumulative[-1])

    if total_length <= 1e-9:
        interpolation = np.linspace(0.0, 1.0, point_count, dtype=np.float64)[:, None]
        return polyline[0][None, :] * (1.0 - interpolation) + polyline[-1][None, :] * interpolation

    sample_positions = np.linspace(0.0, total_length, point_count, dtype=np.float64)
    resampled = np.empty((point_count, 2), dtype=np.float64)
    segment_index = 0

    for sample_index, position in enumerate(sample_positions):
        while segment_index < len(segment_lengths) - 1 and position > cumulative[segment_index + 1]:
            segment_index += 1
        start = polyline[segment_index]
        end = polyline[segment_index + 1]
        length = segment_lengths[segment_index]
        if length <= 1e-9:
            resampled[sample_index] = end
            continue
        alpha = (position - cumulative[segment_index]) / length
        resampled[sample_index] = start + alpha * (end - start)

    resampled[0] = polyline[0]
    resampled[-1] = polyline[-1]
    return resampled


def sample_polyline_control_points(polyline_xy: np.ndarray, point_count: int) -> np.ndarray:
    """Sample ordered control points along a polyline for temporal tracking."""

    return resample_polyline_xy(polyline_xy, point_count)


def _match_polyline_direction(reference_xy: np.ndarray, candidate_xy: np.ndarray) -> np.ndarray:
    reference = np.asarray(reference_xy, dtype=np.float64)
    candidate = np.asarray(candidate_xy, dtype=np.float64)
    if len(reference) < 2 or len(candidate) < 2:
        return candidate
    reference_direction = reference[-1] - reference[0]
    candidate_direction = candidate[-1] - candidate[0]
    if float(np.dot(reference_direction, candidate_direction)) < 0.0:
        return np.asarray(candidate[::-1], dtype=np.float64)
    return candidate


def hybrid_refine_polyline(
    reference_polyline_xy: np.ndarray,
    tracked_points_xy: np.ndarray,
    *,
    tracker_blend: float = 0.35,
) -> np.ndarray:
    """Blend tracker-predicted control points with a per-frame DexiNed polyline."""

    if not 0.0 <= tracker_blend <= 1.0:
        raise ValueError("tracker_blend must be inside [0, 1].")

    tracked_points = np.asarray(tracked_points_xy, dtype=np.float64)
    if tracked_points.ndim != 2 or tracked_points.shape[1] != 2:
        raise ValueError("tracked_points_xy must have shape [N, 2].")
    if len(tracked_points) < 2:
        raise ValueError("tracked_points_xy must contain at least two points.")

    reference_resampled = resample_polyline_xy(reference_polyline_xy, len(tracked_points))
    tracked_points = _match_polyline_direction(reference_resampled, tracked_points)
    return (1.0 - float(tracker_blend)) * reference_resampled + float(tracker_blend) * tracked_points
