from __future__ import annotations

import colorsys
from dataclasses import dataclass
from math import isfinite
from typing import Literal, Sequence

from .molecular_m6_analysis import MolecularM6OrientationAnalysis


M6AnalysisOverlayMode = Literal["none", "q6", "orientation", "domain_id"]
M6OverlayMode = Literal[
    "none",
    "q6",
    "orientation",
    "domain_id",
    "domain_type",
]
M6OverlayPointStatus = Literal[
    "q6",
    "orientation",
    "domain",
    "domain_type",
    "unclassified_domain",
    "small_ordered_island",
    "unassigned",
    "undefined_orientation",
    "insufficient_neighbors",
    "duplicate_excluded",
    "invalid_position",
]

M6_ANALYSIS_OVERLAY_MODES: tuple[M6AnalysisOverlayMode, ...] = (
    "none",
    "q6",
    "orientation",
    "domain_id",
)
M6_OVERLAY_MODES: tuple[M6OverlayMode, ...] = (
    *M6_ANALYSIS_OVERLAY_MODES,
    "domain_type",
)

_UNASSIGNED_COLOR = (145, 155, 165)
_UNDEFINED_ORIENTATION_COLOR = (160, 135, 175)
_SMALL_ISLAND_COLOR = (165, 145, 95)
_QC_COLORS = {
    "insufficient_neighbors": (135, 145, 150),
    "duplicate_excluded": (100, 110, 120),
    "invalid_position": (80, 85, 90),
}
_VIRIDIS_STOPS = (
    (68, 1, 84),
    (59, 82, 139),
    (33, 145, 140),
    (94, 201, 98),
    (253, 231, 37),
)


@dataclass(frozen=True)
class M6OverlayPointState:
    """Render-only projection of one molecule from an M6 analysis result."""

    source_id: str
    source_xy_px: tuple[float, float]
    q6: float | None
    orientation_deg: float | None
    orientation_status: str
    computation_status: str
    assignment_status: str
    m6_orientation_domain_id: int
    ordered_component_id: int
    component_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be a non-empty string.")
        point = tuple(float(value) for value in self.source_xy_px)
        if len(point) != 2 or not all(isfinite(value) for value in point):
            raise ValueError("source_xy_px must contain two finite coordinates.")
        if self.q6 is not None and not 0.0 <= float(self.q6) <= 1.0:
            raise ValueError("q6 must be None or lie between 0 and 1.")
        if self.orientation_deg is not None and not isfinite(float(self.orientation_deg)):
            raise ValueError("orientation_deg must be None or finite.")
        object.__setattr__(self, "source_xy_px", point)


@dataclass(frozen=True)
class M6PointOverlay:
    """One batched, immutable point overlay aligned with source-image pixels."""

    mode: M6OverlayMode
    source_ids: tuple[str, ...]
    points_xy_px: tuple[tuple[float, float], ...]
    colors_rgba: tuple[tuple[int, int, int, int], ...]
    point_statuses: tuple[M6OverlayPointStatus, ...]

    def __post_init__(self) -> None:
        if self.mode not in M6_OVERLAY_MODES:
            raise ValueError(f"Unsupported M6 overlay mode: {self.mode!r}.")
        count = len(self.source_ids)
        if not (
            len(self.points_xy_px)
            == len(self.colors_rgba)
            == len(self.point_statuses)
            == count
        ):
            raise ValueError("M6 overlay point arrays must have equal lengths.")
        if len(set(self.source_ids)) != count:
            raise ValueError("M6 overlay source_ids must be unique.")
        for color in self.colors_rgba:
            if len(color) != 4 or any(not 0 <= int(channel) <= 255 for channel in color):
                raise ValueError("M6 overlay colors must be RGBA bytes.")

    @property
    def point_count(self) -> int:
        return len(self.source_ids)


def build_m6_point_overlay(
    point_states: Sequence[M6OverlayPointState],
    *,
    mode: M6AnalysisOverlayMode,
    opacity_percent: int,
    show_unassigned_points: bool = True,
) -> M6PointOverlay:
    """Map immutable M6 point states to one deterministic render batch."""

    if mode not in M6_ANALYSIS_OVERLAY_MODES:
        raise ValueError(f"Unsupported M6 overlay mode: {mode!r}.")
    opacity = int(opacity_percent)
    if not 0 <= opacity <= 100:
        raise ValueError("opacity_percent must be between 0 and 100.")
    states = tuple(point_states)
    if any(not isinstance(point, M6OverlayPointState) for point in states):
        raise TypeError("point_states must contain M6OverlayPointState values.")
    if mode == "none":
        return M6PointOverlay(mode, (), (), (), ())

    source_ids: list[str] = []
    points_xy_px: list[tuple[float, float]] = []
    colors_rgba: list[tuple[int, int, int, int]] = []
    statuses: list[M6OverlayPointStatus] = []
    base_alpha = round(255 * opacity / 100.0)
    for point in states:
        if point.assignment_status != "assigned" and not show_unassigned_points:
            continue
        rgb, status, alpha_scale = _point_color(point, mode=mode)
        source_ids.append(point.source_id)
        points_xy_px.append(point.source_xy_px)
        colors_rgba.append((*rgb, round(base_alpha * alpha_scale)))
        statuses.append(status)
    return M6PointOverlay(
        mode=mode,
        source_ids=tuple(source_ids),
        points_xy_px=tuple(points_xy_px),
        colors_rgba=tuple(colors_rgba),
        point_statuses=tuple(statuses),
    )


def build_m6_point_overlay_from_analysis(
    analysis: MolecularM6OrientationAnalysis,
    *,
    mode: M6AnalysisOverlayMode,
    opacity_percent: int,
    show_unassigned_points: bool = True,
) -> M6PointOverlay:
    """Project a complete M6 result back onto its source-image coordinates."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be MolecularM6OrientationAnalysis.")
    sample = analysis.sample_coordinates
    local = analysis.local_order
    segmentation = analysis.segmentation
    states = tuple(
        M6OverlayPointState(
            source_id=source_id,
            source_xy_px=source_xy_px,
            q6=local.q6[index],
            orientation_deg=local.lattice_orientation_deg[index],
            orientation_status=local.orientation_status[index],
            computation_status=local.computation_status[index],
            assignment_status=segmentation.assignment_status[index],
            m6_orientation_domain_id=segmentation.m6_orientation_domain_id[index],
            ordered_component_id=segmentation.ordered_component_id[index],
            component_type=segmentation.component_type[index],
        )
        for index, (source_id, source_xy_px) in enumerate(
            zip(sample.point_source_ids, sample.source_points_xy_px)
        )
    )
    return build_m6_point_overlay(
        states,
        mode=mode,
        opacity_percent=opacity_percent,
        show_unassigned_points=show_unassigned_points,
    )


def _point_color(
    point: M6OverlayPointState,
    *,
    mode: M6AnalysisOverlayMode,
) -> tuple[tuple[int, int, int], M6OverlayPointStatus, float]:
    if point.computation_status != "valid_order":
        status = point.computation_status
        color = _QC_COLORS.get(status, _UNASSIGNED_COLOR)
        return color, status, 1.0
    if point.assignment_status != "assigned":
        return _UNASSIGNED_COLOR, "unassigned", 1.0
    if mode == "q6":
        if point.q6 is None:
            return _UNASSIGNED_COLOR, "unassigned", 1.0
        return _interpolate_viridis(float(point.q6)), "q6", 1.0
    if mode == "orientation":
        if point.orientation_status != "defined" or point.orientation_deg is None:
            return _UNDEFINED_ORIENTATION_COLOR, "undefined_orientation", 1.0
        q6 = 0.0 if point.q6 is None else float(point.q6)
        return _orientation_color(float(point.orientation_deg)), "orientation", 0.35 + 0.65 * q6
    if point.component_type == "full_domain" and point.m6_orientation_domain_id >= 0:
        return _domain_color(point.m6_orientation_domain_id), "domain", 1.0
    if point.component_type == "small_ordered_island":
        return _SMALL_ISLAND_COLOR, "small_ordered_island", 1.0
    return _UNASSIGNED_COLOR, "unassigned", 1.0


def _interpolate_viridis(value: float) -> tuple[int, int, int]:
    scaled = min(1.0, max(0.0, value)) * (len(_VIRIDIS_STOPS) - 1)
    left_index = min(int(scaled), len(_VIRIDIS_STOPS) - 2)
    fraction = scaled - left_index
    left = _VIRIDIS_STOPS[left_index]
    right = _VIRIDIS_STOPS[left_index + 1]
    return tuple(
        round(left[channel] + fraction * (right[channel] - left[channel]))
        for channel in range(3)
    )


def _orientation_color(orientation_deg: float) -> tuple[int, int, int]:
    hue = (orientation_deg % 60.0) / 60.0
    return tuple(round(255 * value) for value in colorsys.hsv_to_rgb(hue, 0.72, 0.95))


def _domain_color(domain_id: int) -> tuple[int, int, int]:
    hue = (0.08 + int(domain_id) * 0.6180339887498949) % 1.0
    return tuple(round(255 * value) for value in colorsys.hsv_to_rgb(hue, 0.62, 0.88))
