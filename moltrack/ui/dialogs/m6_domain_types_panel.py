from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    M6DomainTypeAnalysisOutcome,
    M6DomainTypeAnalysisSource,
    M6DomainTypeAnalysisStoreState,
    M6DomainTypeClassificationSettings,
)
from moltrack.ui.m6_domain_type_worker import M6DomainTypeAnalysisProgress

from .m6_domain_type_plots_panel import M6DomainTypePlotsPanel
from .m6_domain_type_results_table import M6DomainTypeResultsTable


_NON_TRACKING_TOOLTIP = (
    "Classifies shared structural types from independent domain observations; "
    "this does not track domains between frames."
)

_PanelPresentationState = Literal[
    "running",
    "error",
    "override",
    "missing_source",
    "invalid_settings",
    "out_of_date",
    "current",
    "ready",
]


class M6DomainTypesPanel(QScrollArea):
    """Settings and lifecycle status for structural domain-type classification."""

    classification_requested = pyqtSignal(object)
    settings_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source: M6DomainTypeAnalysisSource | None = None
        self._store_state: M6DomainTypeAnalysisStoreState | None = None
        self._running = False
        self._progress: M6DomainTypeAnalysisProgress | None = None
        self._error_message: str | None = None
        self._status_override: str | None = None
        self._validation_error: str | None = None

        self.setWidgetResizable(True)
        content = QWidget(self)
        layout = QVBoxLayout(content)

        settings_group = QGroupBox("Shared structural type settings", content)
        form = QFormLayout(settings_group)

        self.orientation_tolerance_deg = QDoubleSpinBox(settings_group)
        self.orientation_tolerance_deg.setRange(0.0, 30.0)
        self.orientation_tolerance_deg.setDecimals(2)
        self.orientation_tolerance_deg.setSingleStep(0.5)
        self.orientation_tolerance_deg.setSuffix(" deg")
        form.addRow("Orientation tolerance", self.orientation_tolerance_deg)

        self.bond_length_tolerance_mode = QComboBox(settings_group)
        self.bond_length_tolerance_mode.addItem(
            "Relative difference",
            "relative_percent",
        )
        self.bond_length_tolerance_mode.addItem("Absolute distance", "absolute_nm")
        form.addRow("Bond-length tolerance mode", self.bond_length_tolerance_mode)

        self.bond_length_tolerance_value = QDoubleSpinBox(settings_group)
        self.bond_length_tolerance_value.setRange(0.0, 1_000_000.0)
        self.bond_length_tolerance_value.setDecimals(3)
        self.bond_length_tolerance_value.setSingleStep(0.5)
        form.addRow("Bond-length tolerance", self.bond_length_tolerance_value)

        self.minimum_observations_per_type = QSpinBox(settings_group)
        self.minimum_observations_per_type.setRange(0, 1_000_000)
        self.minimum_observations_per_type.setSuffix(" observations")
        form.addRow("Minimum observations per type", self.minimum_observations_per_type)

        self.include_small_ordered_islands = QCheckBox(
            "Include small ordered islands",
            settings_group,
        )
        form.addRow("", self.include_small_ordered_islands)

        self.exclude_bond_length_heterogeneity_qc = QCheckBox(
            "Exclude domains failing bond-length heterogeneity QC",
            settings_group,
        )
        form.addRow("", self.exclude_bond_length_heterogeneity_qc)
        layout.addWidget(settings_group)

        self.validation_label = QLabel("", content)
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        self.classify_button = QPushButton("Classify Types", content)
        self.classify_button.setToolTip(_NON_TRACKING_TOOLTIP)
        layout.addWidget(self.classify_button)

        self.status_label = QLabel("Run/Recalculate M6 before classifying types.", content)
        self.status_label.setWordWrap(True)
        self.status_label.setToolTip(_NON_TRACKING_TOOLTIP)
        layout.addWidget(self.status_label)

        self.results_table = M6DomainTypeResultsTable(content)
        layout.addWidget(self.results_table)

        self.plots_panel = M6DomainTypePlotsPanel(content)
        layout.addWidget(self.plots_panel)
        layout.addStretch(1)
        self.setWidget(content)

        for widget in self.settings_widgets():
            widget.setToolTip(_NON_TRACKING_TOOLTIP)

        self.orientation_tolerance_deg.valueChanged.connect(self._on_settings_changed)
        self.bond_length_tolerance_mode.currentIndexChanged.connect(
            self._on_bond_length_mode_changed
        )
        self.bond_length_tolerance_value.valueChanged.connect(self._on_settings_changed)
        self.minimum_observations_per_type.valueChanged.connect(
            self._on_settings_changed
        )
        self.include_small_ordered_islands.toggled.connect(self._on_settings_changed)
        self.exclude_bond_length_heterogeneity_qc.toggled.connect(
            self._on_settings_changed
        )
        self.classify_button.clicked.connect(self._request_classification)

        self.set_settings(M6DomainTypeClassificationSettings(), notify=False)

    def settings_widgets(self) -> tuple[QWidget, ...]:
        return (
            self.orientation_tolerance_deg,
            self.bond_length_tolerance_mode,
            self.bond_length_tolerance_value,
            self.minimum_observations_per_type,
            self.include_small_ordered_islands,
            self.exclude_bond_length_heterogeneity_qc,
        )

    def settings(self) -> M6DomainTypeClassificationSettings:
        return M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=self.orientation_tolerance_deg.value(),
            bond_length_tolerance_mode=str(
                self.bond_length_tolerance_mode.currentData()
            ),
            bond_length_tolerance_value=self.bond_length_tolerance_value.value(),
            minimum_observations_per_type=(
                self.minimum_observations_per_type.value()
            ),
            include_small_ordered_islands=(
                self.include_small_ordered_islands.isChecked()
            ),
            exclude_bond_length_heterogeneity_qc=(
                self.exclude_bond_length_heterogeneity_qc.isChecked()
            ),
        )

    def set_settings(
        self,
        settings: M6DomainTypeClassificationSettings,
        *,
        notify: bool = True,
    ) -> None:
        if not isinstance(settings, M6DomainTypeClassificationSettings):
            raise TypeError("settings must be domain type classification settings.")
        widgets = self.settings_widgets()
        blocked = tuple(widget.blockSignals(True) for widget in widgets)
        try:
            self.orientation_tolerance_deg.setValue(
                settings.orientation_tolerance_deg
            )
            mode_index = self.bond_length_tolerance_mode.findData(
                settings.bond_length_tolerance_mode
            )
            self.bond_length_tolerance_mode.setCurrentIndex(mode_index)
            self.bond_length_tolerance_value.setValue(
                settings.bond_length_tolerance_value
            )
            self.minimum_observations_per_type.setValue(
                settings.minimum_observations_per_type
            )
            self.include_small_ordered_islands.setChecked(
                settings.include_small_ordered_islands
            )
            self.exclude_bond_length_heterogeneity_qc.setChecked(
                settings.exclude_bond_length_heterogeneity_qc
            )
        finally:
            for widget, previous in zip(widgets, blocked):
                widget.blockSignals(previous)
        self._update_bond_length_unit()
        self._validate_settings()
        if notify:
            self.settings_changed.emit(settings)

    def validation_message(self) -> str:
        return self.validation_label.text()

    def status_text(self) -> str:
        return self.status_label.text()

    def outcome(self) -> M6DomainTypeAnalysisOutcome | None:
        if self._store_state is None:
            return None
        return self._store_state.outcome

    def set_analysis_source(
        self,
        source: M6DomainTypeAnalysisSource | None,
    ) -> None:
        if source is not None and not isinstance(source, M6DomainTypeAnalysisSource):
            raise TypeError("source must be an M6 domain type analysis source or None.")
        self._source = source
        self._refresh_state()

    def set_store_state(
        self,
        state: M6DomainTypeAnalysisStoreState | None,
    ) -> None:
        if state is not None and not isinstance(state, M6DomainTypeAnalysisStoreState):
            raise TypeError("state must be an M6 domain type store state or None.")
        self._store_state = state
        self._error_message = None
        self._status_override = None
        self._refresh_state()

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        if self._running:
            self._error_message = None
            self._status_override = None
            self._progress = None
        self._refresh_state()

    def set_progress(self, progress: M6DomainTypeAnalysisProgress) -> None:
        if not isinstance(progress, M6DomainTypeAnalysisProgress):
            raise TypeError("progress must be M6 domain type analysis progress.")
        self._progress = progress
        self._refresh_state()

    def set_error(self, message: str) -> None:
        self._error_message = str(message).strip() or "Unknown classification error."
        self._status_override = None
        self._refresh_state()

    def set_canceled(self) -> None:
        self._status_override = "Structural type classification was canceled."
        self._refresh_state()

    def _on_bond_length_mode_changed(self, _index: int) -> None:
        self._update_bond_length_unit()
        self._on_settings_changed()

    def _update_bond_length_unit(self) -> None:
        suffix = (
            " nm"
            if self.bond_length_tolerance_mode.currentData() == "absolute_nm"
            else " %"
        )
        self.bond_length_tolerance_value.setSuffix(suffix)

    def _on_settings_changed(self, _value=None) -> None:
        self._error_message = None
        self._status_override = None
        settings = self._validate_settings()
        self.settings_changed.emit(settings)

    def _validate_settings(self) -> M6DomainTypeClassificationSettings | None:
        try:
            settings = self.settings()
        except (TypeError, ValueError) as exc:
            self._validation_error = str(exc)
            self.validation_label.setText(str(exc))
            self._refresh_state()
            return None
        self._validation_error = None
        self.validation_label.setText("")
        self._refresh_state()
        return settings

    def _request_classification(self) -> None:
        settings = self._validate_settings()
        if settings is None or self._source is None or self._running:
            return
        self.classification_requested.emit(settings)

    def _refresh_state(self) -> None:
        presentation_state = self._presentation_state()
        valid = self._validation_error is None
        self.classify_button.setEnabled(
            self._source is not None and valid and not self._running
        )
        current = presentation_state == "current"
        self.classify_button.setText(
            "Recalculate Types" if current else "Classify Types"
        )
        if presentation_state == "running":
            if self._progress is None:
                status = "Starting structural type classification..."
            else:
                status = (
                    f"Phase {self._progress.phase_number}/"
                    f"{self._progress.total_phase_count}: {self._progress.message}"
                )
        elif presentation_state == "error":
            status = f"Classification error: {self._error_message}"
        elif presentation_state == "override":
            status = self._status_override
        elif presentation_state == "missing_source":
            status = "Run/Recalculate M6 for the active range mode before classifying types."
        elif presentation_state == "invalid_settings":
            status = "Correct the classification settings before running."
        elif presentation_state == "out_of_date":
            status = (
                "Structural type result is out of date: "
                f"{self._store_state.invalidation_reason}. Reclassify types."
            )
        elif current:
            status = self._completed_status(self._store_state.outcome)
        else:
            status = (
                f"Ready to classify shared structural types. {self._frame_status()}"
            )
        self.status_label.setText(status)
        self._refresh_results(presentation_state)

    def _presentation_state(self) -> _PanelPresentationState:
        if self._running:
            return "running"
        if self._error_message is not None:
            return "error"
        if self._status_override is not None:
            return "override"
        if self._source is None:
            return "missing_source"
        if self._validation_error is not None:
            return "invalid_settings"
        if self._store_state is not None:
            if self._store_state.status == "out_of_date":
                return "out_of_date"
            if (
                self._store_state.status == "current"
                and self._store_state.outcome is not None
            ):
                return "current"
        return "ready"

    def _refresh_results(self, presentation_state: _PanelPresentationState) -> None:
        if presentation_state == "running":
            message = "Structural type classification is running."
        elif presentation_state == "error":
            message = f"Classification failed: {self._error_message}"
        elif presentation_state == "override":
            message = self._status_override
        elif presentation_state == "missing_source":
            message = "Run/Recalculate M6 before showing domain types."
        elif presentation_state == "invalid_settings":
            message = "Correct the classification settings before showing results."
        elif presentation_state == "out_of_date":
            message = "Domain type result is out of date. Reclassify types."
        elif presentation_state == "current":
            outcome = self._store_state.outcome
            if outcome.table_result is not None:
                self.results_table.set_table_result(outcome.table_result)
                self.plots_panel.set_outcome(outcome)
                return
            message = outcome.status_message
        else:
            message = "Classify domain types to show the result table."
        self.results_table.set_table_result(None, empty_message=message)
        self.plots_panel.set_outcome(None, empty_message=message)

    def _completed_status(self, outcome: M6DomainTypeAnalysisOutcome) -> str:
        classification = outcome.classification
        classified = 0 if classification is None else classification.classified_observation_count
        unclassified = (
            0 if classification is None else classification.unclassified_observation_count
        )
        return (
            f"{outcome.status_message} Classified observations: {classified} | "
            f"Unclassified: {unclassified} | {self._frame_status()} "
            "Structural types aggregate independent frames; domains are not tracked."
        )

    def _frame_status(self) -> str:
        if self._source is None:
            return "Available M6 frames: none."
        ranges = []
        for named_range in self._source.named_ranges:
            results = named_range.analysis.frame_results
            available = sum(
                result.m6_orientation_availability_status == "available"
                for result in results
            )
            ranges.append(f"{named_range.name}: {available}/{len(results)}")
        return "Available M6 frames: " + "; ".join(ranges) + "."
