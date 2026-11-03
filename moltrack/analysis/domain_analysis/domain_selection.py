from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from .models import M6FrameGate


DomainSelectionView = Literal["raw", "expanded_aligned"]


@dataclass(frozen=True)
class DomainSelectionPolygon:
    """Transient raw-pixel polygon used only to preserve visible selection."""

    vertices_xy: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        vertices = tuple(_finite_point(value) for value in self.vertices_xy)
        if len(vertices) < 3 or len(set(vertices)) < 3:
            raise ValueError("Selection polygon requires three distinct vertices.")
        if _signed_area(vertices) == 0.0:
            raise ValueError("Selection polygon cannot have zero area.")
        object.__setattr__(self, "vertices_xy", vertices)


@dataclass(frozen=True)
class ToggleDomainMoleculeSelection:
    source_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be non-empty text.")
        object.__setattr__(self, "source_id", self.source_id.strip())


@dataclass(frozen=True)
class SelectDomainMoleculesByPolygons:
    polygons: tuple[tuple[tuple[float, float], ...], ...]
    target_view: DomainSelectionView

    def __post_init__(self) -> None:
        if not self.polygons:
            raise ValueError("Polygon selection requires at least one polygon.")
        if self.target_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported selection target view: {self.target_view!r}.")


@dataclass(frozen=True)
class ClearDomainMoleculeSelection:
    pass


def raw_selection_polygon(
    vertices_xy: tuple[tuple[float, float], ...],
    target_view: DomainSelectionView,
    frame: M6FrameGate,
) -> DomainSelectionPolygon:
    if target_view not in {"raw", "expanded_aligned"}:
        raise ValueError(f"Unsupported selection target view: {target_view!r}.")
    if target_view == "raw":
        return DomainSelectionPolygon(vertices_xy)
    origin_x, origin_y = frame.presentation_provenance.frame_origin_xy
    return DomainSelectionPolygon(tuple(
        (x - origin_x, y - origin_y)
        for x, y in vertices_xy
    ))


def source_ids_inside_polygons(
    frame: M6FrameGate,
    polygons: tuple[DomainSelectionPolygon, ...],
) -> tuple[str, ...]:
    members = {
        member.source_id: member
        for component in frame.full_domains + frame.small_ordered_islands
        for member in component.members
    }
    members.update({value.source_id: value for value in frame.outside_members})
    return tuple(sorted(
        source_id
        for source_id, member in members.items()
        if member.raw_centroid_xy is not None
        and any(
            _point_inside_polygon(member.raw_centroid_xy, polygon.vertices_xy)
            for polygon in polygons
        )
    ))


def _point_inside_polygon(
    point: tuple[float, float],
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if _point_on_segment(point, previous, current):
            return True
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    x, y = point
    x1, y1 = start
    x2, y2 = end
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > 1e-9:
        return False
    return (
        min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9
        and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9
    )


def _finite_point(value: object) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("Selection polygon vertices must be finite XY pairs.")
    try:
        point = float(value[0]), float(value[1])
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Selection polygon vertices must be finite XY pairs."
        ) from error
    if not all(isfinite(item) for item in point):
        raise ValueError("Selection polygon vertices must be finite XY pairs.")
    return point


def _signed_area(vertices: tuple[tuple[float, float], ...]) -> float:
    return sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(vertices, vertices[1:] + vertices[:1])
    ) / 2.0


__all__ = [
    "DomainSelectionPolygon",
    "DomainSelectionView",
    "ClearDomainMoleculeSelection",
    "SelectDomainMoleculesByPolygons",
    "ToggleDomainMoleculeSelection",
    "raw_selection_polygon",
    "source_ids_inside_polygons",
]
