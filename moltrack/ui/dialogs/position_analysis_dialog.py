from __future__ import annotations

from typing import cast

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSignalBlocker, QRectF, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    FirstShellSuggestionResult,
    MolecularFrameRange,
    MolecularFrameRangeAnalysisMode,
    MolecularFrameRangeAnalysisScope,
    MolecularFrameRangeComparison,
    MolecularFrameRangeSelection,
    MolecularNearestNeighborAngleMetrics,
    MolecularNearestNeighborMetrics,
    MolecularM6OrientationAnalysisSettings,
    MolecularM6ViewSettings,
    MolecularPositionPlotData,
    MolecularRangeComparisonTrendData,
    MolecularRangeSpatialComparisonData,
    build_molecular_range_comparison_trend_data,
    build_molecular_range_spatial_comparison_data,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)

from .m6_settings_panel import M6SettingsPanel


class PositionAnalysisDialog(QDialog):
    """Scatter view of molecular positions for one frame and source view."""

    compare_ranges_requested = pyqtSignal(object)
    range_analysis_requested = pyqtSignal(object)
    analysis_context_changed = pyqtSignal(str)
    analysis_mode_changed = pyqtSignal(str)
    centroid_source_mode_changed = pyqtSignal(bool)
    intensity_metric_changed = pyqtSignal(str)
    intensity_background_changed = pyqtSignal(int, int)
    export_analysis_requested = pyqtSignal()
    m6_analysis_requested = pyqtSignal(object)
    m6_analysis_settings_changed = pyqtSignal()
    m6_first_shell_suggestion_requested = pyqtSignal(object)
    m6_view_settings_changed = pyqtSignal(object)
    m6_domain_selection_changed = pyqtSignal(object)

    _INTENSITY_METRIC_OPTIONS = (
        ("Background-corrected median", "background_corrected_median"),
        ("Mean", "mean"),
        ("Maximum", "max"),
        ("Integrated", "sum"),
    )
    _POINT_SIZE = 8.0
    _DEFAULT_POINT_COLOR = (0, 180, 100, 220)
    _MISSING_INTENSITY_COLOR = (145, 150, 155, 210)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot_data: MolecularPositionPlotData | None = None
        self._displayed_points_xy: tuple[tuple[float, float], ...] = ()
        self._displayed_point_colors: tuple[tuple[int, int, int, int], ...] = ()
        self._point_tooltips: tuple[str, ...] = ()
        self._intensity_color_range: tuple[float, float] | None = None
        self._intensity_colorbar_label = ""
        self._distance_metrics: MolecularNearestNeighborMetrics | None = None
        self._angle_metrics: MolecularNearestNeighborAngleMetrics | None = None
        self._range_trend_data: MolecularRangeComparisonTrendData | None = None
        self._range_spatial_data: MolecularRangeSpatialComparisonData | None = None
        self._range_comparison: MolecularFrameRangeComparison | None = None
        self._density_grid_shape = (32, 32)
        self._first_density_levels = (0.0, 1.0)
        self._second_density_levels = (0.0, 1.0)
        self._first_spatial_scatter_intensity_levels: tuple[float, float] | None = None
        self._second_spatial_scatter_intensity_levels: tuple[float, float] | None = None
        self._first_spatial_scatter_colors: tuple[tuple[int, ...], ...] = ()
        self._second_spatial_scatter_colors: tuple[tuple[int, ...], ...] = ()
        self._first_spatial_intensity_levels: tuple[float, float] | None = None
        self._second_spatial_intensity_levels: tuple[float, float] | None = None
        self._range_frame_count: int | None = None
        self._range_source_view = "raw"
        self._analysis_mode: MolecularFrameRangeAnalysisMode = "compare_ranges"
        self._m6_context_enabled_states: dict[QWidget, bool] | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle("Position Analysis")
        self.resize(760, 820)

        layout = QVBoxLayout(self)
        self.chk_use_segmentation_centroids = QCheckBox("Use segmentation centroids", self)
        self.chk_use_segmentation_centroids.setChecked(True)
        self.chk_use_segmentation_centroids.toggled.connect(self.centroid_source_mode_changed.emit)
        layout.addWidget(self.chk_use_segmentation_centroids)
        self.range_group = QGroupBox("Frame ranges", self)
        range_layout = QGridLayout(self.range_group)
        range_mode_row = QHBoxLayout()
        self.range_mode_group = QButtonGroup(self)
        self.range_mode_group.setExclusive(True)
        self.btn_range_mode_single = QPushButton("Single range", self.range_group)
        self.btn_range_mode_single.setCheckable(True)
        self.btn_range_mode_compare = QPushButton("Compare two ranges", self.range_group)
        self.btn_range_mode_compare.setCheckable(True)
        self.range_mode_group.addButton(self.btn_range_mode_single)
        self.range_mode_group.addButton(self.btn_range_mode_compare)
        self.btn_range_mode_compare.setChecked(True)
        range_mode_row.addWidget(self.btn_range_mode_single)
        range_mode_row.addWidget(self.btn_range_mode_compare)
        range_layout.addLayout(range_mode_row, 0, 0, 1, 3)
        self.lbl_range_source_view = QLabel("Source view: raw", self.range_group)
        range_layout.addWidget(self.lbl_range_source_view, 1, 0, 1, 3)
        range_layout.addWidget(QLabel("Condition", self.range_group), 2, 0)
        range_layout.addWidget(QLabel("Start frame", self.range_group), 2, 1)
        range_layout.addWidget(QLabel("End frame", self.range_group), 2, 2)
        self.edit_first_range_name = QLineEdit("before desorption", self.range_group)
        self.sp_first_range_start = QSpinBox(self.range_group)
        self.sp_first_range_end = QSpinBox(self.range_group)
        range_layout.addWidget(self.edit_first_range_name, 3, 0)
        range_layout.addWidget(self.sp_first_range_start, 3, 1)
        range_layout.addWidget(self.sp_first_range_end, 3, 2)
        self.edit_second_range_name = QLineEdit("after adsorption", self.range_group)
        self.sp_second_range_start = QSpinBox(self.range_group)
        self.sp_second_range_end = QSpinBox(self.range_group)
        range_layout.addWidget(self.edit_second_range_name, 4, 0)
        range_layout.addWidget(self.sp_second_range_start, 4, 1)
        range_layout.addWidget(self.sp_second_range_end, 4, 2)
        self.lbl_range_validation = QLabel("", self.range_group)
        self.lbl_range_validation.setWordWrap(True)
        self.lbl_range_validation.setStyleSheet("color: #b42318;")
        range_layout.addWidget(self.lbl_range_validation, 5, 0, 1, 3)
        self.btn_run_range_analysis = QPushButton("Compare ranges", self.range_group)
        self.btn_run_range_analysis.setEnabled(False)
        self.btn_compare_ranges = self.btn_run_range_analysis
        range_layout.addWidget(self.btn_run_range_analysis, 6, 0, 1, 3)
        for spin_box in (
            self.sp_first_range_start,
            self.sp_first_range_end,
            self.sp_second_range_start,
            self.sp_second_range_end,
        ):
            spin_box.valueChanged.connect(self._on_frame_range_context_changed)
        self.edit_first_range_name.textChanged.connect(
            self._on_frame_range_context_changed
        )
        self.edit_second_range_name.textChanged.connect(
            self._on_frame_range_context_changed
        )
        self.btn_range_mode_single.clicked.connect(
            lambda: self.set_analysis_mode("single_range")
        )
        self.btn_range_mode_compare.clicked.connect(
            lambda: self.set_analysis_mode("compare_ranges")
        )
        self.btn_run_range_analysis.clicked.connect(self._request_range_analysis)
        layout.addWidget(self.range_group)

        self.tabs = QTabWidget(self)
        self.current_frame_tab = QWidget(self.tabs)
        current_frame_layout = QVBoxLayout(self.current_frame_tab)
        intensity_controls = QWidget(self.current_frame_tab)
        intensity_controls_layout = QGridLayout(intensity_controls)
        intensity_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_color_by_intensity = QCheckBox("Color points by intensity", intensity_controls)
        self.chk_color_by_intensity.setChecked(True)
        self.chk_color_by_intensity.setEnabled(False)
        self.cmb_intensity_metric = QComboBox(intensity_controls)
        for label, metric in self._INTENSITY_METRIC_OPTIONS:
            self.cmb_intensity_metric.addItem(label, metric)
        self.cmb_intensity_metric.setEnabled(False)
        intensity_controls_layout.addWidget(self.chk_color_by_intensity, 0, 0)
        intensity_controls_layout.addWidget(QLabel("Intensity metric", intensity_controls), 0, 1)
        intensity_controls_layout.addWidget(self.cmb_intensity_metric, 0, 2)
        self.sp_background_inner_radius = QSpinBox(intensity_controls)
        self.sp_background_inner_radius.setRange(0, 99)
        self.sp_background_inner_radius.setValue(1)
        self.sp_background_outer_radius = QSpinBox(intensity_controls)
        self.sp_background_outer_radius.setRange(2, 100)
        self.sp_background_outer_radius.setValue(3)
        intensity_controls_layout.addWidget(QLabel("Inner radius [px]", intensity_controls), 1, 0)
        intensity_controls_layout.addWidget(self.sp_background_inner_radius, 1, 1)
        intensity_controls_layout.addWidget(QLabel("Outer radius [px]", intensity_controls), 2, 0)
        intensity_controls_layout.addWidget(self.sp_background_outer_radius, 2, 1)
        self.sp_background_inner_radius.valueChanged.connect(
            self._on_background_inner_radius_changed
        )
        self.sp_background_outer_radius.valueChanged.connect(
            self._emit_intensity_background_changed
        )
        current_frame_layout.addWidget(intensity_controls)
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
        self._intensity_colormap = pg.colormap.get("viridis")
        self.intensity_colorbar = pg.ColorBarItem(
            values=(0.0, 1.0),
            colorMap=self._intensity_colormap,
            interactive=False,
            colorMapMenu=False,
        )
        self.intensity_colorbar.setImageItem([], insert_in=self.plot.getPlotItem())
        self.intensity_colorbar.setVisible(False)
        self.chk_color_by_intensity.toggled.connect(self._render_current_scatter)
        self.cmb_intensity_metric.currentIndexChanged.connect(self._on_intensity_metric_changed)
        current_frame_layout.addWidget(self.plot, 1)

        self.lbl_metrics = QLabel(
            "Molecules: 0\nNearest neighbor: unavailable\nAngular coherence: unavailable",
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
            y_label="Angular coherence",
        )
        self.intensity_trend_plot = self._create_trend_plot(
            self.range_trends_tab,
            y_label="Median intensity [a.u.]",
        )
        range_trends_layout.addWidget(self.molecule_count_trend_plot, 1)
        range_trends_layout.addWidget(self.nearest_neighbor_trend_plot, 1)
        range_trends_layout.addWidget(self.line_order_trend_plot, 1)
        range_trends_layout.addWidget(self.intensity_trend_plot, 1)
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
        self.first_intensity_plot = self._create_spatial_plot(self.spatial_comparison_tab)
        self.second_intensity_plot = self._create_spatial_plot(self.spatial_comparison_tab)
        self.first_intensity_image = pg.ImageItem(axisOrder="row-major")
        self.second_intensity_image = pg.ImageItem(axisOrder="row-major")
        intensity_lut = self._intensity_colormap.getLookupTable(0.0, 1.0, 256)
        self.first_intensity_image.setLookupTable(intensity_lut)
        self.second_intensity_image.setLookupTable(intensity_lut)
        self.first_intensity_plot.addItem(self.first_intensity_image)
        self.second_intensity_plot.addItem(self.second_intensity_image)
        spatial_layout.addWidget(self.first_spatial_scatter_plot, 0, 0)
        spatial_layout.addWidget(self.second_spatial_scatter_plot, 0, 1)
        spatial_layout.addWidget(self.first_density_plot, 1, 0)
        spatial_layout.addWidget(self.second_density_plot, 1, 1)
        spatial_layout.addWidget(self.first_intensity_plot, 2, 0)
        spatial_layout.addWidget(self.second_intensity_plot, 2, 1)
        self.lbl_spatial_status = QLabel("No spatial comparison.", self.spatial_comparison_tab)
        spatial_layout.addWidget(self.lbl_spatial_status, 3, 0, 1, 2)
        self.tabs.addTab(self.spatial_comparison_tab, "Spatial comparison")

        self.m6_settings_panel = M6SettingsPanel(self.tabs)
        self.m6_settings_panel.analysis_requested.connect(
            self.m6_analysis_requested.emit
        )
        self.m6_settings_panel.analysis_settings_changed.connect(
            self.m6_analysis_settings_changed.emit
        )
        self.m6_settings_panel.first_shell_suggestion_requested.connect(
            self.m6_first_shell_suggestion_requested.emit
        )
        self.m6_settings_panel.view_settings_changed.connect(
            self.m6_view_settings_changed.emit
        )
        self.m6_settings_panel.domain_selection_changed.connect(
            self.m6_domain_selection_changed.emit
        )
        self.tabs.addTab(self.m6_settings_panel, "Sixfold Bond Order")
        self.m6_advanced_group = self.m6_settings_panel.advanced_group
        self.m6_min_neighbors_for_seed_spin = (
            self.m6_settings_panel.min_neighbors_for_seed
        )
        self.m6_first_shell_r_min_spin = self.m6_settings_panel.first_shell_r_min_nm
        self.m6_first_shell_r_max_spin = self.m6_settings_panel.first_shell_r_max_nm
        self.m6_run_button = self.m6_settings_panel.run_button
        self.m6_apply_suggestion_button = (
            self.m6_settings_panel.apply_suggestion_button
        )
        self.chk_use_segmentation_centroids.toggled.connect(
            lambda _checked: self.m6_settings_panel.invalidate_first_shell_suggestion()
        )
        layout.addWidget(self.tabs, 1)
        self.btn_export_analysis = QPushButton("Export Analysis...", self)
        self.btn_export_analysis.clicked.connect(self.export_analysis_requested.emit)
        layout.addWidget(self.btn_export_analysis)

    def use_segmentation_centroids(self) -> bool:
        return self.chk_use_segmentation_centroids.isChecked()

    def set_use_segmentation_centroids(self, enabled: bool) -> None:
        self.chk_use_segmentation_centroids.setChecked(bool(enabled))

    def m6_analysis_settings(self) -> MolecularM6OrientationAnalysisSettings:
        return self.m6_settings_panel.settings()

    def set_m6_analysis_settings(
        self,
        settings: MolecularM6OrientationAnalysisSettings,
    ) -> None:
        self.m6_settings_panel.set_settings(settings)

    def m6_overlay_mode_options(self) -> tuple[str, ...]:
        return self.m6_settings_panel.overlay_mode_options()

    def set_m6_overlay_mode(self, mode: str) -> None:
        self.m6_settings_panel.set_overlay_mode(mode)

    def m6_view_settings(self) -> MolecularM6ViewSettings:
        return self.m6_settings_panel.view_settings()

    def set_m6_view_settings(self, settings: MolecularM6ViewSettings) -> None:
        self.m6_settings_panel.set_view_settings(settings)

    def set_m6_current_frame_results(self, results) -> None:
        self.m6_settings_panel.set_current_frame_results(results)

    def m6_validation_message(self) -> str:
        return self.m6_settings_panel.validation_message()

    def set_m6_first_shell_suggestion(
        self,
        suggestion: FirstShellSuggestionResult,
    ) -> None:
        self.m6_settings_panel.set_first_shell_suggestion(suggestion)

    def m6_suggestion_status_text(self) -> str:
        return self.m6_settings_panel.suggestion_status_text()

    def set_m6_suggestion_unavailable(self, message: str) -> None:
        self.m6_settings_panel.set_suggestion_unavailable(message)

    def apply_m6_first_shell_suggestion(self) -> None:
        self.m6_settings_panel.apply_first_shell_suggestion()

    def set_m6_analysis_running(self, running: bool) -> None:
        self.m6_settings_panel.set_analysis_running(running)
        context_widgets = (
            self.chk_use_segmentation_centroids,
            self.range_group,
            self.cmb_intensity_metric,
            self.sp_background_inner_radius,
            self.sp_background_outer_radius,
            self.btn_export_analysis,
        )
        if running:
            self._m6_context_enabled_states = {
                widget: widget.isEnabled() for widget in context_widgets
            }
            for widget in context_widgets:
                widget.setEnabled(False)
            return
        if self._m6_context_enabled_states is not None:
            for widget, enabled in self._m6_context_enabled_states.items():
                widget.setEnabled(enabled)
        self._m6_context_enabled_states = None

    def set_m6_analysis_progress(
        self,
        completed_count: int,
        total_count: int,
        frame_index: int,
    ) -> None:
        self.m6_settings_panel.set_analysis_progress(
            completed_count,
            total_count,
            frame_index,
        )

    def set_plot_data(self, plot_data: MolecularPositionPlotData) -> None:
        if not isinstance(plot_data, MolecularPositionPlotData):
            raise TypeError("plot_data must be MolecularPositionPlotData.")
        previous_source_view = (
            None if self._plot_data is None else self._plot_data.source_view
        )
        self._plot_data = plot_data
        self._range_source_view = plot_data.source_view
        self.lbl_range_source_view.setText(f"Source view: {self._range_source_view}")
        self._displayed_points_xy = tuple(plot_data.points_xy)
        metric_index = self.cmb_intensity_metric.findData(plot_data.intensity_metric)
        if metric_index >= 0 and metric_index != self.cmb_intensity_metric.currentIndex():
            self.cmb_intensity_metric.blockSignals(True)
            self.cmb_intensity_metric.setCurrentIndex(metric_index)
            self.cmb_intensity_metric.blockSignals(False)
        has_measurements = plot_data.intensity_unit is not None
        self.chk_color_by_intensity.setEnabled(has_measurements)
        self.cmb_intensity_metric.setEnabled(has_measurements)
        self._render_current_scatter()
        if (
            previous_source_view is not None
            and previous_source_view != plot_data.source_view
        ):
            self.analysis_context_changed.emit("source_view")
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
        previous_source_view = self._range_source_view
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
        if not first_configuration and self._range_source_view != previous_source_view:
            self.analysis_context_changed.emit("source_view")

    def frame_range_selection(self) -> MolecularFrameRangeSelection:
        if self._range_frame_count is None:
            raise RuntimeError("Frame range context has not been configured.")
        return MolecularFrameRangeSelection(
            frame_count=self._range_frame_count,
            source_view=self._range_source_view,
            first_range=self._frame_range_from_controls(
                self.edit_first_range_name,
                self.sp_first_range_start,
                self.sp_first_range_end,
            ),
            second_range=self._frame_range_from_controls(
                self.edit_second_range_name,
                self.sp_second_range_start,
                self.sp_second_range_end,
            ),
        )

    def analysis_mode(self) -> MolecularFrameRangeAnalysisMode:
        return self._analysis_mode

    def set_analysis_mode(
        self,
        mode: MolecularFrameRangeAnalysisMode,
        *,
        notify: bool = True,
    ) -> None:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"single_range", "compare_ranges"}:
            raise ValueError(
                "analysis mode must be 'single_range' or 'compare_ranges'."
            )
        changed = normalized_mode != self._analysis_mode
        self._analysis_mode = cast(MolecularFrameRangeAnalysisMode, normalized_mode)
        single_range = normalized_mode == "single_range"
        with QSignalBlocker(self.range_mode_group):
            self.btn_range_mode_single.setChecked(single_range)
            self.btn_range_mode_compare.setChecked(not single_range)
        for widget in (
            self.edit_second_range_name,
            self.sp_second_range_start,
            self.sp_second_range_end,
        ):
            widget.setVisible(not single_range)
        self.btn_run_range_analysis.setText(
            "Analyze range" if single_range else "Compare ranges"
        )
        self._refresh_range_validation()
        if changed and notify:
            self.analysis_mode_changed.emit(normalized_mode)

    def frame_range_analysis_scope(self) -> MolecularFrameRangeAnalysisScope:
        if self._range_frame_count is None:
            raise RuntimeError("Frame range context has not been configured.")
        ranges = [
            self._frame_range_from_controls(
                self.edit_first_range_name,
                self.sp_first_range_start,
                self.sp_first_range_end,
            )
        ]
        if self._analysis_mode == "compare_ranges":
            ranges.append(
                self._frame_range_from_controls(
                    self.edit_second_range_name,
                    self.sp_second_range_start,
                    self.sp_second_range_end,
                )
            )
        return MolecularFrameRangeAnalysisScope(
            analysis_mode=self._analysis_mode,
            frame_count=self._range_frame_count,
            source_view=self._range_source_view,
            ranges=tuple(ranges),
        )

    @staticmethod
    def _frame_range_from_controls(
        name_edit: QLineEdit,
        start_spin: QSpinBox,
        end_spin: QSpinBox,
    ) -> MolecularFrameRange:
        return MolecularFrameRange(
            name_edit.text(),
            start_spin.value() - 1,
            end_spin.value() - 1,
        )

    def apply_frame_range_selection(
        self,
        selection: MolecularFrameRangeSelection,
        *,
        notify: bool = True,
    ) -> None:
        if not isinstance(selection, MolecularFrameRangeSelection):
            raise TypeError("selection must be a MolecularFrameRangeSelection instance.")
        if self._range_frame_count is None or selection.frame_count != self._range_frame_count:
            raise ValueError("selection frame_count must match the configured series.")
        previous_selection = self.frame_range_selection()
        widgets = (
            self.edit_first_range_name,
            self.sp_first_range_start,
            self.sp_first_range_end,
            self.edit_second_range_name,
            self.sp_second_range_start,
            self.sp_second_range_end,
        )
        blockers = [QSignalBlocker(widget) for widget in widgets]
        try:
            self._range_source_view = selection.source_view
            self.lbl_range_source_view.setText(f"Source view: {selection.source_view}")
            self.edit_first_range_name.setText(selection.first_range.name)
            self.sp_first_range_start.setValue(selection.first_range.start_frame + 1)
            self.sp_first_range_end.setValue(selection.first_range.end_frame + 1)
            self.edit_second_range_name.setText(selection.second_range.name)
            self.sp_second_range_start.setValue(selection.second_range.start_frame + 1)
            self.sp_second_range_end.setValue(selection.second_range.end_frame + 1)
        finally:
            del blockers
        self._refresh_range_validation()
        if notify and selection != previous_selection:
            reason = (
                "source_view"
                if selection.source_view != previous_selection.source_view
                else "frame_ranges"
            )
            self.analysis_context_changed.emit(reason)

    def set_range_comparison(
        self,
        comparison: MolecularFrameRangeComparison,
        *,
        density_grid_shape: tuple[int, int] = (32, 32),
    ) -> None:
        if not isinstance(comparison, MolecularFrameRangeComparison):
            raise TypeError("comparison must be a MolecularFrameRangeComparison instance.")
        trend_data = build_molecular_range_comparison_trend_data(comparison)
        spatial_data = build_molecular_range_spatial_comparison_data(
            comparison,
            density_grid_shape=density_grid_shape,
        )
        self._range_trend_data = trend_data
        self._range_spatial_data = spatial_data
        self._range_comparison = comparison
        self.m6_settings_panel.set_range_trend_data(trend_data)
        self._density_grid_shape = (
            len(spatial_data.density_y_edges) - 1,
            len(spatial_data.density_x_edges) - 1,
        )
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
        self.intensity_trend_plot.setLabel(
            "left",
            f"Median intensity [{trend_data.first.intensity_unit}]",
        )
        self._set_trend_plot_data(
            self.intensity_trend_plot,
            trend_data,
            first_values=trend_data.first.median_intensities,
            second_values=trend_data.second.median_intensities,
        )
        self.lbl_range_trend_status.setText(
            f"Compared {trend_data.first.condition_name} and {trend_data.second.condition_name}."
        )
        self._set_spatial_comparison_data(spatial_data)
        self.tabs.setCurrentWidget(self.range_trends_tab)

    def range_trend_data(self) -> MolecularRangeComparisonTrendData | None:
        return self._range_trend_data

    def m6_trend_data(self) -> MolecularRangeComparisonTrendData | None:
        return self.m6_settings_panel.range_trend_data()

    def m6_trend_metric_options(self) -> tuple[str, ...]:
        return self.m6_settings_panel.range_trend_metric_options()

    def set_m6_trend_metric(self, metric: str) -> None:
        self.m6_settings_panel.set_range_trend_metric(metric)

    def set_m6_trend_frame_axis(self, axis: str) -> None:
        self.m6_settings_panel.set_range_trend_frame_axis(axis)

    def m6_trend_legend_labels(self) -> tuple[str, str] | None:
        return self.m6_settings_panel.range_trend_legend_labels()

    def m6_trend_axis_labels(self) -> tuple[str, str]:
        return self.m6_settings_panel.range_trend_axis_labels()

    def m6_trend_plot_values(self):
        return self.m6_settings_panel.range_trend_plot_values()

    def m6_trend_frame_values(self):
        return self.m6_settings_panel.range_trend_frame_values()

    def m6_trend_status_text(self) -> str:
        return self.m6_settings_panel.range_trend_status_text()

    def range_comparison(self) -> MolecularFrameRangeComparison | None:
        return self._range_comparison

    def range_spatial_data(self) -> MolecularRangeSpatialComparisonData | None:
        return self._range_spatial_data

    def has_range_comparison(self) -> bool:
        return self._range_trend_data is not None and self._range_spatial_data is not None

    def has_active_range_comparison(self) -> bool:
        return (
            self._analysis_mode == "compare_ranges"
            and self.has_range_comparison()
            and self.has_valid_frame_range_selection()
        )

    def density_grid_shape(self) -> tuple[int, int]:
        return self._density_grid_shape

    def source_view(self) -> str:
        return self._range_source_view

    def intensity_metric(self) -> str:
        return str(self.cmb_intensity_metric.currentData())

    def intensity_unit(self) -> str:
        if self._plot_data is None or self._plot_data.intensity_unit is None:
            return "a.u."
        return str(self._plot_data.intensity_unit)

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
        intensity_unit = "a.u."
        if self._range_trend_data is not None:
            distance_unit = self._range_trend_data.first.distance_unit
            intensity_unit = self._range_trend_data.first.intensity_unit
        return (
            ("Frame", "Molecules"),
            ("Frame", f"Nearest neighbor [{distance_unit}]"),
            ("Frame", "Angular coherence"),
            ("Frame", f"Median intensity [{intensity_unit}]"),
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

    def spatial_scatter_intensity_value_ranges(
        self,
    ) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        return (
            self._first_spatial_scatter_intensity_levels,
            self._second_spatial_scatter_intensity_levels,
        )

    def spatial_intensity_value_ranges(
        self,
    ) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        return self._first_spatial_intensity_levels, self._second_spatial_intensity_levels

    def spatial_scatter_point_colors(
        self,
    ) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
        return self._first_spatial_scatter_colors, self._second_spatial_scatter_colors

    def spatial_intensity_condition_names(self) -> tuple[str, str] | None:
        return self.spatial_condition_names()

    def has_valid_frame_range_selection(self) -> bool:
        try:
            self.frame_range_selection()
        except (RuntimeError, ValueError):
            return False
        return True

    def has_valid_frame_range_analysis_scope(self) -> bool:
        try:
            self.frame_range_analysis_scope()
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

    def displayed_intensity_values(self) -> tuple[float | None, ...]:
        if self._plot_data is None:
            return ()
        return self._plot_data.intensity_values

    def displayed_point_colors(self) -> tuple[tuple[int, int, int, int], ...]:
        return self._displayed_point_colors

    def displayed_point_sizes(self) -> tuple[float, ...]:
        return (self._POINT_SIZE,) * len(self._displayed_points_xy)

    def intensity_metric_options(self) -> tuple[str, ...]:
        return tuple(label for label, _metric in self._INTENSITY_METRIC_OPTIONS)

    def intensity_background_radii(self) -> tuple[int, int]:
        return (
            self.sp_background_inner_radius.value(),
            self.sp_background_outer_radius.value(),
        )

    def set_intensity_background_radii(self, inner_radius_px: int, outer_radius_px: int) -> None:
        inner_radius_px = int(inner_radius_px)
        outer_radius_px = int(outer_radius_px)
        if inner_radius_px < 0:
            raise ValueError("inner_radius_px must be non-negative.")
        if outer_radius_px <= inner_radius_px:
            raise ValueError("outer_radius_px must be greater than inner_radius_px.")
        self.sp_background_inner_radius.blockSignals(True)
        self.sp_background_outer_radius.blockSignals(True)
        try:
            self.sp_background_inner_radius.setValue(inner_radius_px)
            self.sp_background_outer_radius.setMinimum(inner_radius_px + 1)
            self.sp_background_outer_radius.setValue(outer_radius_px)
        finally:
            self.sp_background_inner_radius.blockSignals(False)
            self.sp_background_outer_radius.blockSignals(False)
        self.intensity_background_changed.emit(inner_radius_px, outer_radius_px)

    @staticmethod
    def shared_intensity_scale_enabled() -> bool:
        return True

    def intensity_color_range(self) -> tuple[float, float] | None:
        return self._intensity_color_range

    def intensity_colorbar_label(self) -> str:
        return self._intensity_colorbar_label

    def missing_intensity_color(self) -> tuple[int, int, int, int]:
        return self._MISSING_INTENSITY_COLOR

    def point_tooltip(self, point_index: int) -> str:
        return self._point_tooltips[int(point_index)]

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
            return "Molecules: 0\nNearest neighbor: unavailable\nAngular coherence: unavailable"
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
            lines.append("Angular coherence: unavailable")
        else:
            lines.append(f"Angular coherence: {angle_metrics.line_order_score:.3f}")
        return "\n".join(lines)

    def _on_intensity_metric_changed(self, _index: int) -> None:
        metric = self.cmb_intensity_metric.currentData()
        if metric is not None:
            self.intensity_metric_changed.emit(str(metric))

    def _on_background_inner_radius_changed(self, inner_radius_px: int) -> None:
        minimum_outer_radius = int(inner_radius_px) + 1
        previous_outer_radius = self.sp_background_outer_radius.value()
        self.sp_background_outer_radius.setMinimum(minimum_outer_radius)
        if previous_outer_radius >= minimum_outer_radius:
            self._emit_intensity_background_changed()

    def _emit_intensity_background_changed(self, _value=None) -> None:
        inner_radius_px, outer_radius_px = self.intensity_background_radii()
        self.intensity_background_changed.emit(inner_radius_px, outer_radius_px)

    def _render_current_scatter(self, _checked=None) -> None:
        if self._plot_data is None or not self._displayed_points_xy:
            self.scatter.setData(x=[], y=[])
            self._displayed_point_colors = ()
            self._point_tooltips = ()
            self._intensity_color_range = None
            self._intensity_colorbar_label = ""
            self.intensity_colorbar.setVisible(False)
            return

        points = np.asarray(self._displayed_points_xy, dtype=np.float64)
        use_intensity = self.chk_color_by_intensity.isChecked() and self.chk_color_by_intensity.isEnabled()
        colors = [self._DEFAULT_POINT_COLOR] * len(self._displayed_points_xy)
        self._intensity_color_range = None
        self._intensity_colorbar_label = ""
        if use_intensity:
            finite_values = [
                float(value)
                for value in self._plot_data.intensity_values
                if value is not None and np.isfinite(float(value))
            ]
            colors = [self._MISSING_INTENSITY_COLOR] * len(self._displayed_points_xy)
            if finite_values:
                low = min(finite_values)
                high = max(finite_values)
                self._intensity_color_range = (low, high)
                denominator = high - low
                lookup_table = np.asarray(
                    self._intensity_colormap.getLookupTable(0.0, 1.0, 256),
                    dtype=np.uint8,
                )
                for point_index, value in enumerate(self._plot_data.intensity_values):
                    if value is None or not np.isfinite(float(value)):
                        continue
                    normalized = 0.5 if denominator == 0.0 else (float(value) - low) / denominator
                    color = lookup_table[int(round(normalized * 255.0))]
                    colors[point_index] = tuple(int(channel) for channel in color)
                render_high = high if high > low else low + 1.0
                self.intensity_colorbar.setLevels(values=(low, render_high))
                metric_label = self.cmb_intensity_metric.currentText()
                unit = self._plot_data.intensity_unit or "a.u."
                self._intensity_colorbar_label = f"{metric_label} [{unit}]"
                self.intensity_colorbar.getAxis("left").setLabel(self._intensity_colorbar_label)
                self.intensity_colorbar.setVisible(True)
            else:
                self.intensity_colorbar.setVisible(False)
        else:
            self.intensity_colorbar.setVisible(False)

        self._displayed_point_colors = tuple(colors)
        self._point_tooltips = tuple(
            self._format_point_tooltip(point_index)
            for point_index in range(len(self._displayed_points_xy))
        )
        self.scatter.setData(
            x=points[:, 0],
            y=points[:, 1],
            size=self._POINT_SIZE,
            pen=pg.mkPen((20, 20, 20, 220), width=1.0),
            brush=[pg.mkBrush(color) for color in colors],
            data=list(self._point_tooltips),
            hoverable=True,
            tip=lambda *, x, y, data: str(data),
        )

    def _format_point_tooltip(self, point_index: int) -> str:
        if self._plot_data is None:
            return ""
        x, y = self._plot_data.points_xy[point_index]
        lines = [
            f"x: {x:.3f} {self._plot_data.unit}",
            f"y: {y:.3f} {self._plot_data.unit}",
        ]
        intensity = self._plot_data.intensity_values[point_index]
        if intensity is None or not np.isfinite(float(intensity)):
            lines.append("Intensity: unavailable")
        else:
            metric_label = self.cmb_intensity_metric.currentText()
            unit = self._plot_data.intensity_unit or "a.u."
            lines.append(f"{metric_label}: {float(intensity):.3f} {unit}")
        area_px = self._plot_data.point_areas_px[point_index]
        lines.append("Area: unavailable" if area_px is None else f"Area: {float(area_px):g} px^2")
        lines.append(f"Source: {self._plot_data.point_source_kinds[point_index] or 'unavailable'}")
        return "\n".join(lines)

    def _refresh_range_validation(self, _value=None) -> None:
        if hasattr(self, "m6_settings_panel"):
            self.m6_settings_panel.invalidate_first_shell_suggestion()
        valid = False
        try:
            self.frame_range_analysis_scope()
        except RuntimeError:
            self.lbl_range_validation.setText("")
            self.btn_run_range_analysis.setEnabled(False)
        except ValueError as exc:
            if "start_frame" in str(exc):
                self.lbl_range_validation.setText("Start frame must not exceed end frame.")
            else:
                self.lbl_range_validation.setText(str(exc))
            self.btn_run_range_analysis.setEnabled(False)
        else:
            self.lbl_range_validation.setText("")
            self.btn_run_range_analysis.setEnabled(True)
            valid = True
        self.m6_settings_panel.set_analysis_context_enabled(
            valid and self._analysis_mode == "compare_ranges"
        )

    def _on_frame_range_context_changed(self, _value=None) -> None:
        self._refresh_range_validation()
        self.analysis_context_changed.emit("frame_ranges")

    def _request_range_analysis(self) -> None:
        if not self.has_valid_frame_range_analysis_scope():
            return
        scope = self.frame_range_analysis_scope()
        self.range_analysis_requested.emit(scope)
        if scope.analysis_mode == "compare_ranges":
            self.compare_ranges_requested.emit(scope.to_frame_range_selection())

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
        if not np.any(np.isfinite(first_y)):
            first_x = np.asarray([], dtype=np.float64)
            first_y = np.asarray([], dtype=np.float64)
        if not np.any(np.isfinite(second_y)):
            second_x = np.asarray([], dtype=np.float64)
            second_y = np.asarray([], dtype=np.float64)
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
        intensity_levels = spatial_data.intensity_value_range
        first_colors = self._spatial_intensity_colors(
            spatial_data.first.intensity_values,
            levels=intensity_levels,
        )
        second_colors = self._spatial_intensity_colors(
            spatial_data.second.intensity_values,
            levels=intensity_levels,
        )
        self._first_spatial_scatter_colors = first_colors
        self._second_spatial_scatter_colors = second_colors
        if first_points.size:
            self.first_spatial_scatter.setData(
                x=first_points[:, 0],
                y=first_points[:, 1],
                brush=[pg.mkBrush(color) for color in first_colors],
            )
        else:
            self.first_spatial_scatter.setData(x=[], y=[])
        if second_points.size:
            self.second_spatial_scatter.setData(
                x=second_points[:, 0],
                y=second_points[:, 1],
                brush=[pg.mkBrush(color) for color in second_colors],
            )
        else:
            self.second_spatial_scatter.setData(x=[], y=[])
        self._first_spatial_scatter_intensity_levels = intensity_levels
        self._second_spatial_scatter_intensity_levels = intensity_levels

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
        intensity_render_levels = (
            (0.0, 1.0)
            if intensity_levels is None
            else (
                intensity_levels
                if intensity_levels[1] > intensity_levels[0]
                else (intensity_levels[0], intensity_levels[0] + 1.0)
            )
        )
        self.first_intensity_image.setImage(
            np.asarray(spatial_data.first.intensity_grid, dtype=np.float64),
            autoLevels=False,
            levels=intensity_render_levels,
        )
        self.second_intensity_image.setImage(
            np.asarray(spatial_data.second.intensity_grid, dtype=np.float64),
            autoLevels=False,
            levels=intensity_render_levels,
        )
        self.first_intensity_image.setRect(density_rect)
        self.second_intensity_image.setRect(density_rect)
        self._first_spatial_intensity_levels = intensity_levels
        self._second_spatial_intensity_levels = intensity_levels

        plots = (
            self.first_spatial_scatter_plot,
            self.second_spatial_scatter_plot,
            self.first_density_plot,
            self.second_density_plot,
            self.first_intensity_plot,
            self.second_intensity_plot,
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
        metric_label = spatial_data.intensity_metric.replace("_", " ")
        self.first_intensity_plot.setTitle(
            f"{spatial_data.first.condition_name}: {metric_label} intensity"
        )
        self.second_intensity_plot.setTitle(
            f"{spatial_data.second.condition_name}: {metric_label} intensity"
        )
        intensity_status = (
            "unavailable"
            if intensity_levels is None
            else (
                f"{intensity_levels[0]:.3f} to {intensity_levels[1]:.3f} "
                f"{spatial_data.intensity_unit}"
            )
        )
        self.lbl_spatial_status.setText(
            f"Shared density scale: {levels[0]:.3f} to {levels[1]:.3f} "
            "molecules/frame/bin | "
            f"Shared intensity scale: {intensity_status}"
        )

    def _spatial_intensity_colors(
        self,
        values: tuple[float | None, ...],
        *,
        levels: tuple[float, float] | None,
    ) -> tuple[tuple[int, ...], ...]:
        lookup_table = np.asarray(
            self._intensity_colormap.getLookupTable(0.0, 1.0, 256),
            dtype=np.uint8,
        )
        colors = []
        low, high = (0.0, 1.0) if levels is None else levels
        denominator = high - low
        for value in values:
            if levels is None or value is None or not np.isfinite(float(value)):
                color = self._MISSING_INTENSITY_COLOR
            else:
                normalized = 0.5 if denominator == 0.0 else (float(value) - low) / denominator
                color = tuple(int(channel) for channel in lookup_table[int(round(normalized * 255.0))])
            colors.append(color)
        return tuple(colors)
