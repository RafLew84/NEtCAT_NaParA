from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    M6_OVERLAY_MODES,
    FirstShellSuggestionResult,
    MolecularM6OrientationAnalysisSettings,
    MolecularM6ViewSettings,
)

from .m6_pair_correlation_plot import M6PairCorrelationPlot
from .m6_current_frame_results_panel import M6CurrentFrameResultsPanel
from .m6_range_trends_panel import M6RangeTrendsPanel


class M6SettingsPanel(QScrollArea):
    """Validated controls for one M6 orientation-domain analysis run."""

    _GR_FLOAT_CONTROL_MAXIMUM = 1e12
    _GR_FLOAT_CONTROL_DECIMALS = 12
    _GR_CONTRIBUTING_FRAMES_MAXIMUM = 1_000_000

    analysis_requested = pyqtSignal(object)
    analysis_settings_changed = pyqtSignal()
    first_shell_suggestion_requested = pyqtSignal(object)
    view_settings_changed = pyqtSignal(object)
    domain_selection_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._base_settings = MolecularM6OrientationAnalysisSettings()
        self._base_view_settings = MolecularM6ViewSettings()
        self._pending_suggestion: FirstShellSuggestionResult | None = None
        self._analysis_context_enabled = False
        self._analysis_running = False
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        terminology = QLabel(
            "Local q6 | Global q6 coherence | M6 orientation domains",
            content,
        )
        terminology.setWordWrap(True)
        layout.addWidget(terminology)

        overlay_group = QGroupBox("M6 point overlay", content)
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_mode_row = QHBoxLayout()
        self.overlay_mode_group = QButtonGroup(self)
        self.overlay_mode_group.setExclusive(True)
        self._overlay_mode_buttons: dict[str, QPushButton] = {}
        for button_id, (mode, label) in enumerate(
            (
                ("none", "None"),
                ("q6", "q6"),
                ("orientation", "Orientation"),
                ("domain_id", "Domain ID"),
            )
        ):
            button = QPushButton(label, overlay_group)
            button.setCheckable(True)
            self.overlay_mode_group.addButton(button, button_id)
            self._overlay_mode_buttons[mode] = button
            overlay_mode_row.addWidget(button)
        overlay_layout.addLayout(overlay_mode_row)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity", overlay_group))
        self.overlay_opacity = QSlider(Qt.Orientation.Horizontal, overlay_group)
        self.overlay_opacity.setRange(0, 100)
        self.overlay_opacity.setSingleStep(1)
        self.overlay_opacity_value = QLabel("60%", overlay_group)
        opacity_row.addWidget(self.overlay_opacity, 1)
        opacity_row.addWidget(self.overlay_opacity_value)
        overlay_layout.addLayout(opacity_row)
        self.show_unassigned_points = QCheckBox(
            "Show unassigned and QC points",
            overlay_group,
        )
        overlay_layout.addWidget(self.show_unassigned_points)
        layout.addWidget(overlay_group)

        self.current_frame_results_panel = M6CurrentFrameResultsPanel(content)
        self.current_frame_results_panel.domain_selection_changed.connect(
            self.domain_selection_changed.emit
        )
        layout.addWidget(self.current_frame_results_panel)

        self.range_trends_panel = M6RangeTrendsPanel(content)
        layout.addWidget(self.range_trends_panel)

        neighborhood_group = QGroupBox("Neighbors and first shell", content)
        neighborhood_form = QFormLayout(neighborhood_group)
        self.duplicate_detection_enabled = QCheckBox(
            "Enable duplicate detection", neighborhood_group
        )
        neighborhood_form.addRow("", self.duplicate_detection_enabled)
        self.duplicate_max_distance_nm = self._distance_spin(neighborhood_group)
        neighborhood_form.addRow(
            "Duplicate max distance [nm]", self.duplicate_max_distance_nm
        )
        self.first_shell_r_min_nm = self._distance_spin(neighborhood_group)
        neighborhood_form.addRow("First-shell r min [nm]", self.first_shell_r_min_nm)
        self.first_shell_r_max_nm = self._distance_spin(neighborhood_group)
        neighborhood_form.addRow("First-shell r max [nm]", self.first_shell_r_max_nm)
        self.min_neighbors_for_local_order = self._integer_spin(
            neighborhood_group, 1, 100
        )
        neighborhood_form.addRow(
            "Min neighbors for Local q6", self.min_neighbors_for_local_order
        )
        self.min_neighbors_for_seed = self._integer_spin(neighborhood_group, 1, 100)
        neighborhood_form.addRow(
            "Min neighbors for domain seed", self.min_neighbors_for_seed
        )
        layout.addWidget(neighborhood_group)

        pair_correlation_group = QGroupBox("Pair correlation g(r)", content)
        pair_correlation_layout = QVBoxLayout(pair_correlation_group)
        pair_correlation_form = QFormLayout()
        self.gr_bin_width_nm = self._distance_spin(pair_correlation_group)
        pair_correlation_form.addRow("Bin width [nm]", self.gr_bin_width_nm)
        self.gr_max_nm = self._distance_spin(pair_correlation_group)
        pair_correlation_form.addRow("Maximum radius [nm]", self.gr_max_nm)
        self.gr_min_expected_pair_exposure = self._positive_spin(
            pair_correlation_group
        )
        pair_correlation_form.addRow(
            "Min expected pair exposure",
            self.gr_min_expected_pair_exposure,
        )
        self.gr_min_contributing_frames = self._integer_spin(
            pair_correlation_group,
            1,
            1_000_000,
        )
        pair_correlation_form.addRow(
            "Min contributing frames",
            self.gr_min_contributing_frames,
        )
        self.gr_smoothing_method = QComboBox(pair_correlation_group)
        self.gr_smoothing_method.addItem("Gaussian (bins)", "gaussian_bins")
        pair_correlation_form.addRow("Smoothing method", self.gr_smoothing_method)
        self.gr_smoothing_width = self._positive_spin(pair_correlation_group)
        pair_correlation_form.addRow(
            "Smoothing width [bins]",
            self.gr_smoothing_width,
        )
        self.gr_peak_prominence = self._nonnegative_spin(pair_correlation_group)
        pair_correlation_form.addRow(
            "Required peak prominence",
            self.gr_peak_prominence,
        )
        pair_correlation_layout.addLayout(pair_correlation_form)
        self.pair_correlation_plot = M6PairCorrelationPlot(pair_correlation_group)
        pair_correlation_layout.addWidget(self.pair_correlation_plot)
        layout.addWidget(pair_correlation_group)

        domain_group = QGroupBox("M6 orientation domains", content)
        domain_form = QFormLayout(domain_group)
        self.q_seed = self._ratio_spin(domain_group)
        domain_form.addRow("Seed q6 threshold", self.q_seed)
        self.q_grow = self._ratio_spin(domain_group)
        domain_form.addRow("Growth q6 threshold", self.q_grow)
        self.min_ordered_component_size = self._integer_spin(
            domain_group, 1, 1_000_000
        )
        domain_form.addRow("Min ordered component size", self.min_ordered_component_size)
        self.min_seed_size = self._integer_spin(domain_group, 1, 1_000_000)
        domain_form.addRow("Min seed size", self.min_seed_size)
        self.min_domain_size = self._integer_spin(domain_group, 1, 1_000_000)
        domain_form.addRow("Min domain size", self.min_domain_size)
        self.seed_angle_tolerance_deg = self._angle_spin(domain_group)
        domain_form.addRow("Seed angle tolerance [deg]", self.seed_angle_tolerance_deg)
        self.grow_angle_tolerance_deg = self._angle_spin(domain_group)
        domain_form.addRow("Growth angle tolerance [deg]", self.grow_angle_tolerance_deg)
        self.domain_merge_angle_tolerance_deg = self._angle_spin(domain_group)
        domain_form.addRow(
            "Merge angle tolerance [deg]", self.domain_merge_angle_tolerance_deg
        )
        self.footprint_support_radius_nm = self._distance_spin(domain_group)
        domain_form.addRow(
            "Footprint support radius [nm]", self.footprint_support_radius_nm
        )
        layout.addWidget(domain_group)

        robust_group = QGroupBox("Robust bond statistics", content)
        robust_form = QFormLayout(robust_group)
        self.min_bonds_for_domain_length_stats = self._integer_spin(
            robust_group, 1, 1_000_000
        )
        robust_form.addRow(
            "Min bonds for length statistics", self.min_bonds_for_domain_length_stats
        )
        self.domain_bond_length_robust_cv_qc_threshold = self._nonnegative_spin(
            robust_group
        )
        robust_form.addRow(
            "Robust bond-length CV QC threshold",
            self.domain_bond_length_robust_cv_qc_threshold,
        )
        layout.addWidget(robust_group)

        self.advanced_group = QGroupBox("Advanced numerical tolerances", content)
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        advanced_form = QFormLayout(self.advanced_group)
        self.geometry_absolute_tolerance_nm = self._scientific_spin(self.advanced_group)
        advanced_form.addRow(
            "Geometry absolute tolerance [nm]", self.geometry_absolute_tolerance_nm
        )
        self.geometry_relative_tolerance = self._scientific_spin(self.advanced_group)
        advanced_form.addRow("Geometry relative tolerance", self.geometry_relative_tolerance)
        self.orientation_zero_tolerance = self._scientific_spin(self.advanced_group)
        advanced_form.addRow("Orientation zero tolerance", self.orientation_zero_tolerance)
        self.domain_conflict_margin = self._nonnegative_spin(self.advanced_group)
        advanced_form.addRow("Domain conflict margin", self.domain_conflict_margin)
        layout.addWidget(self.advanced_group)

        self.validation_label = QLabel("", content)
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)
        suggestion_row = QHBoxLayout()
        self.suggest_button = QPushButton(
            "Suggest first-shell r_max from g(r)", content
        )
        self.apply_suggestion_button = QPushButton("Apply suggestion", content)
        self.apply_suggestion_button.setEnabled(False)
        suggestion_row.addWidget(self.suggest_button)
        suggestion_row.addWidget(self.apply_suggestion_button)
        layout.addLayout(suggestion_row)
        self.suggestion_label = QLabel("No first-shell suggestion.", content)
        self.suggestion_label.setWordWrap(True)
        layout.addWidget(self.suggestion_label)
        self.progress_label = QLabel("", content)
        layout.addWidget(self.progress_label)
        self.run_button = QPushButton("Run/Recalculate", content)
        layout.addWidget(self.run_button)
        layout.addStretch(1)
        self.setWidget(content)

        self._settings_widgets = (
            self.duplicate_detection_enabled,
            self.duplicate_max_distance_nm,
            self.first_shell_r_min_nm,
            self.first_shell_r_max_nm,
            self.gr_bin_width_nm,
            self.gr_max_nm,
            self.gr_min_expected_pair_exposure,
            self.gr_min_contributing_frames,
            self.gr_smoothing_method,
            self.gr_smoothing_width,
            self.gr_peak_prominence,
            self.min_neighbors_for_local_order,
            self.min_neighbors_for_seed,
            self.q_seed,
            self.q_grow,
            self.min_ordered_component_size,
            self.min_seed_size,
            self.min_domain_size,
            self.seed_angle_tolerance_deg,
            self.grow_angle_tolerance_deg,
            self.domain_merge_angle_tolerance_deg,
            self.footprint_support_radius_nm,
            self.min_bonds_for_domain_length_stats,
            self.domain_bond_length_robust_cv_qc_threshold,
            self.geometry_absolute_tolerance_nm,
            self.geometry_relative_tolerance,
            self.orientation_zero_tolerance,
            self.domain_conflict_margin,
        )
        for widget in self._settings_widgets:
            if isinstance(widget, QCheckBox):
                signal = widget.toggled
            elif isinstance(widget, QComboBox):
                signal = widget.currentIndexChanged
            else:
                signal = widget.valueChanged
            signal.connect(self._on_settings_changed)
        self.pair_correlation_plot.current_r_max_changed.connect(
            self._on_plot_r_max_changed
        )
        self.suggest_button.clicked.connect(self._request_suggestion)
        self.apply_suggestion_button.clicked.connect(self.apply_first_shell_suggestion)
        self.run_button.clicked.connect(self._request_analysis)
        self.set_settings(self._base_settings)
        self.overlay_mode_group.idClicked.connect(self._emit_view_settings_changed)
        self.overlay_opacity.valueChanged.connect(self._on_overlay_opacity_changed)
        self.show_unassigned_points.toggled.connect(self._emit_view_settings_changed)
        self.set_view_settings(self._base_view_settings)

    @staticmethod
    def _distance_spin(parent) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(12)
        spin.setRange(1e-12, 1e12)
        spin.setSingleStep(0.1)
        return spin

    @staticmethod
    def _ratio_spin(parent, *, maximum: float = 1.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(6)
        spin.setRange(0.0, maximum)
        spin.setSingleStep(0.01)
        return spin

    @staticmethod
    def _angle_spin(parent) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(3)
        spin.setRange(0.0, 30.0)
        spin.setSingleStep(0.5)
        return spin

    @staticmethod
    def _scientific_spin(parent) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(15)
        spin.setRange(0.0, 1e12)
        spin.setSingleStep(1e-10)
        return spin

    @staticmethod
    def _nonnegative_spin(parent) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(12)
        spin.setRange(0.0, 1e12)
        spin.setSingleStep(0.01)
        return spin

    @staticmethod
    def _positive_spin(parent) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(12)
        spin.setRange(1e-12, 1e12)
        spin.setSingleStep(0.1)
        return spin

    @staticmethod
    def _integer_spin(parent, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setRange(minimum, maximum)
        return spin

    def settings(self) -> MolecularM6OrientationAnalysisSettings:
        settings = replace(
            self._base_settings,
            duplicate_detection_enabled=self.duplicate_detection_enabled.isChecked(),
            duplicate_max_distance_nm=self.duplicate_max_distance_nm.value(),
            first_shell_r_min_nm=self.first_shell_r_min_nm.value(),
            first_shell_r_max_nm=self.first_shell_r_max_nm.value(),
            gr_bin_width_nm=self.gr_bin_width_nm.value(),
            gr_max_nm=self.gr_max_nm.value(),
            gr_min_expected_pair_exposure=(
                self.gr_min_expected_pair_exposure.value()
            ),
            gr_min_contributing_frames=self.gr_min_contributing_frames.value(),
            gr_smoothing_method=str(self.gr_smoothing_method.currentData()),
            gr_smoothing_width=self.gr_smoothing_width.value(),
            gr_peak_prominence=self.gr_peak_prominence.value(),
            min_neighbors_for_local_order=self.min_neighbors_for_local_order.value(),
            min_neighbors_for_seed=self.min_neighbors_for_seed.value(),
            q_seed=self.q_seed.value(),
            q_grow=self.q_grow.value(),
            min_ordered_component_size=self.min_ordered_component_size.value(),
            min_seed_size=self.min_seed_size.value(),
            min_domain_size=self.min_domain_size.value(),
            seed_angle_tolerance_deg=self.seed_angle_tolerance_deg.value(),
            grow_angle_tolerance_deg=self.grow_angle_tolerance_deg.value(),
            domain_merge_angle_tolerance_deg=(
                self.domain_merge_angle_tolerance_deg.value()
            ),
            footprint_support_radius_nm=self.footprint_support_radius_nm.value(),
            min_bonds_for_domain_length_stats=(
                self.min_bonds_for_domain_length_stats.value()
            ),
            domain_bond_length_robust_cv_qc_threshold=(
                self.domain_bond_length_robust_cv_qc_threshold.value()
            ),
            geometry_absolute_tolerance_nm=self.geometry_absolute_tolerance_nm.value(),
            geometry_relative_tolerance=self.geometry_relative_tolerance.value(),
            orientation_zero_tolerance=self.orientation_zero_tolerance.value(),
            domain_conflict_margin=self.domain_conflict_margin.value(),
        )
        if settings.gr_bin_width_nm >= settings.gr_max_nm:
            raise ValueError("gr_bin_width_nm must be less than gr_max_nm.")
        if settings.first_shell_r_max_nm > settings.gr_max_nm:
            raise ValueError("first_shell_r_max_nm must not exceed gr_max_nm.")
        return settings

    def overlay_mode_options(self) -> tuple[str, ...]:
        return M6_OVERLAY_MODES

    def set_current_frame_results(self, results) -> None:
        self.current_frame_results_panel.set_results(results)

    def set_range_trend_data(self, trend_data) -> None:
        self.range_trends_panel.set_trend_data(trend_data)

    def range_trend_data(self):
        return self.range_trends_panel.trend_data()

    def range_trend_metric_options(self) -> tuple[str, ...]:
        return self.range_trends_panel.metric_options()

    def set_range_trend_metric(self, metric: str) -> None:
        self.range_trends_panel.set_metric(metric)

    def set_range_trend_frame_axis(self, axis: str) -> None:
        self.range_trends_panel.set_frame_axis(axis)

    def range_trend_legend_labels(self) -> tuple[str, str] | None:
        return self.range_trends_panel.legend_labels()

    def range_trend_axis_labels(self) -> tuple[str, str]:
        return self.range_trends_panel.axis_labels()

    def range_trend_plot_values(self):
        return self.range_trends_panel.plot_values()

    def range_trend_frame_values(self):
        return self.range_trends_panel.frame_values()

    def range_trend_status_text(self) -> str:
        return self.range_trends_panel.status_text()

    def overlay_mode(self) -> str:
        for mode, button in self._overlay_mode_buttons.items():
            if button.isChecked():
                return mode
        return "none"

    def set_overlay_mode(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        if normalized not in self._overlay_mode_buttons:
            raise ValueError(f"Unsupported M6 overlay mode: {mode!r}.")
        self._overlay_mode_buttons[normalized].setChecked(True)
        self._emit_view_settings_changed()

    def view_settings(self) -> MolecularM6ViewSettings:
        selected_mode = self.overlay_mode()
        stored_mode = (
            self._base_view_settings.overlay_mode
            if selected_mode == "none"
            else selected_mode
        )
        return replace(
            self._base_view_settings,
            show_domain_overlay=selected_mode != "none",
            overlay_mode=stored_mode,
            show_unassigned_points=self.show_unassigned_points.isChecked(),
            overlay_opacity_percent=self.overlay_opacity.value(),
        )

    def set_view_settings(self, settings: MolecularM6ViewSettings) -> None:
        if not isinstance(settings, MolecularM6ViewSettings):
            raise TypeError("settings must be MolecularM6ViewSettings.")
        self._base_view_settings = settings
        selected_mode = settings.overlay_mode if settings.show_domain_overlay else "none"
        blockers = [
            QSignalBlocker(self.overlay_mode_group),
            QSignalBlocker(self.overlay_opacity),
            QSignalBlocker(self.show_unassigned_points),
        ]
        try:
            self._overlay_mode_buttons[selected_mode].setChecked(True)
            self.overlay_opacity.setValue(settings.overlay_opacity_percent)
            self.show_unassigned_points.setChecked(settings.show_unassigned_points)
            self.overlay_opacity_value.setText(
                f"{settings.overlay_opacity_percent}%"
            )
        finally:
            del blockers

    def set_settings(self, settings: MolecularM6OrientationAnalysisSettings) -> None:
        if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        self._validate_gr_control_representation(settings)
        self._base_settings = settings
        values = {
            self.duplicate_detection_enabled: settings.duplicate_detection_enabled,
            self.duplicate_max_distance_nm: settings.duplicate_max_distance_nm,
            self.first_shell_r_min_nm: settings.first_shell_r_min_nm,
            self.first_shell_r_max_nm: settings.first_shell_r_max_nm,
            self.gr_bin_width_nm: settings.gr_bin_width_nm,
            self.gr_max_nm: settings.gr_max_nm,
            self.gr_min_expected_pair_exposure: (
                settings.gr_min_expected_pair_exposure
            ),
            self.gr_min_contributing_frames: settings.gr_min_contributing_frames,
            self.gr_smoothing_method: settings.gr_smoothing_method,
            self.gr_smoothing_width: settings.gr_smoothing_width,
            self.gr_peak_prominence: settings.gr_peak_prominence,
            self.min_neighbors_for_local_order: settings.min_neighbors_for_local_order,
            self.min_neighbors_for_seed: settings.min_neighbors_for_seed,
            self.q_seed: settings.q_seed,
            self.q_grow: settings.q_grow,
            self.min_ordered_component_size: settings.min_ordered_component_size,
            self.min_seed_size: settings.min_seed_size,
            self.min_domain_size: settings.min_domain_size,
            self.seed_angle_tolerance_deg: settings.seed_angle_tolerance_deg,
            self.grow_angle_tolerance_deg: settings.grow_angle_tolerance_deg,
            self.domain_merge_angle_tolerance_deg: (
                settings.domain_merge_angle_tolerance_deg
            ),
            self.footprint_support_radius_nm: settings.footprint_support_radius_nm,
            self.min_bonds_for_domain_length_stats: (
                settings.min_bonds_for_domain_length_stats
            ),
            self.domain_bond_length_robust_cv_qc_threshold: (
                settings.domain_bond_length_robust_cv_qc_threshold
            ),
            self.geometry_absolute_tolerance_nm: settings.geometry_absolute_tolerance_nm,
            self.geometry_relative_tolerance: settings.geometry_relative_tolerance,
            self.orientation_zero_tolerance: settings.orientation_zero_tolerance,
            self.domain_conflict_margin: settings.domain_conflict_margin,
        }
        blockers = [QSignalBlocker(widget) for widget in values]
        try:
            for widget, value in values.items():
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    index = widget.findData(str(value))
                    if index < 0:
                        widget.addItem(str(value), str(value))
                        index = widget.findData(str(value))
                    widget.setCurrentIndex(index)
                else:
                    widget.setValue(value)
        finally:
            del blockers
        self._pending_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.suggestion_label.setText("No first-shell suggestion.")
        self.pair_correlation_plot.clear_result()
        self.range_trends_panel.invalidate_for_settings_change()
        self._sync_pair_correlation_shell_markers()
        self._refresh_validation()

    def validation_message(self) -> str:
        return self.validation_label.text()

    def set_analysis_context_enabled(self, enabled: bool) -> None:
        self._analysis_context_enabled = bool(enabled)
        self._refresh_validation()

    def set_analysis_running(self, running: bool) -> None:
        self._analysis_running = bool(running)
        self.pair_correlation_plot.set_current_r_max_movable(
            not self._analysis_running
        )
        self.advanced_group.setEnabled(not self._analysis_running)
        for widget in self._settings_widgets:
            widget.setEnabled(not self._analysis_running)
        if not self._analysis_running:
            self.progress_label.setText("")
        self._refresh_validation()

    def set_analysis_progress(
        self,
        completed_count: int,
        total_count: int,
        frame_index: int,
    ) -> None:
        self.progress_label.setText(
            f"Analyzing frame {int(frame_index) + 1}: "
            f"{int(completed_count)}/{int(total_count)}"
        )

    def set_first_shell_suggestion(self, suggestion: FirstShellSuggestionResult) -> None:
        if not isinstance(suggestion, FirstShellSuggestionResult):
            raise TypeError("suggestion must be FirstShellSuggestionResult.")
        self._pending_suggestion = suggestion
        self.pair_correlation_plot.set_suggestion_result(suggestion)
        radius = suggestion.suggested_first_shell_r_max_nm
        if suggestion.quality_status == "valid_suggestion" and radius is not None:
            self.suggestion_label.setText(
                f"Suggested first-shell r_max: {radius:.3f} nm"
            )
            self._refresh_validation()
            return
        self.suggestion_label.setText(
            f"No reliable first-shell suggestion: {suggestion.quality_status}."
        )
        self._pending_suggestion = None
        self.apply_suggestion_button.setEnabled(False)

    def _on_settings_changed(self, _value=None) -> None:
        self.range_trends_panel.invalidate_for_settings_change()
        self._sync_pair_correlation_shell_markers()
        if self.sender() is not self.first_shell_r_max_nm:
            self.pair_correlation_plot.mark_result_stale()
        if self._pending_suggestion is not None:
            self._pending_suggestion = None
            self.suggestion_label.setText(
                "First-shell suggestion is out of date; request a new suggestion."
            )
        self.analysis_settings_changed.emit()
        self._refresh_validation()

    def _on_overlay_opacity_changed(self, opacity_percent: int) -> None:
        self.overlay_opacity_value.setText(f"{int(opacity_percent)}%")
        self._emit_view_settings_changed()

    def _emit_view_settings_changed(self, _value=None) -> None:
        settings = self.view_settings()
        self._base_view_settings = settings
        self.view_settings_changed.emit(settings)

    def suggestion_status_text(self) -> str:
        return self.suggestion_label.text()

    def set_suggestion_unavailable(self, message: str) -> None:
        self._pending_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.suggestion_label.setText(str(message))
        self.pair_correlation_plot.clear_result(str(message))

    def invalidate_first_shell_suggestion(self) -> None:
        self.pair_correlation_plot.mark_result_stale()
        if self._pending_suggestion is None:
            return
        self.set_suggestion_unavailable(
            "First-shell suggestion is out of date; request a new suggestion."
        )

    def apply_first_shell_suggestion(self) -> None:
        suggestion = self._pending_suggestion
        if suggestion is None or suggestion.suggested_first_shell_r_max_nm is None:
            return
        self.first_shell_r_max_nm.setValue(
            suggestion.suggested_first_shell_r_max_nm
        )
        self._pending_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.suggestion_label.setText("First-shell r_max suggestion applied.")

    def _refresh_validation(self, _value=None) -> None:
        try:
            self.settings()
        except ValueError as exc:
            message = str(exc)
            valid = False
        else:
            valid = True
            if self.min_neighbors_for_seed.value() >= 5:
                message = (
                    "Points with 3-4 neighbors can contribute to Local q6 and "
                    "domain growth, but do not initiate domains."
                )
            else:
                threshold = self.min_neighbors_for_seed.value()
                message = (
                    f"Settings valid. With this threshold, points with at least "
                    f"{threshold} neighbors may initiate domains."
                )
        self.validation_label.setText(message)
        self.validation_label.setStyleSheet(
            "color: #b42318;" if not valid else "color: #344054;"
        )
        self.run_button.setEnabled(
            valid and self._analysis_context_enabled and not self._analysis_running
        )
        suggestion_enabled = (
            valid and self._analysis_context_enabled and not self._analysis_running
        )
        self.suggest_button.setEnabled(suggestion_enabled)
        self.apply_suggestion_button.setEnabled(
            suggestion_enabled and self._pending_suggestion is not None
        )

    def _request_analysis(self) -> None:
        try:
            settings = self.settings()
        except ValueError:
            return
        if not self.run_button.isEnabled():
            return
        self.analysis_requested.emit(settings)

    def _request_suggestion(self) -> None:
        try:
            settings = self.settings()
        except ValueError:
            return
        if not self.suggest_button.isEnabled():
            return
        self.first_shell_suggestion_requested.emit(settings)

    def _on_plot_r_max_changed(self, radius_nm: float) -> None:
        self.first_shell_r_max_nm.setValue(float(radius_nm))

    def _sync_pair_correlation_shell_markers(self) -> None:
        self.pair_correlation_plot.set_shell_bounds(
            self.first_shell_r_min_nm.value(),
            self.first_shell_r_max_nm.value(),
            gr_max_nm=self.gr_max_nm.value(),
        )

    def _validate_gr_control_representation(
        self,
        settings: MolecularM6OrientationAnalysisSettings,
    ) -> None:
        self.validate_gr_settings_representable(settings)

    @classmethod
    def validate_gr_settings_representable(
        cls,
        settings: MolecularM6OrientationAnalysisSettings,
    ) -> None:
        if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        float_controls = (
            ("gr_bin_width_nm", 1e-12, settings.gr_bin_width_nm),
            ("gr_max_nm", 1e-12, settings.gr_max_nm),
            (
                "gr_min_expected_pair_exposure",
                1e-12,
                settings.gr_min_expected_pair_exposure,
            ),
            (
                "gr_smoothing_width",
                1e-12,
                settings.gr_smoothing_width,
            ),
            (
                "gr_peak_prominence",
                0.0,
                settings.gr_peak_prominence,
            ),
        )
        for field_name, minimum, value in float_controls:
            if not minimum <= value <= cls._GR_FLOAT_CONTROL_MAXIMUM or (
                round(value, cls._GR_FLOAT_CONTROL_DECIMALS) != value
            ):
                raise ValueError(
                    f"{field_name} cannot be represented exactly by this UI control."
                )
        contributing_frames = settings.gr_min_contributing_frames
        if not (
            1
            <= contributing_frames
            <= cls._GR_CONTRIBUTING_FRAMES_MAXIMUM
        ):
            raise ValueError(
                "gr_min_contributing_frames cannot be represented by this UI control."
            )
