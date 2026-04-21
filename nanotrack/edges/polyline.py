"""Helpers for reducing a dominant edge mask to a centerline polyline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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


def dominant_edge_to_polyline(
    edge_mask: np.ndarray,
    *,
    edge_prob: np.ndarray | None = None,
    max_points: int = 64,
) -> EdgePolylineExtraction:
    """Approximate one dominant edge component by a centerline polyline.

    The edge pixels are projected onto their weighted principal axis and then
    collapsed into ordered bins along that axis. Each occupied bin contributes
    one weighted center point, producing a compact polyline that follows the
    dominant orientation of the edge.
    """

    mask = np.asarray(edge_mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("edge_mask must have shape [H, W].")
    if not np.any(mask):
        raise ValueError("edge_mask must contain at least one True pixel.")
    if max_points < 2:
        raise ValueError("max_points must be at least 2.")

    coords_yx = np.argwhere(mask)
    coords_xy = np.column_stack([coords_yx[:, 1], coords_yx[:, 0]]).astype(np.float64, copy=False)

    if edge_prob is None:
        weights = np.ones(len(coords_xy), dtype=np.float64)
    else:
        edge_prob_f32 = np.asarray(edge_prob, dtype=np.float32)
        if edge_prob_f32.shape != mask.shape:
            raise ValueError("edge_prob must match edge_mask shape.")
        weights = np.asarray(edge_prob_f32[mask], dtype=np.float64)
        if not np.all(np.isfinite(weights)):
            raise ValueError("edge_prob values must be finite on edge_mask.")
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
