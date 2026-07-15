from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from moltrack.core import MolecularCentroid

from .intensity import MolecularIntensityMeasurement


SUPPORTED_INTENSITY_METRICS = (
    "background_corrected_median",
    "background_corrected_mean",
    "mean",
    "median",
    "max",
    "sum",
)


@dataclass(frozen=True)
class MolecularPositionPlotData:
    """UI-independent scatter-plot data for one molecular-position context."""

    frame_index: int
    source_view: str
    points_xy: tuple[tuple[float, float], ...]
    unit: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    intensity_values: tuple[float | None, ...] = ()
    intensity_metric: str | None = None
    intensity_unit: str | None = None
    point_source_ids: tuple[str, ...] = ()
    point_source_kinds: tuple[str, ...] = ()
    point_areas_px: tuple[float | None, ...] = ()

    def __post_init__(self) -> None:
        intensity_values = tuple(self.intensity_values)
        if not intensity_values and self.points_xy:
            intensity_values = (None,) * len(self.points_xy)
        if len(intensity_values) != len(self.points_xy):
            raise ValueError("intensity_values must align with points_xy.")
        object.__setattr__(self, "intensity_values", intensity_values)
        for field_name, values, missing_value in (
            ("point_source_ids", self.point_source_ids, ""),
            ("point_source_kinds", self.point_source_kinds, ""),
            ("point_areas_px", self.point_areas_px, None),
        ):
            normalized = tuple(values)
            if not normalized and self.points_xy:
                normalized = (missing_value,) * len(self.points_xy)
            if len(normalized) != len(self.points_xy):
                raise ValueError(f"{field_name} must align with points_xy.")
            object.__setattr__(self, field_name, normalized)

    @property
    def point_count(self) -> int:
        return len(self.points_xy)


def build_molecular_position_plot_data(
    centroids: list[MolecularCentroid] | tuple[MolecularCentroid, ...],
    *,
    frame_index: int,
    source_view: str,
    frame_shape: tuple[int, int],
    scale_nm_per_px: tuple[float, float] | None = None,
    coordinate_origin_px: tuple[float, float] = (0.0, 0.0),
    intensity_measurements: list[MolecularIntensityMeasurement]
    | tuple[MolecularIntensityMeasurement, ...] = (),
    intensity_metric: str = "background_corrected_median",
) -> MolecularPositionPlotData:
    """Build scatter data for one frame and source view."""

    frame_index = int(frame_index)
    source_view = str(source_view).strip()
    centroids = tuple(centroids)
    for centroid in centroids:
        if not isinstance(centroid, MolecularCentroid):
            raise TypeError("centroids must contain MolecularCentroid instances.")
        if centroid.frame_index != frame_index:
            raise ValueError("Centroid frame_index must match the plot frame_index.")
        if centroid.source_view != source_view:
            raise ValueError("Centroid source_view must match the plot source_view.")
    height, width = (int(value) for value in frame_shape)
    origin_x, origin_y = (float(value) for value in coordinate_origin_px)
    intensity_metric = str(intensity_metric).strip()
    if intensity_metric not in SUPPORTED_INTENSITY_METRICS:
        supported = ", ".join(SUPPORTED_INTENSITY_METRICS)
        raise ValueError(f"Unsupported intensity_metric: {intensity_metric!r}. Supported: {supported}.")
    if not isfinite(origin_x) or not isfinite(origin_y):
        raise ValueError("coordinate_origin_px values must be finite.")
    if scale_nm_per_px is None:
        points_xy = tuple(
            (float(centroid.x_px - origin_x), float(centroid.y_px - origin_y))
            for centroid in centroids
        )
        unit = "px"
        x_range = (-origin_x, float(width) - origin_x)
        y_range = (-origin_y, float(height) - origin_y)
    else:
        scale_x, scale_y = (float(value) for value in scale_nm_per_px)
        if not isfinite(scale_x) or not isfinite(scale_y) or scale_x <= 0.0 or scale_y <= 0.0:
            raise ValueError("scale_nm_per_px values must be positive and finite.")
        points_xy = tuple(
            (
                float(centroid.x_nm - origin_x * scale_x),
                float(centroid.y_nm - origin_y * scale_y),
            )
            for centroid in centroids
        )
        unit = "nm"
        x_range = (-origin_x * scale_x, (float(width) - origin_x) * scale_x)
        y_range = (-origin_y * scale_y, (float(height) - origin_y) * scale_y)
    aligned_measurements, intensity_unit = _aligned_intensity_measurements(
        centroids,
        intensity_measurements,
        frame_index=frame_index,
    )
    intensity_values = tuple(
        None
        if measurement is None or getattr(measurement, intensity_metric) is None
        else float(getattr(measurement, intensity_metric))
        for measurement in aligned_measurements
    )
    return MolecularPositionPlotData(
        frame_index=frame_index,
        source_view=source_view,
        points_xy=points_xy,
        unit=unit,
        x_range=x_range,
        y_range=y_range,
        intensity_values=intensity_values,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        point_source_ids=tuple(centroid.source_id for centroid in centroids),
        point_source_kinds=tuple(
            (
                measurement.source_kind
                if measurement is not None
                else "segmentation" if centroid.source_kind == "segmentation" else "bbox"
            )
            for centroid, measurement in zip(centroids, aligned_measurements)
        ),
        point_areas_px=tuple(
            (
                float(measurement.pixel_count)
                if measurement is not None
                else centroid.area_px
            )
            for centroid, measurement in zip(centroids, aligned_measurements)
        ),
    )


def _aligned_intensity_measurements(
    centroids: tuple[MolecularCentroid, ...],
    measurements: list[MolecularIntensityMeasurement]
    | tuple[MolecularIntensityMeasurement, ...],
    *,
    frame_index: int,
) -> tuple[tuple[MolecularIntensityMeasurement | None, ...], str | None]:

    measurements_by_source_id: dict[str, MolecularIntensityMeasurement] = {}
    for measurement in measurements:
        if not isinstance(measurement, MolecularIntensityMeasurement):
            raise TypeError("intensity_measurements must contain MolecularIntensityMeasurement instances.")
        if measurement.frame_index != frame_index:
            raise ValueError("Intensity measurement frame_index must match the plot frame_index.")
        if measurement.source_id in measurements_by_source_id:
            raise ValueError(f"Duplicate intensity measurement source_id: {measurement.source_id}")
        measurements_by_source_id[measurement.source_id] = measurement

    aligned: list[MolecularIntensityMeasurement | None] = []
    used_units: set[str] = set()
    for centroid in centroids:
        measurement = measurements_by_source_id.get(centroid.source_id)
        aligned.append(measurement)
        if measurement is None:
            continue
        used_units.add(measurement.unit)
    if len(used_units) > 1:
        raise ValueError("Intensity measurements aligned to one plot must use one unit.")
    return tuple(aligned), (next(iter(used_units)) if used_units else None)
