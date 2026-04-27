from __future__ import annotations

import os
from pathlib import Path
import sys
import time

import numpy as np
from PyQt6.QtCore import QObject, QSignalBlocker, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
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

from nanotrack.analysis import compute_edge_metrics, compute_particle_metrics
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
    YoloDetection,
    YoloDetectionSet,
)
from nanotrack.io import load_stm_sequence
from nanotrack.persistence import NanoTrackSessionSnapshot, load_session_snapshot, save_session_snapshot
from nanotrack.processing import (
    run_bm3d_batch,
    run_bm3d_preview,
    run_horizontal_dropout_batch,
    run_horizontal_dropout_preview,
)
from nanotrack.edges import (
    DdnSubprocessBackend,
    DexiNedRunInput,
    DexiNedRunOutput,
    DexiNedSubprocessBackend,
    MugeBackendConfig,
    MugeSubprocessBackend,
    NbedSubprocessBackend,
    PidinetSubprocessBackend,
    TeedSubprocessBackend,
    UaedSubprocessBackend,
    assess_edge_geometry_quality,
    format_edge_geometry_review,
    hybrid_refine_polyline,
    refine_edge_polyline,
    sample_polyline_control_points,
)
from nanotrack.edges.polyline import dominant_edge_to_polyline, select_best_edge_polyline_candidate
from nanotrack.edges.selection import DominantEdgeSelection, select_dominant_edge
from nanotrack.sam2 import Sam2RunInput, Sam2RunOutput, Sam2SubprocessBackend
from nanotrack.trackers import (
    PointTrackerBackendConfig,
    PointTrackerRunInput,
    PointTrackerRunOutput,
    PointTrackerSubprocessBackend,
)
from nanotrack.yolo import YoloRuntime
from nanotrack.ui.dialogs import Bm3dPreviewDialog, EdgePreviewDialog, EdgeTrackResultsDialog, TrackResultsDialog
from nanotrack.ui.widgets import (
    BBoxToolsPanel,
    EdgeTrackListPanel,
    PolygonRoiToolsPanel,
    PreprocessingActionsPanel,
    SequenceMetadataPanel,
    SequenceViewerWidget,
    TrackListPanel,
    YoloSeedDetectionPanel,
)


class _DexiNedRunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(
        self,
        backend: (
            DexiNedSubprocessBackend
            | TeedSubprocessBackend
            | NbedSubprocessBackend
            | DdnSubprocessBackend
            | PidinetSubprocessBackend
            | UaedSubprocessBackend
            | MugeSubprocessBackend
        ),
        run_input: DexiNedRunInput,
    ):
        super().__init__()
        self._backend = backend
        self._run_input = run_input
        self._cancel_requested = False

    def run(self) -> None:
        try:
            output = self._backend.run(self._run_input)
        except Exception as exc:
            if self._cancel_requested:
                self.canceled.emit()
                return
            self.failed.emit(str(exc))
            return
        if self._cancel_requested:
            self.canceled.emit()
            return
        self.finished.emit(output)

    def cancel(self) -> None:
        self._cancel_requested = True
        cancel = getattr(self._backend, "cancel", None)
        if callable(cancel):
            cancel()


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


class _PointTrackerRunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, backend: PointTrackerSubprocessBackend, run_input: PointTrackerRunInput):
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


class NanoTrackMainWindow(QMainWindow):
    """Main window for MPP sequence browsing and navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._tracks: list[ParticleTrack] = []
        self._edge_tracks: list[EdgeTrack] = []
        self._selected_track_id: int | None = None
        self._selected_edge_track_id: int | None = None
        self._yolo_detections: YoloDetectionSet | None = None
        self._yolo_edit_target: YoloDetection | None = None
        self._draft_bboxes_by_frame: dict[int, BBoxXYXY] = {}
        self._draft_polygons_by_frame: dict[int, PolygonROI] = {}
        self._draft_edge_polylines_by_frame: dict[int, np.ndarray] = {}
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
        self._edge_results_dialog: EdgeTrackResultsDialog | None = None
        self._dexined_backend = DexiNedSubprocessBackend()
        self._teed_backend = TeedSubprocessBackend()
        self._nbed_backend = NbedSubprocessBackend()
        self._ddn_backend = DdnSubprocessBackend()
        self._pidinet_backend = PidinetSubprocessBackend()
        self._uaed_backend = UaedSubprocessBackend()
        self._muge_backend = MugeSubprocessBackend()
        self._point_tracker_backends = self._build_point_tracker_backends()
        self._dexined_progress_dialog: QProgressDialog | None = None
        self._dexined_thread: QThread | None = None
        self._dexined_worker: _DexiNedRunWorker | None = None
        self._edge_detector_cancel_requested = False
        self._active_edge_backend_label: str | None = None
        self._point_tracker_progress_dialog: QProgressDialog | None = None
        self._point_tracker_thread: QThread | None = None
        self._point_tracker_worker: _PointTrackerRunWorker | None = None
        self._pending_edge_preview_frame: np.ndarray | None = None
        self._pending_edge_preview_meta: dict[str, object] | None = None
        self._pending_edge_sequence_meta: dict[str, object] | None = None
        self._pending_edge_resume_meta: dict[str, object] | None = None
        self._pending_edge_hybrid_meta: dict[str, object] | None = None
        self._sam2_backend = Sam2SubprocessBackend()
        self._yolo_runtime = YoloRuntime()
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
        self.action_open_mpp = QAction("Open STM...", self)
        self.action_open_mpp.setToolTip("Load an MPP movie or STP/S94 frame series into NanoTrack")
        toolbar.addAction(self.action_open_mpp)
        self.action_open_mpp_reverse = QAction("Open Reverse...", self)
        self.action_open_mpp_reverse.setToolTip("Load an STM sequence with reversed frame order")
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
        self.action_open_edge_results = toolbar.addAction("View Edge Results...")
        self.action_open_edge_results.setToolTip("Open the quantitative edge-tracking results window")
        self.action_open_edge_results.setEnabled(False)

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
        self.chk_exclude_frame = QCheckBox("Exclude From Analysis", self)
        self.chk_exclude_frame.setToolTip(
            "Exclude the current frame from tracks, edge tracks, metrics, exports, and future analysis runs."
        )
        self.btn_next = QPushButton("Next Frame", self)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.spin_frame)
        nav_layout.addWidget(self.chk_exclude_frame)
        nav_layout.addWidget(self.btn_next)

        layout.addWidget(nav_row)

        self.sidebar_content = QWidget(self)
        sidebar_layout = QVBoxLayout(self.sidebar_content)
        self.metadata_panel = SequenceMetadataPanel(self.sidebar_content)
        self.track_list_panel = TrackListPanel(self.sidebar_content)
        self.edge_track_list_panel = EdgeTrackListPanel(self.sidebar_content)
        self.bbox_tools_panel = BBoxToolsPanel(self.sidebar_content)
        self.yolo_panel = YoloSeedDetectionPanel(self.sidebar_content)
        self.polygon_tools_panel = PolygonRoiToolsPanel(self.sidebar_content)
        self.preprocessing_panel = PreprocessingActionsPanel(self.sidebar_content)
        sidebar_layout.addWidget(self.metadata_panel, 0)
        sidebar_layout.addWidget(self.track_list_panel, 1)
        sidebar_layout.addWidget(self.edge_track_list_panel, 1)
        sidebar_layout.addWidget(self.bbox_tools_panel, 0)
        sidebar_layout.addWidget(self.yolo_panel, 0)
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
        self.action_open_edge_results.triggered.connect(self._on_open_edge_results_requested)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)
        self.spin_frame.valueChanged.connect(self._on_spin_frame_selected)
        self.chk_exclude_frame.toggled.connect(self._on_exclude_frame_toggled)
        self.btn_prev.clicked.connect(self._on_prev_frame)
        self.btn_next.clicked.connect(self._on_next_frame)
        self.viewer.bbox_changed.connect(self._on_viewer_bbox_changed)
        self.viewer.polygon_changed.connect(self._on_viewer_polygon_changed)
        self.viewer.edge_polyline_changed.connect(self._on_viewer_edge_polyline_changed)
        self.viewer.yolo_detection_clicked.connect(self._on_yolo_detection_clicked)
        self.bbox_tools_panel.place_mode_toggled.connect(self._on_bbox_place_mode_toggled)
        self.bbox_tools_panel.default_size_changed.connect(self._on_bbox_default_size_changed)
        self.bbox_tools_panel.add_seed_requested.connect(self._on_add_seed_requested)
        self.bbox_tools_panel.clear_requested.connect(self._on_clear_current_bbox_requested)
        self.bbox_tools_panel.load_track_bbox_requested.connect(self._on_load_track_bbox_requested)
        self.bbox_tools_panel.save_correction_requested.connect(self._on_save_correction_requested)
        self.bbox_tools_panel.resume_track_requested.connect(self._on_resume_track_requested)
        self.yolo_panel.detect_current_requested.connect(self._on_yolo_detect_current_requested)
        self.yolo_panel.detect_all_requested.connect(self._on_yolo_detect_all_requested)
        self.yolo_panel.scale_current_requested.connect(self._on_yolo_scale_current_requested)
        self.yolo_panel.scale_all_requested.connect(self._on_yolo_scale_all_requested)
        self.yolo_panel.load_selected_bbox_requested.connect(self._on_yolo_load_selected_bbox_requested)
        self.yolo_panel.save_edited_bbox_requested.connect(self._on_yolo_save_edited_bbox_requested)
        self.yolo_panel.select_all_current_requested.connect(self._on_yolo_select_all_current_requested)
        self.yolo_panel.deselect_all_current_requested.connect(self._on_yolo_deselect_all_current_requested)
        self.yolo_panel.select_all_global_requested.connect(self._on_yolo_select_all_global_requested)
        self.yolo_panel.deselect_all_global_requested.connect(self._on_yolo_deselect_all_global_requested)
        self.yolo_panel.convert_selected_current_requested.connect(self._on_yolo_convert_selected_current_requested)
        self.yolo_panel.convert_selected_all_requested.connect(self._on_yolo_convert_selected_all_requested)
        self.yolo_panel.clear_detections_requested.connect(self._on_yolo_clear_detections_requested)
        self.polygon_tools_panel.draw_mode_toggled.connect(self._on_polygon_draw_mode_toggled)
        self.polygon_tools_panel.finish_requested.connect(self._on_finish_polygon_requested)
        self.polygon_tools_panel.clear_requested.connect(self._on_clear_current_polygon_requested)
        self.polygon_tools_panel.preview_requested.connect(self._on_edge_preview_requested)
        self.polygon_tools_panel.run_sequence_requested.connect(self._on_edge_sequence_requested)
        self.polygon_tools_panel.load_edge_requested.connect(self._on_load_current_edge_requested)
        self.polygon_tools_panel.save_edge_correction_requested.connect(self._on_save_edge_correction_requested)
        self.polygon_tools_panel.resume_edge_requested.connect(self._on_resume_edge_requested)
        self.polygon_tools_panel.redetect_edge_requested.connect(self._on_redetect_edge_requested)
        self.polygon_tools_panel.redetect_edge_range_requested.connect(self._on_redetect_edge_range_requested)
        self.polygon_tools_panel.hybrid_stabilize_requested.connect(self._on_edge_hybrid_requested)
        self.track_list_panel.track_selected.connect(self._on_track_selected)
        self.track_list_panel.run_selected_requested.connect(self._on_run_sam2_for_selected_requested)
        self.track_list_panel.run_all_requested.connect(self._on_run_sam2_for_all_requested)
        self.edge_track_list_panel.track_selected.connect(self._on_edge_track_selected)
        self.edge_track_list_panel.track_delete_requested.connect(self._on_edge_track_delete_requested)
        self.preprocessing_panel.repair_preview_requested.connect(self._on_repair_preview_requested)
        self.preprocessing_panel.repair_apply_all_requested.connect(self._on_repair_apply_all_requested)
        self.preprocessing_panel.preview_requested.connect(self._on_bm3d_preview_requested)
        self.preprocessing_panel.apply_all_requested.connect(self._on_bm3d_apply_all_requested)
        self.preprocessing_panel.show_denoised_toggled.connect(self._on_show_denoised_toggled)
        self._on_bbox_default_size_changed(*self.bbox_tools_panel.default_size_px())

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)
        self.spin_frame.setEnabled(enabled)
        self.chk_exclude_frame.setEnabled(enabled)
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.bbox_tools_panel.set_sequence_loaded(enabled)
        self.yolo_panel.set_sequence_loaded(enabled)
        self.yolo_panel.set_detect_all_available(enabled)
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

        with QSignalBlocker(self.chk_exclude_frame):
            self.chk_exclude_frame.setChecked(self._sequence.is_frame_excluded(current))

        self.btn_prev.setEnabled(current > 0)
        self.btn_next.setEnabled(current < total - 1)
        self.yolo_panel.set_frame_context(current, total)
        exclusion_suffix = " | excluded" if self._sequence.is_frame_excluded(current) else ""
        self.lbl_frame.setText(f"Frame: {current + 1} / {total}{exclusion_suffix}")
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
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        self._sync_navigation_controls()
        excluded_suffix = " | excluded from analysis" if self._sequence.is_frame_excluded(self._sequence.active_frame_index) else ""
        self.statusBar().showMessage(
            f"{Path(self._sequence.source_path).name} | frame {self._sequence.active_frame_index + 1}/{self._sequence.frame_count}{excluded_suffix}",
            3000,
        )

    def set_sequence(self, sequence: STMSequence) -> None:
        self._sequence = sequence
        self._selected_track_id = None
        self._selected_edge_track_id = None
        self._edge_tracks = []
        self._yolo_detections = None
        self._yolo_edit_target = None
        self._draft_bboxes_by_frame = {}
        self._draft_polygons_by_frame = {}
        self._draft_edge_polylines_by_frame = {}
        self._clear_all_preprocessing_cache()
        self._set_bbox_place_mode(False)
        self._set_polygon_draw_mode(False)
        self.viewer.set_sequence(sequence)
        self._reset_preview_state(close_dialog=True)
        self._sync_navigation_controls()
        self._sync_current_bbox_ui()
        self._sync_current_polygon_ui()
        self.yolo_panel.clear_detection_state()
        self.yolo_panel.set_edit_actions_available(load_available=False, save_available=False)
        self.yolo_panel.set_conversion_actions_available(current_available=False, global_available=False)
        self._update_menu_action_state()
        self._sync_edge_results_dialog()
        self.statusBar().showMessage(
            (
                f"{Path(sequence.source_path).name} | frame {sequence.active_frame_index + 1}/{sequence.frame_count}"
                f"{' | excluded from analysis' if sequence.is_frame_excluded(sequence.active_frame_index) else ''}"
            ),
            3000,
        )
        self.set_tracks([])
        self.set_edge_tracks([])

    def load_sequence_from_path(self, file_path: str | list[str], *, reverse_frame_order: bool = False) -> None:
        sequence = load_stm_sequence(file_path, reverse_frame_order=reverse_frame_order)
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

    def current_draft_edge_polyline(self) -> np.ndarray | None:
        if self._sequence is None:
            return None
        polyline = self._draft_edge_polylines_by_frame.get(self._sequence.active_frame_index)
        if polyline is None:
            return None
        return np.asarray(polyline, dtype=np.float64)

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

    def set_edge_tracks(self, tracks: list[EdgeTrack], *, selected_track_id: int | None = None) -> None:
        self._edge_tracks = list(tracks)
        valid_track_ids = {track.edge_track_id for track in self._edge_tracks}
        if selected_track_id is not None and selected_track_id in valid_track_ids:
            self._selected_edge_track_id = selected_track_id
        elif self._selected_edge_track_id not in valid_track_ids:
            self._selected_edge_track_id = None
        self.edge_track_list_panel.set_tracks(self._edge_tracks, selected_track_id=self._selected_edge_track_id)
        self._update_results_action_state()
        self._sync_edge_results_dialog()
        self._sync_track_overlays()
        self._sync_edge_track_context()

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

    def current_edge_results_dialog(self) -> EdgeTrackResultsDialog | None:
        return self._edge_results_dialog

    def current_yolo_detection_set(self) -> YoloDetectionSet | None:
        return self._yolo_detections

    def _build_point_tracker_backends(self) -> dict[str, PointTrackerSubprocessBackend]:
        worker_root = Path(__file__).resolve().parents[1] / "trackers"
        model_specs = {
            "tapir": {
                "env_prefix": "TAPIR",
                "worker_script": worker_root / "run_tapir_subprocess.py",
            },
            "locotrack": {
                "env_prefix": "LOCOTRACK",
                "worker_script": worker_root / "run_locotrack_subprocess.py",
            },
            "trackonr": {
                "env_prefix": "TRACKONR",
                "worker_script": worker_root / "run_trackonr_subprocess.py",
            },
        }
        backends: dict[str, PointTrackerSubprocessBackend] = {}
        for model_name, spec in model_specs.items():
            env_prefix = spec["env_prefix"]
            config = PointTrackerBackendConfig(
                model_name=model_name,
                python_executable=os.environ.get(f"NANOTRACK_{env_prefix}_PYTHON", sys.executable),
                worker_script=spec["worker_script"],
                checkpoint_path=os.environ.get(f"NANOTRACK_{env_prefix}_CHECKPOINT"),
                repo_path=os.environ.get(f"NANOTRACK_{env_prefix}_REPO"),
                device=os.environ.get(f"NANOTRACK_{env_prefix}_DEVICE", "auto"),
                timeout_sec=float(os.environ.get(f"NANOTRACK_{env_prefix}_TIMEOUT_SEC", "300.0")),
                working_directory=worker_root,
            )
            backends[model_name] = PointTrackerSubprocessBackend(config)
        return backends

    def _selected_edge_detector_backend_key(self) -> str:
        return self.polygon_tools_panel.edge_backend()

    def _format_edge_detector_backend_label(self, backend_key: str) -> str:
        normalized = str(backend_key).strip().lower()
        if normalized == "teed":
            return "TEED"
        if normalized == "nbed":
            return "NBED"
        if normalized == "ddn":
            return "DDN"
        if normalized == "pidinet":
            return "PiDiNet"
        if normalized == "uaed":
            return "UAED"
        if normalized == "muge":
            return "MuGE"
        if normalized == "dexined":
            return "DexiNed"
        return str(backend_key)

    def _selected_edge_detector_backend_label(self) -> str:
        return self._format_edge_detector_backend_label(self._selected_edge_detector_backend_key())

    def _selected_edge_detector_backend(
        self,
    ) -> (
        DexiNedSubprocessBackend
        | TeedSubprocessBackend
        | NbedSubprocessBackend
        | DdnSubprocessBackend
        | PidinetSubprocessBackend
        | UaedSubprocessBackend
        | MugeSubprocessBackend
    ):
        backend_key = self._selected_edge_detector_backend_key()
        if backend_key == "teed":
            return self._teed_backend
        if backend_key == "nbed":
            return self._nbed_backend
        if backend_key == "ddn":
            return self._ddn_backend
        if backend_key == "pidinet":
            return self._pidinet_backend
        if backend_key == "uaed":
            return self._uaed_backend
        if backend_key == "muge":
            self._sync_muge_backend_config()
            return self._muge_backend
        return self._dexined_backend

    def _sync_muge_backend_config(self) -> None:
        current = self._muge_backend.config
        self._muge_backend.config = MugeBackendConfig(
            python_executable=current.python_executable,
            worker_script=current.worker_script,
            checkpoint_path=current.checkpoint_path,
            repo_path=current.repo_path,
            distribution=current.distribution,
            device=current.device,
            granularity=self.polygon_tools_panel.muge_granularity(),
            timeout_sec=current.timeout_sec,
            working_directory=current.working_directory,
        )

    def _current_edge_detector_backend_label(self) -> str:
        if self._active_edge_backend_label:
            return self._active_edge_backend_label
        return self._selected_edge_detector_backend_label()

    def _update_menu_action_state(self) -> None:
        busy = self._is_preprocessing or self._is_tracking
        self.action_open_mpp.setEnabled(not busy)
        self.action_open_mpp_reverse.setEnabled(not busy)
        self.action_open_session.setEnabled(not busy)
        self.action_save_session.setEnabled(self._sequence is not None and not busy)
        self.action_open_results.setEnabled(self._has_results_data() and not busy)
        self.action_open_edge_results.setEnabled(self._has_edge_results_data() and not busy)

    def current_session_snapshot(self) -> NanoTrackSessionSnapshot | None:
        if self._sequence is None:
            return None
        return NanoTrackSessionSnapshot(
            sequence=self._sequence,
            tracks=self.current_tracks(),
            edge_tracks=self.current_edge_tracks(),
            yolo_detections=self._yolo_detections,
            selected_track_id=self._selected_track_id,
            selected_edge_track_id=self._selected_edge_track_id,
            draft_bboxes_by_frame=dict(self._draft_bboxes_by_frame),
            draft_polygons_by_frame=dict(self._draft_polygons_by_frame),
            draft_edge_polylines_by_frame={
                frame_index: np.asarray(polyline, dtype=np.float64)
                for frame_index, polyline in self._draft_edge_polylines_by_frame.items()
            },
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
        self._open_stm_sequence(reverse_frame_order=True)

    def _open_mpp_sequence(self, *, reverse_frame_order: bool) -> None:
        self._open_stm_sequence(reverse_frame_order=reverse_frame_order)

    def _open_stm_sequence(self, *, reverse_frame_order: bool) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open STM sequence (reverse)" if reverse_frame_order else "Open STM sequence",
            "",
            (
                "STM files (*.mpp *.MPP *.stp *.STP *.s94 *.S94);;"
                "MPP movies (*.mpp *.MPP);;"
                "STP/S94 frame series (*.stp *.STP *.s94 *.S94);;"
                "All files (*.*)"
            ),
        )
        if not paths:
            return

        source = paths[0] if len(paths) == 1 else list(paths)
        try:
            self.load_sequence_from_path(source, reverse_frame_order=reverse_frame_order)
        except Exception as exc:
            source_label = "\n".join(paths)
            QMessageBox.critical(self, "Load error", f"Cannot load STM sequence:\n{source_label}\n\n{exc}")
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

    def _on_open_edge_results_requested(self) -> None:
        if not self._has_edge_results_data():
            return
        dialog = self._ensure_edge_results_dialog()
        dialog.set_context(self._sequence, self._edge_tracks, selected_track_id=self._selected_edge_track_id)
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
        self._draft_polygons_by_frame = dict(snapshot.draft_polygons_by_frame)
        self._draft_edge_polylines_by_frame = {
            frame_index: np.asarray(polyline, dtype=np.float64)
            for frame_index, polyline in snapshot.draft_edge_polylines_by_frame.items()
        }
        self._yolo_detections = snapshot.yolo_detections
        self._yolo_edit_target = None
        self._update_cached_preprocessing_availability()
        self._show_denoised_in_viewer = bool(snapshot.show_denoised_in_viewer and self._has_any_preprocessing_cache())
        with QSignalBlocker(self.preprocessing_panel.chk_show_denoised):
            self.preprocessing_panel.chk_show_denoised.setChecked(self._show_denoised_in_viewer)
        self.set_tracks(snapshot.tracks, selected_track_id=snapshot.selected_track_id)
        self.set_edge_tracks(snapshot.edge_tracks, selected_track_id=snapshot.selected_edge_track_id)
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

    def _on_exclude_frame_toggled(self, checked: bool) -> None:
        if self._sequence is None:
            return

        frame_index = int(self._sequence.active_frame_index)
        if self._sequence.is_frame_excluded(frame_index) == bool(checked):
            return

        self._sequence.set_frame_excluded(frame_index, bool(checked))
        if checked:
            self._draft_bboxes_by_frame.pop(frame_index, None)
            self._draft_polygons_by_frame.pop(frame_index, None)
            self._draft_edge_polylines_by_frame.pop(frame_index, None)
            removed_yolo_detections = self._prune_excluded_frame_from_yolo_detections(frame_index)
            removed_particle_tracks, removed_particle_annotations = self._prune_excluded_frame_from_tracks(frame_index)
            removed_edge_tracks, removed_edge_annotations = self._prune_excluded_frame_from_edge_tracks(frame_index)
            self._reset_preview_state(close_dialog=True)
            self._show_current_frame(preserve_zoom=True)
            self.statusBar().showMessage(
                (
                    f"Excluded frame {frame_index + 1} from analysis "
                    f"(removed {removed_yolo_detections} YOLO detections, "
                    f"{removed_particle_annotations} particle annotations, {removed_edge_annotations} edge annotations, "
                    f"dropped {removed_particle_tracks} particle tracks, {removed_edge_tracks} edge tracks)."
                ),
                5000,
            )
            return

        self._show_current_frame(preserve_zoom=True)
        self.statusBar().showMessage(
            f"Frame {frame_index + 1} restored for future analysis runs.", 4000
        )

    def _ensure_current_frame_included(self, action_label: str) -> bool:
        if self._sequence is None:
            return False
        frame_index = int(self._sequence.active_frame_index)
        if not self._sequence.is_frame_excluded(frame_index):
            return True
        QMessageBox.warning(
            self,
            "Frame excluded from analysis",
            (
                f"Frame {frame_index + 1} is currently excluded from analysis. "
                f"Restore it before using: {action_label}."
            ),
        )
        return False

    def _prune_excluded_frame_from_tracks(self, frame_index: int) -> tuple[int, int]:
        removed_tracks = 0
        removed_annotations = 0
        remaining_tracks: list[ParticleTrack] = []
        for track in self._tracks:
            if track.seed_frame_index == frame_index:
                removed_tracks += 1
                continue
            if frame_index in track.annotations:
                track.annotations.pop(frame_index, None)
                removed_annotations += 1
            remaining_tracks.append(track)
        next_selected_track_id = self._selected_track_id if any(
            track.track_id == self._selected_track_id for track in remaining_tracks
        ) else (remaining_tracks[0].track_id if remaining_tracks else None)
        self.set_tracks(remaining_tracks, selected_track_id=next_selected_track_id)
        return removed_tracks, removed_annotations

    def _prune_excluded_frame_from_yolo_detections(self, frame_index: int) -> int:
        if self._yolo_detections is None:
            return 0
        removed = len(self._yolo_detections.get_detections(frame_index))
        if removed == 0:
            return 0
        if self._yolo_edit_target is not None and self._yolo_edit_target.frame_index == int(frame_index):
            self._yolo_edit_target = None
        self._yolo_detections.clear_frame(frame_index)
        if self._yolo_detections.detection_count == 0:
            self._yolo_detections = None
        self._sync_yolo_detection_ui()
        return removed

    def _on_yolo_detect_current_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        if not self._ensure_current_frame_included("Detect YOLO on Current Frame"):
            return

        model_path = self.yolo_panel.current_model_path()
        model_name = self.yolo_panel.current_model_name()
        if model_path is None or model_name is None:
            QMessageBox.warning(
                self,
                "YOLO model missing",
                "No local YOLO checkpoint is available in nanotrack/yolo_models.",
            )
            return

        frame_index = int(self._sequence.active_frame_index)
        input_frame, source_view = self._current_yolo_input_frame()
        self._set_tracking_busy(True)
        self.statusBar().showMessage(
            f"Running YOLO on frame {frame_index + 1} using {model_name}...",
            0,
        )
        QApplication.processEvents()
        try:
            runtime_detections = self._yolo_runtime.predict_frame(
                input_frame,
                model_path=model_path,
                conf_threshold=self.yolo_panel.confidence_threshold(),
                iou_threshold=self.yolo_panel.nms_iou_threshold(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "YOLO detection error", str(exc))
            return
        finally:
            self._set_tracking_busy(False)

        detections = [
            YoloDetection(
                frame_index=frame_index,
                bbox=detection.bbox,
                confidence=detection.confidence,
                selected=True,
                model_name=model_name,
            )
            for detection in runtime_detections
        ]
        self._upsert_current_frame_yolo_detections(model_name=model_name, frame_index=frame_index, detections=detections)
        self.statusBar().showMessage(
            (
                f"YOLO detected {len(detections)} bbox proposals on frame {frame_index + 1} "
                f"using {model_name} ({source_view})."
            ),
            4000,
        )

    def _on_yolo_detect_all_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        model_path = self.yolo_panel.current_model_path()
        model_name = self.yolo_panel.current_model_name()
        if model_path is None or model_name is None:
            QMessageBox.warning(
                self,
                "YOLO model missing",
                "No local YOLO checkpoint is available in nanotrack/yolo_models.",
            )
            return

        input_frames, source_view = self._current_yolo_input_frames()
        included_frame_indices = self._sequence.included_frame_indices()
        if not included_frame_indices:
            QMessageBox.warning(
                self,
                "No frames available",
                "All frames are currently excluded from analysis. Restore at least one frame before running YOLO.",
            )
            return

        progress = QProgressDialog("Running YOLO on all included frames...", "", 0, len(included_frame_indices), self)
        progress.setWindowTitle("YOLO Detection")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)

        self._set_tracking_busy(True)
        self.statusBar().showMessage(
            f"Running YOLO on {len(included_frame_indices)} frames using {model_name}...",
            0,
        )
        progress.show()
        QApplication.processEvents()

        detections_by_frame: dict[int, list[YoloDetection]] = {}
        try:
            for processed_index, frame_index in enumerate(included_frame_indices, start=1):
                runtime_detections = self._yolo_runtime.predict_frame(
                    input_frames[frame_index],
                    model_path=model_path,
                    conf_threshold=self.yolo_panel.confidence_threshold(),
                    iou_threshold=self.yolo_panel.nms_iou_threshold(),
                )
                detections_by_frame[frame_index] = [
                    YoloDetection(
                        frame_index=frame_index,
                        bbox=detection.bbox,
                        confidence=detection.confidence,
                        selected=True,
                        model_name=model_name,
                    )
                    for detection in runtime_detections
                ]
                progress.setValue(processed_index)
                self.statusBar().showMessage(
                    (
                        f"Running YOLO on frame {frame_index + 1}/{self._sequence.frame_count} "
                        f"({processed_index}/{len(included_frame_indices)})..."
                    ),
                    0,
                )
                QApplication.processEvents()
        except Exception as exc:
            QMessageBox.critical(self, "YOLO detection error", str(exc))
            return
        finally:
            progress.close()
            self._set_tracking_busy(False)

        self._replace_yolo_detections(
            model_name=model_name,
            detections_by_frame=detections_by_frame,
        )
        self.statusBar().showMessage(
            (
                f"YOLO detected {self._yolo_detections.detection_count if self._yolo_detections is not None else 0} "
                f"bbox proposals on {len(included_frame_indices)} frames using {model_name} ({source_view})."
            ),
            5000,
        )

    def _current_yolo_input_frame(self) -> tuple[np.ndarray, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        frames_source, source_view = self._current_sam2_input_frames()
        return np.asarray(frames_source[self._sequence.active_frame_index], dtype=np.float32), source_view

    def _current_yolo_input_frames(self) -> tuple[np.ndarray, str]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        frames_source, source_view = self._current_sam2_input_frames()
        return np.asarray(frames_source, dtype=np.float32), source_view

    def _upsert_current_frame_yolo_detections(
        self,
        *,
        model_name: str,
        frame_index: int,
        detections: list[YoloDetection],
    ) -> None:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        if (
            self._yolo_detections is None
            or self._yolo_detections.model_name != model_name
            or self._yolo_detections.source_path != self._sequence.source_path
        ):
            self._yolo_detections = YoloDetectionSet(
                model_name=model_name,
                source_path=self._sequence.source_path,
            )
        self._yolo_edit_target = None
        self._yolo_detections.set_detections(frame_index, detections)
        if self._yolo_detections.detection_count == 0:
            self._yolo_detections = None
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()

    def _replace_yolo_detections(
        self,
        *,
        model_name: str,
        detections_by_frame: dict[int, list[YoloDetection]],
    ) -> None:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        self._yolo_edit_target = None
        normalized = {
            int(frame_index): list(frame_detections)
            for frame_index, frame_detections in detections_by_frame.items()
            if frame_detections
        }
        if normalized:
            self._yolo_detections = YoloDetectionSet(
                model_name=model_name,
                source_path=self._sequence.source_path,
                detections_by_frame=normalized,
            )
        else:
            self._yolo_detections = None
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()

    def _sync_yolo_detection_ui(self) -> None:
        if self._sequence is None:
            self.yolo_panel.set_frame_context(None, None)
            self.yolo_panel.set_current_selection_actions_available(False)
            self.yolo_panel.set_global_selection_actions_available(False)
            self.yolo_panel.set_edit_actions_available(load_available=False, save_available=False)
            self.yolo_panel.set_conversion_actions_available(current_available=False, global_available=False)
            self.yolo_panel.set_clear_action_available(False)
            self.yolo_panel.clear_detection_state()
            return

        current_frame_index = int(self._sequence.active_frame_index)
        self.yolo_panel.set_frame_context(current_frame_index, self._sequence.frame_count)
        if self._yolo_detections is None:
            self.yolo_panel.set_current_selection_actions_available(False)
            self.yolo_panel.set_global_selection_actions_available(False)
            self.yolo_panel.set_edit_actions_available(load_available=False, save_available=False)
            self.yolo_panel.set_conversion_actions_available(current_available=False, global_available=False)
            self.yolo_panel.set_clear_action_available(False)
            self.yolo_panel.clear_detection_state()
            return

        current_selected_count = self._yolo_detections.selected_detection_count(current_frame_index)
        has_current_draft_bbox = self.current_draft_bbox() is not None
        save_edit_available = (
            self._yolo_edit_target is not None
            and self._yolo_edit_target.frame_index == current_frame_index
            and has_current_draft_bbox
        )
        self.yolo_panel.set_current_selection_actions_available(True)
        self.yolo_panel.set_global_selection_actions_available(True)
        self.yolo_panel.set_edit_actions_available(
            load_available=current_selected_count == 1,
            save_available=save_edit_available,
        )
        self.yolo_panel.set_conversion_actions_available(
            current_available=self._yolo_edit_target is None,
            global_available=self._yolo_edit_target is None,
        )
        self.yolo_panel.set_clear_action_available(True)
        self.yolo_panel.set_detection_counts(
            current_detection_count=len(self._yolo_detections.get_detections(current_frame_index)),
            total_detection_count=self._yolo_detections.detection_count,
            current_selected_count=current_selected_count,
            total_selected_count=self._yolo_detections.selected_detection_count(),
        )

    def _on_yolo_load_selected_bbox_requested(self) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return
        frame_index = int(self._sequence.active_frame_index)
        selected_detections = self._yolo_detections.selected_detections(frame_index)
        if len(selected_detections) != 1:
            QMessageBox.warning(
                self,
                "YOLO edit unavailable",
                "Select exactly one YOLO detection on the current frame before loading it for manual editing.",
            )
            return

        detection = selected_detections[0]
        self._set_bbox_place_mode(False)
        self._yolo_edit_target = detection
        self._draft_bboxes_by_frame[frame_index] = detection.bbox
        self._sync_current_bbox_ui()
        self._sync_yolo_detection_ui()
        self.statusBar().showMessage(
            f"Loaded selected YOLO bbox on frame {frame_index + 1} for manual editing.",
            3000,
        )

    def _on_yolo_save_edited_bbox_requested(self) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return
        if not self._ensure_current_frame_included("Save Edited YOLO BBox"):
            return

        frame_index = int(self._sequence.active_frame_index)
        current_bbox = self.current_draft_bbox()
        target = self._yolo_edit_target
        if current_bbox is None or target is None:
            return
        if target.frame_index != frame_index:
            QMessageBox.warning(
                self,
                "YOLO edit frame mismatch",
                "The loaded YOLO detection belongs to a different frame. Load the detection again on the current frame.",
            )
            return
        if all(detection is not target for detection in self._yolo_detections.get_detections(frame_index)):
            self._yolo_edit_target = None
            self._sync_yolo_detection_ui()
            QMessageBox.warning(
                self,
                "YOLO detection missing",
                "The loaded YOLO detection is no longer available on the current frame.",
            )
            return

        target.bbox = current_bbox
        self._draft_bboxes_by_frame.pop(frame_index, None)
        self._yolo_edit_target = None
        self._sync_current_bbox_ui()
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        self.statusBar().showMessage(
            f"Saved edited YOLO bbox on frame {frame_index + 1}.",
            3000,
        )

    def _on_yolo_select_all_current_requested(self) -> None:
        self._set_yolo_current_selection_state(True)

    def _on_yolo_deselect_all_current_requested(self) -> None:
        self._set_yolo_current_selection_state(False)

    def _on_yolo_convert_selected_current_requested(self) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return
        if not self._ensure_current_frame_included("Convert Selected YOLO Detections to Seeds"):
            return
        if self._yolo_edit_target is not None:
            QMessageBox.warning(
                self,
                "Finish YOLO bbox editing",
                "Save or clear the currently edited YOLO bbox before converting detections to seeds.",
            )
            return

        frame_index = int(self._sequence.active_frame_index)
        frame_detections = self._yolo_detections.get_detections(frame_index)
        selected_detections = [detection for detection in frame_detections if detection.selected]
        if not selected_detections:
            return

        created_tracks: list[ParticleTrack] = []
        next_track_id = self._next_track_id()
        for offset, detection in enumerate(selected_detections):
            created_tracks.append(
                ParticleTrack(
                    track_id=next_track_id + offset,
                    seed_frame_index=frame_index,
                    seed_bbox=detection.bbox,
                )
            )

        remaining_detections = [detection for detection in frame_detections if not detection.selected]
        self._yolo_detections.set_detections(frame_index, remaining_detections)
        if self._yolo_detections.detection_count == 0:
            self._yolo_detections = None

        self.set_tracks(self._tracks + created_tracks, selected_track_id=created_tracks[-1].track_id)
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        self.statusBar().showMessage(
            f"Converted {len(created_tracks)} selected YOLO detection(s) on frame {frame_index + 1} to seeds.",
            3500,
        )

    def _on_yolo_convert_selected_all_requested(self) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return
        if self._yolo_edit_target is not None:
            QMessageBox.warning(
                self,
                "Finish YOLO bbox editing",
                "Save or clear the currently edited YOLO bbox before converting detections to seeds.",
            )
            return

        selected_by_frame = {
            frame_index: [detection for detection in self._yolo_detections.get_detections(frame_index) if detection.selected]
            for frame_index in self._yolo_detections.frame_indices
        }
        selected_by_frame = {
            frame_index: detections
            for frame_index, detections in selected_by_frame.items()
            if detections
        }
        if not selected_by_frame:
            return

        created_tracks: list[ParticleTrack] = []
        next_track_id = self._next_track_id()
        next_offset = 0
        for frame_index in sorted(selected_by_frame):
            for detection in selected_by_frame[frame_index]:
                created_tracks.append(
                    ParticleTrack(
                        track_id=next_track_id + next_offset,
                        seed_frame_index=frame_index,
                        seed_bbox=detection.bbox,
                    )
                )
                next_offset += 1

        for frame_index in sorted(selected_by_frame):
            frame_detections = self._yolo_detections.get_detections(frame_index)
            remaining_detections = [detection for detection in frame_detections if not detection.selected]
            self._yolo_detections.set_detections(frame_index, remaining_detections)

        if self._yolo_detections.detection_count == 0:
            self._yolo_detections = None

        self.set_tracks(self._tracks + created_tracks, selected_track_id=created_tracks[-1].track_id)
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        self.statusBar().showMessage(
            f"Converted {len(created_tracks)} selected YOLO detection(s) across all frames to seeds.",
            3500,
        )

    def _on_yolo_clear_detections_requested(self) -> None:
        if self._yolo_detections is None:
            return

        cleared_count = self._yolo_detections.detection_count
        if cleared_count <= 0:
            return

        cleared_current_draft = False
        if self._yolo_edit_target is not None:
            edit_frame_index = int(self._yolo_edit_target.frame_index)
            if self._draft_bboxes_by_frame.pop(edit_frame_index, None) is not None:
                cleared_current_draft = self._sequence is not None and edit_frame_index == int(self._sequence.active_frame_index)
            self._yolo_edit_target = None

        self._yolo_detections = None
        if cleared_current_draft:
            self._sync_current_bbox_ui()
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        self.statusBar().showMessage(
            f"Cleared {cleared_count} YOLO detection proposal(s). Existing seeds were left unchanged.",
            3500,
        )

    def _on_yolo_scale_current_requested(self) -> None:
        self._scale_yolo_detections(current_only=True)

    def _on_yolo_scale_all_requested(self) -> None:
        self._scale_yolo_detections(current_only=False)

    def _on_yolo_select_all_global_requested(self) -> None:
        self._set_yolo_global_selection_state(True)

    def _on_yolo_deselect_all_global_requested(self) -> None:
        self._set_yolo_global_selection_state(False)

    def _on_yolo_detection_clicked(self, detection_index: int) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return
        frame_index = int(self._sequence.active_frame_index)
        frame_detections = self._yolo_detections.get_detections(frame_index)
        if not 0 <= int(detection_index) < len(frame_detections):
            return

        detection = frame_detections[int(detection_index)]
        detection.selected = not detection.selected
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        state_label = "selected" if detection.selected else "deselected"
        self.statusBar().showMessage(
            f"YOLO detection on frame {frame_index + 1} {state_label} ({detection.confidence:.2f}).",
            2500,
        )

    def _set_yolo_current_selection_state(self, selected: bool) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return
        frame_index = int(self._sequence.active_frame_index)
        if not self._yolo_detections.get_detections(frame_index):
            return
        self._yolo_detections.set_selected(frame_index, selected)
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        state_label = "selected" if selected else "deselected"
        self.statusBar().showMessage(
            f"All YOLO detections on frame {frame_index + 1} {state_label}.",
            2500,
        )

    def _scale_yolo_detections(self, *, current_only: bool) -> None:
        if self._sequence is None or self._yolo_detections is None:
            return

        multiplier = self.yolo_panel.bbox_scale_multiplier()
        frame_height, frame_width = self._sequence.frame_shape
        frame_indices = (
            [int(self._sequence.active_frame_index)]
            if current_only
            else list(self._yolo_detections.frame_indices)
        )

        scaled_count = 0
        for frame_index in frame_indices:
            frame_detections = self._yolo_detections.get_detections(frame_index)
            if not frame_detections:
                continue
            for detection in frame_detections:
                detection.bbox = self._scaled_yolo_bbox(
                    detection.bbox,
                    multiplier=multiplier,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                scaled_count += 1

        if scaled_count <= 0:
            return

        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        if current_only:
            target_label = f"on frame {int(self._sequence.active_frame_index) + 1}"
        else:
            target_label = "across all frames"
        self.statusBar().showMessage(
            f"Scaled {scaled_count} YOLO bbox proposals by x{multiplier:.2f} {target_label}.",
            3500,
        )

    def _scaled_yolo_bbox(
        self,
        bbox: BBoxXYXY,
        *,
        multiplier: float,
        frame_width: int,
        frame_height: int,
    ) -> BBoxXYXY:
        multiplier = float(multiplier)
        frame_width_f = float(frame_width)
        frame_height_f = float(frame_height)
        center_x, center_y = bbox.center_xy
        half_width = (bbox.width * multiplier) / 2.0
        half_height = (bbox.height * multiplier) / 2.0

        x0 = max(0.0, center_x - half_width)
        y0 = max(0.0, center_y - half_height)
        x1 = min(frame_width_f, center_x + half_width)
        y1 = min(frame_height_f, center_y + half_height)

        min_extent = 1e-6
        if x1 <= x0:
            x0 = min(max(0.0, center_x - (min_extent / 2.0)), max(0.0, frame_width_f - min_extent))
            x1 = min(frame_width_f, x0 + min_extent)
        if y1 <= y0:
            y0 = min(max(0.0, center_y - (min_extent / 2.0)), max(0.0, frame_height_f - min_extent))
            y1 = min(frame_height_f, y0 + min_extent)

        return BBoxXYXY(x0, y0, x1, y1)

    def _set_yolo_global_selection_state(self, selected: bool) -> None:
        if self._yolo_detections is None:
            return
        if self._yolo_detections.detection_count <= 0:
            return
        self._yolo_detections.set_selected(None, selected)
        self._sync_yolo_detection_ui()
        self._sync_track_overlays()
        state_label = "selected" if selected else "deselected"
        self.statusBar().showMessage(f"All YOLO detections {state_label}.", 2500)

    def _prune_excluded_frame_from_edge_tracks(self, frame_index: int) -> tuple[int, int]:
        removed_tracks = 0
        removed_annotations = 0
        remaining_tracks: list[EdgeTrack] = []
        for track in self._edge_tracks:
            if track.seed_frame_index == frame_index:
                removed_tracks += 1
                continue
            if frame_index in track.annotations:
                track.annotations.pop(frame_index, None)
                removed_annotations += 1
            remaining_tracks.append(track)
        next_selected_track_id = self._selected_edge_track_id if any(
            track.edge_track_id == self._selected_edge_track_id for track in remaining_tracks
        ) else (remaining_tracks[0].edge_track_id if remaining_tracks else None)
        self.set_edge_tracks(remaining_tracks, selected_track_id=next_selected_track_id)
        return removed_tracks, removed_annotations

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
        self._sync_yolo_detection_ui()

    def _on_viewer_polygon_changed(self, polygon: object) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        if polygon is None:
            self._draft_polygons_by_frame.pop(frame_index, None)
        else:
            self._draft_polygons_by_frame[frame_index] = polygon
        self.polygon_tools_panel.set_current_polygon(frame_index, self.current_draft_polygon_roi())
        self._sync_edge_track_context()

    def _on_viewer_edge_polyline_changed(self, polyline: object) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        if polyline is None:
            self._draft_edge_polylines_by_frame.pop(frame_index, None)
        else:
            self._draft_edge_polylines_by_frame[frame_index] = np.asarray(polyline, dtype=np.float64)
        self._sync_edge_track_context()

    def _on_clear_current_bbox_requested(self) -> None:
        if self._sequence is None:
            return
        frame_index = self._sequence.active_frame_index
        self._draft_bboxes_by_frame.pop(frame_index, None)
        if self._yolo_edit_target is not None and self._yolo_edit_target.frame_index == frame_index:
            self._yolo_edit_target = None
        self.viewer.clear_bbox()
        self.bbox_tools_panel.set_current_bbox(frame_index, None)
        self.statusBar().showMessage(f"Cleared bbox for frame {frame_index + 1}.", 2000)
        self._sync_bbox_track_context()
        self._sync_yolo_detection_ui()

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

    def _start_edge_detector_worker(
        self,
        run_input: DexiNedRunInput,
        *,
        backend_label: str,
        progress_label: str,
        window_title: str,
        finished_slot,
        failed_slot,
        cancel_enabled: bool = False,
    ) -> None:
        self._set_preprocessing_busy(True)
        self._active_edge_backend_label = backend_label
        self._edge_detector_cancel_requested = False
        self._dexined_progress_dialog = QProgressDialog(progress_label, "", 0, 0, self)
        self._dexined_progress_dialog.setWindowTitle(window_title)
        self._dexined_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        if cancel_enabled:
            self._dexined_progress_dialog.setCancelButtonText("Cancel")
            self._dexined_progress_dialog.canceled.connect(self._on_edge_detector_cancel_requested)
        else:
            self._dexined_progress_dialog.setCancelButton(None)
        self._dexined_progress_dialog.setMinimumDuration(0)
        self._dexined_progress_dialog.setAutoClose(False)
        self._dexined_progress_dialog.setAutoReset(False)
        self._dexined_progress_dialog.setValue(0)
        self._dexined_progress_dialog.show()
        self.statusBar().showMessage(progress_label, 0)
        QApplication.processEvents()

        self._dexined_thread = QThread(self)
        self._dexined_worker = _DexiNedRunWorker(self._selected_edge_detector_backend(), run_input)
        self._dexined_worker.moveToThread(self._dexined_thread)
        self._dexined_thread.started.connect(self._dexined_worker.run)
        self._dexined_worker.finished.connect(finished_slot)
        self._dexined_worker.failed.connect(failed_slot)
        self._dexined_worker.canceled.connect(self._on_dexined_run_canceled)
        self._dexined_worker.finished.connect(self._dexined_thread.quit)
        self._dexined_worker.failed.connect(self._dexined_thread.quit)
        self._dexined_worker.canceled.connect(self._dexined_thread.quit)
        self._dexined_thread.finished.connect(self._cleanup_dexined_worker)
        self._dexined_thread.start()

    def _on_edge_preview_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return

        polygon = self.current_draft_polygon_roi()
        if polygon is None:
            return

        backend_label = self._selected_edge_detector_backend_label()
        try:
            run_input, input_frame, preview_meta = self._build_dexined_preview_input(polygon)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} preview error", str(exc))
            return

        self._pending_edge_preview_frame = np.asarray(input_frame, dtype=np.float32)
        self._pending_edge_preview_meta = {**preview_meta, "backend_label": backend_label}
        self._start_edge_detector_worker(
            run_input,
            backend_label=backend_label,
            progress_label=f"Running {backend_label} preview for frame {self._sequence.active_frame_index + 1}...",
            window_title=f"{backend_label} Preview",
            finished_slot=self._on_dexined_preview_finished,
            failed_slot=self._on_dexined_preview_failed,
            cancel_enabled=False,
        )

    def _on_edge_sequence_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        backend_label = self._selected_edge_detector_backend_label()
        if not self._ensure_current_frame_included("Run Edge Detection on Range"):
            return

        polygon = self.current_draft_polygon_roi()
        if polygon is None:
            return

        stitch_track = self._find_edge_track_by_id(self._selected_edge_track_id) if self.polygon_tools_panel.stitch_to_active_edge() else None
        try:
            if stitch_track is None:
                run_input, sequence_meta = self._build_dexined_sequence_input(polygon)
            else:
                run_input, sequence_meta = self._build_dexined_stitch_input(stitch_track, polygon)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} sequence error", str(exc))
            return

        if run_input is None:
            try:
                self._apply_edge_stitch_output(None, sequence_meta)
            except Exception as exc:
                QMessageBox.critical(self, f"{backend_label} stitch error", str(exc))
                return
            track_id = int(sequence_meta["track_id"])
            start_frame_index = int(sequence_meta["start_frame_index"])
            end_frame_index = int(sequence_meta["end_frame_index"])
            self.statusBar().showMessage(
                (
                    f"Stitched Edge Track {track_id} on frames "
                    f"{start_frame_index + 1}-{end_frame_index + 1}."
                ),
                4000,
            )
            return

        self._pending_edge_sequence_meta = {**sequence_meta, "backend_label": backend_label}
        start_frame_index = int(sequence_meta["start_frame_index"])
        end_frame_index = int(sequence_meta["end_frame_index"])
        run_label = (
            f"Stitching Edge Track {int(sequence_meta['track_id'])} on frames {start_frame_index + 1}-{end_frame_index + 1}..."
            if sequence_meta.get("mode") == "stitch"
            else f"Running {backend_label} on frames {start_frame_index + 1}-{end_frame_index + 1}..."
        )
        self._start_edge_detector_worker(
            run_input,
            backend_label=backend_label,
            progress_label=run_label,
            window_title=(
                "Edge Stitch"
                if sequence_meta.get("mode") == "stitch"
                else f"{backend_label} Sequence"
            ),
            finished_slot=self._on_dexined_sequence_finished,
            failed_slot=self._on_dexined_sequence_failed,
            cancel_enabled=True,
        )

    def _on_load_current_edge_requested(self) -> None:
        if self._sequence is None:
            return
        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            return
        annotation = track.get_annotation(self._sequence.active_frame_index)
        if annotation is None or annotation.polyline is None:
            return

        frame_index = self._sequence.active_frame_index
        self._draft_polygons_by_frame[frame_index] = track.polygon_roi
        self._draft_edge_polylines_by_frame[frame_index] = np.asarray(annotation.polyline, dtype=np.float64)
        self.viewer.set_polygon_roi(track.polygon_roi)
        self.viewer.set_edge_polyline(annotation.polyline)
        self.polygon_tools_panel.set_current_polygon(frame_index, track.polygon_roi)
        self._sync_edge_track_context()
        self.statusBar().showMessage(
            f"Loaded {track.label or f'Edge {track.edge_track_id}'} for manual correction on frame {frame_index + 1}.",
            3000,
        )

    def _on_save_edge_correction_requested(self) -> None:
        if self._sequence is None:
            return
        if not self._ensure_current_frame_included("Save Edge Correction"):
            return
        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            return

        polygon = self.current_draft_polygon_roi() or track.polygon_roi
        polyline = self.current_draft_edge_polyline()
        if polyline is None:
            return

        frame_index = self._sequence.active_frame_index
        previous = track.get_annotation(frame_index)
        edge_mask = None if previous is None else previous.edge_mask
        track.polygon_roi = polygon
        if frame_index == track.seed_frame_index:
            track.seed_polyline = np.asarray(polyline, dtype=np.float64)
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=frame_index,
                polyline=np.asarray(polyline, dtype=np.float64),
                edge_mask=edge_mask,
                visibility=FrameVisibility.VISIBLE,
                source=EdgeAnnotationSource.MANUAL,
                metrics=self._compute_edge_metrics(polyline),
            )
        )
        self.set_edge_tracks(self._edge_tracks, selected_track_id=track.edge_track_id)
        self._show_current_frame(preserve_zoom=True)
        self._sync_edge_track_context()
        self.statusBar().showMessage(
            f"Saved edge correction for {track.label or f'Edge {track.edge_track_id}'} on frame {frame_index + 1}.",
            3000,
        )

    def _on_resume_edge_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        if not self._ensure_current_frame_included("Resume Edge Tracking"):
            return
        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            return

        frame_index = self._sequence.active_frame_index
        polygon = self.current_draft_polygon_roi() or track.polygon_roi
        polyline = self.current_draft_edge_polyline()
        if polyline is None:
            annotation = track.get_annotation(frame_index)
            if annotation is None or annotation.polyline is None:
                return
            polyline = np.asarray(annotation.polyline, dtype=np.float64)

        track.polygon_roi = polygon
        if frame_index == track.seed_frame_index:
            track.seed_polyline = np.asarray(polyline, dtype=np.float64)
        previous = track.get_annotation(frame_index)
        current_edge_mask = None if previous is None else previous.edge_mask
        current_annotation = EdgeFrameAnnotation(
            frame_index=frame_index,
            polyline=np.asarray(polyline, dtype=np.float64),
            edge_mask=current_edge_mask,
            visibility=FrameVisibility.VISIBLE,
            source=EdgeAnnotationSource.MANUAL,
            metrics=self._compute_edge_metrics(polyline),
        )

        if frame_index >= self._sequence.frame_count - 1:
            track.drop_annotations_after(frame_index)
            track.add_annotation(current_annotation)
            self._show_current_frame(preserve_zoom=True)
            self.statusBar().showMessage(
                f"Saved edge correction at final frame for {track.label or f'Edge {track.edge_track_id}'}.",
                3000,
            )
            return

        backend_label = self._selected_edge_detector_backend_label()
        try:
            run_input, resume_meta = self._build_dexined_resume_input(track, polygon, current_annotation)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} resume error", str(exc))
            return

        self._pending_edge_resume_meta = {**resume_meta, "backend_label": backend_label}
        remaining = self._sequence.frame_count - frame_index - 1
        self._start_edge_detector_worker(
            run_input,
            backend_label=backend_label,
            progress_label=(
                f"Resuming edge tracking with {backend_label} for "
                f"{track.label or f'Edge {track.edge_track_id}'} ({remaining} frames)..."
            ),
            window_title=f"{backend_label} Edge Resume",
            finished_slot=self._on_dexined_resume_finished,
            failed_slot=self._on_dexined_resume_failed,
            cancel_enabled=True,
        )

    def _on_redetect_edge_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            return

        backend_label = self._selected_edge_detector_backend_label()
        try:
            run_input, redetect_meta = self._build_dexined_redetect_input(track)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} re-detect error", str(exc))
            return

        self._pending_edge_sequence_meta = {**redetect_meta, "backend_label": backend_label}
        start_frame_index = int(redetect_meta["start_frame_index"])
        end_frame_index = int(redetect_meta["end_frame_index"])
        run_label = (
            f"Re-detecting Edge Track {track.edge_track_id} with {backend_label} on frames "
            f"{start_frame_index + 1}-{end_frame_index + 1}..."
        )
        self._start_edge_detector_worker(
            run_input,
            backend_label=backend_label,
            progress_label=run_label,
            window_title=f"{backend_label} Re-detect",
            finished_slot=self._on_dexined_sequence_finished,
            failed_slot=self._on_dexined_sequence_failed,
            cancel_enabled=True,
        )

    def _on_redetect_edge_range_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        if not self._ensure_current_frame_included("Re-detect Range"):
            return
        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            return

        backend_label = self._selected_edge_detector_backend_label()
        try:
            run_input, redetect_meta = self._build_dexined_partial_redetect_input(track)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} re-detect error", str(exc))
            return

        self._pending_edge_sequence_meta = {**redetect_meta, "backend_label": backend_label}
        start_frame_index = int(redetect_meta["start_frame_index"])
        end_frame_index = int(redetect_meta["end_frame_index"])
        run_label = (
            f"Re-detecting Edge Track {track.edge_track_id} with {backend_label} on frames "
            f"{start_frame_index + 1}-{end_frame_index + 1}..."
        )
        self._start_edge_detector_worker(
            run_input,
            backend_label=backend_label,
            progress_label=run_label,
            window_title=f"{backend_label} Re-detect Range",
            finished_slot=self._on_dexined_sequence_finished,
            failed_slot=self._on_dexined_sequence_failed,
            cancel_enabled=True,
        )

    def _on_edge_hybrid_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        if not self._ensure_current_frame_included("Hybrid Stabilize"):
            return

        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            return

        frame_index = self._sequence.active_frame_index
        annotation = track.get_annotation(frame_index)
        draft_polyline = self.current_draft_edge_polyline()
        anchor_polyline = (
            np.asarray(draft_polyline, dtype=np.float64)
            if draft_polyline is not None
            else None if annotation is None or annotation.polyline is None else np.asarray(annotation.polyline, dtype=np.float64)
        )
        if anchor_polyline is None:
            QMessageBox.warning(
                self,
                "Hybrid stabilization unavailable",
                (
                    f"Edge {track.edge_track_id} has no polyline on frame {frame_index + 1}. "
                    "Load or edit the current edge first."
                ),
            )
            return

        anchor_polygon = self.current_draft_polygon_roi() or track.polygon_roi
        current_edge_mask = None if annotation is None else annotation.edge_mask
        current_source = (
            EdgeAnnotationSource.MANUAL
            if draft_polyline is not None or self.current_draft_polygon_roi() is not None
            else EdgeAnnotationSource.MANUAL
            if annotation is None
            else annotation.source
        )
        current_annotation = EdgeFrameAnnotation(
            frame_index=frame_index,
            polyline=np.asarray(anchor_polyline, dtype=np.float64),
            edge_mask=current_edge_mask,
            visibility=FrameVisibility.VISIBLE,
            source=current_source,
            metrics=self._compute_edge_metrics(anchor_polyline),
        )

        if frame_index >= self._sequence.frame_count - 1:
            track.polygon_roi = anchor_polygon
            if frame_index == track.seed_frame_index:
                track.seed_polyline = np.asarray(anchor_polyline, dtype=np.float64)
            track.drop_annotations_after(frame_index)
            track.add_annotation(current_annotation)
            self.set_edge_tracks(self._edge_tracks, selected_track_id=track.edge_track_id)
            self._show_current_frame(preserve_zoom=True)
            self.statusBar().showMessage(
                f"Saved final-frame edge correction for {track.label or f'Edge {track.edge_track_id}'}.",
                3000,
            )
            return

        try:
            run_input, hybrid_meta = self._build_edge_hybrid_input(
                track,
                anchor_polygon,
                current_annotation,
                tracker_model=self.polygon_tools_panel.hybrid_tracker_model(),
                control_point_count=self.polygon_tools_panel.hybrid_control_point_count(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Hybrid stabilization error", str(exc))
            return

        tracker_label = str(hybrid_meta["tracker_model"]).upper()
        self._pending_edge_hybrid_meta = hybrid_meta
        self._set_preprocessing_busy(True)
        self._point_tracker_progress_dialog = QProgressDialog(
            f"Running {tracker_label} hybrid stabilization for {self._sequence.frame_count - frame_index} frames...",
            "",
            0,
            0,
            self,
        )
        self._point_tracker_progress_dialog.setWindowTitle("Hybrid Edge Stabilization")
        self._point_tracker_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._point_tracker_progress_dialog.setCancelButton(None)
        self._point_tracker_progress_dialog.setMinimumDuration(0)
        self._point_tracker_progress_dialog.setAutoClose(False)
        self._point_tracker_progress_dialog.setAutoReset(False)
        self._point_tracker_progress_dialog.setValue(0)
        self._point_tracker_progress_dialog.show()
        self.statusBar().showMessage(
            f"Running {tracker_label} hybrid stabilization for {track.label or f'Edge {track.edge_track_id}'}...",
            0,
        )
        QApplication.processEvents()

        backend = self._point_tracker_backends[str(hybrid_meta["tracker_model"])]
        self._point_tracker_thread = QThread(self)
        self._point_tracker_worker = _PointTrackerRunWorker(backend, run_input)
        self._point_tracker_worker.moveToThread(self._point_tracker_thread)
        self._point_tracker_thread.started.connect(self._point_tracker_worker.run)
        self._point_tracker_worker.finished.connect(self._on_edge_hybrid_finished)
        self._point_tracker_worker.failed.connect(self._on_edge_hybrid_failed)
        self._point_tracker_worker.finished.connect(self._point_tracker_thread.quit)
        self._point_tracker_worker.failed.connect(self._point_tracker_thread.quit)
        self._point_tracker_thread.finished.connect(self._cleanup_point_tracker_worker)
        self._point_tracker_thread.start()

    def _on_add_seed_requested(self) -> None:
        if self._sequence is None:
            return
        if not self._ensure_current_frame_included("Add Seed"):
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
        if self._yolo_edit_target is not None and self._yolo_edit_target.frame_index == int(self._sequence.active_frame_index):
            self._yolo_edit_target = None
        self.viewer.clear_bbox()
        self.bbox_tools_panel.set_current_bbox(self._sequence.active_frame_index, None)
        self.statusBar().showMessage(
            f"Added seed Track {track_id} on frame {self._sequence.active_frame_index + 1}.",
            3000,
        )
        self._sync_bbox_track_context()
        self._sync_yolo_detection_ui()

    def _on_load_track_bbox_requested(self) -> None:
        if self._sequence is None:
            return
        track = self._find_track_by_id(self._selected_track_id)
        if track is None:
            return
        annotation = track.get_annotation(self._sequence.active_frame_index)
        if annotation is None or annotation.bbox is None:
            return
        self._yolo_edit_target = None
        self._draft_bboxes_by_frame[self._sequence.active_frame_index] = annotation.bbox
        self.viewer.set_bbox(annotation.bbox)
        self.bbox_tools_panel.set_current_bbox(self._sequence.active_frame_index, annotation.bbox)
        self._sync_bbox_track_context()
        self._sync_yolo_detection_ui()
        self.statusBar().showMessage(
            f"Loaded bbox from {track.label or f'Track {track.track_id}'} on frame {self._sequence.active_frame_index + 1}.",
            3000,
        )

    def _on_save_correction_requested(self) -> None:
        if self._sequence is None:
            return
        if not self._ensure_current_frame_included("Save Correction"):
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
        if self._yolo_edit_target is not None and self._yolo_edit_target.frame_index == current_frame:
            self._yolo_edit_target = None
        self.viewer.clear_bbox()
        self.set_tracks(self._tracks, selected_track_id=track.track_id)
        self._show_current_frame(preserve_zoom=True)
        self._sync_yolo_detection_ui()
        self.statusBar().showMessage(
            f"Saved manual correction for {track.label or f'Track {track.track_id}'} on frame {current_frame + 1}.",
            3000,
        )

    def _on_resume_track_requested(self) -> None:
        if self._sequence is None or self._is_preprocessing or self._is_tracking:
            return
        if not self._ensure_current_frame_included("Resume SAM2"):
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

    def _on_edge_track_selected(self, track_id: object) -> None:
        selected_id = None if track_id is None else int(track_id)
        self._selected_edge_track_id = selected_id
        self._sync_edge_results_dialog_selection()
        track = self._find_edge_track_by_id(selected_id)
        if track is not None and self._sequence is not None and track.seed_frame_index != self._sequence.active_frame_index:
            self._set_active_frame(track.seed_frame_index)
            return
        self._sync_track_overlays()
        self._sync_edge_track_context()
        if track is not None:
            self.statusBar().showMessage(
                f"Selected {track.label or f'Edge {track.edge_track_id}'} | seed frame {track.seed_frame_index + 1}",
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

        backend_label = str(
            self._pending_edge_preview_meta.get("backend_label", self._format_edge_detector_backend_label(output.model_name))
        )
        current_index = int(self._pending_edge_preview_meta["frame_index"])
        source_title = str(self._pending_edge_preview_meta["source_title"])
        source_meta = str(self._pending_edge_preview_meta["source_meta"])
        source_view = str(self._pending_edge_preview_meta["source_view"])
        polygon_mask = np.asarray(self._pending_edge_preview_meta["polygon_mask"], dtype=bool)
        threshold = float(self._pending_edge_preview_meta["threshold"])
        top_k_components = int(self._pending_edge_preview_meta["top_k_components"])
        inference_resolution_hw = self._pending_edge_preview_meta["inference_resolution_hw"]
        polyline_method = str(self._pending_edge_preview_meta.get("polyline_method", "graph"))
        refine_score_mode = str(self._pending_edge_preview_meta["refine_score_mode"])
        refine_search_radius_px = int(self._pending_edge_preview_meta["refine_search_radius_px"])
        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        edge_frame = np.asarray(output.edge_prob[0], dtype=np.float32)
        edge_binary_frame = None if output.edge_binary is None else np.asarray(output.edge_binary[0], dtype=bool)
        selection, selected_edge_frame, coarse_polyline, refined_polyline, geometry_quality, max_prob = self._extract_dominant_edge_geometry(
            edge_frame,
            polygon_mask,
            input_frame=self._pending_edge_preview_frame,
            edge_binary_frame=edge_binary_frame,
            requested_threshold=threshold,
            top_k_components=top_k_components,
            polyline_method=polyline_method,
            refine_score_mode=refine_score_mode,
            refine_search_radius_px=refine_search_radius_px,
        )
        subpixel_meta = (
            f"subpx {refined_polyline.subpixel_mode} {refined_polyline.mean_subpixel_correction_px:.2f}px"
        )
        if refined_polyline.subpixel_mode in {"step_tanh", "step_erf"}:
            subpixel_meta = (
                f"{subpixel_meta} fit {refined_polyline.profile_fit_success_rate:.0%} "
                f"sigma {refined_polyline.mean_step_width_px:.2f}px"
            )

        dialog = self._ensure_edge_preview_dialog()
        dialog.set_preview(
            self._pending_edge_preview_frame,
            selected_edge_frame,
            frame_index=current_index,
            frame_count=self._sequence.frame_count,
            scale_nm_per_px=(px_x, px_y),
            window_title=f"{backend_label} Preview",
            input_title=source_title,
            input_meta=source_meta,
            input_overlay_mask=selection.edge_mask,
            input_overlay_polyline=refined_polyline.polyline_xy,
            edge_title="Dominant Edge",
            edge_meta=(
                f"View: {source_view} | mode {selection.selection_mode} | "
                f"thr {threshold:.2f} | k {top_k_components} | "
                f"res {inference_resolution_hw if inference_resolution_hw is not None else 'auto'} | "
                f"selected px {selection.pixel_count} | mean p {selection.mean_probability:.3f} | "
                f"coarse {coarse_polyline.extraction_mode} | "
                f"refine {refined_polyline.score_mode} r {refine_search_radius_px}px | "
                f"{subpixel_meta} | "
                f"pts {refined_polyline.point_count} | shift {refined_polyline.mean_shift_px:.2f}px | "
                f"{format_edge_geometry_review(geometry_quality)} | max p {max_prob:.3f}"
            ),
            edge_overlay_polyline=refined_polyline.polyline_xy,
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

        self.statusBar().showMessage(f"{backend_label} preview opened for frame {current_index + 1}.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_dexined_sequence_finished(self, output: DexiNedRunOutput) -> None:
        if self._sequence is None or self._pending_edge_sequence_meta is None:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()
            return

        backend_label = str(
            self._pending_edge_sequence_meta.get("backend_label", self._format_edge_detector_backend_label(output.model_name))
        )
        try:
            if self._pending_edge_sequence_meta.get("mode") == "stitch":
                self._apply_edge_stitch_output(output, self._pending_edge_sequence_meta)
                track_id = int(self._pending_edge_sequence_meta["track_id"])
                start_frame_index = int(self._pending_edge_sequence_meta["start_frame_index"])
                end_frame_index = int(self._pending_edge_sequence_meta["end_frame_index"])
                self.statusBar().showMessage(
                    (
                        f"Stitched Edge Track {track_id}: frames "
                        f"{start_frame_index + 1}-{end_frame_index + 1}."
                    ),
                    4000,
                )
                track = None
            elif self._pending_edge_sequence_meta.get("mode") == "redetect":
                self._apply_edge_redetect_output(output, self._pending_edge_sequence_meta)
                track_id = int(self._pending_edge_sequence_meta["track_id"])
                start_frame_index = int(self._pending_edge_sequence_meta["start_frame_index"])
                end_frame_index = int(self._pending_edge_sequence_meta["end_frame_index"])
                self.statusBar().showMessage(
                    (
                        f"Re-detected Edge Track {track_id}: frames "
                        f"{start_frame_index + 1}-{end_frame_index + 1}."
                    ),
                    4000,
                )
                track = None
            elif self._pending_edge_sequence_meta.get("mode") == "partial_redetect":
                self._apply_edge_partial_redetect_output(output, self._pending_edge_sequence_meta)
                track_id = int(self._pending_edge_sequence_meta["track_id"])
                start_frame_index = int(self._pending_edge_sequence_meta["start_frame_index"])
                end_frame_index = int(self._pending_edge_sequence_meta["end_frame_index"])
                self.statusBar().showMessage(
                    (
                        f"Partially re-detected Edge Track {track_id}: frames "
                        f"{start_frame_index + 1}-{end_frame_index + 1}."
                    ),
                    4000,
                )
                track = None
            else:
                track = self._build_edge_track_from_dexined_output(output, self._pending_edge_sequence_meta)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} sequence error", str(exc))
            self.statusBar().showMessage(f"{backend_label} sequence failed.", 3000)
        else:
            if track is not None:
                self.set_edge_tracks([*self._edge_tracks, track], selected_track_id=track.edge_track_id)
                self._show_current_frame(preserve_zoom=True)
                self.statusBar().showMessage(
                    f"{backend_label} sequence finished: Edge Track {track.edge_track_id} with {len(track.annotations)} frames.",
                    4000,
                )
        finally:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()

    def _on_dexined_resume_finished(self, output: DexiNedRunOutput) -> None:
        if self._sequence is None or self._pending_edge_resume_meta is None:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()
            return

        backend_label = str(
            self._pending_edge_resume_meta.get("backend_label", self._format_edge_detector_backend_label(output.model_name))
        )
        try:
            self._apply_edge_resume_output(output, self._pending_edge_resume_meta)
        except Exception as exc:
            QMessageBox.critical(self, f"{backend_label} resume error", str(exc))
            self.statusBar().showMessage(f"{backend_label} edge resume failed.", 3000)
        else:
            track_id = int(self._pending_edge_resume_meta["track_id"])
            self.statusBar().showMessage(
                f"Resumed edge tracking with {backend_label} for Edge Track {track_id} from frame {int(self._pending_edge_resume_meta['resume_from_frame']) + 1}.",
                4000,
            )
        finally:
            self._set_preprocessing_busy(False)
            self._close_dexined_progress_dialog()

    def _on_dexined_preview_failed(self, error_message: str) -> None:
        backend_label = self._current_edge_detector_backend_label()
        QMessageBox.critical(self, f"{backend_label} preview error", error_message)
        self.statusBar().showMessage(f"{backend_label} preview failed.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_dexined_sequence_failed(self, error_message: str) -> None:
        backend_label = self._current_edge_detector_backend_label()
        QMessageBox.critical(self, f"{backend_label} sequence error", error_message)
        self.statusBar().showMessage(f"{backend_label} sequence failed.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_dexined_resume_failed(self, error_message: str) -> None:
        backend_label = self._current_edge_detector_backend_label()
        QMessageBox.critical(self, f"{backend_label} resume error", error_message)
        self.statusBar().showMessage(f"{backend_label} edge resume failed.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_edge_detector_cancel_requested(self) -> None:
        if self._dexined_worker is None:
            return
        self._edge_detector_cancel_requested = True
        backend_label = self._current_edge_detector_backend_label()
        if self._dexined_progress_dialog is not None:
            self._dexined_progress_dialog.setLabelText(f"Cancelling {backend_label} operation...")
            self._dexined_progress_dialog.setCancelButton(None)
        self.statusBar().showMessage(f"Cancelling {backend_label} operation...", 0)
        self._dexined_worker.cancel()

    def _on_dexined_run_canceled(self) -> None:
        backend_label = self._current_edge_detector_backend_label()
        self.statusBar().showMessage(f"{backend_label} operation canceled.", 3000)
        self._set_preprocessing_busy(False)
        self._close_dexined_progress_dialog()

    def _on_edge_hybrid_finished(self, output: object) -> None:
        assert isinstance(output, PointTrackerRunOutput)
        if self._pending_edge_hybrid_meta is None:
            self._set_preprocessing_busy(False)
            self._close_point_tracker_progress_dialog()
            return

        try:
            self._apply_edge_hybrid_output(output, self._pending_edge_hybrid_meta)
        except Exception as exc:
            QMessageBox.critical(self, "Hybrid stabilization error", str(exc))
            self.statusBar().showMessage("Hybrid edge stabilization failed.", 3000)
        else:
            track_id = int(self._pending_edge_hybrid_meta["track_id"])
            tracker_model = str(self._pending_edge_hybrid_meta["tracker_model"]).upper()
            start_frame_index = int(self._pending_edge_hybrid_meta["start_frame_index"])
            self.set_edge_tracks(self._edge_tracks, selected_track_id=track_id)
            self._show_current_frame(preserve_zoom=True)
            self.statusBar().showMessage(
                f"{tracker_model} hybrid stabilization finished for Edge Track {track_id} from frame {start_frame_index + 1}.",
                4000,
            )
        finally:
            self._set_preprocessing_busy(False)
            self._close_point_tracker_progress_dialog()

    def _on_edge_hybrid_failed(self, error_message: str) -> None:
        QMessageBox.critical(self, "Hybrid stabilization error", error_message)
        self.statusBar().showMessage("Hybrid edge stabilization failed.", 3000)
        self._set_preprocessing_busy(False)
        self._close_point_tracker_progress_dialog()

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
        self.yolo_panel.set_processing(busy)
        self.polygon_tools_panel.set_processing(busy)
        self.preprocessing_panel.set_processing(busy)
        self.track_list_panel.set_processing(busy)
        self.edge_track_list_panel.set_processing(busy)
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
        try:
            self._dexined_progress_dialog.canceled.disconnect(self._on_edge_detector_cancel_requested)
        except TypeError:
            pass
        self._dexined_progress_dialog.close()
        self._dexined_progress_dialog.deleteLater()
        self._dexined_progress_dialog = None

    def _close_point_tracker_progress_dialog(self) -> None:
        if self._point_tracker_progress_dialog is None:
            return
        self._point_tracker_progress_dialog.close()
        self._point_tracker_progress_dialog.deleteLater()
        self._point_tracker_progress_dialog = None

    def _cleanup_dexined_worker(self) -> None:
        if self._dexined_worker is not None:
            self._dexined_worker.deleteLater()
            self._dexined_worker = None
        if self._dexined_thread is not None:
            self._dexined_thread.deleteLater()
            self._dexined_thread = None
        self._active_edge_backend_label = None
        self._edge_detector_cancel_requested = False
        self._pending_edge_preview_frame = None
        self._pending_edge_preview_meta = None
        self._pending_edge_sequence_meta = None
        self._pending_edge_resume_meta = None

    def _cleanup_point_tracker_worker(self) -> None:
        if self._point_tracker_worker is not None:
            self._point_tracker_worker.deleteLater()
            self._point_tracker_worker = None
        if self._point_tracker_thread is not None:
            self._point_tracker_thread.deleteLater()
            self._point_tracker_thread = None
        self._pending_edge_hybrid_meta = None

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
            self.polygon_tools_panel.set_frame_context(None, None)
            self.viewer.set_edge_polyline(None)
            self.polygon_tools_panel.set_edge_track_context(
                None,
                has_polyline_on_current_frame=False,
                has_editable_polyline=False,
            )
            return
        current_polygon = self.current_draft_polygon_roi()
        self.viewer.set_polygon_roi(current_polygon)
        self.polygon_tools_panel.set_current_polygon(self._sequence.active_frame_index, current_polygon)
        self.polygon_tools_panel.set_frame_context(self._sequence.active_frame_index, self._sequence.frame_count)
        self.viewer.set_edge_polyline(self.current_draft_edge_polyline())
        self._sync_edge_track_context()

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
        threshold = self.polygon_tools_panel.dexined_threshold()
        inference_resolution_hw = self.polygon_tools_panel.dexined_inference_resolution_hw()
        run_input = DexiNedRunInput(
            frames=np.asarray(input_frame[None, ...], dtype=np.float32),
            polygon_mask=polygon_mask,
            inference_resolution_hw=None
            if inference_resolution_hw is None
            else np.asarray(inference_resolution_hw, dtype=np.int32),
            threshold=threshold,
            source_view=source_view,
        )
        preview_meta = {
            "frame_index": self._sequence.active_frame_index,
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
            "polygon_mask": polygon_mask,
            "threshold": threshold,
            "top_k_components": self.polygon_tools_panel.dexined_top_k_components(),
            "inference_resolution_hw": inference_resolution_hw,
            "polyline_method": self.polygon_tools_panel.edge_polyline_method(),
            "refine_score_mode": self.polygon_tools_panel.edge_refine_score_mode(),
            "refine_search_radius_px": self.polygon_tools_panel.edge_refine_search_radius_px(),
        }
        return run_input, np.asarray(input_frame, dtype=np.float32), preview_meta

    def _build_dexined_sequence_input(
        self,
        polygon: PolygonROI,
    ) -> tuple[DexiNedRunInput, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        start_frame_index, end_frame_index = self._selected_edge_run_range()
        input_frames, source_title, source_meta, source_view = self._current_edge_input_frames()
        polygon_mask = self._polygon_roi_to_mask(polygon)
        threshold = self.polygon_tools_panel.dexined_threshold()
        inference_resolution_hw = self.polygon_tools_panel.dexined_inference_resolution_hw()
        frame_indices = np.arange(start_frame_index, end_frame_index + 1, dtype=np.int32)
        run_input = DexiNedRunInput(
            frames=np.asarray(input_frames[start_frame_index : end_frame_index + 1], dtype=np.float32),
            polygon_mask=polygon_mask,
            frame_indices=frame_indices,
            inference_resolution_hw=None
            if inference_resolution_hw is None
            else np.asarray(inference_resolution_hw, dtype=np.int32),
            threshold=threshold,
            source_view=source_view,
        )
        sequence_meta = {
            "polygon": polygon,
            "polygon_mask": polygon_mask,
            "seed_frame_index": start_frame_index,
            "start_frame_index": start_frame_index,
            "end_frame_index": end_frame_index,
            "frame_indices": frame_indices,
            "input_frames": np.asarray(input_frames[start_frame_index : end_frame_index + 1], dtype=np.float32),
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
            "threshold": threshold,
            "top_k_components": self.polygon_tools_panel.dexined_top_k_components(),
            "inference_resolution_hw": inference_resolution_hw,
            "polyline_method": self.polygon_tools_panel.edge_polyline_method(),
            "refine_score_mode": self.polygon_tools_panel.edge_refine_score_mode(),
            "refine_search_radius_px": self.polygon_tools_panel.edge_refine_search_radius_px(),
            "mode": "create",
        }
        return run_input, sequence_meta

    def _selected_edge_run_range(self) -> tuple[int, int]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        start_frame_index = int(self._sequence.active_frame_index)
        end_frame_index = int(self.polygon_tools_panel.edge_run_end_frame_index())
        if end_frame_index < start_frame_index:
            raise ValueError("DexiNed end frame must not be earlier than the active frame.")
        if end_frame_index >= self._sequence.frame_count:
            raise ValueError("DexiNed end frame is out of range.")
        return start_frame_index, end_frame_index

    def _build_dexined_stitch_input(
        self,
        track: EdgeTrack,
        polygon: PolygonROI,
    ) -> tuple[DexiNedRunInput | None, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")

        start_frame_index, end_frame_index = self._selected_edge_run_range()
        input_frames, source_title, source_meta, source_view = self._current_edge_input_frames()
        polygon_mask = self._polygon_roi_to_mask(polygon)
        threshold = self.polygon_tools_panel.dexined_threshold()
        inference_resolution_hw = self.polygon_tools_panel.dexined_inference_resolution_hw()
        top_k_components = self.polygon_tools_panel.dexined_top_k_components()

        existing_annotation = track.get_annotation(start_frame_index)
        draft_polyline = self.current_draft_edge_polyline()
        current_annotation = None
        suffix_start_frame_index = start_frame_index
        if draft_polyline is not None:
            current_annotation = EdgeFrameAnnotation(
                frame_index=start_frame_index,
                polyline=np.asarray(draft_polyline, dtype=np.float64),
                edge_mask=None if existing_annotation is None else existing_annotation.edge_mask,
                visibility=FrameVisibility.VISIBLE,
                source=EdgeAnnotationSource.MANUAL,
                metrics=self._compute_edge_metrics(draft_polyline),
            )
            suffix_start_frame_index = start_frame_index + 1
        elif existing_annotation is not None and existing_annotation.polyline is not None:
            current_annotation = EdgeFrameAnnotation(
                frame_index=start_frame_index,
                polyline=np.asarray(existing_annotation.polyline, dtype=np.float64),
                edge_mask=existing_annotation.edge_mask,
                visibility=existing_annotation.visibility,
                source=existing_annotation.source,
                metrics=existing_annotation.metrics,
            )
            suffix_start_frame_index = start_frame_index + 1

        frame_indices = np.arange(suffix_start_frame_index, end_frame_index + 1, dtype=np.int32)
        stitch_meta = {
            "mode": "stitch",
            "track_id": track.edge_track_id,
            "polygon": polygon,
            "polygon_mask": polygon_mask,
            "start_frame_index": start_frame_index,
            "end_frame_index": end_frame_index,
            "current_annotation": current_annotation,
            "frame_indices": frame_indices,
            "input_frames": np.asarray(input_frames[suffix_start_frame_index : end_frame_index + 1], dtype=np.float32),
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
            "threshold": threshold,
            "top_k_components": top_k_components,
            "inference_resolution_hw": inference_resolution_hw,
            "polyline_method": self.polygon_tools_panel.edge_polyline_method(),
            "refine_score_mode": self.polygon_tools_panel.edge_refine_score_mode(),
            "refine_search_radius_px": self.polygon_tools_panel.edge_refine_search_radius_px(),
        }
        if len(frame_indices) == 0:
            return None, stitch_meta

        run_input = DexiNedRunInput(
            frames=np.asarray(input_frames[suffix_start_frame_index : end_frame_index + 1], dtype=np.float32),
            polygon_mask=polygon_mask,
            frame_indices=frame_indices,
            inference_resolution_hw=None
            if inference_resolution_hw is None
            else np.asarray(inference_resolution_hw, dtype=np.int32),
            threshold=threshold,
            source_view=source_view,
        )
        return run_input, stitch_meta

    def _build_dexined_redetect_input(
        self,
        track: EdgeTrack,
    ) -> tuple[DexiNedRunInput, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")

        frame_indices = np.asarray(track.frame_indices, dtype=np.int32)
        if len(frame_indices) == 0:
            raise ValueError("Selected edge track has no annotated frames to re-detect.")

        polygon = self.current_draft_polygon_roi() or track.polygon_roi
        input_frames, source_title, source_meta, source_view = self._current_edge_input_frames()
        polygon_mask = self._polygon_roi_to_mask(polygon)
        threshold = self.polygon_tools_panel.dexined_threshold()
        inference_resolution_hw = self.polygon_tools_panel.dexined_inference_resolution_hw()
        top_k_components = self.polygon_tools_panel.dexined_top_k_components()
        run_frames = np.asarray(input_frames[frame_indices], dtype=np.float32)

        run_input = DexiNedRunInput(
            frames=run_frames,
            polygon_mask=polygon_mask,
            frame_indices=frame_indices,
            inference_resolution_hw=None
            if inference_resolution_hw is None
            else np.asarray(inference_resolution_hw, dtype=np.int32),
            threshold=threshold,
            source_view=source_view,
        )
        redetect_meta = {
            "mode": "redetect",
            "track_id": track.edge_track_id,
            "polygon": polygon,
            "polygon_mask": polygon_mask,
            "start_frame_index": int(frame_indices[0]),
            "end_frame_index": int(frame_indices[-1]),
            "frame_indices": frame_indices,
            "input_frames": run_frames,
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
            "threshold": threshold,
            "top_k_components": top_k_components,
            "inference_resolution_hw": inference_resolution_hw,
            "polyline_method": self.polygon_tools_panel.edge_polyline_method(),
            "refine_score_mode": self.polygon_tools_panel.edge_refine_score_mode(),
            "refine_search_radius_px": self.polygon_tools_panel.edge_refine_search_radius_px(),
        }
        return run_input, redetect_meta

    def _build_dexined_partial_redetect_input(
        self,
        track: EdgeTrack,
    ) -> tuple[DexiNedRunInput, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")

        annotated_frame_indices = np.asarray(track.frame_indices, dtype=np.int32)
        if len(annotated_frame_indices) == 0:
            raise ValueError("Selected edge track has no annotated frames to re-detect.")

        start_frame_index = int(self._sequence.active_frame_index)
        end_frame_index = int(self.polygon_tools_panel.edge_run_end_frame_index())
        if end_frame_index < start_frame_index:
            raise ValueError("End frame must be at or after the current frame.")
        if start_frame_index < int(annotated_frame_indices[0]) or end_frame_index > int(annotated_frame_indices[-1]):
            raise ValueError(
                "Partial re-detect must stay within the currently annotated frame range of the selected edge track."
            )

        frame_indices = annotated_frame_indices[
            (annotated_frame_indices >= start_frame_index) & (annotated_frame_indices <= end_frame_index)
        ]
        if len(frame_indices) == 0:
            raise ValueError("Selected frame range does not overlap the current edge track.")

        polygon = self.current_draft_polygon_roi() or track.polygon_roi
        input_frames, source_title, source_meta, source_view = self._current_edge_input_frames()
        polygon_mask = self._polygon_roi_to_mask(polygon)
        threshold = self.polygon_tools_panel.dexined_threshold()
        inference_resolution_hw = self.polygon_tools_panel.dexined_inference_resolution_hw()
        top_k_components = self.polygon_tools_panel.dexined_top_k_components()
        run_frames = np.asarray(input_frames[frame_indices], dtype=np.float32)

        run_input = DexiNedRunInput(
            frames=run_frames,
            polygon_mask=polygon_mask,
            frame_indices=frame_indices,
            inference_resolution_hw=None
            if inference_resolution_hw is None
            else np.asarray(inference_resolution_hw, dtype=np.int32),
            threshold=threshold,
            source_view=source_view,
        )
        redetect_meta = {
            "mode": "partial_redetect",
            "track_id": track.edge_track_id,
            "polygon": polygon,
            "polygon_mask": polygon_mask,
            "start_frame_index": start_frame_index,
            "end_frame_index": end_frame_index,
            "frame_indices": frame_indices,
            "input_frames": run_frames,
            "source_title": source_title,
            "source_meta": source_meta,
            "source_view": source_view,
            "threshold": threshold,
            "top_k_components": top_k_components,
            "inference_resolution_hw": inference_resolution_hw,
            "polyline_method": self.polygon_tools_panel.edge_polyline_method(),
            "refine_score_mode": self.polygon_tools_panel.edge_refine_score_mode(),
            "refine_search_radius_px": self.polygon_tools_panel.edge_refine_search_radius_px(),
        }
        return run_input, redetect_meta

    def _effective_dexined_threshold(
        self,
        edge_frame: np.ndarray,
        polygon_mask: np.ndarray,
        *,
        edge_binary_frame: np.ndarray | None,
        requested_threshold: float | None = None,
    ) -> float:
        if requested_threshold is not None:
            return float(requested_threshold)
        effective_threshold = 0.5
        if edge_binary_frame is not None and np.any(edge_binary_frame & polygon_mask):
            effective_threshold = float(np.min(edge_frame[edge_binary_frame & polygon_mask]))
        return effective_threshold

    def _extract_dominant_edge_geometry(
        self,
        edge_frame: np.ndarray,
        polygon_mask: np.ndarray,
        *,
        input_frame: np.ndarray,
        edge_binary_frame: np.ndarray | None,
        requested_threshold: float | None = None,
        top_k_components: int = 1,
        refine_score_mode: str = "combined",
        refine_search_radius_px: int = 4,
        polyline_method: str = "graph",
    ):
        effective_threshold = self._effective_dexined_threshold(
            edge_frame,
            polygon_mask,
            edge_binary_frame=edge_binary_frame,
            requested_threshold=requested_threshold,
        )
        selection = select_dominant_edge(
            edge_frame,
            polygon_mask,
            threshold=effective_threshold,
            max_components=top_k_components,
        )
        if selection.candidates:
            polyline_candidate = select_best_edge_polyline_candidate(
                edge_frame,
                selection.candidates,
                candidate_limit=max(1, top_k_components),
                polyline_method=polyline_method,
            )
            selected_components = tuple(polyline_candidate.components)
            selected_mask = np.asarray(polyline_candidate.edge_mask, dtype=bool)
            selected_label_ids = tuple(candidate.label_id for candidate in selected_components)
            current_label_ids = tuple(candidate.label_id for candidate in selection.selected_candidates)
            if selected_label_ids != current_label_ids:
                total_score = float(sum(candidate.sum_probability for candidate in selected_components))
                pixel_count = int(np.count_nonzero(selected_mask))
                mean_probability = 0.0 if pixel_count == 0 else float(np.mean(edge_frame[selected_mask]))
                selection = DominantEdgeSelection(
                    edge_mask=selected_mask,
                    score=total_score,
                    pixel_count=pixel_count,
                    mean_probability=mean_probability,
                    selection_mode=polyline_candidate.selection_mode,
                    candidates=selection.candidates,
                    selected_candidates=selected_components,
                    quality_score=polyline_candidate.geometry_score,
                )
            coarse_polyline = polyline_candidate.extraction
        else:
            coarse_polyline = dominant_edge_to_polyline(
                selection.edge_mask,
                edge_prob=edge_frame,
                method=polyline_method,
            )
        selected_edge_frame = edge_frame * selection.edge_mask.astype(np.float32, copy=False)
        refined_polyline = refine_edge_polyline(
            coarse_polyline.polyline_xy,
            edge_prob=edge_frame,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode=refine_score_mode,
            search_radius_px=refine_search_radius_px,
            subpixel_mode="step_tanh",
        )
        geometry_quality = assess_edge_geometry_quality(
            selection,
            coarse_polyline,
            refined_polyline,
            polyline_method=polyline_method,
            method_explicit=True,
        )
        max_prob = float(np.max(selected_edge_frame)) if selected_edge_frame.size else 0.0
        return selection, selected_edge_frame, coarse_polyline, refined_polyline, geometry_quality, max_prob

    def _compute_edge_metrics(self, polyline_xy: np.ndarray):
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        return compute_edge_metrics(
            polyline_xy,
            pixel_size_nm=self._sequence.metadata.get_pixel_size_nm(),
        )

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
        threshold = float(sequence_meta["threshold"])
        top_k_components = int(sequence_meta["top_k_components"])
        frame_indices = np.asarray(sequence_meta["frame_indices"], dtype=np.int32)
        input_frames = np.asarray(sequence_meta["input_frames"], dtype=np.float32)
        polyline_method = str(sequence_meta.get("polyline_method", "graph"))
        refine_score_mode = str(sequence_meta["refine_score_mode"])
        refine_search_radius_px = int(sequence_meta["refine_search_radius_px"])
        annotations = self._build_edge_annotations_from_dexined_output(
            output,
            frame_indices=frame_indices,
            input_frames=input_frames,
            polygon_mask=polygon_mask,
            threshold=threshold,
            top_k_components=top_k_components,
            polyline_method=polyline_method,
            refine_score_mode=refine_score_mode,
            refine_search_radius_px=refine_search_radius_px,
        )
        seed_annotation = annotations.get(seed_frame_index)
        seed_polyline = None if seed_annotation is None else np.asarray(seed_annotation.polyline, dtype=np.float64)

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

    def _build_edge_annotations_from_dexined_output(
        self,
        output: DexiNedRunOutput,
        *,
        frame_indices: np.ndarray,
        input_frames: np.ndarray,
        polygon_mask: np.ndarray,
        threshold: float,
        top_k_components: int,
        polyline_method: str,
        refine_score_mode: str,
        refine_search_radius_px: int,
    ) -> dict[int, EdgeFrameAnnotation]:
        edge_prob = np.asarray(output.edge_prob, dtype=np.float32)
        frame_indices = np.asarray(frame_indices, dtype=np.int32)
        if edge_prob.shape[0] != len(frame_indices):
            raise ValueError("DexiNed output length must match the requested frame range.")
        input_frames_f32 = np.asarray(input_frames, dtype=np.float32)
        if input_frames_f32.shape[0] != len(frame_indices):
            raise ValueError("Input frame range length must match the requested frame range.")

        annotations: dict[int, EdgeFrameAnnotation] = {}
        for local_index, frame_index in enumerate(frame_indices):
            if self._sequence is not None and self._sequence.is_frame_excluded(int(frame_index)):
                continue
            edge_frame = np.asarray(edge_prob[local_index], dtype=np.float32)
            input_frame = np.asarray(input_frames_f32[local_index], dtype=np.float32)
            edge_binary_frame = None
            if output.edge_binary is not None:
                edge_binary_frame = np.asarray(output.edge_binary[local_index], dtype=bool)
            selection, _selected_edge_frame, _coarse_polyline, refined_polyline, geometry_quality, _max_prob = self._extract_dominant_edge_geometry(
                edge_frame,
                polygon_mask,
                input_frame=input_frame,
                edge_binary_frame=edge_binary_frame,
                requested_threshold=threshold,
                top_k_components=top_k_components,
                polyline_method=polyline_method,
                refine_score_mode=refine_score_mode,
                refine_search_radius_px=refine_search_radius_px,
            )
            annotations[int(frame_index)] = EdgeFrameAnnotation(
                frame_index=int(frame_index),
                polyline=refined_polyline.polyline_xy,
                edge_mask=selection.edge_mask,
                source=EdgeAnnotationSource.DEXINED,
                metrics=self._compute_edge_metrics(refined_polyline.polyline_xy),
                geometry_quality=geometry_quality,
            )
        return annotations

    def _replace_edge_track_annotations_in_range(
        self,
        track: EdgeTrack,
        *,
        start_frame_index: int,
        end_frame_index: int,
        replacement_annotations: dict[int, EdgeFrameAnnotation],
    ) -> None:
        preserved_annotations = {
            frame_index: annotation
            for frame_index, annotation in track.annotations.items()
            if frame_index < start_frame_index or frame_index > end_frame_index
        }
        preserved_annotations.update(replacement_annotations)
        track.annotations = dict(sorted(preserved_annotations.items()))

    def _apply_edge_stitch_output(
        self,
        output: DexiNedRunOutput | None,
        stitch_meta: dict[str, object],
    ) -> None:
        track = self._find_edge_track_by_id(int(stitch_meta["track_id"]))
        if track is None:
            raise RuntimeError("Selected edge track is no longer available.")

        start_frame_index = int(stitch_meta["start_frame_index"])
        end_frame_index = int(stitch_meta["end_frame_index"])
        polygon = stitch_meta["polygon"]
        polygon_mask = np.asarray(stitch_meta["polygon_mask"], dtype=bool)
        threshold = float(stitch_meta["threshold"])
        top_k_components = int(stitch_meta["top_k_components"])
        frame_indices = np.asarray(stitch_meta["frame_indices"], dtype=np.int32)
        input_frames = np.asarray(stitch_meta["input_frames"], dtype=np.float32)
        polyline_method = str(stitch_meta.get("polyline_method", "graph"))
        refine_score_mode = str(stitch_meta["refine_score_mode"])
        refine_search_radius_px = int(stitch_meta["refine_search_radius_px"])
        current_annotation = stitch_meta.get("current_annotation")

        replacement_annotations: dict[int, EdgeFrameAnnotation] = {}
        if isinstance(current_annotation, EdgeFrameAnnotation):
            replacement_annotations[current_annotation.frame_index] = current_annotation
        if output is not None and len(frame_indices) > 0:
            replacement_annotations.update(
                self._build_edge_annotations_from_dexined_output(
                    output,
                    frame_indices=frame_indices,
                    input_frames=input_frames,
                    polygon_mask=polygon_mask,
                    threshold=threshold,
                    top_k_components=top_k_components,
                    polyline_method=polyline_method,
                    refine_score_mode=refine_score_mode,
                    refine_search_radius_px=refine_search_radius_px,
                )
            )

        track.polygon_roi = polygon
        self._replace_edge_track_annotations_in_range(
            track,
            start_frame_index=start_frame_index,
            end_frame_index=end_frame_index,
            replacement_annotations=replacement_annotations,
        )
        if track.seed_frame_index in replacement_annotations and replacement_annotations[track.seed_frame_index].polyline is not None:
            track.seed_polyline = np.asarray(replacement_annotations[track.seed_frame_index].polyline, dtype=np.float64)

        self.set_edge_tracks(self._edge_tracks, selected_track_id=track.edge_track_id)
        self._show_current_frame(preserve_zoom=True)

    def _apply_edge_redetect_output(
        self,
        output: DexiNedRunOutput,
        redetect_meta: dict[str, object],
    ) -> None:
        track = self._find_edge_track_by_id(int(redetect_meta["track_id"]))
        if track is None:
            raise RuntimeError("Selected edge track is no longer available.")

        polygon = redetect_meta["polygon"]
        polygon_mask = np.asarray(redetect_meta["polygon_mask"], dtype=bool)
        threshold = float(redetect_meta["threshold"])
        top_k_components = int(redetect_meta["top_k_components"])
        frame_indices = np.asarray(redetect_meta["frame_indices"], dtype=np.int32)
        input_frames = np.asarray(redetect_meta["input_frames"], dtype=np.float32)
        polyline_method = str(redetect_meta.get("polyline_method", "graph"))
        refine_score_mode = str(redetect_meta["refine_score_mode"])
        refine_search_radius_px = int(redetect_meta["refine_search_radius_px"])

        replacement_annotations = self._build_edge_annotations_from_dexined_output(
            output,
            frame_indices=frame_indices,
            input_frames=input_frames,
            polygon_mask=polygon_mask,
            threshold=threshold,
            top_k_components=top_k_components,
            polyline_method=polyline_method,
            refine_score_mode=refine_score_mode,
            refine_search_radius_px=refine_search_radius_px,
        )
        if track.seed_frame_index not in replacement_annotations or replacement_annotations[track.seed_frame_index].polyline is None:
            raise ValueError("Re-detect output does not contain a valid seed-frame polyline.")

        track.polygon_roi = polygon
        track.seed_polyline = np.asarray(replacement_annotations[track.seed_frame_index].polyline, dtype=np.float64)
        track.annotations = dict(sorted(replacement_annotations.items()))
        self.set_edge_tracks(self._edge_tracks, selected_track_id=track.edge_track_id)
        self._show_current_frame(preserve_zoom=True)

    def _apply_edge_partial_redetect_output(
        self,
        output: DexiNedRunOutput,
        redetect_meta: dict[str, object],
    ) -> None:
        track = self._find_edge_track_by_id(int(redetect_meta["track_id"]))
        if track is None:
            raise RuntimeError("Selected edge track is no longer available.")

        start_frame_index = int(redetect_meta["start_frame_index"])
        end_frame_index = int(redetect_meta["end_frame_index"])
        polygon = redetect_meta["polygon"]
        polygon_mask = np.asarray(redetect_meta["polygon_mask"], dtype=bool)
        threshold = float(redetect_meta["threshold"])
        top_k_components = int(redetect_meta["top_k_components"])
        frame_indices = np.asarray(redetect_meta["frame_indices"], dtype=np.int32)
        input_frames = np.asarray(redetect_meta["input_frames"], dtype=np.float32)
        polyline_method = str(redetect_meta.get("polyline_method", "graph"))
        refine_score_mode = str(redetect_meta["refine_score_mode"])
        refine_search_radius_px = int(redetect_meta["refine_search_radius_px"])

        replacement_annotations = self._build_edge_annotations_from_dexined_output(
            output,
            frame_indices=frame_indices,
            input_frames=input_frames,
            polygon_mask=polygon_mask,
            threshold=threshold,
            top_k_components=top_k_components,
            polyline_method=polyline_method,
            refine_score_mode=refine_score_mode,
            refine_search_radius_px=refine_search_radius_px,
        )
        if (
            start_frame_index <= track.seed_frame_index <= end_frame_index
            and (
                track.seed_frame_index not in replacement_annotations
                or replacement_annotations[track.seed_frame_index].polyline is None
            )
        ):
            raise ValueError("Partial re-detect output does not contain a valid seed-frame polyline.")

        track.polygon_roi = polygon
        self._replace_edge_track_annotations_in_range(
            track,
            start_frame_index=start_frame_index,
            end_frame_index=end_frame_index,
            replacement_annotations=replacement_annotations,
        )
        if track.seed_frame_index in replacement_annotations and replacement_annotations[track.seed_frame_index].polyline is not None:
            track.seed_polyline = np.asarray(replacement_annotations[track.seed_frame_index].polyline, dtype=np.float64)

        self.set_edge_tracks(self._edge_tracks, selected_track_id=track.edge_track_id)
        self._show_current_frame(preserve_zoom=True)

    def _sync_track_overlays(self) -> None:
        if self._sequence is None:
            self.viewer.clear_track_seed_overlays()
            return
        current_frame_index = int(self._sequence.active_frame_index)
        yolo_detections = [] if self._yolo_detections is None else self._yolo_detections.get_detections(current_frame_index)
        self.viewer.set_tracks_and_edges(
            self._tracks,
            selected_track_id=self._selected_track_id,
            edge_tracks=self._edge_tracks,
            selected_edge_track_id=self._selected_edge_track_id,
            yolo_detections=yolo_detections,
        )

    def _find_track_by_id(self, track_id: int | None) -> ParticleTrack | None:
        if track_id is None:
            return None
        for track in self._tracks:
            if track.track_id == track_id:
                return track
        return None

    def _find_edge_track_by_id(self, edge_track_id: int | None) -> EdgeTrack | None:
        if edge_track_id is None:
            return None
        for track in self._edge_tracks:
            if track.edge_track_id == edge_track_id:
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

    def _sync_edge_track_context(self) -> None:
        if self._sequence is None:
            self.polygon_tools_panel.set_edge_track_context(
                None,
                has_polyline_on_current_frame=False,
                has_editable_polyline=False,
            )
            return

        track = self._find_edge_track_by_id(self._selected_edge_track_id)
        if track is None:
            self.polygon_tools_panel.set_edge_track_context(
                None,
                has_polyline_on_current_frame=False,
                has_editable_polyline=self.current_draft_edge_polyline() is not None,
            )
            return

        annotation = track.get_annotation(self._sequence.active_frame_index)
        edge_label = track.label or f"Edge {track.edge_track_id}"
        self.polygon_tools_panel.set_edge_track_context(
            edge_label,
            has_polyline_on_current_frame=annotation is not None and annotation.polyline is not None,
            has_editable_polyline=self.current_draft_edge_polyline() is not None,
        )

    def _build_dexined_resume_input(
        self,
        track: EdgeTrack,
        polygon: PolygonROI,
        current_annotation: EdgeFrameAnnotation,
    ) -> tuple[DexiNedRunInput, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        resume_from_frame = self._sequence.active_frame_index
        input_frames, _source_title, _source_meta, source_view = self._current_edge_input_frames()
        suffix_frames = np.asarray(input_frames[resume_from_frame + 1 :], dtype=np.float32)
        polygon_mask = self._polygon_roi_to_mask(polygon)
        threshold = self.polygon_tools_panel.dexined_threshold()
        inference_resolution_hw = self.polygon_tools_panel.dexined_inference_resolution_hw()
        run_input = DexiNedRunInput(
            frames=suffix_frames,
            polygon_mask=polygon_mask,
            inference_resolution_hw=None
            if inference_resolution_hw is None
            else np.asarray(inference_resolution_hw, dtype=np.int32),
            threshold=threshold,
            source_view=source_view,
        )
        resume_meta = {
            "track_id": track.edge_track_id,
            "resume_from_frame": resume_from_frame,
            "polygon": polygon,
            "polygon_mask": polygon_mask,
            "input_frames": suffix_frames,
            "current_annotation": current_annotation,
            "threshold": threshold,
            "top_k_components": self.polygon_tools_panel.dexined_top_k_components(),
            "inference_resolution_hw": inference_resolution_hw,
            "polyline_method": self.polygon_tools_panel.edge_polyline_method(),
            "refine_score_mode": self.polygon_tools_panel.edge_refine_score_mode(),
            "refine_search_radius_px": self.polygon_tools_panel.edge_refine_search_radius_px(),
        }
        return run_input, resume_meta

    def _build_edge_hybrid_input(
        self,
        track: EdgeTrack,
        polygon: PolygonROI,
        current_annotation: EdgeFrameAnnotation,
        *,
        tracker_model: str,
        control_point_count: int,
    ) -> tuple[PointTrackerRunInput, dict[str, object]]:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        if tracker_model not in self._point_tracker_backends:
            raise ValueError(f"Unsupported point tracker backend: {tracker_model}")

        start_frame_index = self._sequence.active_frame_index
        input_frames, _source_title, _source_meta, source_view = self._current_edge_input_frames()
        suffix_frames = np.asarray(input_frames[start_frame_index:], dtype=np.float32)
        if current_annotation.polyline is None:
            raise ValueError("Current edge annotation does not contain a polyline.")

        control_points_xy = sample_polyline_control_points(current_annotation.polyline, int(control_point_count))
        query_points_tyx = np.column_stack(
            [
                np.zeros(len(control_points_xy), dtype=np.float32),
                control_points_xy[:, 1].astype(np.float32, copy=False),
                control_points_xy[:, 0].astype(np.float32, copy=False),
            ]
        )
        run_input = PointTrackerRunInput(
            frames=suffix_frames,
            query_points_tyx=query_points_tyx,
            source_view=source_view,
        )
        existing_annotations = {
            frame_index: track.get_annotation(frame_index)
            for frame_index in range(start_frame_index + 1, self._sequence.frame_count)
        }
        hybrid_meta = {
            "track_id": track.edge_track_id,
            "start_frame_index": start_frame_index,
            "polygon": polygon,
            "current_annotation": current_annotation,
            "existing_annotations": existing_annotations,
            "tracker_model": tracker_model,
            "control_point_count": int(control_point_count),
        }
        return run_input, hybrid_meta

    def _apply_edge_hybrid_output(self, output: PointTrackerRunOutput, hybrid_meta: dict[str, object]) -> None:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")

        track = self._find_edge_track_by_id(int(hybrid_meta["track_id"]))
        if track is None:
            raise RuntimeError("Selected edge track is no longer available.")

        start_frame_index = int(hybrid_meta["start_frame_index"])
        polygon = hybrid_meta["polygon"]
        current_annotation = hybrid_meta["current_annotation"]
        existing_annotations = dict(hybrid_meta["existing_annotations"])
        expected_frame_count = self._sequence.frame_count - start_frame_index

        tracks_xy = np.asarray(output.tracks_xy, dtype=np.float32)
        visible_mask = np.asarray(output.visible_mask, dtype=bool)
        if tracks_xy.shape[1] != expected_frame_count:
            raise ValueError("Point-tracker output length must match the remaining frame count for hybrid stabilization.")
        if tracks_xy.shape[0] < 2:
            raise ValueError("Hybrid stabilization requires at least two tracked control points.")

        track.polygon_roi = polygon
        if start_frame_index == track.seed_frame_index:
            track.seed_polyline = np.asarray(current_annotation.polyline, dtype=np.float64)

        track.drop_annotations_after(start_frame_index)
        track.add_annotation(current_annotation)

        for local_index in range(1, tracks_xy.shape[1]):
            frame_index = start_frame_index + local_index
            if self._sequence.is_frame_excluded(frame_index):
                continue
            tracked_points = np.asarray(tracks_xy[:, local_index, :], dtype=np.float64)
            visible_points = tracked_points[visible_mask[:, local_index]]
            existing_annotation = existing_annotations.get(frame_index)

            if existing_annotation is not None and existing_annotation.polyline is not None and len(visible_points) >= 2:
                refined_polyline = hybrid_refine_polyline(existing_annotation.polyline, visible_points)
                track.add_annotation(
                    EdgeFrameAnnotation(
                        frame_index=frame_index,
                        polyline=refined_polyline,
                        edge_mask=None if existing_annotation is None else existing_annotation.edge_mask,
                        visibility=FrameVisibility.VISIBLE,
                        source=EdgeAnnotationSource.TRACKER_REFINE,
                        metrics=self._compute_edge_metrics(refined_polyline),
                    )
                )
                continue

            if existing_annotation is not None:
                track.add_annotation(existing_annotation)
                continue

            if len(visible_points) >= 2:
                track.add_annotation(
                    EdgeFrameAnnotation(
                        frame_index=frame_index,
                        polyline=visible_points,
                        edge_mask=None,
                        visibility=FrameVisibility.VISIBLE,
                        source=EdgeAnnotationSource.TRACKER_REFINE,
                        metrics=self._compute_edge_metrics(visible_points),
                    )
                )
                continue

            track.add_annotation(
                EdgeFrameAnnotation(
                    frame_index=frame_index,
                    polyline=None,
                    edge_mask=None,
                    visibility=FrameVisibility.LOST,
                    source=EdgeAnnotationSource.TRACKER_REFINE,
                )
            )

    def _apply_edge_resume_output(self, output: DexiNedRunOutput, resume_meta: dict[str, object]) -> None:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        track = self._find_edge_track_by_id(int(resume_meta["track_id"]))
        if track is None:
            raise RuntimeError("Selected edge track is no longer available.")

        resume_from_frame = int(resume_meta["resume_from_frame"])
        polygon = resume_meta["polygon"]
        polygon_mask = np.asarray(resume_meta["polygon_mask"], dtype=bool)
        input_frames = np.asarray(resume_meta["input_frames"], dtype=np.float32)
        current_annotation = resume_meta["current_annotation"]
        threshold = float(resume_meta["threshold"])
        top_k_components = int(resume_meta["top_k_components"])
        polyline_method = str(resume_meta.get("polyline_method", "graph"))
        refine_score_mode = str(resume_meta["refine_score_mode"])
        refine_search_radius_px = int(resume_meta["refine_search_radius_px"])
        expected_suffix_length = self._sequence.frame_count - resume_from_frame - 1

        track.polygon_roi = polygon
        if resume_from_frame == track.seed_frame_index:
            track.seed_polyline = np.asarray(current_annotation.polyline, dtype=np.float64)

        track.drop_annotations_after(resume_from_frame)
        track.add_annotation(current_annotation)

        edge_prob = np.asarray(output.edge_prob, dtype=np.float32)
        if edge_prob.shape[0] != expected_suffix_length:
            raise ValueError("DexiNed resume output length must match the remaining frame count.")
        if input_frames.shape[0] != expected_suffix_length:
            raise ValueError("DexiNed resume input frame range must match the remaining frame count.")
        for local_index in range(edge_prob.shape[0]):
            frame_index = resume_from_frame + 1 + local_index
            if self._sequence.is_frame_excluded(frame_index):
                continue
            edge_frame = np.asarray(edge_prob[local_index], dtype=np.float32)
            input_frame = np.asarray(input_frames[local_index], dtype=np.float32)
            edge_binary_frame = None
            if output.edge_binary is not None:
                edge_binary_frame = np.asarray(output.edge_binary[local_index], dtype=bool)
            selection, _selected_edge_frame, _coarse_polyline, refined_polyline, geometry_quality, _max_prob = self._extract_dominant_edge_geometry(
                edge_frame,
                polygon_mask,
                input_frame=input_frame,
                edge_binary_frame=edge_binary_frame,
                requested_threshold=threshold,
                top_k_components=top_k_components,
                polyline_method=polyline_method,
                refine_score_mode=refine_score_mode,
                refine_search_radius_px=refine_search_radius_px,
            )
            track.add_annotation(
                EdgeFrameAnnotation(
                    frame_index=frame_index,
                    polyline=refined_polyline.polyline_xy,
                    edge_mask=selection.edge_mask,
                    visibility=FrameVisibility.VISIBLE,
                    source=EdgeAnnotationSource.DEXINED,
                    metrics=self._compute_edge_metrics(refined_polyline.polyline_xy),
                    geometry_quality=geometry_quality,
                )
            )

        self.set_edge_tracks(self._edge_tracks, selected_track_id=track.edge_track_id)
        self._show_current_frame(preserve_zoom=True)

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

    def _ensure_edge_results_dialog(self) -> EdgeTrackResultsDialog:
        if self._edge_results_dialog is None:
            self._edge_results_dialog = EdgeTrackResultsDialog(self)
            self._edge_results_dialog.track_selected.connect(self._on_edge_results_track_selected)
        return self._edge_results_dialog

    def _on_results_track_selected(self, track_id: object) -> None:
        if track_id is None:
            return
        self.track_list_panel.set_selected_track_id(int(track_id))
        self._on_track_selected(track_id)

    def _on_edge_results_track_selected(self, track_id: object) -> None:
        self.edge_track_list_panel.set_selected_track_id(None if track_id is None else int(track_id))
        self._on_edge_track_selected(track_id)

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

    def _on_edge_track_delete_requested(self, track_id: int) -> None:
        selected_row = self.edge_track_list_panel.list_tracks.currentRow()
        remaining_tracks = [track for track in self._edge_tracks if track.edge_track_id != track_id]
        if len(remaining_tracks) == len(self._edge_tracks):
            return

        next_selected_track_id = None
        if remaining_tracks:
            next_row = max(0, min(selected_row, len(remaining_tracks) - 1))
            next_selected_track_id = remaining_tracks[next_row].edge_track_id

        self.set_edge_tracks(remaining_tracks, selected_track_id=next_selected_track_id)
        self._show_current_frame(preserve_zoom=True)
        self.statusBar().showMessage(f"Deleted edge track {track_id}.", 3000)

    def _sync_results_dialog(self) -> None:
        if self._results_dialog is None:
            return
        self._results_dialog.set_context(self._sequence, self._tracks, selected_track_id=self._selected_track_id)

    def _sync_edge_results_dialog(self) -> None:
        if self._edge_results_dialog is None:
            return
        self._edge_results_dialog.set_context(
            self._sequence,
            self._edge_tracks,
            selected_track_id=self._selected_edge_track_id,
        )

    def _sync_results_dialog_selection(self) -> None:
        if self._results_dialog is None:
            return
        self._results_dialog.set_selected_track_id(self._selected_track_id)

    def _sync_edge_results_dialog_selection(self) -> None:
        self.edge_track_list_panel.set_selected_track_id(self._selected_edge_track_id)
        if self._edge_results_dialog is None:
            return
        self._edge_results_dialog.set_selected_track_id(self._selected_edge_track_id)

    def _has_results_data(self) -> bool:
        if self._sequence is None:
            return False
        for track in self._tracks:
            for frame_index in track.frame_indices:
                if self._sequence.is_frame_excluded(frame_index):
                    continue
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

    def _has_edge_results_data(self) -> bool:
        if self._sequence is None:
            return False
        for track in self._edge_tracks:
            for frame_index in track.frame_indices:
                if self._sequence.is_frame_excluded(frame_index):
                    continue
                annotation = track.get_annotation(frame_index)
                if annotation is None:
                    continue
                metrics = annotation.metrics
                if (
                    metrics.length_px is not None
                    and metrics.roughness_rms_px is not None
                    and metrics.mean_curvature is not None
                    and metrics.max_curvature is not None
                    and metrics.waviness_amplitude_px is not None
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
            if annotation is not None:
                track.add_annotation(annotation)

    def _resume_track_from_output(self, track_id: int, run_output: Sam2RunOutput, resume_frame: int) -> None:
        track = self._find_track_by_id(track_id)
        if track is None:
            raise RuntimeError(f"Track {track_id} does not exist.")
        track.drop_annotations_after(resume_frame)
        for local_frame_index in range(1, run_output.masks.shape[0]):
            annotation = self._annotation_from_sam2_frame(run_output, local_frame_index)
            if annotation is not None:
                track.add_annotation(annotation)

    def _annotation_from_sam2_frame(
        self,
        run_output: Sam2RunOutput,
        local_frame_index: int,
    ) -> TrackFrameAnnotation | None:
        if self._sequence is None:
            raise RuntimeError("No sequence loaded.")
        frame_index = run_output.frame_index_offset + local_frame_index
        if self._sequence.is_frame_excluded(frame_index):
            return None
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
