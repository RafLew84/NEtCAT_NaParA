"""Polyline-based measurements for STM step-edge tracking."""

from __future__ import annotations

import numpy as np

from nanotrack.core import EdgeMetrics


def compute_edge_metrics(
    polyline_xy: np.ndarray,
    *,
    pixel_size_nm: tuple[float | None, float | None] | None = None,
) -> EdgeMetrics:
    """Compute geometric roughness metrics from a step-edge polyline."""

    polyline = np.asarray(polyline_xy, dtype=np.float64)
    if polyline.ndim != 2 or polyline.shape[1] != 2:
        raise ValueError("polyline_xy must have shape [N, 2].")
    if len(polyline) < 2:
        raise ValueError("polyline_xy must contain at least two points.")
    if not np.all(np.isfinite(polyline)):
        raise ValueError("polyline_xy values must be finite.")

    length_px = _polyline_length(polyline)
    roughness_rms_px, waviness_amplitude_px = _trend_line_roughness(polyline)
    mean_curvature, max_curvature = _discrete_curvature(polyline)

    length_nm = None
    roughness_rms_nm = None
    waviness_amplitude_nm = None
    if pixel_size_nm is not None:
        pixel_size_x_nm, pixel_size_y_nm = pixel_size_nm
        if pixel_size_x_nm is not None and pixel_size_y_nm is not None:
            scaled_polyline = polyline * np.asarray([pixel_size_x_nm, pixel_size_y_nm], dtype=np.float64)
            length_nm = _polyline_length(scaled_polyline)
            roughness_rms_nm, waviness_amplitude_nm = _trend_line_roughness(scaled_polyline)

    return EdgeMetrics(
        length_px=length_px,
        length_nm=length_nm,
        roughness_rms_px=roughness_rms_px,
        roughness_rms_nm=roughness_rms_nm,
        mean_curvature=mean_curvature,
        max_curvature=max_curvature,
        waviness_amplitude_px=waviness_amplitude_px,
        waviness_amplitude_nm=waviness_amplitude_nm,
    )


def _polyline_length(polyline_xy: np.ndarray) -> float:
    deltas = np.diff(np.asarray(polyline_xy, dtype=np.float64), axis=0)
    if len(deltas) == 0:
        return 0.0
    return float(np.sum(np.linalg.norm(deltas, axis=1)))


def _principal_axis(points_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centered = points_xy - np.mean(points_xy, axis=0, keepdims=True)
    if len(points_xy) == 2:
        direction = centered[1] - centered[0]
    else:
        _u, _s, vh = np.linalg.svd(centered, full_matrices=False)
        direction = vh[0]
    direction_norm = float(np.linalg.norm(direction))
    if direction_norm <= 1e-12:
        direction = np.asarray([1.0, 0.0], dtype=np.float64)
    else:
        direction = direction / direction_norm
    normal = np.asarray([-direction[1], direction[0]], dtype=np.float64)
    return direction, normal


def _trend_line_roughness(polyline_xy: np.ndarray) -> tuple[float, float]:
    points = np.asarray(polyline_xy, dtype=np.float64)
    centroid = np.mean(points, axis=0, keepdims=True)
    _direction, normal = _principal_axis(points)
    signed_distances = (points - centroid) @ normal
    if signed_distances.size == 0:
        return 0.0, 0.0
    roughness_rms = float(np.sqrt(np.mean(np.square(signed_distances))))
    waviness_amplitude = float(np.max(signed_distances) - np.min(signed_distances))
    return roughness_rms, waviness_amplitude


def _discrete_curvature(polyline_xy: np.ndarray) -> tuple[float, float]:
    points = np.asarray(polyline_xy, dtype=np.float64)
    if len(points) < 3:
        return 0.0, 0.0

    curvatures: list[float] = []
    for index in range(1, len(points) - 1):
        prev_segment = points[index] - points[index - 1]
        next_segment = points[index + 1] - points[index]
        prev_length = float(np.linalg.norm(prev_segment))
        next_length = float(np.linalg.norm(next_segment))
        if prev_length <= 1e-12 or next_length <= 1e-12:
            continue

        cos_theta = float(np.dot(prev_segment, next_segment) / (prev_length * next_length))
        cos_theta = float(np.clip(cos_theta, -1.0, 1.0))
        turning_angle = float(np.arccos(cos_theta))
        arc_length = 0.5 * (prev_length + next_length)
        if arc_length <= 1e-12:
            continue
        curvatures.append(turning_angle / arc_length)

    if not curvatures:
        return 0.0, 0.0
    curvature_array = np.asarray(curvatures, dtype=np.float64)
    return float(np.mean(curvature_array)), float(np.max(curvature_array))
