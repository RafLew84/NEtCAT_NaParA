"""Molecular row-order score estimated from detection centroids."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from moltrack.core.data_models import AnalysisRegionKind, MolTrackProject
from moltrack.core.population_metrics import _default_analysis_detections_by_effective_region
from moltrack.core.row_orientation_metrics import _estimate_orientation_degrees_and_confidence


@dataclass(frozen=True)
class MolecularRowOrderMetricRow:
    """First-pass molecular row-order score for one frame and analysis region."""

    working_frame_index: int
    source_frame_index: int
    region_name: str
    region_kind: str
    detection_count: int
    assigned_detection_count: int
    orientation_degrees: float
    row_count: int
    row_spacing_px: float
    row_order_score: float


@dataclass(frozen=True)
class MolecularRowOrderMetrics:
    """Centroid-based molecular row-order metrics."""

    rows: tuple[MolecularRowOrderMetricRow, ...]

    @classmethod
    def from_project(cls, project: MolTrackProject) -> MolecularRowOrderMetrics:
        rows: list[MolecularRowOrderMetricRow] = []
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
                result = _estimate_row_order(tuple(detection.centroid_xy for detection in detections))
                rows.append(
                    MolecularRowOrderMetricRow(
                        working_frame_index=working_frame.working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        region_name=region.name,
                        region_kind=region.kind.value,
                        detection_count=len(detections),
                        assigned_detection_count=result.assigned_detection_count,
                        orientation_degrees=result.orientation_degrees,
                        row_count=result.row_count,
                        row_spacing_px=result.row_spacing_px,
                        row_order_score=result.row_order_score,
                    )
                )
        return cls(rows=tuple(rows))


@dataclass(frozen=True)
class _RowOrderEstimate:
    assigned_detection_count: int
    orientation_degrees: float
    row_count: int
    row_spacing_px: float
    row_order_score: float


def _estimate_row_order(
    points_xy: tuple[tuple[float, float], ...],
    *,
    row_projection_tolerance_px: float = 1.0,
    min_detections_per_row: int = 2,
) -> _RowOrderEstimate:
    orientation_degrees, _confidence = _estimate_orientation_degrees_and_confidence(points_xy)
    if len(points_xy) < 2:
        return _RowOrderEstimate(0, orientation_degrees, 0, 0.0, 0.0)

    points = np.asarray(points_xy, dtype=np.float64)
    theta = math.radians(orientation_degrees)
    normal = np.asarray((-math.sin(theta), math.cos(theta)), dtype=np.float64)
    projections = points @ normal
    row_groups = _projection_row_groups_px(projections, tolerance_px=row_projection_tolerance_px)
    accepted_groups = tuple(
        group
        for group in row_groups
        if len(group) >= min_detections_per_row
    )
    assigned_detection_count = sum(len(group) for group in accepted_groups)
    if len(accepted_groups) < 2 or assigned_detection_count == 0:
        return _RowOrderEstimate(assigned_detection_count, orientation_degrees, len(accepted_groups), 0.0, 0.0)

    row_positions = np.asarray([float(np.mean(group)) for group in accepted_groups], dtype=np.float64)
    row_positions.sort()
    gaps = np.diff(row_positions)
    row_spacing_px = float(np.median(gaps))
    if row_spacing_px <= 0.0:
        return _RowOrderEstimate(assigned_detection_count, orientation_degrees, len(accepted_groups), 0.0, 0.0)

    assigned_fraction = assigned_detection_count / len(points_xy)
    residuals = np.asarray(
        [
            abs(float(value) - float(np.mean(group)))
            for group in accepted_groups
            for value in group
        ],
        dtype=np.float64,
    )
    residual_scale = max(row_projection_tolerance_px, row_spacing_px / 2.0)
    residual_score = 1.0 - float(np.median(residuals)) / residual_scale
    if len(gaps) < 2:
        gap_score = 1.0
    else:
        gap_median = float(np.median(gaps))
        gap_mad = float(np.median(np.abs(gaps - gap_median)))
        gap_score = 1.0 - gap_mad / max(gap_median, 1e-9)
    row_order_score = _clamp01(assigned_fraction * _clamp01(residual_score) * _clamp01(gap_score))
    return _RowOrderEstimate(
        assigned_detection_count,
        orientation_degrees,
        len(accepted_groups),
        row_spacing_px,
        row_order_score,
    )


def _projection_row_groups_px(projections: np.ndarray, *, tolerance_px: float) -> tuple[tuple[float, ...], ...]:
    if projections.size == 0:
        return tuple()
    sorted_values = np.sort(np.asarray(projections, dtype=np.float64))
    groups: list[list[float]] = [[float(sorted_values[0])]]
    for value in sorted_values[1:]:
        value = float(value)
        if abs(value - float(np.mean(groups[-1]))) <= tolerance_px:
            groups[-1].append(value)
        else:
            groups.append([value])
    return tuple(tuple(group) for group in groups)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
