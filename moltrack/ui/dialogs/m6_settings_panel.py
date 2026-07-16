from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    FirstShellSuggestionResult,
    MolecularM6OrientationAnalysisSettings,
)


class M6SettingsPanel(QScrollArea):
    """Validated controls for one M6 orientation-domain analysis run."""

    analysis_requested = pyqtSignal(object)
    first_shell_suggestion_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._base_settings = MolecularM6OrientationAnalysisSettings()
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
            signal = widget.toggled if isinstance(widget, QCheckBox) else widget.valueChanged
            signal.connect(self._on_settings_changed)
        self.suggest_button.clicked.connect(self._request_suggestion)
        self.apply_suggestion_button.clicked.connect(self.apply_first_shell_suggestion)
        self.run_button.clicked.connect(self._request_analysis)
        self.set_settings(self._base_settings)

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
    def _integer_spin(parent, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setRange(minimum, maximum)
        return spin

    def settings(self) -> MolecularM6OrientationAnalysisSettings:
        return replace(
            self._base_settings,
            duplicate_detection_enabled=self.duplicate_detection_enabled.isChecked(),
            duplicate_max_distance_nm=self.duplicate_max_distance_nm.value(),
            first_shell_r_min_nm=self.first_shell_r_min_nm.value(),
            first_shell_r_max_nm=self.first_shell_r_max_nm.value(),
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

    def set_settings(self, settings: MolecularM6OrientationAnalysisSettings) -> None:
        if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        self._base_settings = settings
        values = {
            self.duplicate_detection_enabled: settings.duplicate_detection_enabled,
            self.duplicate_max_distance_nm: settings.duplicate_max_distance_nm,
            self.first_shell_r_min_nm: settings.first_shell_r_min_nm,
            self.first_shell_r_max_nm: settings.first_shell_r_max_nm,
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
                else:
                    widget.setValue(value)
        finally:
            del blockers
        self._pending_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.suggestion_label.setText("No first-shell suggestion.")
        self._refresh_validation()

    def validation_message(self) -> str:
        return self.validation_label.text()

    def set_analysis_context_enabled(self, enabled: bool) -> None:
        self._analysis_context_enabled = bool(enabled)
        self._refresh_validation()

    def set_analysis_running(self, running: bool) -> None:
        self._analysis_running = bool(running)
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
        if self._pending_suggestion is not None:
            self._pending_suggestion = None
            self.suggestion_label.setText(
                "First-shell suggestion is out of date; request a new suggestion."
            )
        self._refresh_validation()

    def suggestion_status_text(self) -> str:
        return self.suggestion_label.text()

    def set_suggestion_unavailable(self, message: str) -> None:
        self._pending_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.suggestion_label.setText(str(message))

    def invalidate_first_shell_suggestion(self) -> None:
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
