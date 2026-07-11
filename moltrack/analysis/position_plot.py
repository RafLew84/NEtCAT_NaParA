from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from moltrack.core import MolecularCentroid


@dataclass(frozen=True)
class MolecularPositionPlotData:
    """UI-independent scatter-plot data for one molecular-position context."""

    frame_index: int
    source_view: str
    points_xy: tuple[tuple[float, float], ...]
    unit: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]

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
    return MolecularPositionPlotData(
        frame_index=frame_index,
        source_view=source_view,
        points_xy=points_xy,
        unit=unit,
        x_range=x_range,
        y_range=y_range,
    )
