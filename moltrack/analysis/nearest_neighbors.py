from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .position_plot import MolecularPositionPlotData


NEAREST_NEIGHBOR_ANGLE_BIN_EDGES_DEGREES = tuple(float(value) for value in range(0, 181, 10))


@dataclass(frozen=True)
class MolecularNearestNeighborMetrics:
    """Nearest-neighbor distances and aggregates for one position context."""

    frame_index: int
    source_view: str
    unit: str
    point_count: int
    nearest_neighbor_distances: tuple[float, ...]
    mean_distance: float | None
    median_distance: float | None
    min_distance: float | None
    max_distance: float | None


@dataclass(frozen=True)
class MolecularNearestNeighborAngleMetrics:
    """Axial nearest-neighbor angles and their fixed-bin histogram."""

    frame_index: int
    source_view: str
    unit: str
    point_count: int
    nearest_neighbor_angles_degrees: tuple[float, ...]
    line_order_score: float | None
    histogram_bin_edges_degrees: tuple[float, ...]
    histogram_counts: tuple[int, ...]


def compute_molecular_nearest_neighbor_metrics(
    plot_data: MolecularPositionPlotData,
) -> MolecularNearestNeighborMetrics:
    """Compute one nearest-neighbor distance per molecular position."""

    if not isinstance(plot_data, MolecularPositionPlotData):
        raise TypeError("plot_data must be MolecularPositionPlotData.")
    points = np.asarray(plot_data.points_xy, dtype=np.float64)
    if plot_data.point_count < 2:
        return MolecularNearestNeighborMetrics(
            frame_index=plot_data.frame_index,
            source_view=plot_data.source_view,
            unit=plot_data.unit,
            point_count=plot_data.point_count,
            nearest_neighbor_distances=(),
            mean_distance=None,
            median_distance=None,
            min_distance=None,
            max_distance=None,
        )

    nearest, _indices = _nearest_neighbor_assignments(points)
    return MolecularNearestNeighborMetrics(
        frame_index=plot_data.frame_index,
        source_view=plot_data.source_view,
        unit=plot_data.unit,
        point_count=plot_data.point_count,
        nearest_neighbor_distances=tuple(float(value) for value in nearest),
        mean_distance=float(np.mean(nearest)),
        median_distance=float(np.median(nearest)),
        min_distance=float(np.min(nearest)),
        max_distance=float(np.max(nearest)),
    )


def compute_molecular_nearest_neighbor_angle_metrics(
    plot_data: MolecularPositionPlotData,
) -> MolecularNearestNeighborAngleMetrics:
    """Compute axial angles from each position to its nearest neighbor."""

    if not isinstance(plot_data, MolecularPositionPlotData):
        raise TypeError("plot_data must be MolecularPositionPlotData.")
    edges = NEAREST_NEIGHBOR_ANGLE_BIN_EDGES_DEGREES
    if plot_data.point_count < 2:
        return MolecularNearestNeighborAngleMetrics(
            frame_index=plot_data.frame_index,
            source_view=plot_data.source_view,
            unit=plot_data.unit,
            point_count=plot_data.point_count,
            nearest_neighbor_angles_degrees=(),
            line_order_score=None,
            histogram_bin_edges_degrees=edges,
            histogram_counts=(0,) * (len(edges) - 1),
        )

    points = np.asarray(plot_data.points_xy, dtype=np.float64)
    _distances, indices = _nearest_neighbor_assignments(points)
    vectors = points[indices] - points
    angles = np.mod(np.degrees(np.arctan2(vectors[:, 1], vectors[:, 0])), 180.0)
    axial_vectors = np.exp(2j * np.deg2rad(angles))
    line_order_score = float(np.clip(np.abs(np.mean(axial_vectors)), 0.0, 1.0))
    counts, _edges = np.histogram(angles, bins=np.asarray(edges, dtype=np.float64))
    return MolecularNearestNeighborAngleMetrics(
        frame_index=plot_data.frame_index,
        source_view=plot_data.source_view,
        unit=plot_data.unit,
        point_count=plot_data.point_count,
        nearest_neighbor_angles_degrees=tuple(float(value) for value in angles),
        line_order_score=line_order_score,
        histogram_bin_edges_degrees=edges,
        histogram_counts=tuple(int(value) for value in counts),
    )


def _nearest_neighbor_assignments(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return nearest distances/indices, resolving exact-distance ties by point index."""

    tree = cKDTree(points)
    query_distances, _query_indices = tree.query(points, k=2)
    nearest_distances = np.empty(points.shape[0], dtype=np.float64)
    nearest_indices = np.empty(points.shape[0], dtype=np.int64)
    for point_index, point in enumerate(points):
        approximate_distance = float(query_distances[point_index, 1])
        tolerance = max(1e-12, approximate_distance * 1e-12)
        candidates = tree.query_ball_point(point, r=approximate_distance + tolerance)
        ranked = []
        for candidate_index in candidates:
            if candidate_index == point_index:
                continue
            delta = points[candidate_index] - point
            squared_distance = float(np.dot(delta, delta))
            ranked.append((squared_distance, int(candidate_index)))
        if not ranked:
            raise RuntimeError("Could not resolve a nearest neighbor.")
        squared_distance, nearest_index = min(ranked)
        nearest_distances[point_index] = squared_distance**0.5
        nearest_indices[point_index] = nearest_index
    return nearest_distances, nearest_indices
