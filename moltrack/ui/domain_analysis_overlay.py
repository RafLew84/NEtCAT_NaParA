from __future__ import annotations

from dataclasses import dataclass
import hashlib
from math import floor, isfinite
from typing import Literal, cast

import numpy as np
from scipy.ndimage import affine_transform
from PyQt6.QtCore import QObject, pyqtSignal

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    DomainAnalysisPublication,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceSnapshot,
    DomainComponentKey,
    M6FrameGate,
    M6PresentationProvenance,
    SelectDomainComponent,
)
from moltrack.analysis.m6_point_overlay import M6OverlayPointStatus, M6PointOverlay
from moltrack.ui.widgets.stm_series_viewer import STMSeriesViewer


_SMALL_ISLAND_COLOR = (190, 145, 55)
_SELECTED_COLOR = (255, 220, 0)
ABCPointState = Literal["A", "B", "C", "Unknown orientation"]
_ABC_COLORS: dict[ABCPointState, tuple[int, int, int]] = {
    "A": (45, 125, 255),
    "B": (245, 155, 45),
    "C": (45, 180, 105),
    "Unknown orientation": (135, 140, 150),
}
_ABC_POINT_STATUSES: dict[ABCPointState, M6OverlayPointStatus] = {
    "A": "abc_a",
    "B": "abc_b",
    "C": "abc_c",
    "Unknown orientation": "abc_unknown",
}


@dataclass(frozen=True)
class DomainAnalysisComponentOverlay:
    """One published M6 component projected into the displayed image view."""

    key: DomainComponentKey
    component_type: Literal["full_domain", "small_ordered_island"]
    shape: tuple[int, int]
    pixels_xy: tuple[tuple[int, int], ...]
    m6_boundary_color_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class DomainAnalysisABCPointOverlay:
    """One published, M6-gated molecule classification in the target view."""

    source_id: str
    component_key: DomainComponentKey
    point_xy_px: tuple[float, float]
    state: ABCPointState
    color_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class DomainAnalysisFrameOverlay:
    """Immutable published M6 geometry and per-molecule A/B/C projection."""

    target_view: Literal["raw", "expanded_aligned"]
    components: tuple[DomainAnalysisComponentOverlay, ...]
    abc_points: tuple[DomainAnalysisABCPointOverlay, ...]
    selected_component: DomainComponentKey | None


class DomainAnalysisOverlayPresenter(QObject):
    """Thin Qt adapter from a published workspace snapshot to the STM view."""

    _snapshot_received = pyqtSignal(object)

    def __init__(
        self,
        controller: DomainAnalysisWorkspaceController,
        viewer: STMSeriesViewer,
    ) -> None:
        super().__init__(viewer)
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        if not isinstance(viewer, STMSeriesViewer):
            raise TypeError("viewer must be an STMSeriesViewer.")
        self._controller = controller
        self._viewer = viewer
        self._items: list[object] = []
        self._target_view: Literal["raw", "expanded_aligned"] = "raw"
        self._frame_overlay: DomainAnalysisFrameOverlay | None = None
        self._snapshot_received.connect(self._render_snapshot)
        viewer.image_pixel_clicked.connect(self._select_at_pixel)
        subscription = controller.state_changed.connect(self._snapshot_received.emit)
        self.destroyed.connect(lambda _object=None: subscription.disconnect())
        self._render_snapshot(controller.snapshot)

    def set_target_view(
        self,
        target_view: Literal["raw", "expanded_aligned"],
    ) -> None:
        if target_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported target_view: {target_view!r}.")
        if target_view == self._target_view:
            return
        self._target_view = target_view
        self._render_snapshot(self._controller.snapshot)

    def _render_snapshot(self, value: object) -> None:
        if not isinstance(value, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self._clear_items()
        overlay = _build_domain_analysis_frame_overlay(value, self._target_view)
        self._frame_overlay = overlay
        if overlay is None:
            return
        for component in overlay.components:
            self._render_component(component, overlay.selected_component)
        self._render_abc_points(overlay)

    def _render_component(
        self,
        component: DomainAnalysisComponentOverlay,
        selected_component: DomainComponentKey | None,
    ) -> None:
        mask = _pixel_mask(component.shape, component.pixels_xy)
        fill_item = self._viewer.viewer.add_mask_overlay_px(
            mask,
            color=component.m6_boundary_color_rgb,
            alpha=65,
        )
        boundary_mask = _pixel_mask(
            component.shape,
            _boundary_pixels(component.pixels_xy),
        )
        boundary_item = self._viewer.viewer.add_mask_overlay_px(
            boundary_mask,
            color=component.m6_boundary_color_rgb,
            alpha=220,
        )
        self._append_items(fill_item, boundary_item)
        if component.key == selected_component:
            selected_item = self._viewer.viewer.add_mask_overlay_px(
                boundary_mask,
                color=_SELECTED_COLOR,
                alpha=255,
            )
            self._append_items(selected_item)

    def _render_abc_points(self, overlay: DomainAnalysisFrameOverlay) -> None:
        points = overlay.abc_points
        point_overlay = M6PointOverlay(
            mode="domain_abc",
            source_ids=tuple(value.source_id for value in points),
            points_xy_px=tuple(value.point_xy_px for value in points),
            colors_rgba=tuple((*value.color_rgb, 230) for value in points),
            point_statuses=tuple(
                _ABC_POINT_STATUSES[value.state] for value in points
            ),
        )
        self._viewer.show_m6_point_overlay(point_overlay)
        selected = overlay.selected_component
        if selected is not None:
            self._viewer.highlight_m6_overlay_source_ids(
                value.source_id
                for value in points
                if value.component_key == selected
            )

    def _append_items(self, *items: object | None) -> None:
        self._items.extend(item for item in items if item is not None)

    def _select_at_pixel(self, value: object) -> None:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("image pixel selection must be a finite XY pair.")
        try:
            x_px, y_px = float(value[0]), float(value[1])
        except (TypeError, ValueError) as exc:
            raise ValueError("image pixel selection must be a finite XY pair.") from exc
        if not isfinite(x_px) or not isfinite(y_px):
            raise ValueError("image pixel selection must be a finite XY pair.")
        pixel = (floor(x_px), floor(y_px))
        overlay = self._frame_overlay
        selection = next(
            (
                component.key
                for component in (() if overlay is None else overlay.components)
                if pixel in component.pixels_xy
            ),
            None,
        )
        self._controller.dispatch(SelectDomainComponent(selection))

    def _clear_items(self) -> None:
        self._viewer.clear_m6_point_overlay()
        for item in self._items:
            self._viewer.viewer.remove_item(item)
        self._items.clear()


def _pixel_mask(
    shape: tuple[int, int],
    pixels_xy: tuple[tuple[int, int], ...],
) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    for x, y in pixels_xy:
        mask[y, x] = True
    return mask


def _project_pixels(
    raw_pixels_xy: tuple[tuple[int, int], ...],
    provenance: M6PresentationProvenance,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[tuple[int, int], ...]:
    if target_view == "raw":
        return tuple(raw_pixels_xy)
    raw_mask = _pixel_mask(provenance.raw_shape, raw_pixels_xy)
    origin_x, origin_y = provenance.frame_origin_xy
    projected = affine_transform(
        raw_mask.astype(np.uint8),
        matrix=np.eye(2, dtype=np.float64),
        offset=(-origin_y, -origin_x),
        output_shape=provenance.expanded_shape,
        order=0,
        mode="constant",
        cval=0,
        prefilter=False,
    )
    y_values, x_values = np.nonzero(projected)
    return tuple(
        sorted((int(x), int(y)) for y, x in zip(y_values, x_values))
    )


def _published_frame(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> tuple[DomainAnalysisPublication, M6FrameGate] | None:
    publication = snapshot.published
    if publication is None or publication.result.m6_gate is None:
        return None
    frame = next(
        (
            value
            for value in publication.result.m6_gate.frames
            if value.physical_frame_id == snapshot.active_physical_frame_id
        ),
        None,
    )
    return None if frame is None else (publication, frame)


def _build_domain_analysis_frame_overlay(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    target_view: Literal["raw", "expanded_aligned"],
) -> DomainAnalysisFrameOverlay | None:
    """Project only the active published frame into one immutable UI value."""

    if not isinstance(snapshot, DomainAnalysisWorkspaceSnapshot):
        raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
    if target_view not in {"raw", "expanded_aligned"}:
        raise ValueError(f"Unsupported target_view: {target_view!r}.")
    published_frame = _published_frame(snapshot)
    if published_frame is None:
        return None
    publication, frame = published_frame
    components = _build_component_overlays(frame, target_view)
    component_keys = tuple(value.key for value in components)
    selected = (
        snapshot.selected_component
        if snapshot.selected_component in component_keys
        else None
    )
    return DomainAnalysisFrameOverlay(
        target_view=target_view,
        components=components,
        abc_points=_build_abc_points(publication, frame, target_view),
        selected_component=selected,
    )


def _build_component_overlays(
    frame: M6FrameGate,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[DomainAnalysisComponentOverlay, ...]:
    provenance = frame.presentation_provenance
    shape = provenance.raw_shape if target_view == "raw" else provenance.expanded_shape
    overlays = []
    for component in frame.full_domains + frame.small_ordered_islands:
        boundary_color = _m6_component_color(
            component.lattice_domain_id,
            component.component_type,
        )
        overlays.append(DomainAnalysisComponentOverlay(
            key=DomainComponentKey(
                frame.physical_frame_id,
                component.lattice_domain_id,
            ),
            component_type=component.component_type,
            shape=shape,
            pixels_xy=_project_pixels(
                component.footprint_pixels_xy,
                provenance,
                target_view,
            ),
            m6_boundary_color_rgb=boundary_color,
        ))
    return tuple(overlays)


def _build_abc_points(
    publication: DomainAnalysisPublication,
    frame: M6FrameGate,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[DomainAnalysisABCPointOverlay, ...]:
    outcome = next(
        (
            value
            for value in publication.result.classifier_outcomes or ()
            if value.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        ),
        None,
    )
    if outcome is None or outcome.status != "completed":
        return ()
    classifications = {
        value.source_id: value
        for value in outcome.molecule_classifications
        if value.frame_index == frame.frame_index
        and value.physical_frame_id == frame.physical_frame_id
        and value.m6_partition == "full_domain"
    }
    points = []
    for component in frame.full_domains:
        key = DomainComponentKey(frame.physical_frame_id, component.lattice_domain_id)
        for member in component.members:
            classification = classifications.get(member.source_id)
            if classification is None or member.raw_centroid_xy is None:
                continue
            label = classification.orientation_label
            if label not in _ABC_COLORS:
                continue
            state = cast(ABCPointState, label)
            points.append(DomainAnalysisABCPointOverlay(
                source_id=member.source_id,
                component_key=key,
                point_xy_px=_project_point(
                    member.raw_centroid_xy,
                    frame.presentation_provenance,
                    target_view,
                ),
                state=state,
                color_rgb=_ABC_COLORS[state],
            ))
    return tuple(points)


def _project_point(
    raw_point_xy: tuple[float, float],
    provenance: M6PresentationProvenance,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[float, float]:
    if target_view == "raw":
        return raw_point_xy
    origin_x, origin_y = provenance.frame_origin_xy
    return raw_point_xy[0] + origin_x, raw_point_xy[1] + origin_y


def _m6_component_color(
    lattice_domain_id: str,
    component_type: Literal["full_domain", "small_ordered_island"],
) -> tuple[int, int, int]:
    if component_type == "small_ordered_island":
        return _SMALL_ISLAND_COLOR
    digest = hashlib.sha256(lattice_domain_id.encode("utf-8")).digest()
    return (
        55 + digest[0] * 145 // 255,
        55 + digest[1] * 145 // 255,
        55 + digest[2] * 145 // 255,
    )


def _boundary_pixels(
    pixels_xy: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    pixels = set(pixels_xy)
    return tuple(
        pixel
        for pixel in pixels_xy
        if any(
            (pixel[0] + dx, pixel[1] + dy) not in pixels
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )
    )


__all__ = [
    "DomainAnalysisOverlayPresenter",
]
