from __future__ import annotations

import colorsys
from dataclasses import dataclass
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
    DomainAnalysisWorkspaceSubscription,
    DomainComponentKey,
    DomainHierarchyHighlight,
    EffectiveDomainProjection,
    M6FrameGate,
    M6PresentationProvenance,
    M6PublishedMolecule,
    SelectDomainComponent,
    display_orientation_label,
)
from moltrack.analysis.domain_analysis.manual_domain_projection import (
    membership_footprint,
)
from moltrack.analysis.m6_point_overlay import M6OverlayPointStatus, M6PointOverlay
from moltrack.ui.widgets.stm_series_viewer import STMSeriesViewer
from napara.gui.widgets.viewer_widget import ViewerWidget


DOMAIN_ANALYSIS_DOMAIN_BOUNDARY_COLOR = (220, 230, 233)
DOMAIN_ANALYSIS_SMALL_ISLAND_COLOR = (232, 98, 88)
DOMAIN_ANALYSIS_HIGHLIGHT_COLOR = (241, 196, 15)
OrientationPointState = str
_ABC_POINT_STATUSES: dict[str, M6OverlayPointStatus] = {
    "A": "abc_a",
    "B": "abc_b",
    "C": "abc_c",
    "Unknown orientation": "abc_unknown",
}
_PROTOTYPE_MARKER_STYLES = {
    "A": ((0, 114, 178), "o"),
    "B": ((230, 159, 0), "t"),
    "C": ((204, 121, 167), "s"),
    "D": ((0, 158, 115), "d"),
    "Unknown": ((124, 133, 141), "x"),
    "Unresolvable": ((52, 58, 64), "x"),
}
_EXTENDED_MARKER_SYMBOLS = ("h", "p", "star", "+", "t1", "t2", "t3")


@dataclass(frozen=True)
class OrientationMarkerStyle:
    label: str
    color_rgb: tuple[int, int, int]
    symbol: str


def orientation_marker_style(label: str) -> OrientationMarkerStyle:
    """Return the approved redundant color/shape encoding for A-Z states."""

    if label == "Unknown orientation":
        label = "Unknown"
    if label in _PROTOTYPE_MARKER_STYLES:
        color, symbol = _PROTOTYPE_MARKER_STYLES[label]
        return OrientationMarkerStyle(label, color, symbol)
    if len(label) != 1 or not "E" <= label <= "Z":
        raise ValueError("Orientation marker label must be A-Z or unresolved.")
    index = ord(label) - ord("A")
    hue = (0.17 + index * 0.6180339887498949) % 1.0
    color = cast(tuple[int, int, int], tuple(
        round(255 * channel)
        for channel in colorsys.hsv_to_rgb(hue, 0.68, 0.82)
    ))
    symbol = _EXTENDED_MARKER_SYMBOLS[(index - 4) % len(_EXTENDED_MARKER_SYMBOLS)]
    return OrientationMarkerStyle(
        label,
        color,
        symbol,
    )


@dataclass(frozen=True)
class DomainAnalysisComponentOverlay:
    """One published M6 component projected into the displayed image view."""

    key: DomainComponentKey
    component_type: Literal["full_domain", "small_ordered_island"]
    shape: tuple[int, int]
    pixels_xy: tuple[tuple[int, int], ...]
    m6_boundary_color_rgb: tuple[int, int, int]
    is_highlighted: bool


@dataclass(frozen=True)
class DomainAnalysisOrientationPointOverlay:
    """One effective molecule orientation in the target view."""

    source_id: str
    component_key: DomainComponentKey | None
    point_xy_px: tuple[float, float]
    state: OrientationPointState
    color_rgb: tuple[int, int, int]
    symbol: str


@dataclass(frozen=True)
class DomainAnalysisMoleculePointOverlay:
    """Selectable molecule position independent of M6 membership."""

    source_id: str
    point_xy_px: tuple[float, float]
    is_selected: bool


@dataclass(frozen=True)
class DomainAnalysisFrameOverlay:
    """Immutable published M6 geometry and per-molecule A/B/C projection."""

    target_view: Literal["raw", "expanded_aligned"]
    components: tuple[DomainAnalysisComponentOverlay, ...]
    orientation_points: tuple[DomainAnalysisOrientationPointOverlay, ...]
    molecule_points: tuple[DomainAnalysisMoleculePointOverlay, ...]
    selected_component: DomainComponentKey | None
    hierarchy_highlight: DomainHierarchyHighlight | None
    highlighted_source_ids: tuple[str, ...]
    unassigned_shape: tuple[int, int]
    unassigned_pixels_xy: tuple[tuple[int, int], ...]
    unassigned_is_highlighted: bool


class DomainAnalysisGeometryRenderer:
    """Render shared domain geometry into any MolTrack image canvas."""

    def __init__(self, viewer: ViewerWidget) -> None:
        if not isinstance(viewer, ViewerWidget):
            raise TypeError("viewer must be a ViewerWidget.")
        self._viewer = viewer
        self._items: list[object] = []

    def render(
        self,
        overlay: DomainAnalysisFrameOverlay,
        *,
        selected_component: DomainComponentKey | None,
        fill_alpha: int,
    ) -> None:
        if not isinstance(overlay, DomainAnalysisFrameOverlay):
            raise TypeError("overlay must be a DomainAnalysisFrameOverlay.")
        if not isinstance(fill_alpha, int) or not 0 <= fill_alpha <= 255:
            raise ValueError("fill_alpha must be an integer between 0 and 255.")
        self.clear()
        for component in overlay.components:
            self._render_component(component, selected_component, fill_alpha)
        if overlay.unassigned_is_highlighted:
            self._append(self._viewer.add_mask_overlay_px(
                domain_analysis_pixel_mask(
                    overlay.unassigned_shape,
                    overlay.unassigned_pixels_xy,
                ),
                color=DOMAIN_ANALYSIS_HIGHLIGHT_COLOR,
                alpha=150,
            ))

    def clear(self) -> None:
        for item in self._items:
            self._viewer.remove_item(item)
        self._items.clear()

    def _render_component(
        self,
        component: DomainAnalysisComponentOverlay,
        selected_component: DomainComponentKey | None,
        fill_alpha: int,
    ) -> None:
        mask = domain_analysis_pixel_mask(component.shape, component.pixels_xy)
        boundary = domain_analysis_pixel_mask(
            component.shape,
            domain_analysis_boundary_pixels(component.pixels_xy),
        )
        self._append(
            self._viewer.add_mask_overlay_px(
                mask,
                color=component.m6_boundary_color_rgb,
                alpha=fill_alpha,
            ),
            self._viewer.add_mask_overlay_px(
                boundary,
                color=component.m6_boundary_color_rgb,
                alpha=220,
            ),
        )
        if component.key == selected_component or component.is_highlighted:
            self._append(self._viewer.add_mask_overlay_px(
                boundary,
                color=DOMAIN_ANALYSIS_HIGHLIGHT_COLOR,
                alpha=255,
            ))

    def _append(self, *items: object | None) -> None:
        self._items.extend(item for item in items if item is not None)


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
        self._geometry_renderer = DomainAnalysisGeometryRenderer(viewer.viewer)
        self._target_view: Literal["raw", "expanded_aligned"] = "raw"
        self._frame_overlay: DomainAnalysisFrameOverlay | None = None
        self._snapshot_received.connect(self._render_snapshot)
        viewer.image_pixel_clicked.connect(self._select_at_pixel)
        self._subscription: DomainAnalysisWorkspaceSubscription | None = (
            controller.state_changed.connect(self._snapshot_received.emit)
        )
        self._render_snapshot(controller.snapshot)

    def shutdown(self) -> None:
        """Detach callbacks before the Qt object hierarchy is destroyed."""

        subscription = self._subscription
        self._subscription = None
        if subscription is not None:
            subscription.disconnect()
        self._clear_items()

    @property
    def target_view(self) -> Literal["raw", "expanded_aligned"]:
        return self._target_view

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
        overlay = build_domain_analysis_frame_overlay(value, self._target_view)
        self._frame_overlay = overlay
        if overlay is None:
            return
        self._geometry_renderer.render(
            overlay,
            selected_component=overlay.selected_component,
            fill_alpha=65,
        )
        self._render_orientation_points(overlay)

    def _render_orientation_points(self, overlay: DomainAnalysisFrameOverlay) -> None:
        points = overlay.orientation_points
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
        selected_ids = {
            value.source_id
            for value in points
            if value.component_key == selected
        }
        self._viewer.highlight_m6_overlay_source_ids(
            selected_ids.union(overlay.highlighted_source_ids)
        )

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
        self._geometry_renderer.clear()


def domain_analysis_pixel_mask(
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
    raw_mask = domain_analysis_pixel_mask(provenance.raw_shape, raw_pixels_xy)
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


def build_domain_analysis_frame_overlay(
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
    highlight = snapshot.hierarchy_highlight
    projection = snapshot.domain_corrections.effective_projection
    components = _build_component_overlays(
        frame,
        target_view,
        highlight,
        projection,
    )
    component_keys = tuple(value.key for value in components)
    selected = (
        snapshot.selected_component
        if snapshot.selected_component in component_keys
        else None
    )
    orientation_points = _build_orientation_points(
        snapshot,
        publication,
        frame,
        target_view,
    )
    provenance = frame.presentation_provenance
    return DomainAnalysisFrameOverlay(
        target_view=target_view,
        components=components,
        orientation_points=orientation_points,
        molecule_points=_build_molecule_points(
            frame,
            target_view,
            snapshot.domain_corrections.selected_source_ids,
        ),
        selected_component=selected,
        hierarchy_highlight=highlight,
        highlighted_source_ids=_highlighted_source_ids(
            highlight,
            orientation_points,
        ),
        unassigned_shape=(
            provenance.raw_shape
            if target_view == "raw"
            else provenance.expanded_shape
        ),
        unassigned_pixels_xy=_project_pixels(
            _effective_outside_pixels(frame, projection),
            provenance,
            target_view,
        ),
        unassigned_is_highlighted=(
            highlight is not None
            and highlight.target_kind == "unassigned"
        ),
    )


def _build_component_overlays(
    frame: M6FrameGate,
    target_view: Literal["raw", "expanded_aligned"],
    highlight: DomainHierarchyHighlight | None,
    projection: EffectiveDomainProjection | None,
) -> tuple[DomainAnalysisComponentOverlay, ...]:
    if projection is not None:
        return _build_effective_component_overlays(
            frame,
            projection,
            target_view,
            highlight,
        )
    provenance = frame.presentation_provenance
    shape = provenance.raw_shape if target_view == "raw" else provenance.expanded_shape
    overlays = []
    for component in frame.full_domains + frame.small_ordered_islands:
        boundary_color = (
            DOMAIN_ANALYSIS_DOMAIN_BOUNDARY_COLOR
            if component.component_type == "full_domain"
            else DOMAIN_ANALYSIS_SMALL_ISLAND_COLOR
        )
        is_highlighted = highlight is not None and (
            (
                highlight.target_kind == "domain"
                and component.component_type == "full_domain"
                and component.lattice_domain_id == highlight.lattice_domain_id
            )
            or (
                highlight.target_kind == "small_ordered_islands"
                and component.component_type == "small_ordered_island"
            )
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
            is_highlighted=is_highlighted,
        ))
    return tuple(overlays)


def _build_effective_component_overlays(
    frame: M6FrameGate,
    projection: EffectiveDomainProjection,
    target_view: Literal["raw", "expanded_aligned"],
    highlight: DomainHierarchyHighlight | None,
) -> tuple[DomainAnalysisComponentOverlay, ...]:
    provenance = frame.presentation_provenance
    shape = provenance.raw_shape if target_view == "raw" else provenance.expanded_shape
    overlays = [
        DomainAnalysisComponentOverlay(
            key=DomainComponentKey(
                domain.physical_frame_id,
                domain.lattice_domain_id,
            ),
            component_type="full_domain",
            shape=shape,
            pixels_xy=_project_pixels(
                domain.footprint_pixels_xy,
                provenance,
                target_view,
            ),
            m6_boundary_color_rgb=DOMAIN_ANALYSIS_DOMAIN_BOUNDARY_COLOR,
            is_highlighted=(
                highlight is not None
                and highlight.target_kind == "domain"
                and highlight.lattice_domain_id == domain.lattice_domain_id
            ),
        )
        for domain in projection.domains
        if domain.physical_frame_id == frame.physical_frame_id
        and not domain.is_tombstone
    ]
    molecules = {
        value.source_id: value
        for value in projection.molecules
        if value.physical_frame_id == frame.physical_frame_id
    }
    for component in frame.small_ordered_islands:
        source_ids = tuple(
            source_id
            for source_id in component.source_ids
            if molecules[source_id].m6_partition == "small_ordered_island"
        )
        pixels = membership_footprint(frame, source_ids)
        if not pixels:
            continue
        overlays.append(DomainAnalysisComponentOverlay(
            key=DomainComponentKey(
                frame.physical_frame_id,
                component.lattice_domain_id,
            ),
            component_type="small_ordered_island",
            shape=shape,
            pixels_xy=_project_pixels(pixels, provenance, target_view),
            m6_boundary_color_rgb=DOMAIN_ANALYSIS_SMALL_ISLAND_COLOR,
            is_highlighted=(
                highlight is not None
                and highlight.target_kind == "small_ordered_islands"
            ),
        ))
    return tuple(overlays)


def _effective_outside_pixels(
    frame: M6FrameGate,
    projection: EffectiveDomainProjection | None,
) -> tuple[tuple[int, int], ...]:
    if projection is None:
        return frame.outside_pixels_xy
    source_ids = tuple(
        value.source_id
        for value in projection.molecules
        if value.physical_frame_id == frame.physical_frame_id
        and value.m6_partition == "outside"
    )
    return membership_footprint(
        frame,
        source_ids,
    )


def _build_orientation_points(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    publication: DomainAnalysisPublication,
    frame: M6FrameGate,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[DomainAnalysisOrientationPointOverlay, ...]:
    projection = snapshot.domain_corrections.effective_projection
    if projection is not None:
        return _build_effective_orientation_points(projection, frame, target_view)
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
            if label not in _ABC_POINT_STATUSES:
                continue
            state = cast(OrientationPointState, label)
            style = orientation_marker_style(state)
            points.append(DomainAnalysisOrientationPointOverlay(
                source_id=member.source_id,
                component_key=key,
                point_xy_px=_project_point(
                    member.raw_centroid_xy,
                    frame.presentation_provenance,
                    target_view,
                ),
                state=state,
                color_rgb=style.color_rgb,
                symbol=style.symbol,
            ))
    return tuple(points)


def _build_effective_orientation_points(
    projection: EffectiveDomainProjection,
    frame: M6FrameGate,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[DomainAnalysisOrientationPointOverlay, ...]:
    molecules = {
        value.source_id: value
        for value in projection.molecules
        if value.physical_frame_id == frame.physical_frame_id
        and value.effective_orientation is not None
    }
    members = _frame_members(frame)
    points = []
    for source_id, molecule in sorted(molecules.items()):
        member = members.get(source_id)
        if member is None or member.raw_centroid_xy is None:
            continue
        label = molecule.effective_orientation
        assert label is not None
        style = orientation_marker_style(label)
        domain_id = molecule.effective_domain_id
        points.append(DomainAnalysisOrientationPointOverlay(
            source_id=source_id,
            component_key=(
                None
                if domain_id is None
                else DomainComponentKey(frame.physical_frame_id, domain_id)
            ),
            point_xy_px=_project_point(
                member.raw_centroid_xy,
                frame.presentation_provenance,
                target_view,
            ),
            state=label,
            color_rgb=style.color_rgb,
            symbol=style.symbol,
        ))
    return tuple(points)


def _build_molecule_points(
    frame: M6FrameGate,
    target_view: Literal["raw", "expanded_aligned"],
    selected_source_ids: tuple[str, ...],
) -> tuple[DomainAnalysisMoleculePointOverlay, ...]:
    selected = set(selected_source_ids)
    members = _frame_members(frame)
    return tuple(
        DomainAnalysisMoleculePointOverlay(
            source_id=source_id,
            point_xy_px=_project_point(
                member.raw_centroid_xy,
                frame.presentation_provenance,
                target_view,
            ),
            is_selected=source_id in selected,
        )
        for source_id, member in sorted(members.items())
        if member.raw_centroid_xy is not None
    )


def _highlighted_source_ids(
    highlight: DomainHierarchyHighlight | None,
    points: tuple[DomainAnalysisOrientationPointOverlay, ...],
) -> tuple[str, ...]:
    if highlight is None or highlight.target_kind not in {
        "domain",
        "orientation_subdomain",
    }:
        return ()
    return tuple(
        point.source_id
        for point in points
        if point.component_key is not None
        and point.component_key.lattice_domain_id == highlight.lattice_domain_id
        and (
            highlight.target_kind == "domain"
            or display_orientation_label(point.state) == highlight.orientation_label
        )
    )


def _frame_members(frame: M6FrameGate) -> dict[str, M6PublishedMolecule]:
    members = {
        member.source_id: member
        for component in frame.full_domains + frame.small_ordered_islands
        for member in component.members
    }
    members.update({member.source_id: member for member in frame.outside_members})
    return members


def _project_point(
    raw_point_xy: tuple[float, float],
    provenance: M6PresentationProvenance,
    target_view: Literal["raw", "expanded_aligned"],
) -> tuple[float, float]:
    if target_view == "raw":
        return raw_point_xy
    origin_x, origin_y = provenance.frame_origin_xy
    return raw_point_xy[0] + origin_x, raw_point_xy[1] + origin_y


def domain_analysis_boundary_pixels(
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
    "DOMAIN_ANALYSIS_DOMAIN_BOUNDARY_COLOR",
    "DOMAIN_ANALYSIS_HIGHLIGHT_COLOR",
    "DOMAIN_ANALYSIS_SMALL_ISLAND_COLOR",
    "DomainAnalysisFrameOverlay",
    "DomainAnalysisOrientationPointOverlay",
    "DomainAnalysisMoleculePointOverlay",
    "DomainAnalysisGeometryRenderer",
    "DomainAnalysisOverlayPresenter",
    "OrientationMarkerStyle",
    "build_domain_analysis_frame_overlay",
    "domain_analysis_boundary_pixels",
    "domain_analysis_pixel_mask",
    "orientation_marker_style",
]
