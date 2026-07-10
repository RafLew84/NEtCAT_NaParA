from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

from moltrack.analysis import MolecularPositionPlotData


class PositionAnalysisDialog(QDialog):
    """Scatter view of molecular positions for one frame and source view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot_data: MolecularPositionPlotData | None = None
        self._displayed_points_xy: tuple[tuple[float, float], ...] = ()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("Position Analysis")
        self.resize(720, 680)

        layout = QVBoxLayout(self)
        self.plot = pg.PlotWidget(self)
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.getPlotItem().setAspectLocked(True)
        self.plot.getPlotItem().invertY(True)
        self.scatter = pg.ScatterPlotItem(
            size=8.0,
            pen=pg.mkPen((20, 20, 20, 220), width=1.0),
            brush=pg.mkBrush((0, 180, 100, 220)),
        )
        self.plot.addItem(self.scatter)
        layout.addWidget(self.plot, 1)

        self.lbl_status = QLabel("Points: 0", self)
        layout.addWidget(self.lbl_status)

    def set_plot_data(self, plot_data: MolecularPositionPlotData) -> None:
        if not isinstance(plot_data, MolecularPositionPlotData):
            raise TypeError("plot_data must be MolecularPositionPlotData.")
        self._plot_data = plot_data
        self._displayed_points_xy = tuple(plot_data.points_xy)
        if self._displayed_points_xy:
            points = np.asarray(self._displayed_points_xy, dtype=np.float64)
            self.scatter.setData(x=points[:, 0], y=points[:, 1])
        else:
            self.scatter.setData(x=[], y=[])
        x_label, y_label = self.axis_labels()
        self.plot.setLabel("bottom", x_label)
        self.plot.setLabel("left", y_label)
        self.plot.setXRange(*plot_data.x_range, padding=0.0)
        self.plot.setYRange(*plot_data.y_range, padding=0.0)
        self.lbl_status.setText(f"Points: {plot_data.point_count}")

    def point_count(self) -> int:
        return 0 if self._plot_data is None else self._plot_data.point_count

    def displayed_points_xy(self) -> tuple[tuple[float, float], ...]:
        return self._displayed_points_xy

    def axis_unit(self) -> str | None:
        return None if self._plot_data is None else self._plot_data.unit

    def axis_labels(self) -> tuple[str, str] | None:
        if self._plot_data is None:
            return None
        return f"x [{self._plot_data.unit}]", f"y [{self._plot_data.unit}]"

    def axis_ranges(self) -> tuple[tuple[float, float], tuple[float, float]] | None:
        if self._plot_data is None:
            return None
        return self._plot_data.x_range, self._plot_data.y_range
