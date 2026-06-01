"""Molecular row-orientation metrics estimated from detection centroids."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from moltrack.core.data_models import AnalysisRegionKind, MolTrackProject
from moltrack.core.population_metrics import _default_analysis_detections_by_effective_region


@dataclass(frozen=True)
class MolecularRowOrientationMetricRow:
    """Dominant row orientation for one working frame and analysis region."""

    working_frame_index: int
    source_frame_index: int
    region_name: str
    region_kind: str
    detection_count: int
    orientation_degrees: float
    orientation_confidence: float


@dataclass(frozen=True)
class MolecularRowOrientationMetrics:
    """PCA-based molecular row-orientation estimates."""

    rows: tuple[MolecularRowOrientationMetricRow, ...]

    @classmethod
    def from_project(cls, project: MolTrackProject) -> MolecularRowOrientationMetrics:
        rows: list[MolecularRowOrientationMetricRow] = []
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
                orientation_degrees, confidence = _estimate_orientation_degrees_and_confidence(
                    tuple(detection.centroid_xy for detection in detections)
                )
                rows.append(
                    MolecularRowOrientationMetricRow(
                        working_frame_index=working_frame.working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        region_name=region.name,
                        region_kind=region.kind.value,
                        detection_count=len(detections),
                        orientation_degrees=orientation_degrees,
                        orientation_confidence=confidence,
                    )
                )
        return cls(rows=tuple(rows))


def _estimate_orientation_degrees_and_confidence(
    points_xy: tuple[tuple[float, float], ...],
) -> tuple[float, float]:
    if len(points_xy) < 2:
        return 0.0, 0.0
    points = np.asarray(points_xy, dtype=np.float64)
    centered = points - points.mean(axis=0)
    scatter = centered.T @ centered
    eigenvalues, eigenvectors = np.linalg.eigh(scatter)
    largest_index = int(np.argmax(eigenvalues))
    largest = float(eigenvalues[largest_index])
    smallest = float(eigenvalues[1 - largest_index])
    if largest <= 0.0:
        return 0.0, 0.0
    direction = eigenvectors[:, largest_index]
    angle = math.degrees(math.atan2(float(direction[1]), float(direction[0]))) % 180.0
    confidence = max(0.0, min(1.0, 1.0 - smallest / largest))
    return float(angle), float(confidence)
