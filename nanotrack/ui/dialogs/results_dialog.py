from __future__ import annotations

from typing import Iterable

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from nanotrack.analysis import compute_particle_metrics
from nanotrack.core import ParticleMetrics
from nanotrack.core import ParticleTrack, STMSequence
from nanotrack.persistence import export_results_csv


class TrackResultsDialog(QDialog):
    """Quantitative review window for per-track measurements."""

    ALL_TRACKS_KEY = "__all_tracks__"
    UNIT_PIXELS = "px"
    UNIT_NANOMETERS = "nm"

    track_selected = pyqtSignal(object)
    track_delete_requested = pyqtSignal(int)

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
        self.chk_exclude_boundary_pixels = QCheckBox("Boundary correction", self)
        self.chk_exclude_boundary_pixels.setToolTip(
            "Recompute displayed plots from stored masks with a configurable boundary-pixel weight. "
            "Saved annotations and exports are not modified."
        )
        self.spn_boundary_pixel_weight = QDoubleSpinBox(self)
        self.spn_boundary_pixel_weight.setRange(0.0, 1.0)
        self.spn_boundary_pixel_weight.setDecimals(2)
        self.spn_boundary_pixel_weight.setSingleStep(0.1)
        self.spn_boundary_pixel_weight.setValue(0.5)
        self.spn_boundary_pixel_weight.setToolTip(
            "Weight assigned to pixels on the mask boundary when boundary correction is enabled. "
            "0.00 excludes boundary pixels, 0.50 half-counts them, 1.00 keeps the original area."
        )
        self.lbl_summary = QLabel("No results available", self)
        self.lbl_summary.setWordWrap(True)
        controls_layout.addRow("Track", self.cmb_tracks)
        controls_layout.addRow("Units", self.cmb_units)
        controls_layout.addRow("Metrics", self.chk_exclude_boundary_pixels)
        controls_layout.addRow("Boundary weight", self.spn_boundary_pixel_weight)
        controls_layout.addRow("Summary", self.lbl_summary)
        layout.addWidget(controls, 0)

        self.plot_area = self._create_plot_widget("Area", "Area [px]")
        self.plot_perimeter = self._create_plot_widget("Perimeter", "Perimeter [px]")
        self.plot_coverage = self._create_plot_widget("Surface Coverage", "Coverage [% of original frame]")
        layout.addWidget(self.plot_area, 1)
        layout.addWidget(self.plot_perimeter, 1)
        layout.addWidget(self.plot_coverage, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_delete = QPushButton("Delete Track", self)
        self.btn_export = QPushButton("Export Results...", self)
        button_row.addWidget(self.btn_delete)
        button_row.addWidget(self.btn_export)
        layout.addLayout(button_row)

        self.cmb_tracks.currentIndexChanged.connect(self._on_track_changed)
        self.cmb_units.currentIndexChanged.connect(self._on_units_changed)
        self.chk_exclude_boundary_pixels.stateChanged.connect(self._on_exclude_boundary_pixels_changed)
        self.spn_boundary_pixel_weight.valueChanged.connect(self._on_boundary_pixel_weight_changed)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self._sync_boundary_weight_state()
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

    def _on_exclude_boundary_pixels_changed(self, _state: int) -> None:
        self._sync_boundary_weight_state()
        self._refresh_plots()

    def _on_boundary_pixel_weight_changed(self, _value: float) -> None:
        self._refresh_plots()

    def _on_delete_clicked(self) -> None:
        track_id = self.current_track_id()
        if track_id is None:
            return
        self.track_delete_requested.emit(track_id)

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
        self.btn_delete.setEnabled(self.current_track_id() is not None)
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
        coverage_percent = self._coverage_percent_for_rows(metric_rows)

        self._plot_single_series(self.plot_area, x, area, pen="#1f77b4", symbol="o")
        self._plot_single_series(self.plot_perimeter, x, perimeter, pen="#2ca02c", symbol="o")
        self._plot_single_series(self.plot_coverage, x, coverage_percent, pen="#d62728", symbol="o")

        if track_key == self.ALL_TRACKS_KEY:
            measured_track_frames = sum(1 for track in self._tracks for _ in self._metric_rows(track))
            source_suffix = self._source_views_summary(self._tracks)
            boundary_suffix = self._boundary_exclusion_summary_suffix()
            self.lbl_summary.setText(
                f"All tracks | measured frames: {len(metric_rows)} / {self._sequence.frame_count} | "
                f"track-frames: {measured_track_frames}{source_suffix}{boundary_suffix}"
            )
        else:
            track = self._current_track()
            source_suffix = self._source_views_summary([] if track is None else [track])
            boundary_suffix = self._boundary_exclusion_summary_suffix()
            self.lbl_summary.setText(
                f"{track.label or f'Track {track.track_id}'} | "
                f"measured frames: {len(metric_rows)} / {self._sequence.frame_count}{source_suffix}{boundary_suffix}"
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

    def _coverage_percent_for_rows(self, metric_rows: list[tuple[int, object]]) -> np.ndarray:
        original_frame_area_px = self._original_frame_area_px()
        if original_frame_area_px <= 0:
            return np.zeros(len(metric_rows), dtype=np.float32)
        if self._current_track_key() == self.ALL_TRACKS_KEY:
            return self._all_tracks_coverage_percent(metric_rows, original_frame_area_px=original_frame_area_px)
        return np.asarray(
            [(metrics.area_px / original_frame_area_px) * 100.0 for _frame_index, metrics in metric_rows],
            dtype=np.float32,
        )

    def _all_tracks_coverage_percent(
        self,
        metric_rows: list[tuple[int, object]],
        *,
        original_frame_area_px: float,
    ) -> np.ndarray:
        coverage_values: list[float] = []
        for frame_index, aggregate_metrics in metric_rows:
            union_area_px = self._union_mask_area_px_for_frame(frame_index)
            area_px = aggregate_metrics.area_px if union_area_px is None else union_area_px
            coverage_values.append((float(area_px) / original_frame_area_px) * 100.0)
        return np.asarray(coverage_values, dtype=np.float32)

    def _union_mask_area_px_for_frame(self, frame_index: int) -> float | None:
        if self._sequence is None:
            return None
        frame_shape = tuple(self._sequence.frame_shape)
        union_mask = np.zeros(frame_shape, dtype=bool)
        measured_annotation_count = 0
        for track in self._tracks:
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            metrics = self._display_metrics_for_annotation(annotation)
            if metrics is None or not self._metrics_are_complete(metrics):
                continue
            measured_annotation_count += 1
            metric_weight_map = self._metric_weight_map_for_annotation(annotation)
            if metric_weight_map is None or metric_weight_map.shape != frame_shape:
                return None
            union_mask = np.maximum(union_mask, metric_weight_map)
        if measured_annotation_count == 0:
            return None
        return float(np.sum(union_mask))

    def _original_frame_area_px(self) -> float:
        if self._sequence is None:
            return 0.0
        pixels_x = int(self._sequence.metadata.pixels_x)
        pixels_y = int(self._sequence.metadata.pixels_y)
        if pixels_x > 0 and pixels_y > 0:
            return float(pixels_x * pixels_y)
        frame_height, frame_width = self._sequence.frame_shape
        return float(frame_width * frame_height)

    def _metric_rows(self, track: ParticleTrack) -> Iterable[tuple[int, object]]:
        for frame_index in track.frame_indices:
            if self._sequence is not None and self._sequence.is_frame_excluded(frame_index):
                continue
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            metrics = self._display_metrics_for_annotation(annotation)
            if metrics is None or not self._metrics_are_complete(metrics):
                continue
            yield frame_index, metrics

    def _annotation_has_complete_metrics(self, annotation) -> bool:
        return self._metrics_are_complete(annotation.metrics)

    def _metrics_are_complete(self, metrics) -> bool:
        return (
            metrics.area_px is not None
            and metrics.perimeter_px is not None
            and metrics.intensity_sum is not None
            and metrics.intensity_mean is not None
            and metrics.intensity_max is not None
        )

    def _display_metrics_for_annotation(self, annotation) -> ParticleMetrics | None:
        if self._exclude_boundary_pixels_enabled():
            metrics = self._boundary_adjusted_metrics_for_annotation(annotation)
            if metrics is not None:
                return metrics
        if not self._annotation_has_complete_metrics(annotation):
            return None
        return annotation.metrics

    def _boundary_adjusted_metrics_for_annotation(self, annotation) -> ParticleMetrics | None:
        if self._sequence is None:
            return None
        metric_weight_map = self._metric_weight_map_for_annotation(annotation)
        if metric_weight_map is None:
            return None
        if not np.any(metric_weight_map > 0.0):
            return self._zero_particle_metrics()
        return self._compute_weighted_particle_metrics(metric_weight_map, self._sequence.get_frame(annotation.frame_index))

    def _metric_mask_for_annotation(self, annotation) -> np.ndarray | None:
        metric_weight_map = self._metric_weight_map_for_annotation(annotation)
        if metric_weight_map is None:
            return None
        return metric_weight_map > 0.0

    def _metric_weight_map_for_annotation(self, annotation) -> np.ndarray | None:
        if self._sequence is None or annotation.mask is None:
            return None
        mask = np.asarray(annotation.mask, dtype=bool)
        if mask.shape != tuple(self._sequence.frame_shape):
            return None
        if not self._exclude_boundary_pixels_enabled():
            return mask.astype(np.float32, copy=False)
        interior = self._interior_mask(mask)
        boundary = mask & ~interior
        weight = self._boundary_pixel_weight()
        metric_weight_map = interior.astype(np.float32, copy=False)
        if weight > 0.0:
            metric_weight_map = metric_weight_map.copy()
            metric_weight_map[boundary] = np.float32(weight)
        return metric_weight_map

    def _exclude_boundary_pixels_enabled(self) -> bool:
        return bool(self.chk_exclude_boundary_pixels.isChecked())

    def _boundary_pixel_weight(self) -> float:
        if not self._exclude_boundary_pixels_enabled():
            return 1.0
        return float(self.spn_boundary_pixel_weight.value())

    def _sync_boundary_weight_state(self) -> None:
        self.spn_boundary_pixel_weight.setEnabled(self._exclude_boundary_pixels_enabled())

    def _interior_mask(self, mask: np.ndarray) -> np.ndarray:
        mask_bool = np.asarray(mask, dtype=bool)
        if mask_bool.ndim != 2 or not np.any(mask_bool):
            return np.zeros(mask_bool.shape, dtype=bool)

        height, width = mask_bool.shape
        padded = np.pad(mask_bool, 1, mode="constant", constant_values=False)
        interior = np.ones((height, width), dtype=bool)
        for row_offset in range(3):
            for col_offset in range(3):
                interior &= padded[row_offset : row_offset + height, col_offset : col_offset + width]
        return interior

    def _compute_weighted_particle_metrics(self, weight_map: np.ndarray, raw_frame: np.ndarray) -> ParticleMetrics:
        weights = np.asarray(weight_map, dtype=np.float32)
        raw_array = np.asarray(raw_frame, dtype=np.float32)
        if weights.shape != raw_array.shape:
            raise ValueError("weight_map and raw_frame must have the same shape.")

        support_mask = weights > 0.0
        area_px = float(np.sum(weights))
        if area_px <= 0.0 or not np.any(support_mask):
            return self._zero_particle_metrics()

        weighted_values = raw_array * weights
        intensity_sum = float(np.sum(weighted_values))
        area_nm2 = None
        perimeter_nm = None
        if self._sequence is not None:
            pixel_size_x_nm, pixel_size_y_nm = self._sequence.metadata.get_pixel_size_nm()
            if pixel_size_x_nm is not None and pixel_size_y_nm is not None:
                area_nm2 = float(area_px * pixel_size_x_nm * pixel_size_y_nm)
                perimeter_nm = compute_particle_metrics(
                    support_mask,
                    raw_array,
                    pixel_size_nm=(pixel_size_x_nm, pixel_size_y_nm),
                ).perimeter_nm

        support_metrics = compute_particle_metrics(support_mask, raw_array)
        return ParticleMetrics(
            area_px=area_px,
            perimeter_px=support_metrics.perimeter_px,
            area_nm2=area_nm2,
            perimeter_nm=perimeter_nm,
            intensity_sum=intensity_sum,
            intensity_mean=float(intensity_sum / area_px),
            intensity_max=float(np.max(raw_array[support_mask])),
        )

    def _zero_particle_metrics(self) -> ParticleMetrics:
        area_nm2 = None
        perimeter_nm = None
        if self._sequence is not None:
            pixel_size_x_nm, pixel_size_y_nm = self._sequence.metadata.get_pixel_size_nm()
            if pixel_size_x_nm is not None and pixel_size_y_nm is not None:
                area_nm2 = 0.0
                perimeter_nm = 0.0
        return ParticleMetrics(
            area_px=0.0,
            perimeter_px=0.0,
            area_nm2=area_nm2,
            perimeter_nm=perimeter_nm,
            intensity_sum=0.0,
            intensity_mean=0.0,
            intensity_max=0.0,
        )

    def _boundary_exclusion_summary_suffix(self) -> str:
        if not self._exclude_boundary_pixels_enabled():
            return ""
        return f" | boundary correction {self._boundary_pixel_weight():.2f}x"

    def _source_views_summary(self, tracks: list[ParticleTrack]) -> str:
        source_views: set[str] = set()
        for track in tracks:
            for frame_index in track.frame_indices:
                annotation = track.get_annotation(frame_index)
                if annotation is not None and annotation.source_view:
                    source_views.add(annotation.source_view)
        if not source_views:
            return ""
        return " | source views: " + ", ".join(sorted(source_views))

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
        self.plot_coverage.clear()

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
        self.plot_coverage.setLabel("left", "Coverage [% of original frame]")

    def _has_exportable_results(self) -> bool:
        return any(True for track in self._tracks for _ in self._metric_rows(track))

    def _set_empty_state(self) -> None:
        self._clear_plots()
        self._update_plot_labels()
        self.btn_export.setEnabled(False)
        self.btn_delete.setEnabled(False)
        if self._tracks:
            self.lbl_summary.setText("Select a track to inspect measured results")
        else:
            self.lbl_summary.setText("No results available")
