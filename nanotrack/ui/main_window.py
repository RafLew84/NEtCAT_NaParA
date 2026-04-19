from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSlider,
    QSplitter,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import ParticleTrack, STMSequence
from nanotrack.io import load_mpp_sequence
from nanotrack.processing import (
    run_bm3d_batch,
    run_bm3d_preview,
    run_horizontal_dropout_batch,
    run_horizontal_dropout_preview,
)
from nanotrack.ui.dialogs import Bm3dPreviewDialog
from nanotrack.ui.widgets import (
    PreprocessingActionsPanel,
    SequenceMetadataPanel,
    SequenceViewerWidget,
    TrackListPanel,
)


class NanoTrackMainWindow(QMainWindow):
    """Main window for MPP sequence browsing and navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._tracks: list[ParticleTrack] = []
        self._repair_frames: np.ndarray | None = None
        self._repair_params: dict[str, float | int | str] | None = None
        self._denoised_frames: np.ndarray | None = None
        self._denoised_sigma_factor: float | None = None
        self._show_denoised_in_viewer = False
        self._is_preprocessing = False
        self._preview_frame_index: int | None = None
        self._bm3d_preview_dialog: Bm3dPreviewDialog | None = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.setWindowTitle("NanoTrack")
        self.resize(1280, 860)

        self._build_actions()
        self._build_central_widget()
        self._update_navigation_enabled(False)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_open_mpp = toolbar.addAction("Open MPP...")
        self.action_open_mpp.setToolTip("Load an MPP sequence into NanoTrack")

    def _build_central_widget(self) -> None:
        central = QSplitter(Qt.Orientation.Horizontal, self)

        viewer_container = QWidget(self)
        layout = QVBoxLayout(viewer_container)

        self.viewer = SequenceViewerWidget(self)
        layout.addWidget(self.viewer, 1)

        self.lbl_frame = QLabel("Frame: - / -", self)
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_frame)

        self.slider_frame = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_frame.setTracking(True)
        layout.addWidget(self.slider_frame)

        nav_row = QWidget(self)
        nav_layout = QHBoxLayout(nav_row)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_prev = QPushButton("Previous Frame", self)
        self.spin_frame = QSpinBox(self)
        self.spin_frame.setPrefix("Frame ")
        self.btn_next = QPushButton("Next Frame", self)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.spin_frame)
        nav_layout.addWidget(self.btn_next)

        layout.addWidget(nav_row)

        sidebar = QWidget(self)
        sidebar_layout = QVBoxLayout(sidebar)
        self.metadata_panel = SequenceMetadataPanel(self)
        self.track_list_panel = TrackListPanel(self)
        self.preprocessing_panel = PreprocessingActionsPanel(self)
        sidebar_layout.addWidget(self.metadata_panel, 0)
        sidebar_layout.addWidget(self.track_list_panel, 1)
        sidebar_layout.addWidget(self.preprocessing_panel, 0)

        central.addWidget(viewer_container)
        central.addWidget(sidebar)
        central.setStretchFactor(0, 1)
        central.setStretchFactor(1, 0)
        central.setSizes([980, 300])
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.action_open_mpp.triggered.connect(self._on_open_mpp)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)
        self.spin_frame.valueChanged.connect(self._on_spin_frame_selected)
        self.btn_prev.clicked.connect(self._on_prev_frame)
        self.btn_next.clicked.connect(self._on_next_frame)
        self.preprocessing_panel.repair_preview_requested.connect(self._on_repair_preview_requested)
        self.preprocessing_panel.repair_apply_all_requested.connect(self._on_repair_apply_all_requested)
        self.preprocessing_panel.preview_requested.connect(self._on_bm3d_preview_requested)
        self.preprocessing_panel.apply_all_requested.connect(self._on_bm3d_apply_all_requested)
        self.preprocessing_panel.show_denoised_toggled.connect(self._on_show_denoised_toggled)

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)
        self.spin_frame.setEnabled(enabled)
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.preprocessing_panel.set_sequence_loaded(enabled)

    def _sync_navigation_controls(self) -> None:
        if self._sequence is None:
            self.lbl_frame.setText("Frame: - / -")
            self._update_navigation_enabled(False)
            self.metadata_panel.clear()
            return

        current = self._sequence.active_frame_index
        total = self._sequence.frame_count
        self._update_navigation_enabled(True)

        with QSignalBlocker(self.slider_frame):
            self.slider_frame.setRange(0, total - 1)
            self.slider_frame.setValue(current)

        with QSignalBlocker(self.spin_frame):
            self.spin_frame.setRange(1, total)
            self.spin_frame.setValue(current + 1)

        self.btn_prev.setEnabled(current > 0)
        self.btn_next.setEnabled(current < total - 1)
        self.lbl_frame.setText(f"Frame: {current + 1} / {total}")
        self.metadata_panel.set_sequence(self._sequence)

    def _show_current_frame(self, preserve_zoom: bool = True) -> None:
        if self._sequence is None:
            self.viewer.clear()
            self._reset_preview_state()
            self._sync_navigation_controls()
            return

        frame_override = None
        view_label = "Raw"
        if self._show_denoised_in_viewer:
            frame_override, view_label = self._current_viewer_override()

        self.viewer.show_frame(
            self._sequence.active_frame_index,
            preserve_zoom=preserve_zoom,
            frame_override=frame_override,
            view_label=view_label,
        )
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"{Path(self._sequence.source_path).name} | frame {self._sequence.active_frame_index + 1}/{self._sequence.frame_count}",
            3000,
        )

    def set_sequence(self, sequence: STMSequence) -> None:
        self._sequence = sequence
        self._clear_all_preprocessing_cache()
        self.viewer.set_sequence(sequence)
        self._reset_preview_state(close_dialog=True)
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"{Path(sequence.source_path).name} | frame {sequence.active_frame_index + 1}/{sequence.frame_count}",
            3000,
        )
        self.set_tracks([])

    def load_sequence_from_path(self, file_path: str) -> None:
        sequence = load_mpp_sequence(file_path)
        self.set_sequence(sequence)

    def current_sequence(self) -> STMSequence | None:
        return self._sequence

    def current_repair_frames(self) -> np.ndarray | None:
        return self._repair_frames

    def current_repaired_frame(self) -> np.ndarray | None:
        if self._repair_frames is None or self._sequence is None:
            return None
        return self._repair_frames[self._sequence.active_frame_index]

    def current_denoised_frames(self) -> np.ndarray | None:
        return self._denoised_frames

    def current_denoised_frame(self) -> np.ndarray | None:
        if self._denoised_frames is None or self._sequence is None:
            return None
        return self._denoised_frames[self._sequence.active_frame_index]

    def set_tracks(self, tracks: list[ParticleTrack]) -> None:
        self._tracks = list(tracks)
        self.track_list_panel.set_tracks(self._tracks)

    def current_tracks(self) -> list[ParticleTrack]:
        return list(self._tracks)

    def _set_active_frame(self, frame_index: int) -> None:
        if self._sequence is None:
            return
        if frame_index == self._sequence.active_frame_index:
            return
        self._sequence.set_active_frame(frame_index)
        self._reset_preview_state()
        self._show_current_frame(preserve_zoom=True)

    def _on_open_mpp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MPP sequence",
            "",
            "MPP files (*.mpp *.MPP);;All files (*.*)",
        )
        if not path:
            return

        try:
            self.load_sequence_from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", f"Cannot load MPP sequence:\n{path}\n\n{exc}")
            return

    def _on_frame_selected(self, frame_index: int) -> None:
        self._set_active_frame(frame_index)

    def _on_spin_frame_selected(self, spin_value: int) -> None:
        self._set_active_frame(spin_value - 1)

    def _on_prev_frame(self) -> None:
        if self._sequence is None:
            return
        self._set_active_frame(max(0, self._sequence.active_frame_index - 1))

    def _on_next_frame(self) -> None:
        if self._sequence is None:
            return
        self._set_active_frame(min(self._sequence.frame_count - 1, self._sequence.active_frame_index + 1))

    def _on_repair_preview_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing:
            return

        current_index = self._sequence.active_frame_index
        params = self.preprocessing_panel.repair_parameters()

        if self._has_matching_repair_cache(params):
            repaired = self.current_repaired_frame()
        else:
            try:
                repaired, _ = run_horizontal_dropout_preview(self._sequence.active_frame, **params)
            except Exception as exc:
                QMessageBox.critical(self, "Repair preview error", str(exc))
                self.preprocessing_panel.set_preview_status("Repair preview failed")
                return

        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        dialog = self._ensure_bm3d_preview_dialog()
        dialog.set_preview(
            self._sequence.active_frame,
            repaired,
            frame_index=current_index,
            frame_count=self._sequence.frame_count,
            scale_nm_per_px=(px_x, px_y),
            window_title="Horizontal Repair Preview",
            left_title="Original",
            left_meta="Raw frame",
            right_title="Repair",
            right_meta=(
                f"thr {params['threshold_sigma']:.1f}, "
                f"width {params['min_width_frac']*100:.1f}-{params['max_width_frac']*100:.1f}%"
            ),
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._preview_frame_index = current_index
        self.preprocessing_panel.set_preview_status(f"Repair preview ready for frame {current_index + 1}")
        self.statusBar().showMessage(f"Repair preview opened for frame {current_index + 1}.", 3000)

    def _on_bm3d_preview_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing:
            return

        current_index = self._sequence.active_frame_index
        sigma_factor = self.preprocessing_panel.bm3d_sigma_factor()
        input_frame = self._current_bm3d_input_frame()
        if input_frame is None:
            return

        if self._has_matching_denoised_cache(sigma_factor):
            denoised = self.current_denoised_frame()
        else:
            try:
                denoised = run_bm3d_preview(input_frame, sigma_factor=sigma_factor)
            except Exception as exc:
                QMessageBox.critical(self, "BM3D preview error", str(exc))
                self.preprocessing_panel.set_preview_status("BM3D preview failed")
                return

        left_title = "Original"
        left_meta = "Raw frame"
        if self._repair_frames is not None:
            left_title = "Repair input"
            left_meta = "Horizontal repair cache"

        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        dialog = self._ensure_bm3d_preview_dialog()
        dialog.set_preview(
            input_frame,
            denoised,
            frame_index=current_index,
            frame_count=self._sequence.frame_count,
            scale_nm_per_px=(px_x, px_y),
            window_title="BM3D Preview",
            left_title=left_title,
            left_meta=left_meta,
            right_title="BM3D",
            right_meta=f"Sigma factor: {sigma_factor:.2f}",
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._preview_frame_index = current_index
        self.preprocessing_panel.set_preview_status(f"BM3D preview ready for frame {current_index + 1}")
        self.statusBar().showMessage(f"BM3D preview opened for frame {current_index + 1}.", 3000)

    def _on_repair_apply_all_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing:
            return

        params = self.preprocessing_panel.repair_parameters()
        frame_count = self._sequence.frame_count
        progress = QProgressDialog("Applying horizontal repair to all frames...", "", 0, frame_count, self)
        progress.setWindowTitle("Horizontal Repair")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        progress.setValue(0)

        self._set_preprocessing_busy(True)
        self.preprocessing_panel.set_preview_status(f"Applying repair... 0/{frame_count}")
        self.statusBar().showMessage("Applying horizontal repair to all frames...", 0)

        def on_progress(processed: int, total: int) -> None:
            progress.setMaximum(total)
            progress.setValue(processed)
            self.preprocessing_panel.set_preview_status(f"Applying repair... {processed}/{total}")
            QApplication.processEvents()

        try:
            repair_frames = run_horizontal_dropout_batch(
                self._sequence.raw_frames,
                progress_callback=on_progress,
                **params,
            )
        except Exception as exc:
            self._clear_repair_cache()
            self._update_cached_preprocessing_availability()
            QMessageBox.critical(self, "Repair apply-all error", str(exc))
            self.preprocessing_panel.set_preview_status("Repair apply-all failed")
        else:
            self._repair_frames = repair_frames
            self._repair_params = dict(params)
            self._clear_denoised_cache()
            self._update_cached_preprocessing_availability()
            if self._show_denoised_in_viewer:
                self._show_current_frame(preserve_zoom=True)
            progress.setValue(frame_count)
            self.preprocessing_panel.set_preview_status(self._default_preprocessing_status())
            self.statusBar().showMessage(
                f"Horizontal repair applied to all {frame_count} frames.",
                3000,
            )
        finally:
            progress.close()
            self._set_preprocessing_busy(False)

    def _on_bm3d_apply_all_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing:
            return

        sigma_factor = self.preprocessing_panel.bm3d_sigma_factor()
        frame_count = self._sequence.frame_count
        progress = QProgressDialog("Applying BM3D to all frames...", "", 0, frame_count, self)
        progress.setWindowTitle("BM3D Processing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        progress.setValue(0)

        self._set_preprocessing_busy(True)
        self.preprocessing_panel.set_preview_status(f"Applying BM3D... 0/{frame_count}")
        self.statusBar().showMessage("Applying BM3D to all frames...", 0)

        def on_progress(processed: int, total: int) -> None:
            progress.setMaximum(total)
            progress.setValue(processed)
            self.preprocessing_panel.set_preview_status(f"Applying BM3D... {processed}/{total}")
            QApplication.processEvents()

        try:
            denoised_frames = run_bm3d_batch(
                self._current_bm3d_input_frames(),
                sigma_factor=sigma_factor,
                progress_callback=on_progress,
            )
        except Exception as exc:
            self._clear_denoised_cache()
            self._update_cached_preprocessing_availability()
            QMessageBox.critical(self, "BM3D apply-all error", str(exc))
            self.preprocessing_panel.set_preview_status("BM3D apply-all failed")
        else:
            self._denoised_frames = denoised_frames
            self._denoised_sigma_factor = sigma_factor
            self._update_cached_preprocessing_availability()
            if self._show_denoised_in_viewer:
                self._show_current_frame(preserve_zoom=True)
            progress.setValue(frame_count)
            self.preprocessing_panel.set_preview_status(self._default_preprocessing_status())
            self.statusBar().showMessage(
                f"BM3D applied to all {frame_count} frames.",
                3000,
            )
        finally:
            progress.close()
            self._set_preprocessing_busy(False)

    def _on_show_denoised_toggled(self, checked: bool) -> None:
        self._show_denoised_in_viewer = bool(checked and self._has_any_preprocessing_cache())
        if self._sequence is not None:
            self._show_current_frame(preserve_zoom=True)

    def _ensure_bm3d_preview_dialog(self) -> Bm3dPreviewDialog:
        if self._bm3d_preview_dialog is None:
            self._bm3d_preview_dialog = Bm3dPreviewDialog(self)
        return self._bm3d_preview_dialog

    def _set_preprocessing_busy(self, busy: bool) -> None:
        self._is_preprocessing = busy
        self.action_open_mpp.setEnabled(not busy)
        self.preprocessing_panel.set_processing(busy)
        if busy:
            self.slider_frame.setEnabled(False)
            self.spin_frame.setEnabled(False)
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            return

        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self._sync_navigation_controls()

    def _clear_denoised_cache(self) -> None:
        self._denoised_frames = None
        self._denoised_sigma_factor = None

    def _clear_repair_cache(self) -> None:
        self._repair_frames = None
        self._repair_params = None

    def _clear_all_preprocessing_cache(self) -> None:
        self._clear_repair_cache()
        self._clear_denoised_cache()
        self._show_denoised_in_viewer = False
        self.preprocessing_panel.set_cached_preprocessing_available(False)

    def _update_cached_preprocessing_availability(self) -> None:
        self.preprocessing_panel.set_cached_preprocessing_available(self._has_any_preprocessing_cache())
        if not self._has_any_preprocessing_cache():
            self._show_denoised_in_viewer = False

    def _has_matching_repair_cache(self, params: dict[str, float | int | str]) -> bool:
        if self._sequence is None or self._repair_frames is None or self._repair_params is None:
            return False
        if self._repair_frames.shape != self._sequence.raw_frames.shape:
            return False
        return all(self._repair_params.get(key) == value for key, value in params.items())

    def _has_matching_denoised_cache(self, sigma_factor: float) -> bool:
        if self._sequence is None or self._denoised_frames is None or self._denoised_sigma_factor is None:
            return False
        return (
            self._denoised_frames.shape == self._sequence.raw_frames.shape
            and abs(self._denoised_sigma_factor - sigma_factor) < 1e-9
        )

    def _has_any_preprocessing_cache(self) -> bool:
        return self._repair_frames is not None or self._denoised_frames is not None

    def _current_bm3d_input_frames(self) -> np.ndarray:
        if self._repair_frames is not None:
            return self._repair_frames
        assert self._sequence is not None
        return self._sequence.raw_frames

    def _current_bm3d_input_frame(self) -> np.ndarray | None:
        if self._sequence is None:
            return None
        if self._repair_frames is not None:
            return self._repair_frames[self._sequence.active_frame_index]
        return self._sequence.active_frame

    def _current_viewer_override(self) -> tuple[np.ndarray | None, str]:
        if self._denoised_frames is not None and self._sequence is not None:
            label = "BM3D" if self._denoised_sigma_factor is None else f"BM3D sigma {self._denoised_sigma_factor:.2f}"
            return self.current_denoised_frame(), label
        if self._repair_frames is not None and self._sequence is not None:
            return self.current_repaired_frame(), "Horizontal repair"
        return None, "Raw"

    def _default_preprocessing_status(self) -> str:
        if self._sequence is None:
            return "No sequence loaded"
        if self._denoised_frames is not None and self._denoised_sigma_factor is not None:
            return (
                f"BM3D cached for all {self._sequence.frame_count} frames "
                f"(sigma {self._denoised_sigma_factor:.2f})"
            )
        if self._repair_frames is not None:
            return f"Horizontal repair cached for all {self._sequence.frame_count} frames"
        return "No preview generated for current frame"

    def _reset_preview_state(self, *, close_dialog: bool = False) -> None:
        if close_dialog:
            self._preview_frame_index = None
        if self._sequence is None:
            self.preprocessing_panel.set_preview_status("No sequence loaded")
        elif self._preview_frame_index == self._sequence.active_frame_index:
            self.preprocessing_panel.set_preview_status(
                f"Preview ready for frame {self._sequence.active_frame_index + 1}"
            )
        else:
            self.preprocessing_panel.set_preview_status(self._default_preprocessing_status())

        if close_dialog and self._bm3d_preview_dialog is not None:
            self._bm3d_preview_dialog.close()
            self._bm3d_preview_dialog.clear_preview()

        if self._sequence is None:
            self._preview_frame_index = None
