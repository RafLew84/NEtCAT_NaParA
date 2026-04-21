from __future__ import annotations

from pathlib import Path
import time

import numpy as np
from PyQt6.QtCore import QObject, QSignalBlocker, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from nanotrack.analysis import compute_particle_metrics
from nanotrack.core import (
    AnnotationSource,
    BBoxXYXY,
    EdgeAnnotationSource,
    EdgeFrameAnnotation,
    EdgeTrack,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    PolygonROI,
    STMSequence,
    TrackFrameAnnotation,
)
from nanotrack.io import load_mpp_sequence
from nanotrack.persistence import NanoTrackSessionSnapshot, load_session_snapshot, save_session_snapshot
from nanotrack.processing import (
    run_bm3d_batch,
    run_bm3d_preview,
    run_horizontal_dropout_batch,
    run_horizontal_dropout_preview,
)
from nanotrack.edges import DexiNedRunInput, DexiNedRunOutput, DexiNedSubprocessBackend
from nanotrack.edges.polyline import dominant_edge_to_polyline
from nanotrack.edges.selection import select_dominant_edge
from nanotrack.sam2 import Sam2RunInput, Sam2RunOutput, Sam2SubprocessBackend
from nanotrack.ui.dialogs import Bm3dPreviewDialog, EdgePreviewDialog, TrackResultsDialog
from nanotrack.ui.widgets import (
    BBoxToolsPanel,
    PolygonRoiToolsPanel,
    PreprocessingActionsPanel,
    SequenceMetadataPanel,
    SequenceViewerWidget,
    TrackListPanel,
)


class _DexiNedRunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, backend: DexiNedSubprocessBackend, run_input: DexiNedRunInput):
        super().__init__()
        self._backend = backend
        self._run_input = run_input

    def run(self) -> None:
        try:
            output = self._backend.run(self._run_input)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(output)


class _Sam2RunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, backend: Sam2SubprocessBackend, run_input: Sam2RunInput):
        super().__init__()
        self._backend = backend
        self._run_input = run_input

    def run(self) -> None:
        try:
            output = self._backend.run(self._run_input)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(output)


class _Sam2BatchWorker(QObject):
    progress = pyqtSignal(int, int, object)
    item_failed = pyqtSignal(int, int, object)
    finished = pyqtSignal(object)

    def __init__(self, backend: Sam2SubprocessBackend, run_items: list[tuple[int, Sam2RunInput]]):
        super().__init__()
        self._backend = backend
        self._run_items = list(run_items)

    def run(self) -> None:
        total = len(self._run_items)
        failures: list[tuple[int, str]] = []
        for index, (track_id, run_input) in enumerate(self._run_items, start=1):
            try:
                output = self._backend.run(run_input)
                self.progress.emit(index, total, (track_id, output))
            except Exception as exc:
                error_message = f"Track {track_id} failed during SAM2 batch.\n{exc}"
                failures.append((track_id, error_message))
                self.item_failed.emit(index, total, (track_id, error_message))
        self.finished.emit({"total": total, "failures": failures})


class NanoTrackMainWindow(QMainWindow):
    """Main window for MPP sequence browsing and navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._tracks: list[ParticleTrack] = []
        self._edge_tracks: list[EdgeTrack] = []
        self._selected_track_id: int | None = None
        self._selected_edge_track_id: int | None = None
        self._draft_bboxes_by_frame: dict[int, BBoxXYXY] = {}
        self._draft_polygons_by_frame: dict[int, PolygonROI] = {}
        self._repair_frames: np.ndarray | None = None
        self._repair_params: dict[str, float | int | str] | None = None
        self._denoised_frames: np.ndarray | None = None
        self._denoised_sigma_factor: float | None = None
        self._show_denoised_in_viewer = False
        self._is_preprocessing = False
        self._is_tracking = False
        self._preview_frame_index: int | None = None
        self._bm3d_preview_dialog: Bm3dPreviewDialog | None = None
        self._edge_preview_dialog: EdgePreviewDialog | None = None
        self._results_dialog: TrackResultsDialog | None = None
        self._dexined_backend = DexiNedSubprocessBackend()
        self._dexined_progress_dialog: QProgressDialog | None = None
        self._dexined_thread: QThread | None = None
        self._dexined_worker: _DexiNedRunWorker | None = None
        self._pending_edge_preview_frame: np.ndarray | None = None
        self._pending_edge_preview_meta: dict[str, object] | None = None
        self._pending_edge_sequence_meta: dict[str, object] | None = None
        self._sam2_backend = Sam2SubprocessBackend()
        self._sam2_progress_dialog: QProgressDialog | None = None
        self._sam2_thread: QThread | None = None
        self._sam2_worker: _Sam2RunWorker | None = None
        self._sam2_running_track_id: int | None = None
        self._sam2_resume_from_frame: int | None = None
        self._sam2_batch_failures: list[tuple[int, str]] = []
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

        file_menu = self.menuBar().addMenu("File")
        self.action_open_mpp = QAction("Open MPP...", self)
        self.action_open_mpp.setToolTip("Load an MPP sequence into NanoTrack")
        toolbar.addAction(self.action_open_mpp)
        self.action_open_mpp_reverse = QAction("Open Reverse...", self)
        self.action_open_mpp_reverse.setToolTip("Load an MPP sequence with reversed frame order")
        self.action_open_session = QAction("Open Session...", self)
        self.action_open_session.setToolTip("Open a saved NanoTrack session")
        self.action_save_session = QAction("Save Session...", self)
        self.action_save_session.setToolTip("Save the current NanoTrack session")
        self.action_save_session.setEnabled(False)
        file_menu.addAction(self.action_open_mpp)
        file_menu.addAction(self.action_open_mpp_reverse)
        file_menu.addSeparator()
        file_menu.addAction(self.action_open_session)
        file_menu.addAction(self.action_save_session)
        self.action_open_results = toolbar.addAction("View Results...")
        self.action_open_results.setToolTip("Open the quantitative results window")
        self.action_open_results.setEnabled(False)

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

        self.sidebar_content = QWidget(self)
        sidebar_layout = QVBoxLayout(self.sidebar_content)
        self.metadata_panel = SequenceMetadataPanel(self.sidebar_content)
        self.track_list_panel = TrackListPanel(self.sidebar_content)
        self.bbox_tools_panel = BBoxToolsPanel(self.sidebar_content)
        self.polygon_tools_panel = PolygonRoiToolsPanel(self.sidebar_content)
        self.preprocessing_panel = PreprocessingActionsPanel(self.sidebar_content)
        sidebar_layout.addWidget(self.metadata_panel, 0)
        sidebar_layout.addWidget(self.track_list_panel, 1)
        sidebar_layout.addWidget(self.bbox_tools_panel, 0)
        sidebar_layout.addWidget(self.polygon_tools_panel, 0)
        sidebar_layout.addWidget(self.preprocessing_panel, 0)
        sidebar_layout.addStretch(0)

        self.sidebar_scroll_area = QScrollArea(self)
        self.sidebar_scroll_area.setWidgetResizable(True)
        self.sidebar_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.sidebar_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll_area.setWidget(self.sidebar_content)

        central.addWidget(viewer_container)
        central.addWidget(self.sidebar_scroll_area)
        central.setStretchFactor(0, 1)
        central.setStretchFactor(1, 0)
        central.setSizes([980, 300])
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.action_open_mpp.triggered.connect(self._on_open_mpp)
        self.action_open_mpp_reverse.triggered.connect(self._on_open_mpp_reverse)
        self.action_open_session.triggered.connect(self._on_open_session_requested)
        self.action_save_session.triggered.connect(self._on_save_session_requested)
        self.action_open_results.triggered.connect(self._on_open_results_requested)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)
        self.spin_frame.valueChanged.connect(self._on_spin_frame_selected)
        self.btn_prev.clicked.connect(self._on_prev_frame)
        self.btn_next.clicked.connect(self._on_next_frame)
        self.viewer.bbox_changed.connect(self._on_viewer_bbox_changed)
        self.viewer.polygon_changed.connect(self._on_viewer_polygon_changed)
        self.bbox_tools_panel.place_mode_toggled.connect(self._on_bbox_place_mode_toggled)
        self.bbox_tools_panel.default_size_changed.connect(self._on_bbox_default_size_changed)
        self.bbox_tools_panel.add_seed_requested.connect(self._on_add_seed_requested)
        self.bbox_tools_panel.clear_requested.connect(self._on_clear_current_bbox_requested)
        self.bbox_tools_panel.load_track_bbox_requested.connect(self._on_load_track_bbox_requested)
        self.bbox_tools_panel.save_correction_requested.connect(self._on_save_correction_requested)
        self.bbox_tools_panel.resume_track_requested.connect(self._on_resume_track_requested)
        self.polygon_tools_panel.draw_mode_toggled.connect(self._on_polygon_draw_mode_toggled)
        self.polygon_tools_panel.finish_requested.connect(self._on_finish_polygon_requested)
        self.polygon_tools_panel.clear_requested.connect(self._on_clear_current_polygon_requested)
        self.polygon_tools_panel.preview_requested.connect(self._on_edge_preview_requested)
        self.polygon_tools_panel.run_sequence_requested.connect(self._on_edge_sequence_requested)
        self.track_list_panel.track_selected.connect(self._on_track_selected)
        self.track_list_panel.run_selected_requested.connect(self._on_run_sam2_for_selected_requested)
        self.track_list_panel.run_all_requested.connect(self._on_run_sam2_for_all_requested)
        self.preprocessing_panel.repair_preview_requested.connect(self._on_repair_preview_requested)
        self.preprocessing_panel.repair_apply_all_requested.connect(self._on_repair_apply_all_requested)
        self.preprocessing_panel.preview_requested.connect(self._on_bm3d_preview_requested)
        self.preprocessing_panel.apply_all_requested.connect(self._on_bm3d_apply_all_requested)
        self.preprocessing_panel.show_denoised_toggled.connect(self._on_show_denoised_toggled)
        self._on_bbox_default_size_changed(*self.bbox_tools_panel.default_size_px())

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)
        self.spin_frame.setEnabled(enabled)
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.bbox_tools_panel.set_sequence_loaded(enabled)
        self.polygon_tools_panel.set_sequence_loaded(enabled)
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
        self._sync_current_bbox_ui()
        self._sync_current_polygon_ui()
        self._sync_track_overlays()
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"{Path(self._sequence.source_path).name} | frame {self._sequence.active_frame_index + 1}/{self._sequence.frame_count}",
            3000,
        )

    def set_sequence(self, sequence: STMSequence) -> None:
        self._sequence = sequence
        self._selected_track_id = None
        self._selected_edge_track_id = None
        self._edge_tracks = []
        self._draft_bboxes_by_frame = {}
        self._draft_polygons_by_frame = {}
        self._clear_all_preprocessing_cache()
        self._set_bbox_place_mode(False)
        self._set_polygon_draw_mode(False)
        self.viewer.set_sequence(sequence)
        self._reset_preview_state(close_dialog=True)
        self._sync_navigation_controls()
        self._sync_current_bbox_ui()
        self._sync_current_polygon_ui()
        self._update_menu_action_state()
        self.statusBar().showMessage(
            f"{Path(sequence.source_path).name} | frame {sequence.active_frame_index + 1}/{sequence.frame_count}",
            3000,
        )
        self.set_tracks([])

    def load_sequence_from_path(self, file_path: str, *, reverse_frame_order: bool = False) -> None:
        sequence = load_mpp_sequence(file_path, reverse_frame_order=reverse_frame_order)
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

    def current_draft_bbox(self) -> BBoxXYXY | None:
        if self._sequence is None:
            return None
        return self._draft_bboxes_by_frame.get(self._sequence.active_frame_index)

    def current_draft_polygon_roi(self) -> PolygonROI | None:
        if self._sequence is None:
            return None
        return self._draft_polygons_by_frame.get(self._sequence.active_frame_index)

    def set_tracks(self, tracks: list[ParticleTrack], *, selected_track_id: int | None = None) -> None:
        self._tracks = list(tracks)
        valid_track_ids = {track.track_id for track in self._tracks}
        if selected_track_id is not None and selected_track_id in valid_track_ids:
            self._selected_track_id = selected_track_id
        elif self._selected_track_id not in valid_track_ids:
            self._selected_track_id = None
        self.track_list_panel.set_tracks(self._tracks, selected_track_id=self._selected_track_id)
        self._update_results_action_state()
        self._sync_results_dialog()
        self._sync_track_overlays()
        self._sync_bbox_track_context()

    def current_tracks(self) -> list[ParticleTrack]:
        return list(self._tracks)

    def current_edge_tracks(self) -> list[EdgeTrack]:
        return list(self._edge_tracks)

    def current_selected_track_id(self) -> int | None:
        return self._selected_track_id

    def current_selected_edge_track_id(self) -> int | None:
        return self._selected_edge_track_id

    def current_results_dialog(self) -> TrackResultsDialog | None:
        return self._results_dialog

    def _update_menu_action_state(self) -> None:
        busy = self._is_preprocessing or self._is_tracking
        self.action_open_mpp.setEnabled(not busy)
        self.action_open_mpp_reverse.setEnabled(not busy)
        self.action_open_session.setEnabled(not busy)
        self.action_save_session.setEnabled(self._sequence is not None and not busy)
        self.action_open_results.setEnabled(self._has_results_data() and not busy)

    def current_session_snapshot(self) -> NanoTrackSessionSnapshot | None:
        if self._sequence is None:
            return None
        return NanoTrackSessionSnapshot(
            sequence=self._sequence,
            tracks=self.current_tracks(),
            selected_track_id=self._selected_track_id,
            draft_bboxes_by_frame=dict(self._draft_bboxes_by_frame),
            repair_frames=None if self._repair_frames is None else np.asarray(self._repair_frames, dtype=np.float32),
            repair_params=None if self._repair_params is None else dict(self._repair_params),
            denoised_frames=None if self._denoised_frames is None else np.asarray(self._denoised_frames, dtype=np.float32),
            denoised_sigma_factor=self._denoised_sigma_factor,
            show_denoised_in_viewer=self._show_denoised_in_viewer,
        )

    def save_session_to_path(self, path: str) -> None:
        snapshot = self.current_session_snapshot()
        if snapshot is None:
            raise RuntimeError("No sequence loaded.")
        save_session_snapshot(path, snapshot)

    def load_session_from_path(self, path: str) -> None:
        snapshot = load_session_snapshot(path)
        self._apply_session_snapshot(snapshot)

    def _set_active_frame(self, frame_index: int) -> None:
        if self._sequence is None:
            return
        if frame_index == self._sequence.active_frame_index:
            return
        self._sequence.set_active_frame(frame_index)
        self._reset_preview_state()
        self._show_current_frame(preserve_zoom=True)

    def _on_open_mpp(self) -> None:
        self._open_mpp_sequence(reverse_frame_order=False)

    def _on_open_mpp_reverse(self) -> None:
        self._open_mpp_sequence(reverse_frame_order=True)

    def _open_mpp_sequence(self, *, reverse_frame_order: bool) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MPP sequence (reverse)" if reverse_frame_order else "Open MPP sequence",
            "",
            "MPP files (*.mpp *.MPP);;All files (*.*)",
        )
        if not path:
            return

        try:
            self.load_sequence_from_path(path, reverse_frame_order=reverse_frame_order)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", f"Cannot load MPP sequence:\n{path}\n\n{exc}")
            return

    def _on_open_session_requested(self) -> None:
        if self._is_preprocessing or self._is_tracking:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open NanoTrack session",
            "",
            "NanoTrack Session (*.nanotrack);;All files (*.*)",
        )
        if not path:
            return
        try:
            self.load_session_from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Session load error", f"Cannot load session:\n{path}\n\n{exc}")
            return
        self.statusBar().showMessage(f"Loaded session: {Path(path).name}", 3000)

    def _on_save_session_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        default_name = Path(self._sequence.file_name).stem if self._sequence.file_name else "session"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save NanoTrack session",
            f"{default_name}.nanotrack",
            "NanoTrack Session (*.nanotrack);;All files (*.*)",
        )
        if not path:
            return
        if not path.lower().endswith(".nanotrack"):
            path = f"{path}.nanotrack"
        try:
            self.save_session_to_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Session save error", f"Cannot save session:\n{path}\n\n{exc}")
            return
        self.statusBar().showMessage(f"Saved session: {Path(path).name}", 3000)

    def _on_open_results_requested(self) -> None:
        if not self._has_results_data():
            return
        dialog = self._ensure_results_dialog()
        dialog.set_context(self._sequence, self._tracks, selected_track_id=self._selected_track_id)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self.statusBar().showMessage("Results window opened.", 3000)

    def _apply_session_snapshot(self, snapshot: NanoTrackSessionSnapshot) -> None:
        self.set_sequence(snapshot.sequence)
        self._repair_frames = snapshot.repair_frames
        self._repair_params = None if snapshot.repair_params is None else dict(snapshot.repair_params)
        self._denoised_frames = snapshot.denoised_frames
        self._denoised_sigma_factor = snapshot.denoised_sigma_factor
        self._draft_bboxes_by_frame = dict(snapshot.draft_bboxes_by_frame)
        self._update_cached_preprocessing_availability()
        self._show_denoised_in_viewer = bool(snapshot.show_denoised_in_viewer and self._has_any_preprocessing_cache())
        with QSignalBlocker(self.preprocessing_panel.chk_show_denoised):
            self.preprocessing_panel.chk_show_denoised.setChecked(self._show_denoised_in_viewer)
        self.set_tracks(snapshot.tracks, selected_track_id=snapshot.selected_track_id)
        self._show_current_frame(preserve_zoom=False)

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

    def _on_bbox_place_mode_toggled(self, checked: bool) -> None:
        self._set_bbox_place_mode(checked)
        if checked:
            self._set_polygon_draw_mode(False)
        if checked:
            self.statusBar().showMessage("BBox placement active: click the image to place a bbox.", 3000)
            return
        self.statusBar().showMessage("BBox placement disabled.", 2000)

    def _on_polygon_draw_mode_toggled(self, checked: bool) -> None:
        self._set_polygon_draw_mode(checked)
        if checked:
            self._set_bbox_place_mode(False)
            self.statusBar().showMessage(
                "Polygon ROI placement active: click successive vertices, then finish the polygon.",
                3000,
            )
            return
        self.statusBar().showMessage("Polygon ROI placement disabled.", 2000)

    def _on_bbox_default_size_changed(self, width_px: int, height_px: int) -> None:
        self.viewer.set_default_bbox_size_px(width_px, height_px)

    def _on_viewer_bbox_changed(self, bbox: object) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        if bbox is None:
            self._draft_bboxes_by_frame.pop(frame_index, None)
        else:
            self._draft_bboxes_by_frame[frame_index] = bbox
        self.bbox_tools_panel.set_current_bbox(frame_index, self.current_draft_bbox())

    def _on_viewer_polygon_changed(self, polygon: object) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        if polygon is None:
            self._draft_polygons_by_frame.pop(frame_index, None)
        else:
            self._draft_polygons_by_frame[frame_index] = polygon
        self.polygon_tools_panel.set_current_polygon(frame_index, self.current_draft_polygon_roi())

    def _on_clear_current_bbox_requested(self) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        self._draft_bboxes_by_frame.pop(frame_index, None)
        self.viewer.clear_bbox()
        self.bbox_tools_panel.set_current_bbox(frame_index, None)
        self.statusBar().showMessage(f"Cleared bbox for frame {frame_index + 1}.", 2000)
        self._sync_bbox_track_context()

    def _on_finish_polygon_requested(self) -> None:
        if self._sequence is None:
            return
        polygon = self.viewer.finish_polygon_drawing()
        if polygon is None:
            self.statusBar().showMessage("Polygon ROI requires at least three vertices before finishing.", 3000)
            return
        self._set_polygon_draw_mode(False)
        self.statusBar().showMessage(
            f"Saved polygon ROI with {polygon.vertex_count} vertices on frame {self._sequence.active_frame_index + 1}.",
            3000,
        )

    def _on_clear_current_polygon_requested(self) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        self.viewer.clear_polygon()
        self.polygon_tools_panel.set_current_polygon(frame_index, None)
        self.statusBar().showMessage(f"Cleared polygon ROI for frame {frame_index + 1}.", 2000)

    def _on_edge_preview_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        polygon = self.current_draft_polygon_roi()
        if polygon is None:
            return

        try:
            run_input, input_frame, preview_meta = self._build_dexined_preview_input(polygon)
        except Exception as exc:
            QMessageBox.critical(self, "DexiNed preview error", str(exc))
            return

        self._pending_edge_preview_frame = np.asarray(input_frame, dtype=np.float32)
        self._pending_edge_preview_meta = preview_meta
        self._set_preprocessing_busy(True)
        self._dexined_progress_dialog = QProgressDialog(
            f"Running DexiNed preview for frame {self._sequence.active_frame_index + 1}...",
            "",
            0,
            0,
            self,
        )
        self._dexined_progress_dialog.setWindowTitle("DexiNed Preview")
        self._dexined_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._dexined_progress_dialog.setCancelButton(None)
        self._dexined_progress_dialog.setMinimumDuration(0)
        self._dexined_progress_dialog.setAutoClose(False)
        self._dexined_progress_dialog.setAutoReset(False)
        self._dexined_progress_dialog.setValue(0)
        self._dexined_progress_dialog.show()
        self.statusBar().showMessage(
            f"Running DexiNed preview for frame {self._sequence.active_frame_index + 1}...",
            0,
        )
        QApplication.processEvents()

        self._dexined_thread = QThread(self)
        self._dexined_worker = _DexiNedRunWorker(self._dexined_backend, run_input)
        self._dexined_worker.moveToThread(self._dexined_thread)
        self._dexined_thread.started.connect(self._dexined_worker.run)
        self._dexined_worker.finished.connect(self._on_dexined_preview_finished)
        self._dexined_worker.failed.connect(self._on_dexined_preview_failed)
        self._dexined_worker.finished.connect(self._dexined_thread.quit)
        self._dexined_worker.failed.connect(self._dexined_thread.quit)
        self._dexined_thread.finished.connect(self._cleanup_dexined_worker)
        self._dexined_thread.start()

    def _on_edge_sequence_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        polygon = self.current_draft_polygon_roi()
        if polygon is None:
            return

        try:
            run_input, sequence_meta = self._build_dexined_sequence_input(polygon)
        except Exception as exc:
            QMessageBox.critical(self, "DexiNed sequence error", str(exc))
            return

        self._pending_edge_sequence_meta = sequence_meta
        self._set_preprocessing_busy(True)
        self._dexined_progress_dialog = QProgressDialog(
            f"Running DexiNed on {self._sequence.frame_count} frames...",
            "",
            0,
            0,
            self,
        )
        self._dexined_progress_dialog.setWindowTitle("DexiNed Sequence")
        self._dexined_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._dexined_progress_dialog.setCancelButton(None)
        self._dexined_progress_dialog.setMinimumDuration(0)
        self._dexined_progress_dialog.setAutoClose(False)
        self._dexined_progress_dialog.setAutoReset(False)
        self._dexined_progress_dialog.setValue(0)
        self._dexined_progress_dialog.show()
        self.statusBar().showMessage(
            f"Running DexiNed on {self._sequence.frame_count} frames...",
            0,
        )
        QApplication.processEvents()

        self._dexined_thread = QThread(self)
        self._dexined_worker = _DexiNedRunWorker(self._dexined_backend, run_input)
        self._dexined_worker.moveToThread(self._dexined_thread)
        self._dexined_thread.started.connect(self._dexined_worker.run)
        self._dexined_worker.finished.connect(self._on_dexined_sequence_finished)
        self._dexined_worker.failed.connect(self._on_dexined_sequence_failed)
        self._dexined_worker.finished.connect(self._dexined_thread.quit)
        self._dexined_worker.failed.connect(self._dexined_thread.quit)
        self._dexined_thread.finished.connect(self._cleanup_dexined_worker)
        self._dexined_thread.start()

    def _on_add_seed_requested(self) -> None:
        if self._sequence is None:
            return
        current_bbox = self.current_draft_bbox()
        if current_bbox is None:
            return

        track_id = self._next_track_id()
        track = ParticleTrack(
            track_id=track_id,
            seed_frame_index=self._sequence.active_frame_index,
            seed_bbox=current_bbox,
        )
        self._tracks.append(track)
        self.set_tracks(self._tracks, selected_track_id=track_id)
        self._draft_bboxes_by_frame.pop(self._sequence.active_frame_index, None)
        self.viewer.clear_bbox()
        self.bbox_tools_panel.set_current_bbox(self._sequence.active_frame_index, None)
        self.statusBar().showMessage(
            f"Added seed Track {track_id} on frame {self._sequence.active_frame_index + 1}.",
            3000,
        )
        self._sync_bbox_track_context()

    def _on_load_track_bbox_requested(self) -> None:
        if self._sequence is None:
            return
        track = self._find_track_by_id(self._selected_track_id)
        if track is None:
            return
        annotation = track.get_annotation(self._sequence.active_frame_index)
        if annotation is None or annotation.bbox is None:
            return
        self._draft_bboxes_by_frame[self._sequence.active_frame_index] = annotation.bbox
        self.viewer.set_bbox(annotation.bbox)
        self.bbox_tools_panel.set_current_bbox(self._sequence.active_frame_index, annotation.bbox)
        self._sync_bbox_track_context()
        self.statusBar().showMessage(
            f"Loaded bbox from {track.label or f'Track {track.track_id}'} on frame {self._sequence.active_frame_index + 1}.",
            3000,
        )

    def _on_save_correction_requested(self) -> None:
        if self._sequence is None:
            return
        track = self._find_track_by_id(self._selected_track_id)
        current_bbox = self.current_draft_bbox()
        if track is None or current_bbox is None:
            return
        current_frame = self._sequence.active_frame_index
        if current_frame < track.seed_frame_index:
            QMessageBox.warning(
                self,
                "Invalid correction frame",
                (
                    f"Track {track.track_id} starts at frame {track.seed_frame_index + 1}. "
                    f"Cannot save a correction on frame {current_frame + 1}."
                ),
            )
            return

        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=current_frame,
                bbox=current_bbox,
                mask=None,
                visibility=FrameVisibility.VISIBLE,
                source=AnnotationSource.MANUAL,
            )
        )
        self._draft_bboxes_by_frame.pop(current_frame, None)
        self.viewer.clear_bbox()
        self.set_tracks(self._tracks, selected_track_id=track.track_id)
        self._show_current_frame(preserve_zoom=True)
        self.statusBar().showMessage(
            f"Saved manual correction for {track.label or f'Track {track.track_id}'} on frame {current_frame + 1}.",
            3000,
        )

    def _on_resume_track_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        track = self._find_track_by_id(self._selected_track_id)
        if track is None:
            return

        resume_frame = self._sequence.active_frame_index
        annotation = track.get_annotation(resume_frame)
        if annotation is None or annotation.bbox is None:
            QMessageBox.warning(
                self,
                "Resume unavailable",
                (
                    f"Track {track.track_id} has no bbox on frame {resume_frame + 1}. "
                    "Load or save a correction first."
                ),
            )
            return

        try:
            run_input = self._build_sam2_input_for_track(
                track,
                start_frame_index=resume_frame,
                prompt_bbox=annotation.bbox,
            )
        except Exception as exc:
            QMessageBox.critical(self, "SAM2 resume input error", str(exc))
            return

        self._set_tracking_busy(True)
        self._sam2_running_track_id = track.track_id
        self._sam2_resume_from_frame = resume_frame
        self._sam2_progress_dialog = QProgressDialog(
            f"Resuming SAM2 for {track.label or f'Track {track.track_id}'} from frame {resume_frame + 1}...",
            "",
            0,
            0,
            self,
        )
        self._sam2_progress_dialog.setWindowTitle("SAM2 Resume")
        self._sam2_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._sam2_progress_dialog.setCancelButton(None)
        self._sam2_progress_dialog.setMinimumDuration(0)
        self._sam2_progress_dialog.setAutoClose(False)
        self._sam2_progress_dialog.setAutoReset(False)
        self._sam2_progress_dialog.setValue(0)
        self._sam2_progress_dialog.show()
        self.statusBar().showMessage(
            f"Resuming SAM2 for {track.label or f'Track {track.track_id}'} from frame {resume_frame + 1}...",
            0,
        )
        QApplication.processEvents()

        self._sam2_thread = QThread(self)
        self._sam2_worker = _Sam2RunWorker(self._sam2_backend, run_input)
        self._sam2_worker.moveToThread(self._sam2_thread)
        self._sam2_thread.started.connect(self._sam2_worker.run)
        self._sam2_worker.finished.connect(self._on_sam2_run_finished)
        self._sam2_worker.failed.connect(self._on_sam2_run_failed)
        self._sam2_worker.finished.connect(self._sam2_thread.quit)
        self._sam2_worker.failed.connect(self._sam2_thread.quit)
        self._sam2_thread.finished.connect(self._cleanup_sam2_worker)
        self._sam2_thread.start()

    def _on_track_selected(self, track_id: object) -> None:
        selected_id = None if track_id is None else int(track_id)
        self._selected_track_id = selected_id
        self._sync_results_dialog_selection()
        track = self._find_track_by_id(selected_id)
        if track is not None and self._sequence is not None and track.seed_frame_index != self._sequence.active_frame_index:
            self._set_active_frame(track.seed_frame_index)
            return
        self._sync_track_overlays()
        self._sync_bbox_track_context()
        if track is not None:
            self.statusBar().showMessage(
                f"Selected {track.label or f'Track {track.track_id}'} | seed frame {track.seed_frame_index + 1}",
                3000,
            )

    def _on_repair_preview_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        current_index = self._sequence.active_frame_index
        params = self.preprocessing_panel.repair_parameters()
        try:
            repaired, mask = run_horizontal_dropout_preview(self._sequence.active_frame, **params)
        except Exception as exc:
            QMessageBox.critical(self, "Repair preview error", str(exc))
            self.preprocessing_panel.set_preview_status("Repair preview failed")
            return

        diff = np.abs(np.asarray(repaired, dtype=np.float32) - np.asarray(self._sequence.active_frame, dtype=np.float32))
        mask_pixels = int(np.count_nonzero(mask))
        changed_pixels = int(np.count_nonzero(diff > 1e-6))
        max_delta = float(diff.max()) if diff.size else 0.0

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
                f"width {params['min_width_frac']*100:.1f}-{params['max_width_frac']*100:.1f}% | "
                f"mask {mask_pixels}px | changed {changed_pixels}px | max Δ {max_delta:.3g}"
            ),
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._preview_frame_index = current_index
        if mask_pixels == 0:
            self.preprocessing_panel.set_preview_status(
                f"Repair preview: no dropout detected on frame {current_index + 1}"
            )
        else:
            self.preprocessing_panel.set_preview_status(
                f"Repair preview ready for frame {current_index + 1} | mask {mask_pixels}px | max Δ {max_delta:.3g}"
            )
        self.statusBar().showMessage(f"Repair preview opened for frame {current_index + 1}.", 3000)

    def _on_bm3d_preview_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
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

    def _on_dexined_preview_finished(self, output: DexiNedRunOutput) -> None:
        if self._sequence is None or self._pending_edge_preview_frame is None or self._pending_edge_preview_meta is None:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()
            return

        current_index = int(self._pending_edge_preview_meta["frame_index"])
        source_title = str(self._pending_edge_preview_meta["source_title"])
        source_meta = str(self._pending_edge_preview_meta["source_meta"])
        source_view = str(self._pending_edge_preview_meta["source_view"])
        polygon_mask = np.asarray(self._pending_edge_preview_meta["polygon_mask"], dtype=bool)
        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        edge_frame = np.asarray(output.edge_prob[0], dtype=np.float32)
        edge_binary_frame = None if output.edge_binary is None else np.asarray(output.edge_binary[0], dtype=bool)
        selection, selected_edge_frame, polyline, max_prob = self._extract_dominant_edge_geometry(
            edge_frame,
            polygon_mask,
            edge_binary_frame=edge_binary_frame,
        )

        dialog = self._ensure_edge_preview_dialog()
        dialog.set_preview(
            self._pending_edge_preview_frame,
            selected_edge_frame,
            frame_index=current_index,
            frame_count=self._sequence.frame_count,
            scale_nm_per_px=(px_x, px_y),
            window_title="DexiNed Preview",
            input_title=source_title,
            input_meta=source_meta,
            input_overlay_mask=selection.edge_mask,
            input_overlay_polyline=polyline.polyline_xy,
            edge_title="Dominant Edge",
            edge_meta=(
                f"View: {source_view} | mode {selection.selection_mode} | "
                f"selected px {selection.pixel_count} | mean p {selection.mean_probability:.3f} | "
                f"polyline {polyline.extraction_mode} | pts {polyline.point_count} | max p {max_prob:.3f}"
            ),
            edge_overlay_polyline=polyline.polyline_xy,
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        self.statusBar().showMessage(f"DexiNed preview opened for frame {current_index + 1}.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_dexined_sequence_finished(self, output: DexiNedRunOutput) -> None:
        if self._sequence is None or self._pending_edge_sequence_meta is None:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()
            return

        try:
            track = self._build_edge_track_from_dexined_output(output, self._pending_edge_sequence_meta)
        except Exception as exc:
            QMessageBox.critical(self, "DexiNed sequence error", str(exc))
            self.statusBar().showMessage("DexiNed sequence failed.", 3000)
        else:
            self._edge_tracks.append(track)
            self._selected_edge_track_id = track.edge_track_id
            self._show_current_frame(preserve_zoom=True)
            self.statusBar().showMessage(
                f"DexiNed sequence finished: Edge Track {track.edge_track_id} with {len(track.annotations)} frames.",
                4000,
            )
        finally:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()

    def _on_dexined_preview_failed(self, error_message: str) -> None:
        QMessageBox.critical(self, "DexiNed preview error", error_message)
        self.statusBar().showMessage("DexiNed preview failed.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_dexined_sequence_failed(self, error_message: str) -> None:
        QMessageBox.critical(self, "DexiNed sequence error", error_message)
        self.statusBar().showMessage("DexiNed sequence failed.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_repair_apply_all_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
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
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
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

    def _on_run_sam2_for_selected_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        track = self._find_track_by_id(self._selected_track_id)
        if track is None:
            return

        try:
            run_input = self._build_sam2_input_for_track(track)
        except Exception as exc:
            QMessageBox.critical(self, "SAM2 input error", str(exc))
            return

        self._set_tracking_busy(True)
        self._sam2_running_track_id = track.track_id
        self._sam2_resume_from_frame = None
        self._sam2_progress_dialog = QProgressDialog(
            f"Running SAM2 for {track.label or f'Track {track.track_id}'}...",
            "",
            0,
            0,
            self,
        )
        self._sam2_progress_dialog.setWindowTitle("SAM2 Tracking")
        self._sam2_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._sam2_progress_dialog.setCancelButton(None)
        self._sam2_progress_dialog.setMinimumDuration(0)
        self._sam2_progress_dialog.setAutoClose(False)
        self._sam2_progress_dialog.setAutoReset(False)
        self._sam2_progress_dialog.setValue(0)
        self._sam2_progress_dialog.show()
        self.statusBar().showMessage(
            f"Running SAM2 for {track.label or f'Track {track.track_id}'}...",
            0,
        )
        QApplication.processEvents()

        self._sam2_thread = QThread(self)
        self._sam2_worker = _Sam2RunWorker(self._sam2_backend, run_input)
        self._sam2_worker.moveToThread(self._sam2_thread)
        self._sam2_thread.started.connect(self._sam2_worker.run)
        self._sam2_worker.finished.connect(self._on_sam2_run_finished)
        self._sam2_worker.failed.connect(self._on_sam2_run_failed)
        self._sam2_worker.finished.connect(self._sam2_thread.quit)
        self._sam2_worker.failed.connect(self._sam2_thread.quit)
        self._sam2_thread.finished.connect(self._cleanup_sam2_worker)
        self._sam2_thread.start()

    def _on_run_sam2_for_all_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking or not self._tracks:
            return

        run_items: list[tuple[int, Sam2RunInput]] = []
        try:
            for track in self._tracks:
                run_items.append((track.track_id, self._build_sam2_input_for_track(track)))
        except Exception as exc:
            QMessageBox.critical(self, "SAM2 input error", str(exc))
            return

        self._set_tracking_busy(True)
        self._sam2_running_track_id = None
        self._sam2_resume_from_frame = None
        self._sam2_batch_failures = []
        self._sam2_progress_dialog = QProgressDialog(
            "Running SAM2 for all seeds...",
            "",
            0,
            len(run_items),
            self,
        )
        self._sam2_progress_dialog.setWindowTitle("SAM2 Tracking")
        self._sam2_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._sam2_progress_dialog.setCancelButton(None)
        self._sam2_progress_dialog.setMinimumDuration(0)
        self._sam2_progress_dialog.setAutoClose(False)
        self._sam2_progress_dialog.setAutoReset(False)
        self._sam2_progress_dialog.setValue(0)
        self._sam2_progress_dialog.show()
        self.statusBar().showMessage(f"Running SAM2 for all {len(run_items)} seeds...", 0)
        QApplication.processEvents()

        self._sam2_thread = QThread(self)
        self._sam2_batch_worker = _Sam2BatchWorker(self._sam2_backend, run_items)
        self._sam2_batch_worker.moveToThread(self._sam2_thread)
        self._sam2_thread.started.connect(self._sam2_batch_worker.run)
        self._sam2_batch_worker.progress.connect(self._on_sam2_batch_progress)
        self._sam2_batch_worker.item_failed.connect(self._on_sam2_batch_item_failed)
        self._sam2_batch_worker.finished.connect(self._on_sam2_batch_finished)
        self._sam2_batch_worker.finished.connect(self._sam2_thread.quit)
        self._sam2_thread.finished.connect(self._cleanup_sam2_worker)
        self._sam2_thread.start()

    def _on_sam2_run_finished(self, run_output: object) -> None:
        assert isinstance(run_output, Sam2RunOutput)
        if self._sam2_resume_from_frame is not None:
            self._resume_track_from_output(run_output.track_id, run_output, self._sam2_resume_from_frame)
            track = self._find_track_by_id(run_output.track_id)
            label = track.label if track is not None and track.label else f"Track {run_output.track_id}"
            self.set_tracks(self._tracks, selected_track_id=run_output.track_id)
            self._show_current_frame(preserve_zoom=True)
            self.statusBar().showMessage(
                f"SAM2 resume finished for {label} from frame {self._sam2_resume_from_frame + 1}.",
                3000,
            )
        else:
            self._apply_sam2_output_to_track(run_output.track_id, run_output)
            self.set_tracks(self._tracks, selected_track_id=run_output.track_id)
            self._show_current_frame(preserve_zoom=True)
            track = self._find_track_by_id(run_output.track_id)
            label = track.label if track is not None and track.label else f"Track {run_output.track_id}"
            self.statusBar().showMessage(
                f"SAM2 finished for {label}.",
                3000,
            )
        self._set_tracking_busy(False)
        self._close_sam2_progress_dialog()

    def _on_sam2_batch_progress(self, completed: int, total: int, payload: object) -> None:
        track_id, run_output = payload
        assert isinstance(track_id, int)
        assert isinstance(run_output, Sam2RunOutput)
        self._apply_sam2_output_to_track(track_id, run_output)
        self.set_tracks(self._tracks, selected_track_id=self._selected_track_id)
        self._show_current_frame(preserve_zoom=True)
        track = self._find_track_by_id(track_id)
        label = track.label if track is not None and track.label else f"Track {track_id}"
        if self._sam2_progress_dialog is not None:
            self._sam2_progress_dialog.setMaximum(total)
            self._sam2_progress_dialog.setLabelText(f"Running SAM2 for all seeds... {completed}/{total}\nFinished: {label}")
            self._sam2_progress_dialog.setValue(completed)
        self.statusBar().showMessage(f"SAM2 batch {completed}/{total} finished: {label}", 0)

    def _on_sam2_batch_item_failed(self, completed: int, total: int, payload: object) -> None:
        track_id, error_message = payload
        assert isinstance(track_id, int)
        assert isinstance(error_message, str)
        self._sam2_batch_failures.append((track_id, error_message))
        if self._sam2_progress_dialog is not None:
            self._sam2_progress_dialog.setMaximum(total)
            self._sam2_progress_dialog.setLabelText(f"Running SAM2 for all seeds... {completed}/{total}\nFailed: Track {track_id}")
            self._sam2_progress_dialog.setValue(completed)
        self.statusBar().showMessage(f"SAM2 batch {completed}/{total} failed: Track {track_id}", 0)

    def _on_sam2_batch_finished(self, summary: object) -> None:
        failures = []
        total = len(self._tracks)
        if isinstance(summary, dict):
            failures = list(summary.get("failures", []))
            total = int(summary.get("total", total))
        if failures:
            failed_track_ids = ", ".join(str(track_id) for track_id, _message in failures)
            QMessageBox.warning(
                self,
                "SAM2 batch finished with failures",
                f"SAM2 finished with failures for {len(failures)}/{total} seeds.\nFailed track IDs: {failed_track_ids}",
            )
            self.statusBar().showMessage(
                f"SAM2 finished with failures for {len(failures)}/{total} seeds.",
                5000,
            )
        else:
            self.statusBar().showMessage(f"SAM2 finished for all {total} seeds.", 3000)
        self._set_tracking_busy(False)
        self._close_sam2_progress_dialog()

    def _on_sam2_run_failed(self, error_message: str) -> None:
        QMessageBox.critical(self, "SAM2 error", error_message)
        self.statusBar().showMessage("SAM2 run failed.", 3000)
        self._set_tracking_busy(False)
        self._close_sam2_progress_dialog()

    def _on_show_denoised_toggled(self, checked: bool) -> None:
        self._show_denoised_in_viewer = bool(checked and self._has_any_preprocessing_cache())
        if self._sequence is not None:
            self._show_current_frame(preserve_zoom=True)

    def _ensure_bm3d_preview_dialog(self) -> Bm3dPreviewDialog:
        if self._bm3d_preview_dialog is None:
            self._bm3d_preview_dialog = Bm3dPreviewDialog(self)
        return self._bm3d_preview_dialog

    def _ensure_edge_preview_dialog(self) -> EdgePreviewDialog:
        if self._edge_preview_dialog is None:
            self._edge_preview_dialog = EdgePreviewDialog(self)
        return self._edge_preview_dialog

    def _set_preprocessing_busy(self, busy: bool) -> None:
        self._is_preprocessing = busy
        self._apply_busy_state()

    def _set_tracking_busy(self, busy: bool) -> None:
        self._is_tracking = busy
        self._apply_busy_state()

    def _apply_busy_state(self) -> None:
        busy = self._is_preprocessing or self._is_tracking
        self._update_menu_action_state()
        self.bbox_tools_panel.set_processing(busy)
        self.polygon_tools_panel.set_processing(busy)
        self.preprocessing_panel.set_processing(busy)
        self.track_list_panel.set_processing(busy)
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

    def _close_sam2_progress_dialog(self) -> None:
        if self._sam2_progress_dialog is None:
            return
        self._sam2_progress_dialog.close()
        self._sam2_progress_dialog.deleteLater()
        self._sam2_progress_dialog = None

    def _close_dexined_progress_dialog(self) -> None:
        if self._dexined_progress_dialog is None:
            return
        self._dexined_progress_dialog.close()
        self._dexined_progress_dialog.deleteLater()
        self._dexined_progress_dialog = None

    def _cleanup_dexined_worker(self) -> None:
        if self._dexined_worker is not None:
            self._dexined_worker.deleteLater()
            self._dexined_worker = None
        if self._dexined_thread is not None:
            self._dexined_thread.deleteLater()
            self._dexined_thread = None
        self._pending_edge_preview_frame = None
        self._pending_edge_preview_meta = None
        self._pending_edge_sequence_meta = None

    def _cleanup_sam2_worker(self) -> None:
        if self._sam2_worker is not None:
            self._sam2_worker.deleteLater()
            self._sam2_worker = None
        if getattr(self, "_sam2_batch_worker", None) is not None:
            self._sam2_batch_worker.deleteLater()
            self._sam2_batch_worker = None
        if self._sam2_thread is not None:
            self._sam2_thread.deleteLater()
            self._sam2_thread = None
        self._sam2_running_track_id = None
        self._sam2_resume_from_frame = None
        self._sam2_batch_failures = []

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
        if close_dialog and self._edge_preview_dialog is not None:
            self._edge_preview_dialog.close()
            self._edge_preview_dialog.clear_preview()

        if self._sequence is None:
            self._preview_frame_index = None

    def _set_bbox_place_mode(self, enabled: bool) -> None:
        self.bbox_tools_panel.set_place_mode_active(enabled)
        self.viewer.set_bbox_draw_mode(enabled)
        if enabled:
            self.polygon_tools_panel.set_draw_mode_active(False)
            self.viewer.set_polygon_draw_mode(False)

    def _set_polygon_draw_mode(self, enabled: bool) -> None:
        self.polygon_tools_panel.set_draw_mode_active(enabled)
        self.viewer.set_polygon_draw_mode(enabled)
        if enabled:
            self.bbox_tools_panel.set_place_mode_active(False)
            self.viewer.set_bbox_draw_mode(False)

    def _sync_current_bbox_ui(self) -> None:
        if self._sequence is None:
            self.viewer.clear_bbox()
            self.bbox_tools_panel.set_current_bbox(None, None)
            return
        current_bbox = self.current_draft_bbox()
        self.viewer.set_bbox(current_bbox)
        self.bbox_tools_panel.set_current_bbox(self._sequence.active_frame_index, current_bbox)
        self._sync_bbox_track_context()

    def _sync_current_polygon_ui(self) -> None:
        if self._sequence is None:
            self.viewer.set_polygon_roi(None)
            self.polygon_tools_panel.set_current_polygon(None, None)
            return
        current_polygon = self.current_draft_polygon_roi()
        self.viewer.set_polygon_roi(current_polygon)
        self.polygon_tools_panel.set_current_polygon(self._sequence.active_frame_index, current_polygon)

    def _current_edge_input_frames(self) -> tuple[np.ndarray, str, str, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        if self._denoised_frames is not None:
            source_view = "repair+bm3d" if self._repair_frames is not None else "bm3d"
            return np.asarray(self._denoised_frames, dtype=np.float32), "BM3D input", "BM3D cache", source_view
        if self._repair_frames is not None:
            return np.asarray(self._repair_frames, dtype=np.float32), "Repair input", "Horizontal repair cache", "repair"
        return np.asarray(self._sequence.raw_frames, dtype=np.float32), "Raw input", "Raw frame", "raw"

    def _current_edge_input_frame(self) -> tuple[np.ndarray, str, str, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        input_frames, source_title, source_meta, source_view = self._current_edge_input_frames()
        return input_frames[self._sequence.active_frame_index], source_title, source_meta, source_view

    def _polygon_roi_to_mask(self, polygon: PolygonROI) -> np.ndarray:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        from skimage.draw import polygon2mask

        polygon_vertices_rc = polygon.as_array()[:, [1, 0]]
        return np.asarray(polygon2mask(self._sequence.frame_shape, polygon_vertices_rc), dtype=bool)

    def _build_dexined_preview_input(
        self,
        polygon: PolygonROI,
    ) -> tuple[DexiNedRunInput, np.ndarray, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        input_frame, source_title, source_meta, source_view = self._current_edge_input_frame()
        polygon_mask = self._polygon_roi_to_mask(polygon)
        run_input = DexiNedRunInput(
            frames=np.asarray(input_frame[None, ...], dtype=np.float32),
            polygon_mask=polygon_mask,
            source_view=source_view,
        )
        preview_meta = {
            "frame_index": self._sequence.active_frame_index,
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
            "polygon_mask": polygon_mask,
        }
        return run_input, np.asarray(input_frame, dtype=np.float32), preview_meta

    def _build_dexined_sequence_input(
        self,
        polygon: PolygonROI,
    ) -> tuple[DexiNedRunInput, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        input_frames, source_title, source_meta, source_view = self._current_edge_input_frames()
        polygon_mask = self._polygon_roi_to_mask(polygon)
        run_input = DexiNedRunInput(
            frames=np.asarray(input_frames, dtype=np.float32),
            polygon_mask=polygon_mask,
            source_view=source_view,
        )
        sequence_meta = {
            "polygon": polygon,
            "polygon_mask": polygon_mask,
            "seed_frame_index": self._sequence.active_frame_index,
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
        }
        return run_input, sequence_meta

    def _effective_dexined_threshold(
        self,
        edge_frame: np.ndarray,
        polygon_mask: np.ndarray,
        *,
        edge_binary_frame: np.ndarray | None,
    ) -> float:
        effective_threshold = 0.5
        if edge_binary_frame is not None and np.any(edge_binary_frame & polygon_mask):
            effective_threshold = float(np.min(edge_frame[edge_binary_frame & polygon_mask]))
        return effective_threshold

    def _extract_dominant_edge_geometry(
        self,
        edge_frame: np.ndarray,
        polygon_mask: np.ndarray,
        *,
        edge_binary_frame: np.ndarray | None,
    ):
        effective_threshold = self._effective_dexined_threshold(
            edge_frame,
            polygon_mask,
            edge_binary_frame=edge_binary_frame,
        )
        selection = select_dominant_edge(edge_frame, polygon_mask, threshold=effective_threshold)
        selected_edge_frame = edge_frame * selection.edge_mask.astype(np.float32, copy=False)
        polyline = dominant_edge_to_polyline(selection.edge_mask, edge_prob=edge_frame)
        max_prob = float(np.max(selected_edge_frame)) if selected_edge_frame.size else 0.0
        return selection, selected_edge_frame, polyline, max_prob

    def _build_edge_track_from_dexined_output(
        self,
        output: DexiNedRunOutput,
        sequence_meta: dict[str, object],
    ) -> EdgeTrack:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")

        polygon = sequence_meta["polygon"]
        polygon_mask = np.asarray(sequence_meta["polygon_mask"], dtype=bool)
        seed_frame_index = int(sequence_meta["seed_frame_index"])
        edge_prob = np.asarray(output.edge_prob, dtype=np.float32)
        if edge_prob.shape[0] != self._sequence.frame_count:
            raise ValueError("DexiNed sequence output length must match the current sequence.")

        annotations: dict[int, EdgeFrameAnnotation] = {}
        seed_polyline = None
        for frame_index in range(self._sequence.frame_count):
            edge_frame = np.asarray(edge_prob[frame_index], dtype=np.float32)
            edge_binary_frame = None
            if output.edge_binary is not None:
                edge_binary_frame = np.asarray(output.edge_binary[frame_index], dtype=bool)
            selection, _selected_edge_frame, polyline, _max_prob = self._extract_dominant_edge_geometry(
                edge_frame,
                polygon_mask,
                edge_binary_frame=edge_binary_frame,
            )
            annotations[frame_index] = EdgeFrameAnnotation(
                frame_index=frame_index,
                polyline=polyline.polyline_xy,
                edge_mask=selection.edge_mask,
                source=EdgeAnnotationSource.DEXINED,
            )
            if frame_index == seed_frame_index:
                seed_polyline = np.asarray(polyline.polyline_xy, dtype=np.float64)

        if seed_polyline is None:
            raise ValueError("Seed frame polyline could not be extracted from DexiNed output.")

        edge_track_id = self._next_edge_track_id()
        return EdgeTrack(
            edge_track_id=edge_track_id,
            seed_frame_index=seed_frame_index,
            polygon_roi=polygon,
            seed_polyline=seed_polyline,
            annotations=annotations,
            label=f"Edge {edge_track_id}",
        )

    def _sync_track_overlays(self) -> None:
        if self._sequence is None:
            self.viewer.clear_track_seed_overlays()
            return
        self.viewer.set_tracks_and_edges(
            self._tracks,
            selected_track_id=self._selected_track_id,
            edge_tracks=self._edge_tracks,
            selected_edge_track_id=self._selected_edge_track_id,
        )

    def _find_track_by_id(self, track_id: int | None) -> ParticleTrack | None:
        if track_id is None:
            return None
        for track in self._tracks:
            if track.track_id == track_id:
                return track
        return None

    def _next_track_id(self) -> int:
        if not self._tracks:
            return 1
        return max(track.track_id for track in self._tracks) + 1

    def _next_edge_track_id(self) -> int:
        if not self._edge_tracks:
            return 1
        return max(track.edge_track_id for track in self._edge_tracks) + 1

    def _sync_bbox_track_context(self) -> None:
        if self._sequence is None:
            self.bbox_tools_panel.set_track_context(None, has_bbox_on_current_frame=False)
            return
        track = self._find_track_by_id(self._selected_track_id)
        if track is None:
            self.bbox_tools_panel.set_track_context(None, has_bbox_on_current_frame=False)
            return
        annotation = track.get_annotation(self._sequence.active_frame_index)
        self.bbox_tools_panel.set_track_context(
            track.track_id,
            has_bbox_on_current_frame=annotation is not None and annotation.bbox is not None,
        )

    def _ensure_results_dialog(self) -> TrackResultsDialog:
        if self._results_dialog is None:
            self._results_dialog = TrackResultsDialog(self)
            self._results_dialog.track_selected.connect(self._on_results_track_selected)
            self._results_dialog.track_delete_requested.connect(self._on_results_track_delete_requested)
        return self._results_dialog

    def _on_results_track_selected(self, track_id: object) -> None:
        if track_id is None:
            return
        self.track_list_panel.set_selected_track_id(int(track_id))
        self._on_track_selected(track_id)

    def _on_results_track_delete_requested(self, track_id: int) -> None:
        remaining_tracks = [track for track in self._tracks if track.track_id != track_id]
        if len(remaining_tracks) == len(self._tracks):
            return

        next_selected_track_id = self._selected_track_id
        if next_selected_track_id == track_id:
            next_selected_track_id = None

        self.set_tracks(remaining_tracks, selected_track_id=next_selected_track_id)
        self._show_current_frame(preserve_zoom=True)
        self.statusBar().showMessage(f"Deleted track {track_id}.", 3000)

    def _sync_results_dialog(self) -> None:
        if self._results_dialog is None:
            return
        self._results_dialog.set_context(self._sequence, self._tracks, selected_track_id=self._selected_track_id)

    def _sync_results_dialog_selection(self) -> None:
        if self._results_dialog is None:
            return
        self._results_dialog.set_selected_track_id(self._selected_track_id)

    def _has_results_data(self) -> bool:
        for track in self._tracks:
            for frame_index in track.frame_indices:
                annotation = track.get_annotation(frame_index)
                if annotation is None:
                    continue
                metrics = annotation.metrics
                if (
                    metrics.area_px is not None
                    and metrics.perimeter_px is not None
                    and metrics.intensity_sum is not None
                    and metrics.intensity_mean is not None
                    and metrics.intensity_max is not None
                ):
                    return True
        return False

    def _update_results_action_state(self) -> None:
        self._update_menu_action_state()

    def _current_sam2_input_frames(self) -> tuple[np.ndarray, str]:
        if self._denoised_frames is not None:
            return self._denoised_frames, "bm3d"
        if self._repair_frames is not None:
            return self._repair_frames, "repair"
        assert self._sequence is not None
        return self._sequence.raw_frames, "raw"

    def _build_sam2_input_for_track(
        self,
        track: ParticleTrack,
        *,
        start_frame_index: int | None = None,
        prompt_bbox: BBoxXYXY | None = None,
    ) -> Sam2RunInput:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")

        frames_source, source_view = self._current_sam2_input_frames()
        frame_offset = track.seed_frame_index if start_frame_index is None else int(start_frame_index)
        if frame_offset < track.seed_frame_index:
            raise ValueError("start_frame_index cannot be earlier than the seed frame.")
        frames = np.asarray(frames_source[frame_offset:], dtype=np.float32)
        bbox = track.seed_bbox if prompt_bbox is None else prompt_bbox
        center_x, center_y = bbox.center_xy
        return Sam2RunInput(
            track_id=track.track_id,
            frame_index_offset=frame_offset,
            frames=frames,
            query_box_xyxy=np.asarray(bbox.as_tuple(), dtype=np.float32),
            query_point_tyx=np.asarray([0.0, center_y, center_x], dtype=np.float32),
            source_view=source_view,
        )

    def _apply_sam2_output_to_track(self, track_id: int, run_output: Sam2RunOutput) -> None:
        track = self._find_track_by_id(track_id)
        if track is None:
            raise RuntimeError(f"Track {track_id} does not exist.")

        for local_frame_index in range(run_output.masks.shape[0]):
            annotation = self._annotation_from_sam2_frame(run_output, local_frame_index)
            track.add_annotation(annotation)

    def _resume_track_from_output(self, track_id: int, run_output: Sam2RunOutput, resume_frame: int) -> None:
        track = self._find_track_by_id(track_id)
        if track is None:
            raise RuntimeError(f"Track {track_id} does not exist.")
        track.drop_annotations_after(resume_frame)
        for local_frame_index in range(1, run_output.masks.shape[0]):
            annotation = self._annotation_from_sam2_frame(run_output, local_frame_index)
            track.add_annotation(annotation)

    def _annotation_from_sam2_frame(
        self,
        run_output: Sam2RunOutput,
        local_frame_index: int,
    ) -> TrackFrameAnnotation:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        frame_index = run_output.frame_index_offset + local_frame_index
        visible = bool(run_output.visible_mask[local_frame_index])
        mask = np.asarray(run_output.masks[local_frame_index], dtype=bool)
        bbox = None
        metrics = ParticleMetrics()
        if visible and run_output.mask_bboxes_xyxy is not None:
            bbox = self._bbox_from_output_array(run_output.mask_bboxes_xyxy[local_frame_index])
        if visible and np.any(mask):
            metrics = compute_particle_metrics(
                mask,
                self._sequence.get_frame(frame_index),
                pixel_size_nm=self._sequence.metadata.get_pixel_size_nm(),
            )

        return TrackFrameAnnotation(
            frame_index=frame_index,
            bbox=bbox,
            mask=mask,
            visibility=FrameVisibility.VISIBLE if visible else FrameVisibility.LOST,
            source=AnnotationSource.SAM2,
            metrics=metrics,
        )

    def _bbox_from_output_array(self, bbox_xyxy: np.ndarray) -> BBoxXYXY | None:
        bbox_array = np.asarray(bbox_xyxy, dtype=np.float32)
        if bbox_array.shape != (4,):
            return None
        x0, y0, x1, y1 = [float(value) for value in bbox_array.tolist()]
        if x1 <= x0 or y1 <= y0:
            return None
        return BBoxXYXY(x0, y0, x1, y1)
