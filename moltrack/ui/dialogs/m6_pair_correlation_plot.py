from __future__ import annotations

import math

import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moltrack.analysis import FirstShellSuggestionResult


class M6PairCorrelationPlot(QWidget):
    """Plot g(r), its smoothed estimate, and first-shell radius markers."""

    current_r_max_changed = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating_current_r_max = False
        self._raw_data: tuple[tuple[float, ...], tuple[float, ...]] = ((), ())
        self._smoothed_data: tuple[tuple[float, ...], tuple[float, ...]] = ((), ())
        self._marker_positions: dict[str, float | None] = {
            "first_shell_r_min": None,
            "current_first_shell_r_max": None,
            "first_peak": None,
            "suggested_minimum": None,
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot_widget = pg.PlotWidget(self)
        self.plot_widget.setMinimumHeight(250)
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel("bottom", "Radius", units="nm")
        self.plot_widget.setLabel("left", "g(r)")
        self.legend = self.plot_widget.addLegend()

        self.raw_curve = self.plot_widget.plot(
            [],
            [],
            name="Raw g(r)",
            pen=pg.mkPen((95, 105, 120, 210), width=1.2, style=Qt.PenStyle.DashLine),
            connect="finite",
        )
        self.smoothed_curve = self.plot_widget.plot(
            [],
            [],
            name="Smoothed g(r)",
            pen=pg.mkPen((0, 125, 95, 230), width=2.0),
            connect="finite",
        )
        self.peak_marker = pg.ScatterPlotItem(
            size=10,
            symbol="o",
            pen=pg.mkPen((170, 75, 20), width=1.5),
            brush=pg.mkBrush((245, 155, 65, 220)),
        )
        self.minimum_marker = pg.ScatterPlotItem(
            size=11,
            symbol="d",
            pen=pg.mkPen((25, 85, 170), width=1.5),
            brush=pg.mkBrush((80, 150, 230, 220)),
        )
        self.plot_widget.addItem(self.peak_marker)
        self.plot_widget.addItem(self.minimum_marker)
        self.legend.addItem(self.peak_marker, "First peak")
        self.legend.addItem(self.minimum_marker, "Proposed minimum")

        self.first_shell_r_min_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen((110, 110, 110, 200), width=1.2, style=Qt.PenStyle.DashLine),
            label="first-shell r_min",
            labelOpts={"position": 0.92, "color": (80, 80, 80)},
        )
        self.current_r_max_line = pg.InfiniteLine(
            angle=90,
            movable=True,
            pen=pg.mkPen((0, 105, 185, 230), width=2.0),
            hoverPen=pg.mkPen((0, 75, 145, 255), width=3.0),
            label="current r_max",
            labelOpts={"position": 0.82, "color": (0, 85, 155)},
        )
        self.suggested_minimum_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen((25, 85, 170, 180), width=1.2, style=Qt.PenStyle.DotLine),
            label="proposed minimum",
            labelOpts={"position": 0.72, "color": (25, 85, 170)},
        )
        self.plot_widget.addItem(self.first_shell_r_min_line)
        self.plot_widget.addItem(self.current_r_max_line)
        self.plot_widget.addItem(self.suggested_minimum_line)
        self.current_r_max_line.sigPositionChanged.connect(
            self._on_current_r_max_line_changed
        )

        self.status_label = QLabel("No g(r) result.", self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.plot_widget)
        layout.addWidget(self.status_label)
        self._set_result_markers(None, None, None, None)

    @staticmethod
    def axis_labels() -> tuple[str, str]:
        return "Radius [nm]", "g(r)"

    def raw_curve_data(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        return self._raw_data

    def smoothed_curve_data(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        return self._smoothed_data

    def marker_positions_nm(self) -> dict[str, float | None]:
        return dict(self._marker_positions)

    def marker_visibility(self) -> dict[str, bool]:
        return {
            "first_shell_r_min": self.first_shell_r_min_line.isVisible(),
            "current_first_shell_r_max": self.current_r_max_line.isVisible(),
            "first_peak": self.peak_marker.isVisible(),
            "suggested_minimum": (
                self.minimum_marker.isVisible()
                and self.suggested_minimum_line.isVisible()
            ),
        }

    def status_text(self) -> str:
        return self.status_label.text()

    def has_result(self) -> bool:
        return bool(self._raw_data[0])

    def set_shell_bounds(
        self,
        first_shell_r_min_nm: float,
        first_shell_r_max_nm: float,
        *,
        gr_max_nm: float,
    ) -> None:
        r_min = float(first_shell_r_min_nm)
        r_max = float(first_shell_r_max_nm)
        gr_max = float(gr_max_nm)
        if not all(math.isfinite(value) for value in (r_min, r_max, gr_max)):
            raise ValueError("Shell and g(r) radii must be finite.")
        if r_min <= 0.0 or r_max <= 0.0 or gr_max <= 0.0:
            raise ValueError("Shell and g(r) radii must be positive.")
        self._marker_positions["first_shell_r_min"] = r_min
        self._marker_positions["current_first_shell_r_max"] = r_max
        self.first_shell_r_min_line.setValue(r_min)
        self.first_shell_r_min_line.setVisible(True)
        self._updating_current_r_max = True
        try:
            self.current_r_max_line.setValue(r_max)
        finally:
            self._updating_current_r_max = False
        self.current_r_max_line.setVisible(True)
        self.plot_widget.setXRange(0.0, max(gr_max, 1e-12), padding=0.01)

    def set_current_r_max_movable(self, movable: bool) -> None:
        self.current_r_max_line.setMovable(bool(movable))

    def set_suggestion_result(self, result: FirstShellSuggestionResult) -> None:
        if not isinstance(result, FirstShellSuggestionResult):
            raise TypeError("result must be FirstShellSuggestionResult.")
        centers = tuple(float(value) for value in result.bin_centers_nm)
        raw = tuple(float(value) for value in result.raw_g_r)
        smoothed = tuple(float(value) for value in result.smoothed_g_r)
        self._raw_data = centers, raw
        self._smoothed_data = centers, smoothed
        self.raw_curve.setData(x=centers, y=raw)
        self.smoothed_curve.setData(x=centers, y=smoothed)
        self._set_result_markers(
            result.peak_radius_nm,
            result.peak_value,
            result.minimum_radius_nm,
            result.minimum_value,
        )
        if result.quality_status == "valid_suggestion":
            self.status_label.setText(
                "Reliable first peak and following minimum found; "
                f"proposed first-shell r_max: "
                f"{result.suggested_first_shell_r_max_nm:.3f} nm."
            )
            return
        readable_status = result.quality_status.replace("_", " ")
        self.status_label.setText(
            f"No reliable first-shell proposal: {readable_status}."
        )

    def clear_result(self, message: str = "No g(r) result.") -> None:
        self._raw_data = (), ()
        self._smoothed_data = (), ()
        self.raw_curve.setData(x=[], y=[])
        self.smoothed_curve.setData(x=[], y=[])
        self._set_result_markers(None, None, None, None)
        self.status_label.setText(str(message))

    def mark_result_stale(self) -> None:
        if not self.has_result():
            return
        self.clear_result("g(r) settings changed; recalculate the result.")

    def _set_result_markers(
        self,
        peak_radius_nm: float | None,
        peak_value: float | None,
        minimum_radius_nm: float | None,
        minimum_value: float | None,
    ) -> None:
        peak_visible = peak_radius_nm is not None and peak_value is not None
        minimum_visible = minimum_radius_nm is not None and minimum_value is not None
        self._marker_positions["first_peak"] = (
            None if not peak_visible else float(peak_radius_nm)
        )
        self._marker_positions["suggested_minimum"] = (
            None if not minimum_visible else float(minimum_radius_nm)
        )
        if peak_visible:
            self.peak_marker.setData(
                x=[float(peak_radius_nm)],
                y=[float(peak_value)],
            )
        else:
            self.peak_marker.setData(x=[], y=[])
        self.peak_marker.setVisible(peak_visible)
        if minimum_visible:
            self.minimum_marker.setData(
                x=[float(minimum_radius_nm)],
                y=[float(minimum_value)],
            )
            self.suggested_minimum_line.setValue(float(minimum_radius_nm))
        else:
            self.minimum_marker.setData(x=[], y=[])
        self.minimum_marker.setVisible(minimum_visible)
        self.suggested_minimum_line.setVisible(minimum_visible)

    def _on_current_r_max_line_changed(self) -> None:
        radius = float(self.current_r_max_line.value())
        self._marker_positions["current_first_shell_r_max"] = radius
        if not self._updating_current_r_max:
            self.current_r_max_changed.emit(radius)
