"""Centroid-based nearest-neighbour metrics for MolTrack detections."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from moltrack.core.data_models import AnalysisRegionKind, MolTrackProject
from moltrack.core.population_metrics import _default_analysis_detections_by_effective_region


@dataclass(frozen=True)
class CentroidNearestNeighbourMetricRow:
    """Nearest-neighbour distribution for one working frame and analysis region."""

    working_frame_index: int
    source_frame_index: int
    region_name: str
    region_kind: str
    detection_count: int
    nearest_neighbour_count: int
    nearest_neighbour_distances_px: tuple[float, ...]
    mean_nearest_neighbour_distance_px: float
    median_nearest_neighbour_distance_px: float


@dataclass(frozen=True)
class CentroidNearestNeighbourMetrics:
    """Nearest-neighbour metrics computed from reviewed molecular detection centroids."""

    rows: tuple[CentroidNearestNeighbourMetricRow, ...]

    @classmethod
    def from_project(cls, project: MolTrackProject) -> CentroidNearestNeighbourMetrics:
        rows: list[CentroidNearestNeighbourMetricRow] = []
        for working_frame in project.working_series.frames:
            active_regions = project.analysis_regions_for_working_frame(working_frame.working_frame_index)
            detections_by_region = _default_analysis_detections_by_effective_region(
                project,
                working_frame.working_frame_index,
                active_regions,
            )
            for region in active_regions:
                if region.kind == AnalysisRegionKind.IGNORE:
                    continue
                detections = detections_by_region.get(region.name, ())
                distances = _nearest_neighbour_distances_px(
                    tuple(detection.centroid_xy for detection in detections)
                )
                rows.append(
                    CentroidNearestNeighbourMetricRow(
                        working_frame_index=working_frame.working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        region_name=region.name,
                        region_kind=region.kind.value,
                        detection_count=len(detections),
                        nearest_neighbour_count=len(distances),
                        nearest_neighbour_distances_px=distances,
                        mean_nearest_neighbour_distance_px=_mean_or_zero(distances),
                        median_nearest_neighbour_distance_px=_median_or_zero(distances),
                    )
                )
        return cls(rows=tuple(rows))


def _nearest_neighbour_distances_px(points_xy: tuple[tuple[float, float], ...]) -> tuple[float, ...]:
    if len(points_xy) < 2:
        return tuple()
    points = np.asarray(points_xy, dtype=np.float64)
    deltas = points[:, None, :] - points[None, :, :]
    distances = np.sqrt(np.sum(deltas * deltas, axis=2))
    np.fill_diagonal(distances, np.inf)
    nearest = np.min(distances, axis=1)
    return tuple(float(value) for value in nearest)


def _mean_or_zero(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _median_or_zero(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    return float(np.median(np.asarray(values, dtype=np.float64)))
