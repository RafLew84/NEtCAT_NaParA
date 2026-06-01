"""Population-level metrics for MolTrack detections."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from moltrack.core.data_models import (
    AnalysisRegion,
    AnalysisRegionKind,
    MolTrackProject,
    MolecularDetection,
    _point_inside_analysis_region,
)


@dataclass(frozen=True)
class PopulationMetricRow:
    """One population metric row for a working frame and analysis region."""

    working_frame_index: int
    source_frame_index: int
    region_name: str
    region_kind: str
    detection_count: int
    region_area_px2: float
    detection_footprint_area_px2: float
    density_per_px2: float
    detection_footprint_coverage: float


@dataclass(frozen=True)
class PopulationMetrics:
    """Population metric table computed from a MolTrack project."""

    rows: tuple[PopulationMetricRow, ...]

    @classmethod
    def from_project(cls, project: MolTrackProject) -> PopulationMetrics:
        rows: list[PopulationMetricRow] = []
        for working_frame in project.working_series.frames:
            working_frame_index = working_frame.working_frame_index
            active_regions = project.analysis_regions_for_working_frame(working_frame_index)
            detections_by_region = _default_analysis_detections_by_effective_region(
                project,
                working_frame_index,
                active_regions,
            )
            for region in active_regions:
                if region.kind == AnalysisRegionKind.IGNORE:
                    continue
                region_detections = detections_by_region.get(region.name, ())
                region_area = _analysis_region_area_px2(region)
                footprint_area = sum(_detection_bbox_area_px2(detection) for detection in region_detections)
                rows.append(
                    PopulationMetricRow(
                        working_frame_index=working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        region_name=region.name,
                        region_kind=region.kind.value,
                        detection_count=len(region_detections),
                        region_area_px2=region_area,
                        detection_footprint_area_px2=footprint_area,
                        density_per_px2=0.0 if region_area <= 0.0 else len(region_detections) / region_area,
                        detection_footprint_coverage=0.0 if region_area <= 0.0 else footprint_area / region_area,
                    )
                )
        return cls(rows=tuple(rows))


def _default_analysis_detections_by_effective_region(
    project: MolTrackProject,
    working_frame_index: int,
    active_regions: tuple[AnalysisRegion, ...],
) -> dict[str, tuple[MolecularDetection, ...]]:
    regions_by_name = {region.name: region for region in active_regions}
    detections_by_region: dict[str, list[MolecularDetection]] = {
        region.name: []
        for region in active_regions
    }
    for detection in project.molecular_detections_for_working_frame(working_frame_index):
        if not detection.included_in_default_analysis:
            continue
        region = _effective_detection_region(detection, active_regions, regions_by_name)
        if region is None or region.kind == AnalysisRegionKind.IGNORE:
            continue
        detections_by_region.setdefault(region.name, []).append(detection)
    return {
        region_name: tuple(detections)
        for region_name, detections in detections_by_region.items()
    }


def _effective_detection_region(
    detection: MolecularDetection,
    active_regions: tuple[AnalysisRegion, ...],
    regions_by_name: dict[str, AnalysisRegion],
) -> AnalysisRegion | None:
    if detection.region_name is not None:
        return regions_by_name.get(detection.region_name)
    for region in active_regions:
        if _point_inside_analysis_region(region, detection.centroid_xy):
            return region
    return None


def _analysis_region_area_px2(region: AnalysisRegion) -> float:
    if region.rect_xyxy is not None:
        x0, y0, x1, y1 = region.rect_xyxy
        return float((x1 - x0) * (y1 - y0))
    vertices = np.asarray(region.polygon_xy, dtype=np.float64)
    x = vertices[:, 0]
    y = vertices[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def _detection_bbox_area_px2(detection: MolecularDetection) -> float:
    x0, y0, x1, y1 = detection.bbox_xyxy
    return float((x1 - x0) * (y1 - y0))
