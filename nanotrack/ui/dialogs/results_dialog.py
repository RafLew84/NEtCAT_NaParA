from __future__ import annotations

from typing import Iterable

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from nanotrack.core import ParticleTrack, STMSequence
from nanotrack.persistence import export_results_csv


class TrackResultsDialog(QDialog):
    """Quantitative review window for per-track measurements."""

    track_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._tracks: list[ParticleTrack] = []
        self._updating_selection = False
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("NanoTrack Results")
        self.resize(1180, 860)

        layout = QVBoxLayout(self)

        controls = QGroupBox("Results Review", self)
        controls_layout = QFormLayout(controls)
        self.cmb_tracks = QComboBox(self)
        self.lbl_summary = QLabel("No results available", self)
        self.lbl_summary.setWordWrap(True)
        controls_layout.addRow("Track", self.cmb_tracks)
        controls_layout.addRow("Summary", self.lbl_summary)
        layout.addWidget(controls, 0)

        self.plot_area = self._create_plot_widget("Area", "Area [px]")
        self.plot_perimeter = self._create_plot_widget("Perimeter", "Perimeter [px]")
        self.plot_intensity = self._create_plot_widget("Intensity", "Intensity [raw a.u.]")
        layout.addWidget(self.plot_area, 1)
        layout.addWidget(self.plot_perimeter, 1)
        layout.addWidget(self.plot_intensity, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_export = QPushButton("Export Results...", self)
        button_row.addWidget(self.btn_export)
        layout.addLayout(button_row)

        self.cmb_tracks.currentIndexChanged.connect(self._on_track_changed)
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

    def set_context(
        self,
        sequence: STMSequence | None,
        tracks: list[ParticleTrack],
        *,
        selected_track_id: int | None = None,
    ) -> None:
        self._sequence = sequence
        self._tracks = list(tracks)
        self._updating_selection = True
        try:
            self.cmb_tracks.clear()
            for track in self._tracks:
                self.cmb_tracks.addItem(track.label or f"Track {track.track_id}", track.track_id)
            self.set_selected_track_id(selected_track_id)
            if self.cmb_tracks.count() > 0 and self.cmb_tracks.currentIndex() < 0:
                self.cmb_tracks.setCurrentIndex(0)
        finally:
            self._updating_selection = False
        self._refresh_plots()

    def current_track_id(self) -> int | None:
        if self.cmb_tracks.count() == 0:
            return None
        return self.cmb_tracks.currentData(Qt.ItemDataRole.UserRole)

    def set_selected_track_id(self, track_id: int | None) -> None:
        if track_id is None or self.cmb_tracks.count() == 0:
            self.cmb_tracks.setCurrentIndex(-1)
            return
        for index in range(self.cmb_tracks.count()):
            if self.cmb_tracks.itemData(index, Qt.ItemDataRole.UserRole) == track_id:
                self.cmb_tracks.setCurrentIndex(index)
                return
        self.cmb_tracks.setCurrentIndex(-1)

    def _on_track_changed(self, _index: int) -> None:
        self._refresh_plots()
        if self._updating_selection:
            return
        self.track_selected.emit(self.current_track_id())

    def export_results_to_path(self, base_path: str) -> dict[str, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        return export_results_csv(base_path, self._sequence, self._tracks)

    def _on_export_clicked(self) -> None:
        if not self._has_exportable_results():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export NanoTrack results",
            "nanotrack_results.csv",
            "CSV files (*.csv);;All files (*.*)",
        )
        if not path:
            return
        try:
            exported = self.export_results_to_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))
            return
        QMessageBox.information(
            self,
            "Export complete",
            "Saved:\n" + "\n".join(exported.values()),
        )

    def _refresh_plots(self) -> None:
        track = self._current_track()
        self.btn_export.setEnabled(self._has_exportable_results())
        if self._sequence is None or track is None:
            self._set_empty_state()
            return

        metric_rows = list(self._metric_rows(track))
        if not metric_rows:
            self._clear_plots()
            self.lbl_summary.setText(
                f"{track.label or f'Track {track.track_id}'} | no measured frames yet"
            )
            return

        x = np.asarray([frame_index + 1 for frame_index, _metrics in metric_rows], dtype=np.float32)
        area = np.asarray([metrics.area_px for _frame_index, metrics in metric_rows], dtype=np.float32)
        perimeter = np.asarray([metrics.perimeter_px for _frame_index, metrics in metric_rows], dtype=np.float32)
        intensity_sum = np.asarray([metrics.intensity_sum for _frame_index, metrics in metric_rows], dtype=np.float32)
        intensity_mean = np.asarray([metrics.intensity_mean for _frame_index, metrics in metric_rows], dtype=np.float32)
        intensity_max = np.asarray([metrics.intensity_max for _frame_index, metrics in metric_rows], dtype=np.float32)

        self._plot_single_series(self.plot_area, x, area, pen="#1f77b4", symbol="o")
        self._plot_single_series(self.plot_perimeter, x, perimeter, pen="#2ca02c", symbol="o")
        self._plot_intensity_series(x, intensity_sum, intensity_mean, intensity_max)

        self.lbl_summary.setText(
            f"{track.label or f'Track {track.track_id}'} | measured frames: {len(metric_rows)} / {self._sequence.frame_count}"
        )

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

    def _plot_intensity_series(
        self,
        x: np.ndarray,
        intensity_sum: np.ndarray,
        intensity_mean: np.ndarray,
        intensity_max: np.ndarray,
    ) -> None:
        self.plot_intensity.clear()
        self.plot_intensity.addLegend(offset=(8, 8))
        self.plot_intensity.plot(
            x,
            intensity_sum,
            name="sum",
            pen=pg.mkPen("#d62728", width=2),
            symbol="o",
            symbolSize=6,
            symbolBrush="#d62728",
        )
        self.plot_intensity.plot(
            x,
            intensity_mean,
            name="mean",
            pen=pg.mkPen("#ff7f0e", width=2),
            symbol="t",
            symbolSize=7,
            symbolBrush="#ff7f0e",
        )
        self.plot_intensity.plot(
            x,
            intensity_max,
            name="max",
            pen=pg.mkPen("#9467bd", width=2),
            symbol="s",
            symbolSize=6,
            symbolBrush="#9467bd",
        )

    def _metric_rows(self, track: ParticleTrack) -> Iterable[tuple[int, object]]:
        for frame_index in track.frame_indices:
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            metrics = annotation.metrics
            if (
                metrics.area_px is None
                or metrics.perimeter_px is None
                or metrics.intensity_sum is None
                or metrics.intensity_mean is None
                or metrics.intensity_max is None
            ):
                continue
            yield frame_index, metrics

    def _current_track(self) -> ParticleTrack | None:
        track_id = self.current_track_id()
        if track_id is None:
            return None
        for track in self._tracks:
            if track.track_id == track_id:
                return track
        return None

    def _clear_plots(self) -> None:
        self.plot_area.clear()
        self.plot_perimeter.clear()
        self.plot_intensity.clear()

    def _has_exportable_results(self) -> bool:
        return any(True for track in self._tracks for _ in self._metric_rows(track))

    def _set_empty_state(self) -> None:
        self._clear_plots()
        self.btn_export.setEnabled(False)
        if self._tracks:
            self.lbl_summary.setText("Select a track to inspect measured results")
        else:
            self.lbl_summary.setText("No results available")
