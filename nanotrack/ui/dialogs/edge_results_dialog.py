from __future__ import annotations

from typing import Iterable

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from nanotrack.core import EdgeMetrics, EdgeTrack, STMSequence
from nanotrack.persistence import export_edge_results_csv


class EdgeTrackResultsDialog(QDialog):
    """Quantitative review window for step-edge tracking metrics."""

    ALL_EDGE_TRACKS_KEY = "__all_edge_tracks__"
    UNIT_PIXELS = "px"
    UNIT_NANOMETERS = "nm"
    TREND_NONE = "__trend_none__"
    TREND_LENGTH = "length"
    TREND_ROUGHNESS = "roughness"
    TREND_WAVINESS = "waviness"
    TREND_CURVATURE_MEAN = "curvature_mean"
    TREND_CURVATURE_MAX = "curvature_max"

    track_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._edge_tracks: list[EdgeTrack] = []
        self._updating_selection = False
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("NanoTrack Edge Results")
        self.resize(1180, 980)

        layout = QVBoxLayout(self)

        controls = QGroupBox("Edge Results Review", self)
        controls_layout = QFormLayout(controls)
        self.cmb_tracks = QComboBox(self)
        self.cmb_units = QComboBox(self)
        self.cmb_trend = QComboBox(self)
        self.lbl_summary = QLabel("No edge results available", self)
        self.lbl_summary.setWordWrap(True)
        controls_layout.addRow("Edge Track", self.cmb_tracks)
        controls_layout.addRow("Units", self.cmb_units)
        controls_layout.addRow("Trend", self.cmb_trend)
        controls_layout.addRow("Summary", self.lbl_summary)
        layout.addWidget(controls, 0)

        self.plot_length = self._create_plot_widget("Step Length", "Length [px]")
        self.plot_roughness = self._create_plot_widget("RMS Roughness", "RMS Roughness [px]")
        self.plot_waviness = self._create_plot_widget("Waviness Amplitude", "Waviness [px]")
        self.plot_curvature = self._create_plot_widget("Curvature", "Curvature [1/px]")
        layout.addWidget(self.plot_length, 1)
        layout.addWidget(self.plot_roughness, 1)
        layout.addWidget(self.plot_waviness, 1)
        layout.addWidget(self.plot_curvature, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_export = QPushButton("Export Results...", self)
        button_row.addWidget(self.btn_export)
        layout.addLayout(button_row)

        self.cmb_tracks.currentIndexChanged.connect(self._on_track_changed)
        self.cmb_units.currentIndexChanged.connect(self._on_units_changed)
        self.cmb_trend.currentIndexChanged.connect(self._on_trend_changed)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self._populate_trend_selector()
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
        edge_tracks: list[EdgeTrack],
        *,
        selected_track_id: int | None = None,
    ) -> None:
        self._sequence = sequence
        self._edge_tracks = list(edge_tracks)
        self._updating_selection = True
        try:
            self.cmb_tracks.clear()
            if self._edge_tracks:
                self.cmb_tracks.addItem("All edge tracks", self.ALL_EDGE_TRACKS_KEY)
            for track in self._edge_tracks:
                self.cmb_tracks.addItem(track.label or f"Edge {track.edge_track_id}", track.edge_track_id)
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
            all_tracks_index = self._index_for_track_key(self.ALL_EDGE_TRACKS_KEY)
            self.cmb_tracks.setCurrentIndex(all_tracks_index)
            return
        for index in range(self.cmb_tracks.count()):
            if self.cmb_tracks.itemData(index, Qt.ItemDataRole.UserRole) == track_id:
                self.cmb_tracks.setCurrentIndex(index)
                return
        all_tracks_index = self._index_for_track_key(self.ALL_EDGE_TRACKS_KEY)
        self.cmb_tracks.setCurrentIndex(all_tracks_index)

    def _on_track_changed(self, _index: int) -> None:
        self._refresh_plots()
        if self._updating_selection:
            return
        self.track_selected.emit(self.current_track_id())

    def _on_units_changed(self, _index: int) -> None:
        self._refresh_plots()

    def _on_trend_changed(self, _index: int) -> None:
        self._refresh_plots()

    def export_results_to_path(self, base_path: str) -> dict[str, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        return export_edge_results_csv(base_path, self._sequence, self._edge_tracks)

    def _on_export_clicked(self) -> None:
        if not self._has_exportable_results():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export NanoTrack edge results",
            "nanotrack_edge_results.csv",
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
        if track_key == self.ALL_EDGE_TRACKS_KEY:
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
            if track_key == self.ALL_EDGE_TRACKS_KEY:
                self.lbl_summary.setText("All edge tracks | no measured frames yet")
            else:
                track = self._current_track()
                self.lbl_summary.setText(
                    f"{track.label or f'Edge {track.edge_track_id}'} | no measured frames yet"
                )
            return

        self._update_plot_labels()
        x = np.asarray([frame_index + 1 for frame_index, _metrics in metric_rows], dtype=np.float32)

        if self._current_unit_mode() == self.UNIT_NANOMETERS:
            length = np.asarray([metrics.length_nm for _frame_index, metrics in metric_rows], dtype=np.float32)
            roughness = np.asarray([metrics.roughness_rms_nm for _frame_index, metrics in metric_rows], dtype=np.float32)
            waviness = np.asarray(
                [metrics.waviness_amplitude_nm for _frame_index, metrics in metric_rows],
                dtype=np.float32,
            )
        else:
            length = np.asarray([metrics.length_px for _frame_index, metrics in metric_rows], dtype=np.float32)
            roughness = np.asarray([metrics.roughness_rms_px for _frame_index, metrics in metric_rows], dtype=np.float32)
            waviness = np.asarray(
                [metrics.waviness_amplitude_px for _frame_index, metrics in metric_rows],
                dtype=np.float32,
            )

        mean_curvature = np.asarray([metrics.mean_curvature for _frame_index, metrics in metric_rows], dtype=np.float32)
        max_curvature = np.asarray([metrics.max_curvature for _frame_index, metrics in metric_rows], dtype=np.float32)

        trend_key = self._current_trend_key()
        length_trend = self._compute_linear_trend(x, length) if trend_key == self.TREND_LENGTH else None
        roughness_trend = self._compute_linear_trend(x, roughness) if trend_key == self.TREND_ROUGHNESS else None
        waviness_trend = self._compute_linear_trend(x, waviness) if trend_key == self.TREND_WAVINESS else None
        mean_curvature_trend = (
            self._compute_linear_trend(x, mean_curvature)
            if trend_key == self.TREND_CURVATURE_MEAN
            else None
        )
        max_curvature_trend = (
            self._compute_linear_trend(x, max_curvature)
            if trend_key == self.TREND_CURVATURE_MAX
            else None
        )

        self._plot_single_series(
            self.plot_length,
            x,
            length,
            pen="#1f77b4",
            symbol="o",
            trend=length_trend,
        )
        self._plot_single_series(
            self.plot_roughness,
            x,
            roughness,
            pen="#d62728",
            symbol="o",
            trend=roughness_trend,
        )
        self._plot_single_series(
            self.plot_waviness,
            x,
            waviness,
            pen="#2ca02c",
            symbol="o",
            trend=waviness_trend,
        )
        self._plot_curvature_series(
            x,
            mean_curvature,
            max_curvature,
            mean_trend=mean_curvature_trend,
            max_trend=max_curvature_trend,
        )

        if track_key == self.ALL_EDGE_TRACKS_KEY:
            measured_track_frames = sum(1 for track in self._edge_tracks for _ in self._metric_rows(track))
            summary = (
                f"All edge tracks | measured frames: {len(metric_rows)} / {self._sequence.frame_count} | track-frames: {measured_track_frames}"
            )
        else:
            track = self._current_track()
            summary = (
                f"{track.label or f'Edge {track.edge_track_id}'} | measured frames: {len(metric_rows)} / {self._sequence.frame_count}"
            )
        self.lbl_summary.setText(summary + self._format_trend_summary(trend_key, length_trend, roughness_trend, waviness_trend, mean_curvature_trend, max_curvature_trend))

    def _plot_single_series(
        self,
        plot_widget: pg.PlotWidget,
        x: np.ndarray,
        y: np.ndarray,
        *,
        pen: str,
        symbol: str,
        trend: dict[str, float | np.ndarray] | None = None,
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
        if trend is None:
            return
        plot_widget.plot(
            x,
            np.asarray(trend["y"], dtype=np.float32),
            pen=pg.mkPen(pen, width=2, style=Qt.PenStyle.DashLine),
        )

    def _plot_curvature_series(
        self,
        x: np.ndarray,
        mean_curvature: np.ndarray,
        max_curvature: np.ndarray,
        *,
        mean_trend: dict[str, float | np.ndarray] | None = None,
        max_trend: dict[str, float | np.ndarray] | None = None,
    ) -> None:
        self.plot_curvature.clear()
        if self.plot_curvature.plotItem.legend is None:
            self.plot_curvature.addLegend(offset=(8, 8))
        self.plot_curvature.plot(
            x,
            mean_curvature,
            name="mean",
            pen=pg.mkPen("#9467bd", width=2),
            symbol="o",
            symbolSize=6,
            symbolBrush="#9467bd",
        )
        self.plot_curvature.plot(
            x,
            max_curvature,
            name="max",
            pen=pg.mkPen("#ff7f0e", width=2),
            symbol="t",
            symbolSize=7,
            symbolBrush="#ff7f0e",
        )
        if mean_trend is not None:
            self.plot_curvature.plot(
                x,
                np.asarray(mean_trend["y"], dtype=np.float32),
                name="mean trend",
                pen=pg.mkPen("#9467bd", width=2, style=Qt.PenStyle.DashLine),
            )
        if max_trend is not None:
            self.plot_curvature.plot(
                x,
                np.asarray(max_trend["y"], dtype=np.float32),
                name="max trend",
                pen=pg.mkPen("#ff7f0e", width=2, style=Qt.PenStyle.DashLine),
            )

    def _metric_rows(self, track: EdgeTrack) -> Iterable[tuple[int, EdgeMetrics]]:
        for frame_index in track.frame_indices:
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            metrics = annotation.metrics
            if (
                metrics.length_px is None
                or metrics.roughness_rms_px is None
                or metrics.mean_curvature is None
                or metrics.max_curvature is None
                or metrics.waviness_amplitude_px is None
            ):
                continue
            yield frame_index, metrics

    def _aggregate_metric_rows(self) -> list[tuple[int, EdgeMetrics]]:
        grouped: dict[int, list[EdgeMetrics]] = {}
        for track in self._edge_tracks:
            for frame_index, metrics in self._metric_rows(track):
                grouped.setdefault(frame_index, []).append(metrics)
        aggregated_rows = []
        for frame_index in sorted(grouped):
            aggregated_rows.append((frame_index, self._aggregate_metrics(grouped[frame_index])))
        return aggregated_rows

    def _aggregate_metrics(self, metrics_list: list[EdgeMetrics]) -> EdgeMetrics:
        def _mean(values: list[float | None]) -> float | None:
            available = [float(value) for value in values if value is not None]
            if not available:
                return None
            return float(np.mean(np.asarray(available, dtype=np.float64)))

        length_nm_values = [metrics.length_nm for metrics in metrics_list]
        roughness_nm_values = [metrics.roughness_rms_nm for metrics in metrics_list]
        waviness_nm_values = [metrics.waviness_amplitude_nm for metrics in metrics_list]

        return EdgeMetrics(
            length_px=float(sum(metrics.length_px for metrics in metrics_list if metrics.length_px is not None)),
            length_nm=(
                float(sum(value for value in length_nm_values if value is not None))
                if len([value for value in length_nm_values if value is not None]) == len(metrics_list)
                else None
            ),
            roughness_rms_px=_mean([metrics.roughness_rms_px for metrics in metrics_list]),
            roughness_rms_nm=(
                _mean(roughness_nm_values)
                if len([value for value in roughness_nm_values if value is not None]) == len(metrics_list)
                else None
            ),
            mean_curvature=_mean([metrics.mean_curvature for metrics in metrics_list]),
            max_curvature=float(max(metrics.max_curvature for metrics in metrics_list if metrics.max_curvature is not None)),
            waviness_amplitude_px=_mean([metrics.waviness_amplitude_px for metrics in metrics_list]),
            waviness_amplitude_nm=(
                _mean(waviness_nm_values)
                if len([value for value in waviness_nm_values if value is not None]) == len(metrics_list)
                else None
            ),
        )

    def _filter_metric_rows_for_unit(self, metric_rows: list[tuple[int, EdgeMetrics]]) -> list[tuple[int, EdgeMetrics]]:
        if self._current_unit_mode() != self.UNIT_NANOMETERS:
            return metric_rows
        return [
            (frame_index, metrics)
            for frame_index, metrics in metric_rows
            if metrics.length_nm is not None
            and metrics.roughness_rms_nm is not None
            and metrics.waviness_amplitude_nm is not None
        ]

    def _current_track(self) -> EdgeTrack | None:
        track_id = self.current_track_id()
        if track_id is None:
            return None
        for track in self._edge_tracks:
            if track.edge_track_id == track_id:
                return track
        return None

    def _clear_plots(self) -> None:
        self.plot_length.clear()
        self.plot_roughness.clear()
        self.plot_waviness.clear()
        self.plot_curvature.clear()

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

    def _populate_trend_selector(self) -> None:
        current_trend = self._current_trend_key()
        self.cmb_trend.clear()
        self.cmb_trend.addItem("No trend", self.TREND_NONE)
        self.cmb_trend.addItem("Length", self.TREND_LENGTH)
        self.cmb_trend.addItem("Roughness", self.TREND_ROUGHNESS)
        self.cmb_trend.addItem("Waviness", self.TREND_WAVINESS)
        self.cmb_trend.addItem("Curvature mean", self.TREND_CURVATURE_MEAN)
        self.cmb_trend.addItem("Curvature max", self.TREND_CURVATURE_MAX)
        for index in range(self.cmb_trend.count()):
            if self.cmb_trend.itemData(index, Qt.ItemDataRole.UserRole) == current_trend:
                self.cmb_trend.setCurrentIndex(index)
                return
        self.cmb_trend.setCurrentIndex(0)

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
            self.plot_length.setLabel("left", "Length [nm]")
            self.plot_roughness.setLabel("left", "RMS Roughness [nm]")
            self.plot_waviness.setLabel("left", "Waviness [nm]")
        else:
            self.plot_length.setLabel("left", "Length [px]")
            self.plot_roughness.setLabel("left", "RMS Roughness [px]")
            self.plot_waviness.setLabel("left", "Waviness [px]")
        self.plot_curvature.setLabel("left", "Curvature [1/px]")

    def _has_exportable_results(self) -> bool:
        return any(True for track in self._edge_tracks for _ in self._metric_rows(track))

    def _set_empty_state(self) -> None:
        self._clear_plots()
        self._update_plot_labels()
        self.btn_export.setEnabled(False)
        if self._edge_tracks:
            self.lbl_summary.setText("Select an edge track to inspect measured results")
        else:
            self.lbl_summary.setText("No edge results available")

    def _current_trend_key(self) -> str:
        if self.cmb_trend.count() == 0:
            return self.TREND_NONE
        return str(self.cmb_trend.currentData(Qt.ItemDataRole.UserRole))

    def _compute_linear_trend(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> dict[str, float | np.ndarray] | None:
        if x.size < 2 or y.size < 2:
            return None
        coefficients = np.polyfit(
            np.asarray(x, dtype=np.float64),
            np.asarray(y, dtype=np.float64),
            deg=1,
        )
        slope = float(coefficients[0])
        intercept = float(coefficients[1])
        return {
            "slope": slope,
            "intercept": intercept,
            "y": (slope * np.asarray(x, dtype=np.float64) + intercept).astype(np.float32),
        }

    def _format_trend_summary(
        self,
        trend_key: str,
        length_trend: dict[str, float | np.ndarray] | None,
        roughness_trend: dict[str, float | np.ndarray] | None,
        waviness_trend: dict[str, float | np.ndarray] | None,
        mean_curvature_trend: dict[str, float | np.ndarray] | None,
        max_curvature_trend: dict[str, float | np.ndarray] | None,
    ) -> str:
        trend_map = {
            self.TREND_LENGTH: ("Length", length_trend, self._current_length_unit_label()),
            self.TREND_ROUGHNESS: ("Roughness", roughness_trend, self._current_length_unit_label()),
            self.TREND_WAVINESS: ("Waviness", waviness_trend, self._current_length_unit_label()),
            self.TREND_CURVATURE_MEAN: ("Curvature mean", mean_curvature_trend, "1/px"),
            self.TREND_CURVATURE_MAX: ("Curvature max", max_curvature_trend, "1/px"),
        }
        trend_label, trend, unit_label = trend_map.get(trend_key, ("", None, ""))
        if trend is None:
            return ""
        slope = float(trend["slope"])
        return f" | trend: {trend_label} slope {slope:+.4f} {unit_label}/frame"

    def _current_length_unit_label(self) -> str:
        if self._current_unit_mode() == self.UNIT_NANOMETERS:
            return "nm"
        return "px"
