from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, cast

import pyqtgraph as pg
from PyQt6.QtCore import Qt

from napara.gui.widgets.viewer_widget import ViewerWidget


SelectionMode = Literal["point", "polygon"]
SelectionPolygon = tuple[tuple[float, float], ...]


class DomainPolygonSelectionTool:
    """Own the transient gesture state for polygon selection on a viewer."""

    def __init__(
        self,
        viewer: ViewerWidget,
        scale_nm_per_px: tuple[float | None, float | None],
        polygon_finished: Callable[[SelectionPolygon], None],
    ) -> None:
        self._viewer = viewer
        self._scale_nm_per_px = scale_nm_per_px
        self._polygon_finished = polygon_finished
        self._mode: SelectionMode = "point"
        self._vertices_xy: list[tuple[float, float]] = []
        self._item: object | None = None
        viewer.glw.scene().sigMouseClicked.connect(self.handle_scene_click)

    @property
    def mode(self) -> SelectionMode:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in {"point", "polygon"}:
            raise ValueError(f"Unsupported selection mode: {mode!r}.")
        self._mode = cast(SelectionMode, mode)
        if mode == "point":
            self.clear()

    def finish(self) -> None:
        if len(self._vertices_xy) < 3:
            raise ValueError("Polygon selection requires three vertices.")
        polygon = tuple(self._vertices_xy)
        self.clear()
        self._polygon_finished(polygon)

    def handle_scene_click(self, event: Any) -> None:
        if self._mode != "polygon":
            return
        button = event.button()
        if button == Qt.MouseButton.RightButton:
            if len(self._vertices_xy) >= 3:
                self.finish()
            return
        if button != Qt.MouseButton.LeftButton:
            return
        scene_pos = event.scenePos()
        plot = self._viewer.get_plot_item()
        if not plot.sceneBoundingRect().contains(scene_pos):
            return
        view_pos = plot.getViewBox().mapSceneToView(scene_pos)
        scale_x = self._scale_nm_per_px[0] or 1.0
        scale_y = self._scale_nm_per_px[1] or 1.0
        self._vertices_xy.append((
            float(view_pos.x()) / scale_x,
            float(view_pos.y()) / scale_y,
        ))
        self.render()

    def render(self) -> None:
        self.detach()
        if not self._vertices_xy:
            return
        scale_x = self._scale_nm_per_px[0] or 1.0
        scale_y = self._scale_nm_per_px[1] or 1.0
        self._item = pg.PlotDataItem(
            [value[0] * scale_x for value in self._vertices_xy],
            [value[1] * scale_y for value in self._vertices_xy],
            pen=pg.mkPen((58, 178, 187, 230), width=2.0),
            symbol="o",
            symbolSize=6,
        )
        self._viewer.get_plot_item().addItem(self._item)

    def detach(self) -> None:
        if self._item is not None:
            self._viewer.remove_item(self._item)
            self._item = None

    def clear(self) -> None:
        self.detach()
        self._vertices_xy.clear()


__all__ = ["DomainPolygonSelectionTool"]
