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

    ALL_TRACKS_KEY = "__all_tracks__"
    UNIT_PIXELS = "px"
    UNIT_NANOMETERS = "nm"

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
        self.cmb_units = QComboBox(self)
        self.lbl_summary = QLabel("No results available", self)
        self.lbl_summary.setWordWrap(True)
        controls_layout.addRow("Track", self.cmb_tracks)
        controls_layout.addRow("Units", self.cmb_units)
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
        self.cmb_units.currentIndexChanged.connect(self._on_units_changed)
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
            if self._tracks:
                self.cmb_tracks.addItem("All tracks", self.ALL_TRACKS_KEY)
            for track in self._tracks:
                self.cmb_tracks.addItem(track.label or f"Track {track.track_id}", track.track_id)
            self._populate_units_selector()
            self.set_selected_track_id(selected_track_id)
            if self.cmb_tracks.count() > 0 and self.cmb_tracks.currentIndex() < 0:
                self.cmb_tracks.setCurrentIndex(0)
        finally:
            self._updating_selection = False
        self._refresh_plots()

    def current_track_id(self) -> int | None:
        if self.cmb_tracks.count() == 0:
            return None
        track_key = self.cmb_tracks.currentData(Qt.ItemDataRole.UserRole)
        return track_key if isinstance(track_key, int) else None

    def set_selected_track_id(self, track_id: int | None) -> None:
        if self.cmb_tracks.count() == 0:
            self.cmb_tracks.setCurrentIndex(-1)
            return
        if track_id is None:
            all_tracks_index = self._index_for_track_key(self.ALL_TRACKS_KEY)
            self.cmb_tracks.setCurrentIndex(all_tracks_index)
            return
        for index in range(self.cmb_tracks.count()):
            if self.cmb_tracks.itemData(index, Qt.ItemDataRole.UserRole) == track_id:
                self.cmb_tracks.setCurrentIndex(index)
                return
        all_tracks_index = self._index_for_track_key(self.ALL_TRACKS_KEY)
        self.cmb_tracks.setCurrentIndex(all_tracks_index)

    def _on_track_changed(self, _index: int) -> None:
        self._refresh_plots()
        if self._updating_selection:
            return
        self.track_selected.emit(self.current_track_id())

    def _on_units_changed(self, _index: int) -> None:
        self._refresh_plots()

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
        self.btn_export.setEnabled(self._has_exportable_results())
        if self._sequence is None:
            self._set_empty_state()
            return

        track_key = self._current_track_key()
        if track_key == self.ALL_TRACKS_KEY:
            metric_rows = self._aggregate_metric_rows()
        else:
            track = self._current_track()
            if track is None:
                self._set_empty_state()
                return
            metric_rows = list(self._metric_rows(track))

        metric_rows = self._filter_metric_rows_for_unit(metric_rows)
        if not metric_rows:
            self._clear_plots()
            if track_key == self.ALL_TRACKS_KEY:
                self.lbl_summary.setText("All tracks | no measured frames yet")
            else:
                track = self._current_track()
                self.lbl_summary.setText(
                    f"{track.label or f'Track {track.track_id}'} | no measured frames yet"
                )
            return

        self._update_plot_labels()
        x = np.asarray([frame_index + 1 for frame_index, _metrics in metric_rows], dtype=np.float32)
        if self._current_unit_mode() == self.UNIT_NANOMETERS:
            area = np.asarray([metrics.area_nm2 for _frame_index, metrics in metric_rows], dtype=np.float32)
            perimeter = np.asarray([metrics.perimeter_nm for _frame_index, metrics in metric_rows], dtype=np.float32)
        else:
            area = np.asarray([metrics.area_px for _frame_index, metrics in metric_rows], dtype=np.float32)
            perimeter = np.asarray([metrics.perimeter_px for _frame_index, metrics in metric_rows], dtype=np.float32)
        intensity_sum = np.asarray([metrics.intensity_sum for _frame_index, metrics in metric_rows], dtype=np.float32)
        intensity_mean = np.asarray([metrics.intensity_mean for _frame_index, metrics in metric_rows], dtype=np.float32)
        intensity_max = np.asarray([metrics.intensity_max for _frame_index, metrics in metric_rows], dtype=np.float32)

        self._plot_single_series(self.plot_area, x, area, pen="#1f77b4", symbol="o")
        self._plot_single_series(self.plot_perimeter, x, perimeter, pen="#2ca02c", symbol="o")
        self._plot_intensity_series(x, intensity_sum, intensity_mean, intensity_max)

        if track_key == self.ALL_TRACKS_KEY:
            measured_track_frames = sum(1 for track in self._tracks for _ in self._metric_rows(track))
            self.lbl_summary.setText(
                f"All tracks | measured frames: {len(metric_rows)} / {self._sequence.frame_count} | track-frames: {measured_track_frames}"
            )
        else:
            track = self._current_track()
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

    def _aggregate_metric_rows(self) -> list[tuple[int, object]]:
        grouped: dict[int, list[object]] = {}
        for track in self._tracks:
            for frame_index, metrics in self._metric_rows(track):
                grouped.setdefault(frame_index, []).append(metrics)
        aggregated_rows = []
        for frame_index in sorted(grouped):
            aggregated_rows.append((frame_index, self._aggregate_metrics(grouped[frame_index])))
        return aggregated_rows

    def _aggregate_metrics(self, metrics_list: list[object]) -> object:
        total_area_px = sum(metrics.area_px for metrics in metrics_list)
        total_perimeter_px = sum(metrics.perimeter_px for metrics in metrics_list)
        total_intensity_sum = sum(metrics.intensity_sum for metrics in metrics_list)
        total_area_nm2_values = [metrics.area_nm2 for metrics in metrics_list if metrics.area_nm2 is not None]
        total_perimeter_nm_values = [metrics.perimeter_nm for metrics in metrics_list if metrics.perimeter_nm is not None]

        from nanotrack.core import ParticleMetrics

        return ParticleMetrics(
            area_px=total_area_px,
            perimeter_px=total_perimeter_px,
            area_nm2=sum(total_area_nm2_values) if len(total_area_nm2_values) == len(metrics_list) else None,
            perimeter_nm=sum(total_perimeter_nm_values) if len(total_perimeter_nm_values) == len(metrics_list) else None,
            intensity_sum=total_intensity_sum,
            intensity_mean=(total_intensity_sum / total_area_px) if total_area_px > 0 else None,
            intensity_max=max(metrics.intensity_max for metrics in metrics_list),
        )

    def _filter_metric_rows_for_unit(self, metric_rows: list[tuple[int, object]]) -> list[tuple[int, object]]:
        if self._current_unit_mode() != self.UNIT_NANOMETERS:
            return metric_rows
        return [
            (frame_index, metrics)
            for frame_index, metrics in metric_rows
            if metrics.area_nm2 is not None and metrics.perimeter_nm is not None
        ]

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

    def _current_track_key(self) -> object:
        if self.cmb_tracks.count() == 0:
            return None
        return self.cmb_tracks.currentData(Qt.ItemDataRole.UserRole)

    def _current_unit_mode(self) -> str:
        if self.cmb_units.count() == 0:
            return self.UNIT_PIXELS
        return str(self.cmb_units.currentData(Qt.ItemDataRole.UserRole))

    def _index_for_track_key(self, track_key: object) -> int:
        for index in range(self.cmb_tracks.count()):
            if self.cmb_tracks.itemData(index, Qt.ItemDataRole.UserRole) == track_key:
                return index
        return -1

    def _populate_units_selector(self) -> None:
        current_unit = self._current_unit_mode()
        self.cmb_units.clear()
        self.cmb_units.addItem("Pixels", self.UNIT_PIXELS)
        if self._sequence is not None:
            pixel_size_x_nm, pixel_size_y_nm = self._sequence.metadata.get_pixel_size_nm()
            if pixel_size_x_nm is not None and pixel_size_y_nm is not None:
                self.cmb_units.addItem("Nanometers", self.UNIT_NANOMETERS)
        for index in range(self.cmb_units.count()):
            if self.cmb_units.itemData(index, Qt.ItemDataRole.UserRole) == current_unit:
                self.cmb_units.setCurrentIndex(index)
                return
        self.cmb_units.setCurrentIndex(0)

    def _update_plot_labels(self) -> None:
        if self._current_unit_mode() == self.UNIT_NANOMETERS:
            self.plot_area.setLabel("left", "Area [nm²]")
            self.plot_perimeter.setLabel("left", "Perimeter / Obwód [nm]")
        else:
            self.plot_area.setLabel("left", "Area [px]")
            self.plot_perimeter.setLabel("left", "Perimeter / Obwód [px]")

    def _has_exportable_results(self) -> bool:
        return any(True for track in self._tracks for _ in self._metric_rows(track))

    def _set_empty_state(self) -> None:
        self._clear_plots()
        self._update_plot_labels()
        self.btn_export.setEnabled(False)
        if self._tracks:
            self.lbl_summary.setText("Select a track to inspect measured results")
        else:
            self.lbl_summary.setText("No results available")
