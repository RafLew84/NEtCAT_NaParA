from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, STMSequence
from nanotrack.persistence import export_registration_results_csv


class RegistrationResultsDialog(QDialog):
    """Review window for registration shifts and quality metrics."""

    HEADERS = [
        "Frame",
        "dx [px]",
        "dy [px]",
        "quality",
        "status",
        "method",
        "phase peak",
        "ECC",
        "inlier tiles",
        "tile residual",
        "flow MAD",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._result_set: RegistrationResultSet | None = None
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("NanoTrack Registration Results")
        self.resize(1180, 900)

        layout = QVBoxLayout(self)

        controls = QGroupBox("Registration Quality", self)
        controls_layout = QFormLayout(controls)
        self.lbl_summary = QLabel("No registration results available", self)
        self.lbl_summary.setWordWrap(True)
        self.lbl_settings = QLabel("-", self)
        self.lbl_settings.setWordWrap(True)
        controls_layout.addRow("Summary", self.lbl_summary)
        controls_layout.addRow("Settings", self.lbl_settings)
        layout.addWidget(controls, 0)

        self.plot_dx = self._create_plot_widget("Registration dx(t)", "dx [px]")
        self.plot_dy = self._create_plot_widget("Registration dy(t)", "dy [px]")
        self.plot_quality = self._create_plot_widget("Registration Quality", "quality")
        self.plot_quality.setYRange(0.0, 1.0, padding=0.05)
        layout.addWidget(self.plot_dx, 1)
        layout.addWidget(self.plot_dy, 1)
        layout.addWidget(self.plot_quality, 1)

        self.table_results = QTableWidget(self)
        self.table_results.setColumnCount(len(self.HEADERS))
        self.table_results.setHorizontalHeaderLabels(self.HEADERS)
        self.table_results.setAlternatingRowColors(True)
        self.table_results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_results.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_results.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_results, 2)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_export = QPushButton("Export CSV...", self)
        button_row.addWidget(self.btn_export)
        layout.addLayout(button_row)
        self.btn_export.clicked.connect(self._on_export_clicked)

        self._set_empty_state()

    def _create_plot_widget(self, title: str, y_label: str) -> pg.PlotWidget:
        plot = pg.PlotWidget(self)
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.setBackground("w")
        plot.setLabel("bottom", "Frame")
        plot.setLabel("left", y_label)
        plot.setTitle(title)
        return plot

    def set_context(self, sequence: STMSequence | None, result_set: RegistrationResultSet | None) -> None:
        self._sequence = sequence
        self._result_set = result_set
        self._refresh()

    def export_results_to_path(self, base_path: str) -> dict[str, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        if self._result_set is None:
            raise RuntimeError("No registration results available.")
        return export_registration_results_csv(base_path, self._sequence, self._result_set)

    def _refresh(self) -> None:
        if self._result_set is None:
            self._set_empty_state()
            return

        rows = [self._result_set.get_result(frame_index) for frame_index in self._result_set.frame_indices]
        results = [result for result in rows if result is not None]
        if not results:
            self._set_empty_state()
            return
        self.btn_export.setEnabled(self._has_exportable_results())

        x = np.asarray([result.frame_index + 1 for result in results], dtype=np.float32)
        dx = np.asarray([result.dx for result in results], dtype=np.float32)
        dy = np.asarray([result.dy for result in results], dtype=np.float32)
        quality = np.asarray([result.quality_score for result in results], dtype=np.float32)

        self._plot_single_series(self.plot_dx, x, dx, pen="#1f77b4", symbol="o")
        self._plot_single_series(self.plot_dy, x, dy, pen="#d62728", symbol="o")
        self._plot_single_series(self.plot_quality, x, quality, pen="#2ca02c", symbol="o")
        self.plot_quality.setYRange(0.0, 1.0, padding=0.05)
        self._populate_table(results)
        self._update_summary(results)
        self._update_settings_label()

    def _plot_single_series(
        self,
        plot_widget: pg.PlotWidget,
        x: np.ndarray,
        y: np.ndarray,
        *,
        pen: str,
        symbol: str,
    ) -> None:
        plot_widget.clear()
        plot_widget.plot(
            x,
            y,
            pen=pg.mkPen(pen, width=2),
            symbol=symbol,
            symbolSize=7,
            symbolBrush=pen,
        )

    def _populate_table(self, results: list[RegistrationFrameResult]) -> None:
        self.table_results.setRowCount(len(results))
        for row, result in enumerate(results):
            values = [
                str(result.frame_index + 1),
                f"{result.dx:.3f}",
                f"{result.dy:.3f}",
                f"{result.quality_score:.3f}",
                result.status,
                result.method,
                self._format_optional_float(result.phase_peak_ratio),
                self._format_optional_float(result.ecc_score),
                self._format_inlier_tiles(result),
                self._format_optional_float(result.median_tile_residual),
                self._format_optional_float(result.flow_mad),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_results.setItem(row, column, item)
        self.table_results.resizeColumnsToContents()

    def _update_summary(self, results: list[RegistrationFrameResult]) -> None:
        shifts = np.asarray([[result.dx, result.dy] for result in results], dtype=np.float64)
        max_shift = 0.0 if shifts.size == 0 else float(np.max(np.linalg.norm(shifts, axis=1)))
        min_quality = min(result.quality_score for result in results)
        status_counts = self._result_set.status_counts() if self._result_set is not None else {}
        status_parts = [
            f"{status}: {count}"
            for status, count in status_counts.items()
            if count
        ]
        sequence_count = "n/a" if self._sequence is None else str(self._sequence.frame_count)
        self.lbl_summary.setText(
            f"frames: {len(results)} / {sequence_count} | "
            f"max shift {max_shift:.2f}px | min quality {min_quality:.3f} | "
            + " | ".join(status_parts)
        )

    def _update_settings_label(self) -> None:
        if self._result_set is None:
            self.lbl_settings.setText("-")
            return
        settings = self._result_set.settings
        template = self._result_set.template_frame_indices
        template_text = "-" if template is None else ", ".join(str(index + 1) for index in template)
        self.lbl_settings.setText(
            f"backend: {settings.backend} | strategy: {settings.reference_strategy} | "
            f"view: {settings.registration_view} | reference frame: {self._result_set.reference_frame_index + 1} | "
            f"template frames: {template_text}"
        )

    def _set_empty_state(self) -> None:
        self._clear_plots()
        self.table_results.setRowCount(0)
        self.lbl_summary.setText("No registration results available")
        self.lbl_settings.setText("-")
        self.btn_export.setEnabled(False)

    def _on_export_clicked(self) -> None:
        if not self._has_exportable_results():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export NanoTrack registration results",
            "nanotrack_registration_results.csv",
            "CSV files (*.csv);;All files (*.*)",
        )
        if not path:
            return
        try:
            exported = self.export_results_to_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Registration export error", str(exc))
            return
        QMessageBox.information(
            self,
            "Export complete",
            "Saved:\n" + "\n".join(exported.values()),
        )

    def _clear_plots(self) -> None:
        self.plot_dx.clear()
        self.plot_dy.clear()
        self.plot_quality.clear()
        self.plot_quality.setYRange(0.0, 1.0, padding=0.05)

    @staticmethod
    def _format_optional_float(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{float(value):.3f}"

    @staticmethod
    def _format_inlier_tiles(result: RegistrationFrameResult) -> str:
        if result.num_inlier_tiles is None and result.num_total_tiles is None:
            return "-"
        if result.num_inlier_tiles is None:
            return f"-/{result.num_total_tiles}"
        if result.num_total_tiles is None:
            return f"{result.num_inlier_tiles}/-"
        return f"{result.num_inlier_tiles}/{result.num_total_tiles}"

    def _has_exportable_results(self) -> bool:
        return (
            self._sequence is not None
            and self._result_set is not None
            and self._result_set.result_count > 0
        )
