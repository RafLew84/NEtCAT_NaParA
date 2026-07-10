from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

from moltrack.analysis import (
    MolecularNearestNeighborAngleMetrics,
    MolecularNearestNeighborMetrics,
    MolecularPositionPlotData,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)


class PositionAnalysisDialog(QDialog):
    """Scatter view of molecular positions for one frame and source view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot_data: MolecularPositionPlotData | None = None
        self._displayed_points_xy: tuple[tuple[float, float], ...] = ()
        self._distance_metrics: MolecularNearestNeighborMetrics | None = None
        self._angle_metrics: MolecularNearestNeighborAngleMetrics | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("Position Analysis")
        self.resize(760, 820)

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

        self.lbl_metrics = QLabel(
            "Molecules: 0\nNearest neighbor: unavailable\nLine order score: unavailable",
            self,
        )
        self.lbl_metrics.setWordWrap(True)
        layout.addWidget(self.lbl_metrics)

        self.histogram_plot = pg.PlotWidget(self)
        self.histogram_plot.setBackground("w")
        self.histogram_plot.showGrid(x=True, y=True, alpha=0.2)
        self.histogram_plot.setLabel("bottom", "Angle [deg]")
        self.histogram_plot.setLabel("left", "Count")
        self.histogram_plot.setXRange(0.0, 180.0, padding=0.0)
        self.histogram_bars = pg.BarGraphItem(
            x=np.arange(5.0, 180.0, 10.0),
            height=np.zeros(18, dtype=np.float64),
            width=8.0,
            pen=pg.mkPen((20, 20, 20, 180), width=0.8),
            brush=pg.mkBrush((55, 120, 190, 210)),
        )
        self.histogram_plot.addItem(self.histogram_bars)
        layout.addWidget(self.histogram_plot, 1)

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
        self._distance_metrics = compute_molecular_nearest_neighbor_metrics(plot_data)
        self._angle_metrics = compute_molecular_nearest_neighbor_angle_metrics(plot_data)
        self.lbl_metrics.setText(self._format_metrics_summary())
        histogram_counts = np.asarray(self._angle_metrics.histogram_counts, dtype=np.float64)
        self.histogram_bars.setOpts(height=histogram_counts)
        maximum_count = max(self._angle_metrics.histogram_counts, default=0)
        self.histogram_plot.setYRange(0.0, float(max(1, maximum_count)), padding=0.05)
        self.lbl_status.setText(f"Points: {plot_data.point_count}")

    def metrics_summary_text(self) -> str:
        return self.lbl_metrics.text()

    def histogram_counts(self) -> tuple[int, ...]:
        if self._angle_metrics is None:
            return (0,) * 18
        return self._angle_metrics.histogram_counts

    @staticmethod
    def histogram_axis_labels() -> tuple[str, str]:
        return "Angle [deg]", "Count"

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

    def _format_metrics_summary(self) -> str:
        if self._distance_metrics is None or self._angle_metrics is None:
            return "Molecules: 0\nNearest neighbor: unavailable\nLine order score: unavailable"
        distance_metrics = self._distance_metrics
        angle_metrics = self._angle_metrics
        lines = [f"Molecules: {distance_metrics.point_count}"]
        if distance_metrics.mean_distance is None:
            lines.append(f"Nearest neighbor [{distance_metrics.unit}]: unavailable")
        else:
            lines.append(
                f"Nearest neighbor [{distance_metrics.unit}]: "
                f"mean {distance_metrics.mean_distance:.3f} | "
                f"median {distance_metrics.median_distance:.3f} | "
                f"min {distance_metrics.min_distance:.3f} | "
                f"max {distance_metrics.max_distance:.3f}"
            )
        if angle_metrics.line_order_score is None:
            lines.append("Line order score: unavailable")
        else:
            lines.append(f"Line order score: {angle_metrics.line_order_score:.3f}")
        return "\n".join(lines)
