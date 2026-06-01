"""Molecular row-spacing metrics estimated from detection centroids."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from moltrack.core.data_models import AnalysisRegionKind, MolTrackProject
from moltrack.core.population_metrics import _default_analysis_detections_by_effective_region
from moltrack.core.row_orientation_metrics import _estimate_orientation_degrees_and_confidence


@dataclass(frozen=True)
class MolecularRowSpacingMetricRow:
    """Estimated spacing between molecular rows for one frame and region."""

    working_frame_index: int
    source_frame_index: int
    region_name: str
    region_kind: str
    detection_count: int
    orientation_degrees: float
    row_count: int
    row_spacing_px: float


@dataclass(frozen=True)
class MolecularRowSpacingMetrics:
    """Projection-based molecular row-spacing estimates."""

    rows: tuple[MolecularRowSpacingMetricRow, ...]

    @classmethod
    def from_project(cls, project: MolTrackProject) -> MolecularRowSpacingMetrics:
        rows: list[MolecularRowSpacingMetricRow] = []
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
                points_xy = tuple(detection.centroid_xy for detection in detections)
                orientation_degrees, row_count, row_spacing_px = _estimate_row_spacing_px(points_xy)
                rows.append(
                    MolecularRowSpacingMetricRow(
                        working_frame_index=working_frame.working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        region_name=region.name,
                        region_kind=region.kind.value,
                        detection_count=len(detections),
                        orientation_degrees=orientation_degrees,
                        row_count=row_count,
                        row_spacing_px=row_spacing_px,
                    )
                )
        return cls(rows=tuple(rows))


def _estimate_row_spacing_px(points_xy: tuple[tuple[float, float], ...]) -> tuple[float, int, float]:
    orientation_degrees, _confidence = _estimate_orientation_degrees_and_confidence(points_xy)
    if len(points_xy) < 2:
        return orientation_degrees, 0, 0.0

    points = np.asarray(points_xy, dtype=np.float64)
    theta = math.radians(orientation_degrees)
    normal = np.asarray((-math.sin(theta), math.cos(theta)), dtype=np.float64)
    projections = points @ normal
    row_positions = _unique_projection_positions_px(projections)
    if len(row_positions) < 2:
        return orientation_degrees, len(row_positions), 0.0
    gaps = np.diff(np.asarray(row_positions, dtype=np.float64))
    return orientation_degrees, len(row_positions), float(np.median(gaps))


def _unique_projection_positions_px(projections: np.ndarray, *, eps: float = 1e-6) -> tuple[float, ...]:
    if projections.size == 0:
        return tuple()
    sorted_values = np.sort(np.asarray(projections, dtype=np.float64))
    groups: list[list[float]] = [[float(sorted_values[0])]]
    for value in sorted_values[1:]:
        value = float(value)
        if abs(value - groups[-1][-1]) <= eps:
            groups[-1].append(value)
        else:
            groups.append([value])
    return tuple(float(np.mean(group)) for group in groups)
