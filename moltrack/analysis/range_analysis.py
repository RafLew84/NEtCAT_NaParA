from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from moltrack.core import MolecularCentroid, MolTrackImageSeries, build_molecular_centroids

from .frame_ranges import MolecularFrameRange
from .intensity import MolecularIntensityMeasurement, build_molecular_intensity_measurements
from .nearest_neighbors import (
    MolecularNearestNeighborAngleMetrics,
    MolecularNearestNeighborMetrics,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)
from .position_plot import MolecularPositionPlotData, build_molecular_position_plot_data
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .m6_errors import M6BlockingGraphQCError
from .molecular_m6_analysis import (
    MolecularM6OrientationAnalysis,
    analyze_molecular_m6_orientation,
)
from .m6_range_analysis import (
    MolecularM6RangeAggregates,
    aggregate_molecular_m6_frame_range,
)
from .sample_coordinates import build_molecular_sample_coordinates
from .structural_analysis_cache import _get_or_compute_molecular_m6_orientation


MolecularM6FrameAvailabilityStatus = Literal[
    "disabled",
    "available",
    "unavailable_missing_analysis",
    "unavailable_blocking_graph_qc",
]


@dataclass(frozen=True)
class MolecularFrameAnalysisResult:
    """Centroids and position metrics for one frame and source view."""

    frame_index: int
    source_view: str
    centroids: tuple[MolecularCentroid, ...]
    plot_data: MolecularPositionPlotData
    distance_metrics: MolecularNearestNeighborMetrics
    angle_metrics: MolecularNearestNeighborAngleMetrics
    mean_intensity: float | None
    median_intensity: float | None
    intensity_metric: str = "background_corrected_median"
    intensity_unit: str = "a.u."
    intensity_measurements: tuple[MolecularIntensityMeasurement, ...] = ()
    m6_orientation_analysis: MolecularM6OrientationAnalysis | None = None
    m6_orientation_availability_status: MolecularM6FrameAvailabilityStatus = "disabled"
    m6_orientation_unavailability_reason: str | None = None
    source_frame_index: int | None = None

    def __post_init__(self) -> None:
        source_frame_index = (
            self.frame_index
            if self.source_frame_index is None
            else int(self.source_frame_index)
        )
        if source_frame_index < 0:
            raise ValueError("source_frame_index must be non-negative.")
        object.__setattr__(self, "source_frame_index", source_frame_index)
        m6 = self.m6_orientation_analysis
        status = self.m6_orientation_availability_status
        reason = self.m6_orientation_unavailability_reason
        allowed_statuses = {
            "disabled",
            "available",
            "unavailable_missing_analysis",
            "unavailable_blocking_graph_qc",
        }
        if status not in allowed_statuses:
            raise ValueError("Unsupported M6 frame availability status.")
        if m6 is None:
            if status == "available":
                raise ValueError("Available M6 frame status requires an analysis result.")
            if status == "disabled" and reason is not None:
                raise ValueError("Disabled M6 analysis cannot have an unavailable reason.")
            if status.startswith("unavailable_") and not reason:
                raise ValueError("Unavailable M6 frame status requires a reason.")
            return
        if not isinstance(m6, MolecularM6OrientationAnalysis):
            raise TypeError("m6_orientation_analysis must be M6 analysis or None.")
        if status != "available" or reason is not None:
            raise ValueError("M6 analysis result requires available status without a reason.")
        centroid_context = tuple(
            (
                centroid.source_id,
                centroid.source_kind,
                (centroid.x_px, centroid.y_px),
            )
            for centroid in self.centroids
        )
        sample = m6.sample_coordinates
        sample_centroid_context = tuple(
            zip(
                sample.point_source_ids,
                sample.point_source_kinds,
                sample.source_points_xy_px,
            )
        )
        if (
            sample.frame_index != self.frame_index
            or m6.source_view != self.source_view
            or self.plot_data.frame_index != self.frame_index
            or self.plot_data.source_view != self.source_view
            or sample_centroid_context != centroid_context
            or m6.point_source_ids != self.plot_data.point_source_ids
            or self.plot_data.coordinate_frame != "sample_nm"
            or m6.points_xy_nm != self.plot_data.points_xy
            or m6.coordinate_transform_fingerprint
            != self.plot_data.coordinate_transform_fingerprint
        ):
            raise ValueError(
                "m6_orientation_analysis must use this frame's Position Analysis points."
            )

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
    mean_intensity: float | None
    median_intensity: float | None
    m6_orientation: MolecularM6RangeAggregates | None = None


@dataclass(frozen=True)
class MolecularFrameRangeAnalysis:
    """Per-frame molecular position analysis for one named condition."""

    frame_range: MolecularFrameRange
    source_view: str
    frame_results: tuple[MolecularFrameAnalysisResult, ...]
    aggregates: MolecularFrameRangeAggregates
    intensity_metric: str
    intensity_unit: str


def analyze_molecular_frame_range(
    series: MolTrackImageSeries,
    frame_range: MolecularFrameRange,
    *,
    source_view: str,
    use_segmentation_centroids: bool = True,
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    progress_callback=None,
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> MolecularFrameRangeAnalysis:
    """Analyze every frame in one named range without linking molecules across frames."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(frame_range, MolecularFrameRange):
        raise TypeError("frame_range must be a MolecularFrameRange instance.")
    if frame_range.start_frame < 0 or frame_range.end_frame >= series.frame_count:
        raise ValueError("frame_range must fit within the working series.")
    source_view = str(source_view).strip()
    if m6_orientation_settings is not None and not isinstance(
        m6_orientation_settings,
        MolecularM6OrientationAnalysisSettings,
    ):
        raise TypeError("m6_orientation_settings must be M6 settings or None.")
    frame_shape, scale_nm_per_px, coordinate_origin_px = _position_context(
        series,
        source_view=source_view,
    )

    frame_results = []
    frame_indices = frame_range.frame_indices
    total_count = len(frame_indices)
    for completed_count, frame_index in enumerate(frame_indices, start=1):
        centroids = tuple(
            build_molecular_centroids(
                series,
                frame_index=frame_index,
                source_view=source_view,
                use_segmentation_centroids=use_segmentation_centroids,
            )
        )
        intensity_measurements = build_molecular_intensity_measurements(
            series,
            frame_index=frame_index,
            source_view=source_view,
            unit=intensity_unit,
            background_inner_radius_px=background_inner_radius_px,
            background_outer_radius_px=background_outer_radius_px,
        )
        sample_coordinates = (
            None
            if m6_orientation_settings is None
            else build_molecular_sample_coordinates(
                series,
                centroids,
                frame_index=frame_index,
                source_view=source_view,
            )
        )
        legacy_plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=frame_index,
            source_view=source_view,
            frame_shape=frame_shape,
            scale_nm_per_px=scale_nm_per_px,
            coordinate_origin_px=coordinate_origin_px,
            intensity_measurements=intensity_measurements,
            intensity_metric=intensity_metric,
        )
        plot_data = (
            legacy_plot_data
            if sample_coordinates is None
            else build_molecular_position_plot_data(
                centroids,
                frame_index=frame_index,
                source_view=source_view,
                frame_shape=frame_shape,
                scale_nm_per_px=scale_nm_per_px,
                coordinate_origin_px=coordinate_origin_px,
                intensity_measurements=intensity_measurements,
                intensity_metric=intensity_metric,
                sample_coordinates=sample_coordinates,
            )
        )
        mean_intensity, median_intensity = _frame_intensity_aggregates(
            plot_data.intensity_values
        )
        m6_orientation_analysis = None
        m6_orientation_availability_status = "disabled"
        m6_orientation_unavailability_reason = None
        if sample_coordinates is not None:
            try:
                m6_orientation_analysis = _get_or_compute_molecular_m6_orientation(
                    series,
                    sample_coordinates,
                    use_segmentation_centroids=use_segmentation_centroids,
                    settings=m6_orientation_settings,
                    analysis_factory=analyze_molecular_m6_orientation,
                )
                m6_orientation_availability_status = "available"
            except M6BlockingGraphQCError as error:
                m6_orientation_availability_status = "unavailable_blocking_graph_qc"
                m6_orientation_unavailability_reason = error.qc_status
        frame_results.append(
            MolecularFrameAnalysisResult(
                frame_index=frame_index,
                source_view=source_view,
                centroids=centroids,
                plot_data=plot_data,
                distance_metrics=compute_molecular_nearest_neighbor_metrics(
                    legacy_plot_data
                ),
                angle_metrics=compute_molecular_nearest_neighbor_angle_metrics(
                    legacy_plot_data
                ),
                mean_intensity=mean_intensity,
                median_intensity=median_intensity,
                intensity_metric=str(intensity_metric).strip(),
                intensity_unit=str(intensity_unit),
                intensity_measurements=tuple(intensity_measurements),
                m6_orientation_analysis=m6_orientation_analysis,
                m6_orientation_availability_status=(
                    m6_orientation_availability_status
                ),
                m6_orientation_unavailability_reason=(
                    m6_orientation_unavailability_reason
                ),
                source_frame_index=series.source_frame_indices[frame_index],
            )
        )
        if progress_callback is not None:
            progress_callback(completed_count, total_count, frame_index)
    return MolecularFrameRangeAnalysis(
        frame_range=frame_range,
        source_view=source_view,
        frame_results=tuple(frame_results),
        aggregates=_aggregate_frame_results(
            frame_results,
            m6_enabled=m6_orientation_settings is not None,
        ),
        intensity_metric=str(intensity_metric).strip(),
        intensity_unit=str(intensity_unit),
    )


def _frame_intensity_aggregates(
    intensity_values: tuple[float | None, ...],
) -> tuple[float | None, float | None]:
    finite_values = np.asarray(
        [
            float(value)
            for value in intensity_values
            if value is not None and np.isfinite(float(value))
        ],
        dtype=np.float64,
    )
    if finite_values.size == 0:
        return None, None
    return float(np.mean(finite_values)), float(np.median(finite_values))


def _aggregate_frame_results(
    frame_results: list[MolecularFrameAnalysisResult],
    *,
    m6_enabled: bool = False,
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
    mean_intensities = [
        result.mean_intensity
        for result in frame_results
        if result.mean_intensity is not None
    ]
    median_intensities = [
        result.median_intensity
        for result in frame_results
        if result.median_intensity is not None
    ]
    return MolecularFrameRangeAggregates(
        analyzed_frame_count=len(frame_results),
        distance_unit=frame_results[0].distance_metrics.unit,
        total_molecule_count=sum(molecule_counts),
        mean_molecule_count=sum(molecule_counts) / len(molecule_counts),
        mean_nearest_neighbor_distance=_optional_mean(distance_means),
        mean_line_order_score=_optional_mean(line_order_scores),
        mean_intensity=_optional_mean(mean_intensities),
        median_intensity=_optional_mean(median_intensities),
        m6_orientation=aggregate_molecular_m6_frame_range(
            frame_results,
            enabled=m6_enabled,
        ),
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
