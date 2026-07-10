from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeComparison,
    MolecularFrameRangeSelection,
    MolecularNearestNeighborAngleMetrics,
    MolecularNearestNeighborMetrics,
    MolecularPositionPlotData,
    MolecularRangeComparisonTrendData,
    MolecularRangeSpatialComparisonData,
    build_molecular_range_comparison_trend_data,
    build_molecular_range_spatial_comparison_data,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)


class PositionAnalysisDialog(QDialog):
    """Scatter view of molecular positions for one frame and source view."""

    compare_ranges_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot_data: MolecularPositionPlotData | None = None
        self._displayed_points_xy: tuple[tuple[float, float], ...] = ()
        self._distance_metrics: MolecularNearestNeighborMetrics | None = None
        self._angle_metrics: MolecularNearestNeighborAngleMetrics | None = None
        self._range_trend_data: MolecularRangeComparisonTrendData | None = None
        self._range_spatial_data: MolecularRangeSpatialComparisonData | None = None
        self._first_density_levels = (0.0, 1.0)
        self._second_density_levels = (0.0, 1.0)
        self._range_frame_count: int | None = None
        self._range_source_view = "raw"
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("Position Analysis")
        self.resize(760, 820)

        layout = QVBoxLayout(self)
        self.range_group = QGroupBox("Comparison ranges", self)
        range_layout = QGridLayout(self.range_group)
        self.lbl_range_source_view = QLabel("Source view: raw", self.range_group)
        range_layout.addWidget(self.lbl_range_source_view, 0, 0, 1, 3)
        range_layout.addWidget(QLabel("Condition", self.range_group), 1, 0)
        range_layout.addWidget(QLabel("Start frame", self.range_group), 1, 1)
        range_layout.addWidget(QLabel("End frame", self.range_group), 1, 2)
        self.edit_first_range_name = QLineEdit("before desorption", self.range_group)
        self.sp_first_range_start = QSpinBox(self.range_group)
        self.sp_first_range_end = QSpinBox(self.range_group)
        range_layout.addWidget(self.edit_first_range_name, 2, 0)
        range_layout.addWidget(self.sp_first_range_start, 2, 1)
        range_layout.addWidget(self.sp_first_range_end, 2, 2)
        self.edit_second_range_name = QLineEdit("after adsorption", self.range_group)
        self.sp_second_range_start = QSpinBox(self.range_group)
        self.sp_second_range_end = QSpinBox(self.range_group)
        range_layout.addWidget(self.edit_second_range_name, 3, 0)
        range_layout.addWidget(self.sp_second_range_start, 3, 1)
        range_layout.addWidget(self.sp_second_range_end, 3, 2)
        self.lbl_range_validation = QLabel("", self.range_group)
        self.lbl_range_validation.setWordWrap(True)
        self.lbl_range_validation.setStyleSheet("color: #b42318;")
        range_layout.addWidget(self.lbl_range_validation, 4, 0, 1, 3)
        self.btn_compare_ranges = QPushButton("Compare ranges", self.range_group)
        self.btn_compare_ranges.setEnabled(False)
        range_layout.addWidget(self.btn_compare_ranges, 5, 0, 1, 3)
        for spin_box in (
            self.sp_first_range_start,
            self.sp_first_range_end,
            self.sp_second_range_start,
            self.sp_second_range_end,
        ):
            spin_box.valueChanged.connect(self._refresh_range_validation)
        self.edit_first_range_name.textChanged.connect(self._refresh_range_validation)
        self.edit_second_range_name.textChanged.connect(self._refresh_range_validation)
        self.btn_compare_ranges.clicked.connect(self._request_range_comparison)
        layout.addWidget(self.range_group)

        self.tabs = QTabWidget(self)
        self.current_frame_tab = QWidget(self.tabs)
        current_frame_layout = QVBoxLayout(self.current_frame_tab)
        self.plot = pg.PlotWidget(self.current_frame_tab)
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
        current_frame_layout.addWidget(self.plot, 1)

        self.lbl_metrics = QLabel(
            "Molecules: 0\nNearest neighbor: unavailable\nLine order score: unavailable",
            self.current_frame_tab,
        )
        self.lbl_metrics.setWordWrap(True)
        current_frame_layout.addWidget(self.lbl_metrics)

        self.histogram_plot = pg.PlotWidget(self.current_frame_tab)
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
        current_frame_layout.addWidget(self.histogram_plot, 1)

        self.lbl_status = QLabel("Points: 0", self.current_frame_tab)
        current_frame_layout.addWidget(self.lbl_status)
        self.tabs.addTab(self.current_frame_tab, "Current frame")

        self.range_trends_tab = QWidget(self.tabs)
        range_trends_layout = QVBoxLayout(self.range_trends_tab)
        self.molecule_count_trend_plot = self._create_trend_plot(
            self.range_trends_tab,
            y_label="Molecules",
        )
        self.nearest_neighbor_trend_plot = self._create_trend_plot(
            self.range_trends_tab,
            y_label="Nearest neighbor [px]",
        )
        self.line_order_trend_plot = self._create_trend_plot(
            self.range_trends_tab,
            y_label="Line order score",
        )
        range_trends_layout.addWidget(self.molecule_count_trend_plot, 1)
        range_trends_layout.addWidget(self.nearest_neighbor_trend_plot, 1)
        range_trends_layout.addWidget(self.line_order_trend_plot, 1)
        self.lbl_range_trend_status = QLabel("Choose ranges and compare.", self.range_trends_tab)
        range_trends_layout.addWidget(self.lbl_range_trend_status)
        self.tabs.addTab(self.range_trends_tab, "Range trends")

        self.spatial_comparison_tab = QWidget(self.tabs)
        spatial_layout = QGridLayout(self.spatial_comparison_tab)
        self.first_spatial_scatter_plot = self._create_spatial_plot(self.spatial_comparison_tab)
        self.second_spatial_scatter_plot = self._create_spatial_plot(self.spatial_comparison_tab)
        self.first_spatial_scatter = pg.ScatterPlotItem(
            size=7.0,
            pen=pg.mkPen((0, 100, 65), width=0.8),
            brush=pg.mkBrush((0, 140, 90, 190)),
        )
        self.second_spatial_scatter = pg.ScatterPlotItem(
            size=7.0,
            pen=pg.mkPen((30, 75, 150), width=0.8),
            brush=pg.mkBrush((40, 100, 190, 190)),
        )
        self.first_spatial_scatter_plot.addItem(self.first_spatial_scatter)
        self.second_spatial_scatter_plot.addItem(self.second_spatial_scatter)
        self.first_density_plot = self._create_spatial_plot(self.spatial_comparison_tab)
        self.second_density_plot = self._create_spatial_plot(self.spatial_comparison_tab)
        self.first_density_image = pg.ImageItem(axisOrder="row-major")
        self.second_density_image = pg.ImageItem(axisOrder="row-major")
        density_lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self.first_density_image.setLookupTable(density_lut)
        self.second_density_image.setLookupTable(density_lut)
        self.first_density_plot.addItem(self.first_density_image)
        self.second_density_plot.addItem(self.second_density_image)
        spatial_layout.addWidget(self.first_spatial_scatter_plot, 0, 0)
        spatial_layout.addWidget(self.second_spatial_scatter_plot, 0, 1)
        spatial_layout.addWidget(self.first_density_plot, 1, 0)
        spatial_layout.addWidget(self.second_density_plot, 1, 1)
        self.lbl_spatial_status = QLabel("No spatial comparison.", self.spatial_comparison_tab)
        spatial_layout.addWidget(self.lbl_spatial_status, 2, 0, 1, 2)
        self.tabs.addTab(self.spatial_comparison_tab, "Spatial comparison")
        layout.addWidget(self.tabs, 1)

    def set_plot_data(self, plot_data: MolecularPositionPlotData) -> None:
        if not isinstance(plot_data, MolecularPositionPlotData):
            raise TypeError("plot_data must be MolecularPositionPlotData.")
        self._plot_data = plot_data
        self._range_source_view = plot_data.source_view
        self.lbl_range_source_view.setText(f"Source view: {self._range_source_view}")
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

    def configure_frame_ranges(self, *, frame_count: int, source_view: str) -> None:
        frame_count = int(frame_count)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        first_configuration = self._range_frame_count is None
        self._range_frame_count = frame_count
        self._range_source_view = str(source_view).strip()
        self.lbl_range_source_view.setText(f"Source view: {self._range_source_view}")
        for spin_box in (
            self.sp_first_range_start,
            self.sp_first_range_end,
            self.sp_second_range_start,
            self.sp_second_range_end,
        ):
            spin_box.setRange(1, frame_count)
        if first_configuration:
            first_end = max(1, frame_count // 2)
            second_start = min(frame_count, first_end + 1)
            self.sp_first_range_start.setValue(1)
            self.sp_first_range_end.setValue(first_end)
            self.sp_second_range_start.setValue(second_start)
            self.sp_second_range_end.setValue(frame_count)
        self._refresh_range_validation()

    def frame_range_selection(self) -> MolecularFrameRangeSelection:
        if self._range_frame_count is None:
            raise RuntimeError("Frame range context has not been configured.")
        return MolecularFrameRangeSelection(
            frame_count=self._range_frame_count,
            source_view=self._range_source_view,
            first_range=MolecularFrameRange(
                self.edit_first_range_name.text(),
                self.sp_first_range_start.value() - 1,
                self.sp_first_range_end.value() - 1,
            ),
            second_range=MolecularFrameRange(
                self.edit_second_range_name.text(),
                self.sp_second_range_start.value() - 1,
                self.sp_second_range_end.value() - 1,
            ),
        )

    def set_range_comparison(self, comparison: MolecularFrameRangeComparison) -> None:
        if not isinstance(comparison, MolecularFrameRangeComparison):
            raise TypeError("comparison must be a MolecularFrameRangeComparison instance.")
        trend_data = build_molecular_range_comparison_trend_data(comparison)
        spatial_data = build_molecular_range_spatial_comparison_data(comparison)
        self._range_trend_data = trend_data
        self._range_spatial_data = spatial_data
        self._set_trend_plot_data(
            self.molecule_count_trend_plot,
            trend_data,
            first_values=trend_data.first.molecule_counts,
            second_values=trend_data.second.molecule_counts,
        )
        self.nearest_neighbor_trend_plot.setLabel(
            "left",
            f"Nearest neighbor [{trend_data.first.distance_unit}]",
        )
        self._set_trend_plot_data(
            self.nearest_neighbor_trend_plot,
            trend_data,
            first_values=trend_data.first.nearest_neighbor_distances,
            second_values=trend_data.second.nearest_neighbor_distances,
        )
        self._set_trend_plot_data(
            self.line_order_trend_plot,
            trend_data,
            first_values=trend_data.first.line_order_scores,
            second_values=trend_data.second.line_order_scores,
        )
        self.lbl_range_trend_status.setText(
            f"Compared {trend_data.first.condition_name} and {trend_data.second.condition_name}."
        )
        self._set_spatial_comparison_data(spatial_data)
        self.tabs.setCurrentWidget(self.range_trends_tab)

    def range_trend_data(self) -> MolecularRangeComparisonTrendData | None:
        return self._range_trend_data

    def range_spatial_data(self) -> MolecularRangeSpatialComparisonData | None:
        return self._range_spatial_data

    def analysis_tab_labels(self) -> tuple[str, ...]:
        return tuple(self.tabs.tabText(index) for index in range(self.tabs.count()))

    def active_analysis_tab(self) -> str:
        return self.tabs.tabText(self.tabs.currentIndex())

    def activate_analysis_tab(self, tab_label: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == str(tab_label):
                self.tabs.setCurrentIndex(index)
                return
        raise ValueError(f"Unknown analysis tab: {tab_label!r}.")

    def trend_legend_labels(self) -> tuple[str, str] | None:
        if self._range_trend_data is None:
            return None
        return (
            self._range_trend_data.first.condition_name,
            self._range_trend_data.second.condition_name,
        )

    def trend_axis_labels(self) -> tuple[tuple[str, str], ...]:
        distance_unit = "px"
        if self._range_trend_data is not None:
            distance_unit = self._range_trend_data.first.distance_unit
        return (
            ("Frame", "Molecules"),
            ("Frame", f"Nearest neighbor [{distance_unit}]"),
            ("Frame", "Line order score"),
        )

    def spatial_condition_names(self) -> tuple[str, str] | None:
        if self._range_spatial_data is None:
            return None
        return (
            self._range_spatial_data.first.condition_name,
            self._range_spatial_data.second.condition_name,
        )

    def spatial_axis_ranges(self) -> tuple[tuple[float, float], tuple[float, float]] | None:
        if self._range_spatial_data is None:
            return None
        return self._range_spatial_data.x_range, self._range_spatial_data.y_range

    def spatial_density_value_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return self._first_density_levels, self._second_density_levels

    def has_valid_frame_range_selection(self) -> bool:
        try:
            self.frame_range_selection()
        except (RuntimeError, ValueError):
            return False
        return True

    def range_validation_message(self) -> str:
        return self.lbl_range_validation.text()

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

    def _refresh_range_validation(self, _value=None) -> None:
        try:
            self.frame_range_selection()
        except RuntimeError:
            self.lbl_range_validation.setText("")
            self.btn_compare_ranges.setEnabled(False)
        except ValueError as exc:
            if "start_frame" in str(exc):
                self.lbl_range_validation.setText("Start frame must not exceed end frame.")
            else:
                self.lbl_range_validation.setText(str(exc))
            self.btn_compare_ranges.setEnabled(False)
        else:
            self.lbl_range_validation.setText("")
            self.btn_compare_ranges.setEnabled(True)

    def _request_range_comparison(self) -> None:
        if not self.has_valid_frame_range_selection():
            return
        self.compare_ranges_requested.emit(self.frame_range_selection())

    @staticmethod
    def _create_trend_plot(parent: QWidget, *, y_label: str) -> pg.PlotWidget:
        plot = pg.PlotWidget(parent)
        plot.setBackground("w")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.setLabel("bottom", "Frame")
        plot.setLabel("left", y_label)
        plot.addLegend()
        return plot

    @staticmethod
    def _set_trend_plot_data(
        plot: pg.PlotWidget,
        trend_data: MolecularRangeComparisonTrendData,
        *,
        first_values: tuple[int | float | None, ...],
        second_values: tuple[int | float | None, ...],
    ) -> None:
        plot.clear()
        legend = plot.getPlotItem().legend
        if legend is None:
            legend = plot.addLegend()
        else:
            legend.clear()
        first_x = np.asarray(trend_data.first.frame_indices, dtype=np.float64) + 1.0
        second_x = np.asarray(trend_data.second.frame_indices, dtype=np.float64) + 1.0
        first_y = np.asarray(
            [np.nan if value is None else float(value) for value in first_values],
            dtype=np.float64,
        )
        second_y = np.asarray(
            [np.nan if value is None else float(value) for value in second_values],
            dtype=np.float64,
        )
        plot.plot(
            first_x,
            first_y,
            pen=pg.mkPen((0, 140, 90), width=2.0),
            symbol="o",
            symbolBrush=pg.mkBrush((0, 140, 90)),
            name=trend_data.first.condition_name,
            connect="finite",
        )
        plot.plot(
            second_x,
            second_y,
            pen=pg.mkPen((40, 100, 190), width=2.0),
            symbol="s",
            symbolBrush=pg.mkBrush((40, 100, 190)),
            name=trend_data.second.condition_name,
            connect="finite",
        )

    @staticmethod
    def _create_spatial_plot(parent: QWidget) -> pg.PlotWidget:
        plot = pg.PlotWidget(parent)
        plot.setBackground("w")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.getPlotItem().setAspectLocked(True)
        plot.getPlotItem().invertY(True)
        return plot

    def _set_spatial_comparison_data(self, spatial_data: MolecularRangeSpatialComparisonData) -> None:
        first_points = np.asarray(spatial_data.first.points_xy, dtype=np.float64)
        second_points = np.asarray(spatial_data.second.points_xy, dtype=np.float64)
        if first_points.size:
            self.first_spatial_scatter.setData(x=first_points[:, 0], y=first_points[:, 1])
        else:
            self.first_spatial_scatter.setData(x=[], y=[])
        if second_points.size:
            self.second_spatial_scatter.setData(x=second_points[:, 0], y=second_points[:, 1])
        else:
            self.second_spatial_scatter.setData(x=[], y=[])

        levels = spatial_data.density_value_range
        render_levels = levels if levels[1] > levels[0] else (levels[0], levels[0] + 1.0)
        self._first_density_levels = levels
        self._second_density_levels = levels
        density_rect = QRectF(
            spatial_data.x_range[0],
            spatial_data.y_range[0],
            spatial_data.x_range[1] - spatial_data.x_range[0],
            spatial_data.y_range[1] - spatial_data.y_range[0],
        )
        self.first_density_image.setImage(
            np.asarray(spatial_data.first.density_grid, dtype=np.float64),
            autoLevels=False,
            levels=render_levels,
        )
        self.second_density_image.setImage(
            np.asarray(spatial_data.second.density_grid, dtype=np.float64),
            autoLevels=False,
            levels=render_levels,
        )
        self.first_density_image.setRect(density_rect)
        self.second_density_image.setRect(density_rect)

        plots = (
            self.first_spatial_scatter_plot,
            self.second_spatial_scatter_plot,
            self.first_density_plot,
            self.second_density_plot,
        )
        for plot in plots:
            plot.setLabel("bottom", f"x [{spatial_data.unit}]")
            plot.setLabel("left", f"y [{spatial_data.unit}]")
            plot.setXRange(*spatial_data.x_range, padding=0.0)
            plot.setYRange(*spatial_data.y_range, padding=0.0)
        self.first_spatial_scatter_plot.setTitle(f"{spatial_data.first.condition_name}: positions")
        self.second_spatial_scatter_plot.setTitle(f"{spatial_data.second.condition_name}: positions")
        self.first_density_plot.setTitle(f"{spatial_data.first.condition_name}: density")
        self.second_density_plot.setTitle(f"{spatial_data.second.condition_name}: density")
        self.lbl_spatial_status.setText(
            f"Shared density scale: {levels[0]:.3f} to {levels[1]:.3f} molecules/frame/bin"
        )
