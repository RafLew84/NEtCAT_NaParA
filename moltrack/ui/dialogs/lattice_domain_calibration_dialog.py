"""Dialog for reviewed, asynchronous final M3/M6 calibration sweeps."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES,
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS,
    LatticeDomainCalibrationProgress,
    LatticeDomainCalibrationReport,
    LatticeDomainCalibrationSweepSettings,
    M6DomainTypeAnalysisSource,
    MolecularM6OrientationAnalysisSettings,
    load_lattice_domain_calibration_reference,
)
from moltrack.ui.lattice_domain_calibration_worker import (
    LatticeDomainCalibrationController,
    LatticeDomainCalibrationExecution,
)


class LatticeDomainCalibrationDialog(QDialog):
    """Configure a bounded sweep without applying or persisting its candidate."""

    running_changed = pyqtSignal(bool)

    def __init__(
        self,
        source: M6DomainTypeAnalysisSource,
        *,
        source_file_name: str,
        baseline_settings: MolecularM6OrientationAnalysisSettings,
        parent=None,
        controller: LatticeDomainCalibrationController | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(source, M6DomainTypeAnalysisSource):
            raise TypeError("source must be a completed M6 analysis source.")
        if not isinstance(
            baseline_settings,
            MolecularM6OrientationAnalysisSettings,
        ):
            raise TypeError("baseline_settings must be M6 settings.")
        self._source = source
        self._source_file_name = str(source_file_name)
        self._baseline_settings = baseline_settings
        self._controller = (
            controller
            if controller is not None
            else LatticeDomainCalibrationController(self)
        )
        self._report_paths: dict[str, Path] = {}
        self._last_report: LatticeDomainCalibrationReport | None = None
        self._parameter_checkboxes: dict[str, QCheckBox] = {}

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("Final M3/M6 Domain Calibration")
        self.resize(760, 760)
        layout = QVBoxLayout(self)

        files_group = QGroupBox("Experiment files", self)
        files_form = QFormLayout(files_group)
        self.reference_path = QLineEdit(files_group)
        reference_row = QHBoxLayout()
        reference_row.addWidget(self.reference_path, 1)
        self.reference_browse_button = QPushButton("Browse...", files_group)
        reference_row.addWidget(self.reference_browse_button)
        files_form.addRow("Reviewed reference JSON", reference_row)
        self.report_directory = QLineEdit(files_group)
        report_row = QHBoxLayout()
        report_row.addWidget(self.report_directory, 1)
        self.report_browse_button = QPushButton("Browse...", files_group)
        report_row.addWidget(self.report_browse_button)
        files_form.addRow("Report directory", report_row)
        layout.addWidget(files_group)

        parameters_group = QGroupBox("Sweep parameters", self)
        parameters_layout = QVBoxLayout(parameters_group)
        selection_row = QHBoxLayout()
        self.select_all_button = QPushButton("Select all", parameters_group)
        self.clear_all_button = QPushButton("Clear", parameters_group)
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.clear_all_button)
        selection_row.addStretch(1)
        parameters_layout.addLayout(selection_row)
        parameters_scroll = QScrollArea(parameters_group)
        parameters_scroll.setWidgetResizable(True)
        parameters_content = QWidget(parameters_scroll)
        parameters_content_layout = QVBoxLayout(parameters_content)
        default_parameters = {
            value.name
            for value in LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS
            if value.default_selected
        }
        for parameter_name in LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES:
            checkbox = QCheckBox(
                parameter_name.replace("_", " "),
                parameters_content,
            )
            checkbox.setChecked(parameter_name in default_parameters)
            checkbox.setProperty("parameter_name", parameter_name)
            self._parameter_checkboxes[parameter_name] = checkbox
            parameters_content_layout.addWidget(checkbox)
        parameters_content_layout.addStretch(1)
        parameters_scroll.setWidget(parameters_content)
        parameters_layout.addWidget(parameters_scroll, 1)
        self.first_shell_label = QLabel(
            (
                f"First shell fixed at {baseline_settings.first_shell_r_min_nm:g}-"
                f"{baseline_settings.first_shell_r_max_nm:g} nm"
            ),
            parameters_group,
        )
        parameters_layout.addWidget(self.first_shell_label)
        layout.addWidget(parameters_group, 1)

        limits_group = QGroupBox("Selection criteria", self)
        limits_form = QFormLayout(limits_group)
        self.max_multivariate_variants = QSpinBox(limits_group)
        self.max_multivariate_variants.setRange(0, 200)
        self.max_multivariate_variants.setValue(24)
        limits_form.addRow(
            "Maximum multidimensional variants",
            self.max_multivariate_variants,
        )
        self.max_stability_candidates = QSpinBox(limits_group)
        self.max_stability_candidates.setRange(1, 50)
        self.max_stability_candidates.setValue(5)
        limits_form.addRow(
            "Maximum stability candidates",
            self.max_stability_candidates,
        )
        self.minimum_stability_ari = QDoubleSpinBox(limits_group)
        self.minimum_stability_ari.setRange(0.0, 1.0)
        self.minimum_stability_ari.setDecimals(3)
        self.minimum_stability_ari.setSingleStep(0.01)
        self.minimum_stability_ari.setValue(0.8)
        limits_form.addRow("Minimum calibration ARI", self.minimum_stability_ari)
        self.minimum_holdout_ari = QDoubleSpinBox(limits_group)
        self.minimum_holdout_ari.setRange(0.0, 1.0)
        self.minimum_holdout_ari.setDecimals(3)
        self.minimum_holdout_ari.setSingleStep(0.01)
        self.minimum_holdout_ari.setValue(0.8)
        limits_form.addRow("Minimum holdout ARI", self.minimum_holdout_ari)
        self.minimum_first_shell_f1 = QDoubleSpinBox(limits_group)
        self.minimum_first_shell_f1.setRange(0.0, 1.0)
        self.minimum_first_shell_f1.setDecimals(3)
        self.minimum_first_shell_f1.setSingleStep(0.01)
        self.minimum_first_shell_f1.setValue(0.8)
        limits_form.addRow(
            "Minimum first-shell F1",
            self.minimum_first_shell_f1,
        )
        layout.addWidget(limits_group)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Ready.", self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.results_table = QTableWidget(0, 3, self)
        self.results_table.setHorizontalHeaderLabels(
            ("Parameter", "Stable minimum", "Stable maximum")
        )
        self.results_table.setVisible(False)
        layout.addWidget(self.results_table)

        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.run_button = QPushButton("Run Calibration", actions)
        actions.addButton(self.run_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.open_report_button = QPushButton("Open Report", actions)
        self.open_report_button.setEnabled(False)
        actions.addButton(
            self.open_report_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        layout.addWidget(actions)

        self.reference_browse_button.clicked.connect(self._browse_reference)
        self.report_browse_button.clicked.connect(self._browse_report_directory)
        self.select_all_button.clicked.connect(
            lambda: self._set_all_parameters(True)
        )
        self.clear_all_button.clicked.connect(
            lambda: self._set_all_parameters(False)
        )
        self.reference_path.textChanged.connect(self._refresh_run_enabled)
        self.report_directory.textChanged.connect(self._refresh_run_enabled)
        for checkbox in self._parameter_checkboxes.values():
            checkbox.toggled.connect(self._refresh_run_enabled)
        self.run_button.clicked.connect(self._run_or_cancel)
        self.open_report_button.clicked.connect(self._open_report)
        actions.rejected.connect(self.close)

        self._controller.progress.connect(self._on_progress)
        self._controller.finished.connect(self._on_finished)
        self._controller.failed.connect(self._on_failed)
        self._controller.canceled.connect(self._on_canceled)
        self._controller.running_changed.connect(self._on_running_changed)
        self._refresh_run_enabled()

    @property
    def last_report(self) -> LatticeDomainCalibrationReport | None:
        return self._last_report

    @property
    def is_running(self) -> bool:
        return self._controller.is_running

    def selected_parameter_names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES
            if self._parameter_checkboxes[name].isChecked()
        )

    def sweep_settings(self) -> LatticeDomainCalibrationSweepSettings:
        return LatticeDomainCalibrationSweepSettings(
            baseline_settings=self._baseline_settings,
            parameter_names=self.selected_parameter_names(),
            max_multivariate_variants=self.max_multivariate_variants.value(),
            max_stability_candidates=self.max_stability_candidates.value(),
            minimum_stability_ari=self.minimum_stability_ari.value(),
            minimum_holdout_ari=self.minimum_holdout_ari.value(),
            minimum_first_shell_f1=self.minimum_first_shell_f1.value(),
        )

    def _browse_reference(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open reviewed lattice-domain reference",
            self.reference_path.text(),
            "JSON files (*.json);;All files (*)",
        )
        if path:
            self.reference_path.setText(path)

    def _browse_report_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Choose lattice-domain calibration report directory",
            self.report_directory.text(),
        )
        if path:
            self.report_directory.setText(path)

    def _set_all_parameters(self, checked: bool) -> None:
        for checkbox in self._parameter_checkboxes.values():
            checkbox.setChecked(checked)

    def _run_or_cancel(self) -> None:
        if self._controller.is_running:
            self._controller.cancel()
            self.status_label.setText("Canceling calibration...")
            self.run_button.setEnabled(False)
            return
        try:
            reference = load_lattice_domain_calibration_reference(
                self.reference_path.text()
            )
            sweep = self.sweep_settings()
        except Exception as exc:
            self.status_label.setText(f"Configuration error: {exc}")
            return
        self._last_report = None
        self._report_paths = {}
        self.open_report_button.setEnabled(False)
        self.results_table.setVisible(False)
        started = self._controller.start(
            reference,
            sweep,
            self._source,
            source_file_name=self._source_file_name,
            report_directory=self.report_directory.text(),
        )
        if not started:
            self.status_label.setText("Calibration is already running.")

    def _on_progress(self, progress: LatticeDomainCalibrationProgress) -> None:
        self.progress_bar.setMaximum(max(1, progress.total_evaluations))
        self.progress_bar.setValue(progress.completed_evaluations)
        self.status_label.setText(
            f"{progress.phase}: {progress.variant_id}; "
            f"frame {progress.frame_index + 1}; "
            f"{progress.completed_evaluations}/{progress.total_evaluations}"
        )

    def _on_finished(self, execution: LatticeDomainCalibrationExecution) -> None:
        self._last_report = execution.report
        self._report_paths = execution.report_paths
        self.open_report_button.setEnabled("markdown" in self._report_paths)
        if execution.report.status == "no_stable_solution":
            message = "No stable segmentation found for the tested parameter range."
        elif execution.report.status == "stable_geometry_unverified":
            message = (
                "Stable segmentation candidate found, but manual first-shell "
                "validation for both M3 and M6 is missing or below threshold."
            )
        elif execution.report.holdout_passed:
            message = (
                "Stable candidate found and holdout threshold passed. Manual "
                "validation is required before creating a preset."
            )
        else:
            message = (
                "Stable calibration candidate found, but the holdout threshold "
                "did not pass. Review the report before using these settings."
            )
        self.status_label.setText(message)
        self._show_stable_ranges(execution.report)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Calibration error: {message}")

    def _on_canceled(self) -> None:
        self.status_label.setText("Calibration canceled.")

    def _on_running_changed(self, running: bool) -> None:
        self.run_button.setText("Cancel" if running else "Run Calibration")
        self.reference_path.setEnabled(not running)
        self.reference_browse_button.setEnabled(not running)
        self.report_directory.setEnabled(not running)
        self.report_browse_button.setEnabled(not running)
        self.max_multivariate_variants.setEnabled(not running)
        self.max_stability_candidates.setEnabled(not running)
        self.minimum_stability_ari.setEnabled(not running)
        self.minimum_holdout_ari.setEnabled(not running)
        self.minimum_first_shell_f1.setEnabled(not running)
        for checkbox in self._parameter_checkboxes.values():
            checkbox.setEnabled(not running)
        self._refresh_run_enabled()
        self.running_changed.emit(bool(running))

    def _refresh_run_enabled(self, _value=None) -> None:
        running = self._controller.is_running
        valid = (
            bool(self.reference_path.text().strip())
            and bool(self.report_directory.text().strip())
            and bool(self.selected_parameter_names())
        )
        self.run_button.setEnabled(running or valid)

    def _show_stable_ranges(self, report: LatticeDomainCalibrationReport) -> None:
        self.results_table.setRowCount(len(report.stable_ranges))
        for row, value in enumerate(report.stable_ranges):
            self.results_table.setItem(
                row,
                0,
                QTableWidgetItem(value.parameter_name),
            )
            self.results_table.setItem(
                row,
                1,
                QTableWidgetItem(str(value.minimum_value)),
            )
            self.results_table.setItem(
                row,
                2,
                QTableWidgetItem(str(value.maximum_value)),
            )
        self.results_table.resizeColumnsToContents()
        self.results_table.setVisible(True)

    def _open_report(self) -> None:
        path = self._report_paths.get("markdown")
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._controller.is_running:
            self._controller.cancel()
            self.status_label.setText("Canceling calibration...")
            event.ignore()
            return
        super().closeEvent(event)
