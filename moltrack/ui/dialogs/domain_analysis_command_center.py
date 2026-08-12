from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import DomainAnalysisWorkspaceSnapshot
from moltrack.ui.domain_analysis_overlay import (
    DOMAIN_ANALYSIS_HIGHLIGHT_COLOR,
    DomainAnalysisFrameOverlay,
    DomainAnalysisGeometryRenderer,
    build_domain_analysis_frame_overlay,
)
from napara.gui.widgets.viewer_widget import ViewerWidget


DomainAnalysisStageId = Literal[
    "analyze",
    "correct",
    "review",
    "datasets",
    "presets",
    "calibrate",
]
DomainAnalysisCanvasTargetViewFor = Callable[
    [],
    Literal["raw", "expanded_aligned"],
]


@dataclass(frozen=True)
class DomainAnalysisStage:
    stage_id: DomainAnalysisStageId
    label: str
    hint: str


@dataclass(frozen=True)
class SelectDomainAnalysisStage:
    stage_id: DomainAnalysisStageId


DOMAIN_ANALYSIS_STAGES = (
    DomainAnalysisStage("analyze", "Analyze", "immutable automatic snapshot"),
    DomainAnalysisStage("correct", "Correct", "M6 and A-Z overrides"),
    DomainAnalysisStage("review", "Review", "complete frozen scope"),
    DomainAnalysisStage("datasets", "References", "target-specific release"),
    DomainAnalysisStage("presets", "Presets", "future-run configuration"),
    DomainAnalysisStage("calibrate", "Calibrate", "bounded campaign"),
)


class DomainAnalysisImageCanvas(QWidget):
    """Read-only image canvas projected from the active workspace frame."""

    def __init__(
        self,
        frame_for: Callable[[int], object] | None,
        *,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
        target_view_for: DomainAnalysisCanvasTargetViewFor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if frame_for is not None and not callable(frame_for):
            raise TypeError("frame_for must be callable or None.")
        self.setObjectName("domainAnalysisCanvas")
        self._frame_for = frame_for
        self._scale_nm_per_px = scale_nm_per_px
        self._target_view_for = target_view_for or (lambda: "raw")
        self._current_frame_index: int | None = None
        self._current_overlay: DomainAnalysisFrameOverlay | None = None
        self._overlay_items: list[object] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.frame_label = QLabel("No active image frame.", self)
        layout.addWidget(self.frame_label)
        self.viewer = ViewerWidget(self)
        self._geometry_renderer = DomainAnalysisGeometryRenderer(self.viewer)
        self.viewer.setMinimumHeight(260)
        layout.addWidget(self.viewer, 1)

    @property
    def current_frame_index(self) -> int | None:
        return self._current_frame_index

    @property
    def has_image(self) -> bool:
        return self._frame_for is not None and self._current_frame_index is not None

    @property
    def current_overlay(self) -> DomainAnalysisFrameOverlay | None:
        return self._current_overlay

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        if not isinstance(snapshot, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self._clear_overlay()
        self.frame_label.setText(snapshot.active_physical_frame_id)
        if self._frame_for is None:
            self._current_frame_index = None
            self._current_overlay = None
            self.viewer.clear()
            self.viewer.hide()
            return
        preserve_zoom = self._current_frame_index is not None
        self.viewer.show()
        self.viewer.set_image(
            self._frame_for(snapshot.active_frame_index),
            scale_nm_per_px=self._scale_nm_per_px,
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )
        self._current_frame_index = snapshot.active_frame_index
        target_view = self._target_view_for()
        if target_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported target view: {target_view!r}.")
        self._current_overlay = build_domain_analysis_frame_overlay(
            snapshot,
            target_view,
        )
        if self._current_overlay is not None:
            self._render_overlay(self._current_overlay)

    def _render_overlay(self, overlay: DomainAnalysisFrameOverlay) -> None:
        self._geometry_renderer.render(
            overlay,
            selected_component=None,
            fill_alpha=40,
        )
        self._render_points(overlay)

    def _render_points(self, overlay: DomainAnalysisFrameOverlay) -> None:
        points = overlay.abc_points
        if not points:
            return
        scale_x = self._scale_nm_per_px[0] or 1.0
        scale_y = self._scale_nm_per_px[1] or 1.0
        highlighted = set(overlay.highlighted_source_ids)
        dim_others = overlay.hierarchy_highlight is not None
        colors = tuple(
            (
                *point.color_rgb,
                230 if not dim_others or point.source_id in highlighted else 50,
            )
            for point in points
        )
        positions = np.asarray(
            [
                (point.point_xy_px[0] * scale_x, point.point_xy_px[1] * scale_y)
                for point in points
            ],
            dtype=np.float64,
        )
        item = pg.ScatterPlotItem(
            pos=positions,
            brush=[pg.mkBrush(color) for color in colors],
            symbol=tuple(point.symbol for point in points),
            pen=[
                pg.mkPen((*DOMAIN_ANALYSIS_HIGHLIGHT_COLOR, 255), width=2.0)
                if point.source_id in highlighted
                else pg.mkPen((20, 20, 20, 180), width=0.8)
                for point in points
            ],
            size=[
                12.0 if point.source_id in highlighted else 8.0
                for point in points
            ],
        )
        self.viewer.get_plot_item().addItem(item)
        self._overlay_items.append(item)

    def _clear_overlay(self) -> None:
        for item in self._overlay_items:
            self.viewer.remove_item(item)
        self._overlay_items.clear()
        self._geometry_renderer.clear()


class DomainAnalysisStageRail(QFrame):
    """Vertical workflow navigation with no scientific state of its own."""

    def __init__(
        self,
        dispatch: Callable[[SelectDomainAnalysisStage], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not callable(dispatch):
            raise TypeError("dispatch must be callable.")
        self.setObjectName("domainAnalysisStageRail")
        layout = QVBoxLayout(self)
        title = QLabel("Workflow", self)
        title.setObjectName("domainAnalysisStageRailTitle")
        layout.addWidget(title)
        self._buttons: dict[DomainAnalysisStageId, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, stage in enumerate(DOMAIN_ANALYSIS_STAGES, start=1):
            button = QPushButton(f"{index}. {stage.label}", self)
            button.setObjectName(f"domainAnalysisStage_{stage.stage_id}")
            button.setCheckable(True)
            button.setToolTip(stage.hint)
            button.clicked.connect(
                lambda _checked=False, value=stage.stage_id: dispatch(
                    SelectDomainAnalysisStage(value)
                )
            )
            group.addButton(button)
            layout.addWidget(button)
            self._buttons[stage.stage_id] = button
        layout.addStretch(1)

    def render_stage(self, stage_id: DomainAnalysisStageId) -> None:
        self._buttons[stage_id].setChecked(True)

    def stage_button(self, stage_id: DomainAnalysisStageId) -> QPushButton:
        return self._buttons[stage_id]


class DomainAnalysisCommandCenter(QWidget):
    """Variant C shell around one shared Domain Analysis snapshot."""

    def __init__(
        self,
        *,
        canvas: QWidget,
        analyze_sheet: QWidget,
        correct_sheet: QWidget,
        diagnostics: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        for value, name in (
            (canvas, "canvas"),
            (analyze_sheet, "analyze_sheet"),
            (correct_sheet, "correct_sheet"),
            (diagnostics, "diagnostics"),
        ):
            if not isinstance(value, QWidget):
                raise TypeError(f"{name} must be a QWidget.")
        if not isinstance(canvas, DomainAnalysisImageCanvas):
            raise TypeError("canvas must be a DomainAnalysisImageCanvas.")
        self.setObjectName("domainAnalysisCommandCenter")
        self.canvas = canvas
        self._current_stage: DomainAnalysisStageId = "analyze"
        self._rendered_snapshot: DomainAnalysisWorkspaceSnapshot | None = None
        self._sheet_indices: dict[DomainAnalysisStageId, int] = {}
        self._build_ui(analyze_sheet, correct_sheet, diagnostics)
        self.dispatch(SelectDomainAnalysisStage("analyze"))

    @property
    def stage_ids(self) -> tuple[DomainAnalysisStageId, ...]:
        return tuple(stage.stage_id for stage in DOMAIN_ANALYSIS_STAGES)

    @property
    def current_stage(self) -> DomainAnalysisStageId:
        return self._current_stage

    @property
    def current_sheet_stage(self) -> DomainAnalysisStageId:
        page = self.bottom_sheet.currentWidget()
        assert page is not None
        return _validated_stage_id(page.property("domainAnalysisStage"))

    @property
    def rendered_snapshot(self) -> DomainAnalysisWorkspaceSnapshot | None:
        return self._rendered_snapshot

    def stage_button(self, stage_id: DomainAnalysisStageId) -> QPushButton:
        return self.stage_rail.stage_button(stage_id)

    def dispatch(self, action: SelectDomainAnalysisStage) -> None:
        if not isinstance(action, SelectDomainAnalysisStage):
            raise TypeError("action must be a SelectDomainAnalysisStage.")
        stage_id = _validated_stage_id(action.stage_id)
        self._current_stage = stage_id
        self.stage_rail.render_stage(stage_id)
        self.bottom_sheet.setCurrentIndex(self._sheet_indices[stage_id])

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        if not isinstance(snapshot, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self._rendered_snapshot = snapshot
        self.canvas.render_snapshot(snapshot)
        backend_id = snapshot.draft.backend_id or "backend not selected"
        self.backend_status_label.setText(backend_id)
        self.run_status_label.setText(snapshot.run.status.replace("_", " ").title())
        self.frame_status_label.setText(
            f"Frame {snapshot.active_frame_index + 1} / {snapshot.frame_count}"
        )

    def _build_ui(
        self,
        analyze_sheet: QWidget,
        correct_sheet: QWidget,
        diagnostics: QWidget,
    ) -> None:
        layout = QGridLayout(self)
        self.stage_rail = DomainAnalysisStageRail(self.dispatch, self)
        layout.addWidget(self.stage_rail, 0, 0, 3, 1)
        layout.addWidget(self._build_status_bar(diagnostics), 0, 1)
        layout.addWidget(self.canvas, 1, 1)
        self.bottom_sheet = QStackedWidget(self)
        self.bottom_sheet.setObjectName("domainAnalysisBottomSheet")
        for stage in DOMAIN_ANALYSIS_STAGES:
            page = (
                analyze_sheet
                if stage.stage_id == "analyze"
                else (
                    correct_sheet
                    if stage.stage_id == "correct"
                    else _future_stage_sheet(stage, self.bottom_sheet)
                )
            )
            page.setProperty("domainAnalysisStage", stage.stage_id)
            self._sheet_indices[stage.stage_id] = self.bottom_sheet.addWidget(page)
        layout.addWidget(self.bottom_sheet, 2, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(1, 1)

    def _build_status_bar(self, diagnostics: QWidget) -> QWidget:
        bar = QGroupBox("Workspace status", self)
        bar.setObjectName("domainAnalysisStatusBar")
        layout = QHBoxLayout(bar)
        self.backend_status_label = QLabel(bar)
        self.run_status_label = QLabel(bar)
        self.frame_status_label = QLabel(bar)
        for label in (
            self.backend_status_label,
            self.run_status_label,
            self.frame_status_label,
        ):
            layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(diagnostics)
        return bar


def _future_stage_sheet(
    stage: DomainAnalysisStage,
    parent: QWidget,
) -> QWidget:
    page = QWidget(parent)
    page.setObjectName(f"domainAnalysisSheet_{stage.stage_id}")
    layout = QVBoxLayout(page)
    title = QLabel(stage.label, page)
    title.setObjectName("domainAnalysisSheetTitle")
    layout.addWidget(title)
    description = QLabel(
        f"{stage.hint}. The current immutable analysis remains on the canvas.",
        page,
    )
    description.setWordWrap(True)
    layout.addWidget(description)
    layout.addStretch(1)
    return page


def _validated_stage_id(value: object) -> DomainAnalysisStageId:
    stage_ids = tuple(stage.stage_id for stage in DOMAIN_ANALYSIS_STAGES)
    if value not in stage_ids:
        raise ValueError(f"Unsupported Domain Analysis stage: {value!r}.")
    return cast(DomainAnalysisStageId, value)


__all__ = [
    "DOMAIN_ANALYSIS_STAGES",
    "DomainAnalysisCommandCenter",
    "DomainAnalysisCanvasTargetViewFor",
    "DomainAnalysisImageCanvas",
    "DomainAnalysisStageId",
    "SelectDomainAnalysisStage",
]
