from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from moltrack.core import MolecularCentroid, MolTrackImageSeries, build_molecular_centroids

from .frame_ranges import MolecularFrameRange
from .nearest_neighbors import (
    MolecularNearestNeighborAngleMetrics,
    MolecularNearestNeighborMetrics,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)
from .position_plot import MolecularPositionPlotData, build_molecular_position_plot_data


@dataclass(frozen=True)
class MolecularFrameAnalysisResult:
    """Centroids and position metrics for one frame and source view."""

    frame_index: int
    source_view: str
    centroids: tuple[MolecularCentroid, ...]
    plot_data: MolecularPositionPlotData
    distance_metrics: MolecularNearestNeighborMetrics
    angle_metrics: MolecularNearestNeighborAngleMetrics

    @property
    def point_count(self) -> int:
        return len(self.centroids)


@dataclass(frozen=True)
class MolecularFrameRangeAggregates:
    """Frame-weighted aggregate metrics for one experimental condition."""

    analyzed_frame_count: int
    distance_unit: str
    total_molecule_count: int
    mean_molecule_count: float
    mean_nearest_neighbor_distance: float | None
    mean_line_order_score: float | None


@dataclass(frozen=True)
class MolecularFrameRangeAnalysis:
    """Per-frame molecular position analysis for one named condition."""

    frame_range: MolecularFrameRange
    source_view: str
    frame_results: tuple[MolecularFrameAnalysisResult, ...]
    aggregates: MolecularFrameRangeAggregates


def analyze_molecular_frame_range(
    series: MolTrackImageSeries,
    frame_range: MolecularFrameRange,
    *,
    source_view: str,
    use_segmentation_centroids: bool = True,
) -> MolecularFrameRangeAnalysis:
    """Analyze every frame in one named range without linking molecules across frames."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(frame_range, MolecularFrameRange):
        raise TypeError("frame_range must be a MolecularFrameRange instance.")
    if frame_range.start_frame < 0 or frame_range.end_frame >= series.frame_count:
        raise ValueError("frame_range must fit within the working series.")
    source_view = str(source_view).strip()
    frame_shape, scale_nm_per_px, coordinate_origin_px = _position_context(
        series,
        source_view=source_view,
    )

    frame_results = []
    for frame_index in frame_range.frame_indices:
        centroids = tuple(
            build_molecular_centroids(
                series,
                frame_index=frame_index,
                source_view=source_view,
                use_segmentation_centroids=use_segmentation_centroids,
            )
        )
        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=frame_index,
            source_view=source_view,
            frame_shape=frame_shape,
            scale_nm_per_px=scale_nm_per_px,
            coordinate_origin_px=coordinate_origin_px,
        )
        frame_results.append(
            MolecularFrameAnalysisResult(
                frame_index=frame_index,
                source_view=source_view,
                centroids=centroids,
                plot_data=plot_data,
                distance_metrics=compute_molecular_nearest_neighbor_metrics(plot_data),
                angle_metrics=compute_molecular_nearest_neighbor_angle_metrics(plot_data),
            )
        )
    return MolecularFrameRangeAnalysis(
        frame_range=frame_range,
        source_view=source_view,
        frame_results=tuple(frame_results),
        aggregates=_aggregate_frame_results(frame_results),
    )


def _aggregate_frame_results(
    frame_results: list[MolecularFrameAnalysisResult],
) -> MolecularFrameRangeAggregates:
    molecule_counts = [result.point_count for result in frame_results]
    distance_means = [
        result.distance_metrics.mean_distance
        for result in frame_results
        if result.distance_metrics.mean_distance is not None
    ]
    line_order_scores = [
        result.angle_metrics.line_order_score
        for result in frame_results
        if result.angle_metrics.line_order_score is not None
    ]
    return MolecularFrameRangeAggregates(
        analyzed_frame_count=len(frame_results),
        distance_unit=frame_results[0].distance_metrics.unit,
        total_molecule_count=sum(molecule_counts),
        mean_molecule_count=sum(molecule_counts) / len(molecule_counts),
        mean_nearest_neighbor_distance=_optional_mean(distance_means),
        mean_line_order_score=_optional_mean(line_order_scores),
    )


def _optional_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _normalize_scale_nm_per_px(
    scale_nm_per_px: tuple[float | None, float | None],
) -> tuple[float, float] | None:
    scale_x, scale_y = scale_nm_per_px
    if scale_x is None or scale_y is None:
        return None
    return float(scale_x), float(scale_y)


def _position_context(
    series: MolTrackImageSeries,
    *,
    source_view: str,
) -> tuple[tuple[int, int], tuple[float, float] | None, tuple[float, float]]:
    if source_view == "raw":
        return series.frame_shape, _normalize_scale_nm_per_px(series.pixel_size_nm), (0.0, 0.0)
    if source_view != "expanded_aligned":
        raise ValueError(f"Unsupported source_view: {source_view!r}.")

    expanded_stack = series.expanded_aligned_stack
    if expanded_stack is None:
        raise ValueError("expanded_aligned source_view requires an expanded_aligned_stack.")
    frames = np.asarray(getattr(expanded_stack, "frames", None))
    if frames.ndim != 3 or frames.shape[0] != series.frame_count:
        raise ValueError("expanded_aligned_stack frames must match the working series.")
    metadata = getattr(expanded_stack, "metadata", series.metadata)
    get_pixel_size = getattr(metadata, "get_pixel_size_nm", None)
    scale_nm_per_px = (None, None) if not callable(get_pixel_size) else get_pixel_size()
    canvas_offset = getattr(expanded_stack, "canvas_offset_xy", None)
    if canvas_offset is None:
        padding = getattr(expanded_stack, "padding_ltrb", (0, 0, 0, 0))
        canvas_offset = (padding[0], padding[1])
    origin_x, origin_y = (float(value) for value in canvas_offset)
    if not np.isfinite(origin_x) or not np.isfinite(origin_y):
        raise ValueError("expanded_aligned canvas offset must be finite.")
    return (
        (int(frames.shape[1]), int(frames.shape[2])),
        _normalize_scale_nm_per_px(scale_nm_per_px),
        (origin_x, origin_y),
    )
