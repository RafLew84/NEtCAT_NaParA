from __future__ import annotations

from pathlib import Path

import numpy as np

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import build_molecular_position_plot_data, compare_molecular_frame_ranges
from moltrack.core import (
    MolecularDetectionSet,
    MolecularSegmentationSet,
    MolTrackRegistrationSettings,
    SUPPORTED_REGISTRATION_BACKENDS,
    build_moltrack_expanded_aligned_stack,
    build_molecular_centroids,
    run_moltrack_registration,
)
from moltrack.io import load_moltrack_image_series
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from moltrack.ui.dialogs import PositionAnalysisDialog
from moltrack.ui.widgets import STMSeriesViewer, SeriesMetadataPanel
from moltrack.yolo import MolTrackYoloDetector, discover_yolo_models
from moltrack.sam2 import MolTrackSam2Segmenter, discover_sam2_checkpoints, select_default_sam2_checkpoint
from moltrack.sam3 import (
    MolTrackSam3ConceptAdapter,
    MolTrackSam3PromptValidationError,
    build_moltrack_sam3_preview,
    build_moltrack_sam3_prompt_batch,
    commit_moltrack_sam3_preview,
)


MIN_MANUAL_BBOX_SIZE_PX = 1.0
SAM2_EXISTING_MASK_POLICY_REPLACE = "replace"
SAM2_EXISTING_MASK_POLICY_APPEND = "append"
SAM2_EXISTING_MASK_POLICY_SKIP = "skip"
SAM3_PROMPT_SOURCE_ACTIVE = "Active selected BBox"
SAM3_PROMPT_SOURCE_ALL_CURRENT = "All current BBoxes"
SAM3_PROMPT_SOURCE_SELECTED_CURRENT = "Selected current BBoxes"
SAM3_PROMPT_SOURCE_MANUAL = "Manual prompt BBoxes"


def _sam2_checkpoint_path(checkpoint) -> Path:
    return Path(getattr(checkpoint, "path", checkpoint))


class _RegistrationRunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, registration_runner, series, settings: MolTrackRegistrationSettings):
        super().__init__()
        self._registration_runner = registration_runner
        self._series = series
        self._settings = settings

    def run(self) -> None:
        try:
            result_set = self._registration_runner(self._series, settings=self._settings)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.finished.emit(result_set)


class _YoloDetectAllWorker(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        detector,
        frames,
        frame_indices: list[int],
        *,
        checkpoint_path,
        confidence_threshold: float,
        iou_threshold: float,
        source_view: str,
    ):
        super().__init__()
        self._detector = detector
        self._frames = frames
        self._frame_indices = frame_indices
        self._checkpoint_path = checkpoint_path
        self._confidence_threshold = confidence_threshold
        self._iou_threshold = iou_threshold
        self._source_view = source_view

    def run(self) -> None:
        try:
            results = []
            total = len(self._frame_indices)
            for position, (frame, frame_index) in enumerate(zip(self._frames, self._frame_indices), start=1):
                self.progress.emit(position, total)
                detections = self._detector.detect_frame(
                    frame,
                    frame_index=frame_index,
                    checkpoint_path=self._checkpoint_path,
                    confidence_threshold=self._confidence_threshold,
                    iou_threshold=self._iou_threshold,
                    source_view=self._source_view,
                )
                results.append((frame_index, frame.shape[:2], detections))
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.finished.emit(results)


class Sam2SegmentationSettingsDialog(QDialog):
    """Parameter dialog used before launching SAM2 segmentation."""

    def __init__(
        self,
        parent=None,
        *,
        backend: str = "SAM2",
        bbox_count: int = 1,
        initial_mask_threshold: float = 0.5,
        checkpoints=(),
        selected_checkpoint_path=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("SAM2 Segmentation")
        checkpoint_paths = [_sam2_checkpoint_path(checkpoint) for checkpoint in checkpoints]
        selected_path = Path(selected_checkpoint_path) if selected_checkpoint_path is not None else None

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.cmb_backend = QComboBox(self)
        self.cmb_backend.addItems(["SAM2"])
        backend_index = self.cmb_backend.findText(str(backend))
        if backend_index >= 0:
            self.cmb_backend.setCurrentIndex(backend_index)
        self.cmb_backend.setEnabled(False)
        form_layout.addRow("Backend", self.cmb_backend)

        self.lbl_bbox_count = QLabel(f"{int(bbox_count)} BBox(es)", self)
        form_layout.addRow("Scope", self.lbl_bbox_count)

        self.cmb_checkpoint = QComboBox(self)
        for checkpoint_path in checkpoint_paths:
            self.cmb_checkpoint.addItem(checkpoint_path.name, checkpoint_path)
        if selected_path is not None:
            for index in range(self.cmb_checkpoint.count()):
                if Path(self.cmb_checkpoint.itemData(index)) == selected_path:
                    self.cmb_checkpoint.setCurrentIndex(index)
                    break
        if self.cmb_checkpoint.count() == 0:
            self.cmb_checkpoint.addItem("No SAM2 checkpoints found", None)
            self.cmb_checkpoint.setEnabled(False)
        form_layout.addRow("Checkpoint", self.cmb_checkpoint)

        self.sp_mask_threshold = QDoubleSpinBox(self)
        self.sp_mask_threshold.setRange(0.01, 0.99)
        self.sp_mask_threshold.setSingleStep(0.05)
        self.sp_mask_threshold.setDecimals(2)
        self.sp_mask_threshold.setValue(float(initial_mask_threshold))
        form_layout.addRow("Mask threshold", self.sp_mask_threshold)

        self.cmb_existing_masks_policy = QComboBox(self)
        self.cmb_existing_masks_policy.addItem(
            "Replace existing SAM2 masks for same BBox",
            SAM2_EXISTING_MASK_POLICY_REPLACE,
        )
        self.cmb_existing_masks_policy.addItem("Append", SAM2_EXISTING_MASK_POLICY_APPEND)
        self.cmb_existing_masks_policy.addItem(
            "Skip BBoxes that already have SAM2 mask",
            SAM2_EXISTING_MASK_POLICY_SKIP,
        )
        form_layout.addRow("Existing SAM2 masks", self.cmb_existing_masks_policy)

        self.chk_keep_largest_component = QCheckBox("Keep largest component", self)
        form_layout.addRow("", self.chk_keep_largest_component)

        self.sp_min_mask_area_px = QSpinBox(self)
        self.sp_min_mask_area_px.setRange(0, 1_000_000)
        self.sp_min_mask_area_px.setValue(0)
        self.sp_min_mask_area_px.setSpecialValueText("Disabled")
        form_layout.addRow("Min mask area px", self.sp_min_mask_area_px)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(checkpoint_paths))
        layout.addWidget(self.button_box)

    def mask_probability_threshold(self) -> float:
        return float(self.sp_mask_threshold.value())

    def checkpoint_path(self):
        checkpoint_path = self.cmb_checkpoint.currentData()
        if checkpoint_path is None:
            return None
        return Path(checkpoint_path)

    def existing_sam2_masks_policy(self) -> str:
        return str(self.cmb_existing_masks_policy.currentData())

    def keep_largest_component(self) -> bool:
        return bool(self.chk_keep_largest_component.isChecked())

    def min_mask_area_px(self) -> int:
        return int(self.sp_min_mask_area_px.value())


class _Sam2SegmentWorker(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        segmenter,
        frame,
        detections,
        *,
        mask_probability_threshold: float,
        checkpoint_path=None,
        existing_masks_policy: str = SAM2_EXISTING_MASK_POLICY_REPLACE,
        keep_largest_component: bool = False,
        min_mask_area_px: int = 0,
    ):
        super().__init__()
        self._segmenter = segmenter
        self._frame = frame
        self._detections = list(detections)
        self._mask_probability_threshold = mask_probability_threshold
        self._checkpoint_path = Path(checkpoint_path) if checkpoint_path is not None else None
        self._existing_masks_policy = str(existing_masks_policy)
        self._keep_largest_component = bool(keep_largest_component)
        self._min_mask_area_px = int(min_mask_area_px)

    def run(self) -> None:
        try:
            results = []
            total = len(self._detections)
            for position, detection in enumerate(self._detections, start=1):
                self.progress.emit(position - 1, total)
                segmentation = self._segmenter.segment_detection(
                    self._frame,
                    detection,
                    mask_probability_threshold=self._mask_probability_threshold,
                    checkpoint_path=self._checkpoint_path,
                    existing_masks_policy=self._existing_masks_policy,
                    keep_largest_component=self._keep_largest_component,
                    min_mask_area_px=self._min_mask_area_px,
                )
                results.append((detection, segmentation))
                self.progress.emit(position, total)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.finished.emit(results)


class _Sam3ConceptWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        adapter,
        frame,
        prompts,
        *,
        frame_index: int,
        source_view: str,
        model_id: str,
        score_threshold: float,
        mask_threshold: float,
        max_results: int,
    ):
        super().__init__()
        self._adapter = adapter
        self._frame = frame
        self._prompts = tuple(prompts)
        self._frame_index = int(frame_index)
        self._source_view = str(source_view)
        self._model_id = str(model_id)
        self._score_threshold = float(score_threshold)
        self._mask_threshold = float(mask_threshold)
        self._max_results = int(max_results)

    def run(self) -> None:
        try:
            proposals = self._adapter.segment_prompts(
                self._frame,
                self._prompts,
                frame_index=self._frame_index,
                source_view=self._source_view,
                model_id=self._model_id,
                score_threshold=self._score_threshold,
                mask_threshold=self._mask_threshold,
                max_results=self._max_results,
            )
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.finished.emit(proposals)


class MolTrackMainWindow(QMainWindow):
    """Initial empty workspace for MolTrack."""

    _yolo_apply_detection_progress = pyqtSignal(int, int)
    _yolo_apply_detection_finished = pyqtSignal(object)
    _yolo_apply_detection_failed = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        *,
        series_loader=load_moltrack_image_series,
        registration_runner=run_moltrack_registration,
        expanded_aligned_builder=build_moltrack_expanded_aligned_stack,
        session_saver=save_moltrack_session,
        session_loader=load_moltrack_session,
        session_restorer=None,
        yolo_model_discovery=discover_yolo_models,
        yolo_detector=None,
        sam2_checkpoint_discovery=discover_sam2_checkpoints,
        sam2_segmenter=None,
        sam2_settings_dialog_factory=None,
        sam3_adapter=None,
    ):
        super().__init__(parent)
        self._series = None
        self._series_loader = series_loader
        self._registration_runner = registration_runner
        self._expanded_aligned_builder = expanded_aligned_builder
        self._session_saver = session_saver
        self._session_loader = session_loader
        self._session_restorer = (
            session_restorer
            if session_restorer is not None
            else lambda session: restore_moltrack_image_series_from_session(
                session,
                series_loader=self._series_loader,
            )
        )
        self._session_path: str | None = None
        self._yolo_model_discovery = yolo_model_discovery
        self._yolo_detector = yolo_detector if yolo_detector is not None else MolTrackYoloDetector()
        self._sam2_checkpoint_discovery = sam2_checkpoint_discovery
        self._sam2_segmenter = sam2_segmenter if sam2_segmenter is not None else MolTrackSam2Segmenter()
        self._sam2_settings_dialog_factory = sam2_settings_dialog_factory
        self._sam3_adapter = sam3_adapter if sam3_adapter is not None else MolTrackSam3ConceptAdapter()
        self._yolo_models = []
        self._sam2_checkpoints = []
        self._selected_sam2_checkpoint_path = None
        self._yolo_detection_running = False
        self._yolo_detection_progress_dialog: QProgressDialog | None = None
        self._yolo_detection_thread: QThread | None = None
        self._yolo_detection_worker: _YoloDetectAllWorker | None = None
        self._yolo_detection_model_name = ""
        self._yolo_detection_source_view = "raw"
        self._selected_molecular_detection_id: str | None = None
        self._selected_molecular_segmentation_id: str | None = None
        self._mask_edit_undo_stack_by_segmentation_id: dict[str, list[dict[str, object]]] = {}
        self._mask_edit_baseline_by_segmentation_id: dict[str, dict[str, object]] = {}
        self._sam2_segmentation_running = False
        self._sam2_segmentation_progress_dialog: QProgressDialog | None = None
        self._sam2_segmentation_thread: QThread | None = None
        self._sam2_segmentation_worker: _Sam2SegmentWorker | None = None
        self._sam2_segmentation_scope = ""
        self._sam2_segmentation_existing_masks_policy = SAM2_EXISTING_MASK_POLICY_REPLACE
        self._sam3_concept_running = False
        self._sam3_concept_progress_dialog: QProgressDialog | None = None
        self._sam3_concept_thread: QThread | None = None
        self._sam3_concept_worker: _Sam3ConceptWorker | None = None
        self._sam3_concept_source_view = "raw"
        self._sam3_concept_frame_index = 0
        self._sam3_concept_duplicate_iou_threshold = 0.9
        self._sam3_manual_positive_bboxes_by_context: dict[
            tuple[int, str], list[tuple[float, float, float, float]]
        ] = {}
        self._sam3_manual_negative_bboxes_by_context: dict[
            tuple[int, str], list[tuple[float, float, float, float]]
        ] = {}
        self._sam3_prompt_draw_mode: str | None = None
        self._position_analysis_dialog: PositionAnalysisDialog | None = None
        self._registration_running = False
        self._registration_progress_dialog: QProgressDialog | None = None
        self._registration_thread: QThread | None = None
        self._registration_worker: _RegistrationRunWorker | None = None
        self._yolo_apply_detection_progress.connect(
            self._on_yolo_detection_progress,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._yolo_apply_detection_finished.connect(
            self._on_yolo_detection_finished,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._yolo_apply_detection_failed.connect(
            self._on_yolo_detection_failed,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self.setWindowTitle("MolTrack")
        self.resize(1280, 860)
        self._build_actions()
        self._build_central_widget()
        self._refresh_yolo_models()
        self._refresh_sam2_checkpoints()
        self._connect_signals()
        self._update_navigation_enabled(False)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self.action_open_stm = QAction("Open STM...", self)
        self.action_open_stm.setToolTip("Load one MPP movie into MolTrack")
        self.action_open_stm_reverse = QAction("Open STM Reverse...", self)
        self.action_open_stm_reverse.setToolTip("Load one MPP movie with reversed frame order")
        self.action_open_state = QAction("Open State...", self)
        self.action_open_state.setToolTip("Load a saved MolTrack application state")
        self.action_save_state = QAction("Save State...", self)
        self.action_save_state.setToolTip("Save the current MolTrack application state")
        self.action_save_state.setEnabled(False)
        self.action_save_state_as = QAction("Save State As...", self)
        self.action_save_state_as.setToolTip("Save the current MolTrack application state to a new file")
        self.action_save_state_as.setEnabled(False)
        file_menu.addAction(self.action_open_stm)
        file_menu.addAction(self.action_open_stm_reverse)
        file_menu.addSeparator()
        file_menu.addAction(self.action_open_state)
        file_menu.addAction(self.action_save_state)
        file_menu.addAction(self.action_save_state_as)

    def _build_central_widget(self) -> None:
        central = QSplitter(Qt.Orientation.Horizontal, self)

        viewer_container = QWidget(self)
        viewer_layout = QVBoxLayout(viewer_container)
        self.viewer = STMSeriesViewer(viewer_container)
        viewer_layout.addWidget(self.viewer, 1)

        self.lbl_frame = QLabel("Frame: - / -", viewer_container)
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        viewer_layout.addWidget(self.lbl_frame)

        self.slider_frame = QSlider(Qt.Orientation.Horizontal, viewer_container)
        self.slider_frame.setTracking(True)
        viewer_layout.addWidget(self.slider_frame)

        self.sidebar_content = QWidget(self)
        self.sidebar_content.setObjectName("moltrack_right_controls_content")
        sidebar_content = self.sidebar_content
        sidebar_layout = QVBoxLayout(sidebar_content)
        self.metadata_panel = SeriesMetadataPanel(sidebar_content)
        sidebar_layout.addWidget(self.metadata_panel)
        self.btn_remove_current_frame = QPushButton("Remove current frame", sidebar_content)
        self.btn_remove_current_frame.setToolTip("Delete the current frame from the working series")
        self.btn_remove_current_frame.setEnabled(False)
        sidebar_layout.addWidget(self.btn_remove_current_frame)

        self.registration_group = QGroupBox("Registration", sidebar_content)
        registration_layout = QVBoxLayout(self.registration_group)
        self.cmb_registration_backend = QComboBox(self.registration_group)
        self.cmb_registration_backend.addItems(SUPPORTED_REGISTRATION_BACKENDS)
        self.cmb_registration_backend.setEnabled(False)
        registration_layout.addWidget(self.cmb_registration_backend)
        self.btn_run_registration = QPushButton("Run registration", self.registration_group)
        self.btn_run_registration.setEnabled(False)
        registration_layout.addWidget(self.btn_run_registration)
        self.cmb_registration_view_mode = QComboBox(self.registration_group)
        self.cmb_registration_view_mode.addItems(["Show raw", "Show expanded aligned"])
        self.cmb_registration_view_mode.setEnabled(False)
        registration_layout.addWidget(self.cmb_registration_view_mode)
        self.lbl_registration_status = QLabel("No registration results", self.registration_group)
        self.lbl_registration_status.setWordWrap(True)
        registration_layout.addWidget(self.lbl_registration_status)
        sidebar_layout.addWidget(self.registration_group)

        self.yolo_group = QGroupBox("YOLO Detection", sidebar_content)
        yolo_layout = QVBoxLayout(self.yolo_group)
        self.lbl_yolo_models = QLabel("", self.yolo_group)
        self.lbl_yolo_models.setWordWrap(True)
        yolo_layout.addWidget(self.lbl_yolo_models)
        self.cmb_yolo_model = QComboBox(self.yolo_group)
        yolo_layout.addWidget(self.cmb_yolo_model)
        self.btn_yolo_refresh_models = QPushButton("Refresh models", self.yolo_group)
        yolo_layout.addWidget(self.btn_yolo_refresh_models)
        self.sp_yolo_confidence = QDoubleSpinBox(self.yolo_group)
        self.sp_yolo_confidence.setRange(0.0, 1.0)
        self.sp_yolo_confidence.setSingleStep(0.05)
        self.sp_yolo_confidence.setDecimals(2)
        self.sp_yolo_confidence.setPrefix("Confidence ")
        self.sp_yolo_confidence.setValue(0.25)
        yolo_layout.addWidget(self.sp_yolo_confidence)
        self.sp_yolo_iou = QDoubleSpinBox(self.yolo_group)
        self.sp_yolo_iou.setRange(0.0, 1.0)
        self.sp_yolo_iou.setSingleStep(0.05)
        self.sp_yolo_iou.setDecimals(2)
        self.sp_yolo_iou.setPrefix("IoU ")
        self.sp_yolo_iou.setValue(0.45)
        yolo_layout.addWidget(self.sp_yolo_iou)
        self.btn_yolo_detect_current = QPushButton("Detect Current Frame", self.yolo_group)
        self.btn_yolo_detect_current.setEnabled(False)
        yolo_layout.addWidget(self.btn_yolo_detect_current)
        self.btn_yolo_detect_all_frames = QPushButton("Detect All Frames", self.yolo_group)
        self.btn_yolo_detect_all_frames.setEnabled(False)
        yolo_layout.addWidget(self.btn_yolo_detect_all_frames)
        self.btn_yolo_clear_current = QPushButton("Clear Current", self.yolo_group)
        self.btn_yolo_clear_current.setEnabled(False)
        yolo_layout.addWidget(self.btn_yolo_clear_current)
        self.lbl_yolo_status = QLabel("Detections: current 0 | series 0", self.yolo_group)
        self.lbl_yolo_status.setWordWrap(True)
        yolo_layout.addWidget(self.lbl_yolo_status)
        sidebar_layout.addWidget(self.yolo_group)

        self.bbox_resize_group = QGroupBox("BBox Resize", sidebar_content)
        bbox_resize_layout = QVBoxLayout(self.bbox_resize_group)
        self.sp_bbox_resize_margin = QDoubleSpinBox(self.bbox_resize_group)
        self.sp_bbox_resize_margin.setRange(0.1, 1000.0)
        self.sp_bbox_resize_margin.setSingleStep(1.0)
        self.sp_bbox_resize_margin.setDecimals(1)
        self.sp_bbox_resize_margin.setPrefix("Margin px ")
        self.sp_bbox_resize_margin.setValue(1.0)
        self.sp_bbox_resize_margin.setEnabled(False)
        bbox_resize_layout.addWidget(self.sp_bbox_resize_margin)
        self.btn_bbox_increase = QPushButton("Increase BBoxes", self.bbox_resize_group)
        self.btn_bbox_increase.setEnabled(False)
        bbox_resize_layout.addWidget(self.btn_bbox_increase)
        self.btn_bbox_decrease = QPushButton("Decrease BBoxes", self.bbox_resize_group)
        self.btn_bbox_decrease.setEnabled(False)
        bbox_resize_layout.addWidget(self.btn_bbox_decrease)
        self.btn_bbox_reset = QPushButton("Reset BBoxes", self.bbox_resize_group)
        self.btn_bbox_reset.setEnabled(False)
        bbox_resize_layout.addWidget(self.btn_bbox_reset)
        self.lbl_bbox_resize_status = QLabel("BBoxes: no detections", self.bbox_resize_group)
        self.lbl_bbox_resize_status.setWordWrap(True)
        bbox_resize_layout.addWidget(self.lbl_bbox_resize_status)
        sidebar_layout.addWidget(self.bbox_resize_group)

        self.bbox_edit_group = QGroupBox("BBox Edit", sidebar_content)
        bbox_edit_layout = QVBoxLayout(self.bbox_edit_group)
        self.btn_bbox_add = QPushButton("Add BBox", self.bbox_edit_group)
        self.btn_bbox_add.setCheckable(True)
        self.btn_bbox_add.setEnabled(False)
        bbox_edit_layout.addWidget(self.btn_bbox_add)
        self.btn_bbox_delete_selected = QPushButton("Delete Selected BBox", self.bbox_edit_group)
        self.btn_bbox_delete_selected.setEnabled(False)
        bbox_edit_layout.addWidget(self.btn_bbox_delete_selected)
        self.lbl_bbox_edit_status = QLabel("No BBox selected", self.bbox_edit_group)
        self.lbl_bbox_edit_status.setWordWrap(True)
        bbox_edit_layout.addWidget(self.lbl_bbox_edit_status)
        self.lbl_bbox_opacity = QLabel("BBox opacity: 100%", self.bbox_edit_group)
        bbox_edit_layout.addWidget(self.lbl_bbox_opacity)
        self.slider_bbox_opacity = QSlider(Qt.Orientation.Horizontal, self.bbox_edit_group)
        self.slider_bbox_opacity.setRange(0, 100)
        self.slider_bbox_opacity.setValue(100)
        self.slider_bbox_opacity.setTracking(True)
        bbox_edit_layout.addWidget(self.slider_bbox_opacity)
        sidebar_layout.addWidget(self.bbox_edit_group)

        self.segmentation_group = QGroupBox("Segmentation", sidebar_content)
        segmentation_layout = QVBoxLayout(self.segmentation_group)
        self.cmb_segmentation_backend = QComboBox(self.segmentation_group)
        self.cmb_segmentation_backend.addItems(["SAM2", "SAM3"])
        self.cmb_segmentation_backend.setEnabled(False)
        segmentation_layout.addWidget(self.cmb_segmentation_backend)
        self.sp_sam2_mask_threshold = QDoubleSpinBox(self.segmentation_group)
        self.sp_sam2_mask_threshold.setRange(0.01, 0.99)
        self.sp_sam2_mask_threshold.setSingleStep(0.05)
        self.sp_sam2_mask_threshold.setDecimals(2)
        self.sp_sam2_mask_threshold.setPrefix("Mask threshold ")
        self.sp_sam2_mask_threshold.setValue(0.5)
        self.sp_sam2_mask_threshold.setEnabled(False)
        segmentation_layout.addWidget(self.sp_sam2_mask_threshold)
        self.btn_sam2_segment_selected = QPushButton("Segment Selected BBox", self.segmentation_group)
        self.btn_sam2_segment_selected.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam2_segment_selected)
        self.btn_sam2_segment_all_current = QPushButton("Segment All BBoxes In Image", self.segmentation_group)
        self.btn_sam2_segment_all_current.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam2_segment_all_current)
        self.cmb_active_segmentation = QComboBox(self.segmentation_group)
        self.cmb_active_segmentation.setEnabled(False)
        segmentation_layout.addWidget(self.cmb_active_segmentation)
        self.lbl_active_segmentation_status = QLabel("No active segmentation", self.segmentation_group)
        self.lbl_active_segmentation_status.setWordWrap(True)
        segmentation_layout.addWidget(self.lbl_active_segmentation_status)
        self.btn_edit_mask = QPushButton("Edit Mask", self.segmentation_group)
        self.btn_edit_mask.setCheckable(True)
        self.btn_edit_mask.setEnabled(False)
        segmentation_layout.addWidget(self.btn_edit_mask)
        self.cmb_mask_brush_mode = QComboBox(self.segmentation_group)
        self.cmb_mask_brush_mode.addItem("Add pixels", "add")
        self.cmb_mask_brush_mode.addItem("Erase pixels", "erase")
        self.cmb_mask_brush_mode.setEnabled(False)
        segmentation_layout.addWidget(self.cmb_mask_brush_mode)
        self.sp_mask_brush_size = QSpinBox(self.segmentation_group)
        self.sp_mask_brush_size.setRange(0, 100)
        self.sp_mask_brush_size.setPrefix("Brush size px ")
        self.sp_mask_brush_size.setValue(1)
        self.sp_mask_brush_size.setEnabled(False)
        segmentation_layout.addWidget(self.sp_mask_brush_size)
        self.btn_undo_mask_edit = QPushButton("Undo Mask Edit", self.segmentation_group)
        self.btn_undo_mask_edit.setEnabled(False)
        segmentation_layout.addWidget(self.btn_undo_mask_edit)
        self.btn_apply_mask_edit = QPushButton("Apply Edit", self.segmentation_group)
        self.btn_apply_mask_edit.setEnabled(False)
        segmentation_layout.addWidget(self.btn_apply_mask_edit)
        self.btn_cancel_mask_edit = QPushButton("Cancel Edit", self.segmentation_group)
        self.btn_cancel_mask_edit.setEnabled(False)
        segmentation_layout.addWidget(self.btn_cancel_mask_edit)
        self.btn_reset_mask_to_sam2_result = QPushButton("Reset to SAM2 Result", self.segmentation_group)
        self.btn_reset_mask_to_sam2_result.setEnabled(False)
        segmentation_layout.addWidget(self.btn_reset_mask_to_sam2_result)
        self.cmb_sam3_model = QComboBox(self.segmentation_group)
        self.cmb_sam3_model.addItems(["facebook/sam3", "facebook/sam3.1"])
        self.cmb_sam3_model.setEnabled(False)
        segmentation_layout.addWidget(self.cmb_sam3_model)
        self.cmb_sam3_prompt_source = QComboBox(self.segmentation_group)
        self.cmb_sam3_prompt_source.addItems(
            [
                SAM3_PROMPT_SOURCE_ACTIVE,
                SAM3_PROMPT_SOURCE_ALL_CURRENT,
                SAM3_PROMPT_SOURCE_SELECTED_CURRENT,
                SAM3_PROMPT_SOURCE_MANUAL,
            ]
        )
        self.cmb_sam3_prompt_source.setEnabled(False)
        segmentation_layout.addWidget(self.cmb_sam3_prompt_source)
        self.btn_sam3_add_positive_prompt = QPushButton("Add + Prompt BBox", self.segmentation_group)
        self.btn_sam3_add_positive_prompt.setCheckable(True)
        self.btn_sam3_add_positive_prompt.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam3_add_positive_prompt)
        self.btn_sam3_add_negative_prompt = QPushButton("Add - Prompt BBox", self.segmentation_group)
        self.btn_sam3_add_negative_prompt.setCheckable(True)
        self.btn_sam3_add_negative_prompt.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam3_add_negative_prompt)
        self.btn_sam3_clear_prompts = QPushButton("Clear SAM3 Prompts", self.segmentation_group)
        self.btn_sam3_clear_prompts.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam3_clear_prompts)
        self.lbl_sam3_prompt_status = QLabel("Manual prompts: +0 / -0", self.segmentation_group)
        self.lbl_sam3_prompt_status.setWordWrap(True)
        segmentation_layout.addWidget(self.lbl_sam3_prompt_status)
        self.sp_sam3_score_threshold = QDoubleSpinBox(self.segmentation_group)
        self.sp_sam3_score_threshold.setRange(0.0, 1.0)
        self.sp_sam3_score_threshold.setSingleStep(0.05)
        self.sp_sam3_score_threshold.setDecimals(2)
        self.sp_sam3_score_threshold.setPrefix("SAM3 score ")
        self.sp_sam3_score_threshold.setValue(0.3)
        self.sp_sam3_score_threshold.setEnabled(False)
        segmentation_layout.addWidget(self.sp_sam3_score_threshold)
        self.sp_sam3_mask_threshold = QDoubleSpinBox(self.segmentation_group)
        self.sp_sam3_mask_threshold.setRange(0.0, 1.0)
        self.sp_sam3_mask_threshold.setSingleStep(0.05)
        self.sp_sam3_mask_threshold.setDecimals(2)
        self.sp_sam3_mask_threshold.setPrefix("SAM3 mask ")
        self.sp_sam3_mask_threshold.setValue(0.5)
        self.sp_sam3_mask_threshold.setEnabled(False)
        segmentation_layout.addWidget(self.sp_sam3_mask_threshold)
        self.sp_sam3_duplicate_iou = QDoubleSpinBox(self.segmentation_group)
        self.sp_sam3_duplicate_iou.setRange(0.0, 1.0)
        self.sp_sam3_duplicate_iou.setSingleStep(0.05)
        self.sp_sam3_duplicate_iou.setDecimals(2)
        self.sp_sam3_duplicate_iou.setPrefix("Duplicate IoU ")
        self.sp_sam3_duplicate_iou.setValue(0.9)
        self.sp_sam3_duplicate_iou.setEnabled(False)
        segmentation_layout.addWidget(self.sp_sam3_duplicate_iou)
        self.sp_sam3_max_results = QSpinBox(self.segmentation_group)
        self.sp_sam3_max_results.setRange(1, 10000)
        self.sp_sam3_max_results.setPrefix("Max results ")
        self.sp_sam3_max_results.setValue(300)
        self.sp_sam3_max_results.setEnabled(False)
        segmentation_layout.addWidget(self.sp_sam3_max_results)
        self.btn_sam3_run_concepts = QPushButton("Run SAM3 Concepts", self.segmentation_group)
        self.btn_sam3_run_concepts.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam3_run_concepts)
        self.btn_sam3_commit_proposals = QPushButton("Commit Proposals", self.segmentation_group)
        self.btn_sam3_commit_proposals.setEnabled(False)
        segmentation_layout.addWidget(self.btn_sam3_commit_proposals)
        self.lbl_segmentation_status = QLabel("No series loaded", self.segmentation_group)
        self.lbl_segmentation_status.setWordWrap(True)
        segmentation_layout.addWidget(self.lbl_segmentation_status)
        sidebar_layout.addWidget(self.segmentation_group)

        self.position_analysis_group = QGroupBox("Position Analysis", sidebar_content)
        position_analysis_layout = QVBoxLayout(self.position_analysis_group)
        self.chk_show_centroids = QCheckBox("Show centroids", self.position_analysis_group)
        self.chk_show_centroids.setChecked(False)
        position_analysis_layout.addWidget(self.chk_show_centroids)
        self.btn_position_analysis = QPushButton("Position Analysis...", self.position_analysis_group)
        self.btn_position_analysis.setEnabled(False)
        position_analysis_layout.addWidget(self.btn_position_analysis)
        sidebar_layout.addWidget(self.position_analysis_group)

        sidebar_layout.addStretch(1)

        self.sidebar_scroll_area = QScrollArea(self)
        self.sidebar_scroll_area.setObjectName("moltrack_right_controls_scroll")
        self.sidebar_scroll_area.setWidgetResizable(True)
        self.sidebar_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.sidebar_scroll_area.setMinimumWidth(320)
        self.sidebar_scroll_area.setWidget(sidebar_content)

        central.addWidget(viewer_container)
        central.addWidget(self.sidebar_scroll_area)
        central.setStretchFactor(0, 1)
        central.setStretchFactor(1, 0)
        central.setSizes([940, 340])
        self.setCentralWidget(central)

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)

    def _connect_signals(self) -> None:
        self.action_open_stm.triggered.connect(self._on_open_stm_requested)
        self.action_open_stm_reverse.triggered.connect(self._on_open_stm_reverse_requested)
        self.action_open_state.triggered.connect(self._on_open_state_requested)
        self.action_save_state.triggered.connect(self._on_save_state_requested)
        self.action_save_state_as.triggered.connect(self._on_save_state_as_requested)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)
        self.btn_remove_current_frame.clicked.connect(self._on_remove_current_frame_requested)
        self.btn_run_registration.clicked.connect(self._on_run_registration_requested)
        self.cmb_registration_view_mode.currentTextChanged.connect(self._on_registration_view_mode_changed)
        self.btn_yolo_refresh_models.clicked.connect(self._refresh_yolo_models)
        self.btn_yolo_detect_current.clicked.connect(self._on_yolo_detect_current_requested)
        self.btn_yolo_detect_all_frames.clicked.connect(self._on_yolo_detect_all_frames_requested)
        self.btn_yolo_clear_current.clicked.connect(self._on_yolo_clear_current_requested)
        self.btn_bbox_increase.clicked.connect(self._on_bbox_increase_requested)
        self.btn_bbox_decrease.clicked.connect(self._on_bbox_decrease_requested)
        self.btn_bbox_reset.clicked.connect(self._on_bbox_reset_requested)
        self.btn_bbox_add.toggled.connect(self._on_bbox_add_toggled)
        self.btn_bbox_delete_selected.clicked.connect(self._on_bbox_delete_selected_requested)
        self.slider_bbox_opacity.valueChanged.connect(self._on_bbox_opacity_changed)
        self.chk_show_centroids.toggled.connect(self._on_show_centroids_toggled)
        self.btn_position_analysis.clicked.connect(self._on_position_analysis_requested)
        self.cmb_segmentation_backend.currentTextChanged.connect(self._on_segmentation_backend_changed)
        self.cmb_active_segmentation.currentIndexChanged.connect(self._on_active_segmentation_combo_changed)
        self.btn_edit_mask.toggled.connect(self._on_edit_mask_toggled)
        self.btn_undo_mask_edit.clicked.connect(lambda _checked=False: self.undo_last_mask_edit())
        self.btn_apply_mask_edit.clicked.connect(lambda _checked=False: self.apply_active_mask_edit())
        self.btn_cancel_mask_edit.clicked.connect(lambda _checked=False: self.cancel_active_mask_edit())
        self.btn_reset_mask_to_sam2_result.clicked.connect(
            lambda _checked=False: self.reset_active_segmentation_to_sam2_result()
        )
        self.btn_sam2_segment_selected.clicked.connect(self._on_sam2_segment_selected_requested)
        self.btn_sam2_segment_all_current.clicked.connect(self._on_sam2_segment_all_current_requested)
        self.btn_sam3_add_positive_prompt.toggled.connect(self._on_sam3_add_positive_prompt_toggled)
        self.btn_sam3_add_negative_prompt.toggled.connect(self._on_sam3_add_negative_prompt_toggled)
        self.btn_sam3_clear_prompts.clicked.connect(lambda _checked=False: self.clear_sam3_manual_prompts())
        self.btn_sam3_run_concepts.clicked.connect(self._on_sam3_run_concepts_requested)
        self.btn_sam3_commit_proposals.clicked.connect(self._on_sam3_commit_proposals_requested)
        self.viewer.molecular_detection_selection_changed.connect(self._on_molecular_detection_selection_changed)
        self.viewer.molecular_segmentation_selection_changed.connect(self._on_molecular_segmentation_selection_changed)
        self.viewer.manual_molecular_bbox_drawn.connect(self._on_manual_molecular_bbox_drawn)
        self.viewer.manual_molecular_mask_brush_dragged.connect(self._on_manual_mask_brush_dragged)

    def set_image_series(self, series) -> None:
        self._clear_sam3_prompt_draw_mode()
        self._sam3_manual_positive_bboxes_by_context.clear()
        self._sam3_manual_negative_bboxes_by_context.clear()
        self._series = series
        self._set_registration_view_mode("Show raw")
        self._sync_navigation_controls()
        self.viewer.set_image_series(series)
        self.metadata_panel.set_image_series(series)

    def open_stm_source(self, source_path, *, reverse_frame_order: bool = False) -> None:
        series = self._series_loader(source_path, reverse_frame_order=reverse_frame_order)
        self.set_image_series(series)
        self._session_path = None
        self.statusBar().showMessage(f"Loaded {series.source_path}", 3000)

    def _sync_navigation_controls(self) -> None:
        self._set_file_actions_enabled(not self._is_processing())
        if self._series is None:
            self.lbl_frame.setText("Frame: - / -")
            self._update_navigation_enabled(False)
            self.btn_remove_current_frame.setEnabled(False)
            self.cmb_registration_backend.setEnabled(False)
            self.btn_run_registration.setEnabled(False)
            self.cmb_registration_view_mode.setEnabled(False)
            self.btn_position_analysis.setEnabled(False)
            self._set_registration_view_mode("Show raw")
            self.lbl_registration_status.setText("No registration results")
            self._sync_yolo_controls()
            return

        controls_enabled = not self._is_processing()
        self._update_navigation_enabled(controls_enabled)
        self.btn_remove_current_frame.setEnabled(controls_enabled and self._series.frame_count > 1)
        self.cmb_registration_backend.setEnabled(controls_enabled)
        self.btn_run_registration.setEnabled(controls_enabled)
        self.btn_position_analysis.setEnabled(controls_enabled)
        has_registration = self._series.registration_results is not None
        self.cmb_registration_view_mode.setEnabled(controls_enabled and has_registration)
        if not has_registration:
            self._set_registration_view_mode("Show raw")
        self._sync_registration_status()
        self.slider_frame.blockSignals(True)
        try:
            self.slider_frame.setRange(0, self._series.frame_count - 1)
            self.slider_frame.setValue(self._series.active_frame_index)
        finally:
            self.slider_frame.blockSignals(False)
        self.lbl_frame.setText(f"Frame: {self._series.active_frame_index + 1} / {self._series.frame_count}")
        self._sync_yolo_controls()
        self._sync_segmentation_controls()

    def _refresh_yolo_models(self) -> None:
        self._yolo_models = list(self._yolo_model_discovery())
        self.cmb_yolo_model.blockSignals(True)
        try:
            self.cmb_yolo_model.clear()
            for model in self._yolo_models:
                self.cmb_yolo_model.addItem(self._yolo_model_display_name(model), model)
        finally:
            self.cmb_yolo_model.blockSignals(False)

        if self._yolo_models:
            self.lbl_yolo_models.setText(f"{len(self._yolo_models)} YOLO model(s) available")
        else:
            self.lbl_yolo_models.setText("No YOLO models found in nanotrack/yolo_models")
        self._sync_yolo_controls()

    def _refresh_sam2_checkpoints(self) -> None:
        try:
            checkpoints = list(self._sam2_checkpoint_discovery())
        except Exception:
            checkpoints = []
        self._sam2_checkpoints = [_sam2_checkpoint_path(checkpoint) for checkpoint in checkpoints]
        if (
            self._selected_sam2_checkpoint_path is None
            or self._selected_sam2_checkpoint_path not in self._sam2_checkpoints
        ):
            default_checkpoint = select_default_sam2_checkpoint(self._sam2_checkpoints)
            self._selected_sam2_checkpoint_path = (
                _sam2_checkpoint_path(default_checkpoint) if default_checkpoint is not None else None
            )
        self._sync_segmentation_controls()

    def _sync_yolo_controls(self) -> None:
        controls_enabled = self._series is not None and not self._is_processing()
        has_models = self.cmb_yolo_model.count() > 0
        self.cmb_yolo_model.setEnabled(controls_enabled and has_models)
        self.btn_yolo_refresh_models.setEnabled(not self._is_processing())
        self.sp_yolo_confidence.setEnabled(controls_enabled)
        self.sp_yolo_iou.setEnabled(controls_enabled)
        self.btn_yolo_detect_current.setEnabled(controls_enabled and has_models)
        self.btn_yolo_detect_all_frames.setEnabled(controls_enabled and has_models)
        current_count = self._current_molecular_detection_count()
        self.btn_yolo_clear_current.setEnabled(controls_enabled and current_count > 0)
        if self._series is not None and self._series.molecular_detections is not None:
            total_count = self._series.molecular_detections.detection_count
        else:
            total_count = 0
        self.lbl_yolo_status.setText(f"Detections: current {current_count} | series {total_count}")
        self._sync_bbox_resize_controls()
        self._sync_bbox_edit_controls()

    def _sync_bbox_resize_controls(self) -> None:
        controls_enabled = self._series is not None and not self._is_processing()
        if self._series is None or self._series.molecular_detections is None:
            source_count = 0
            source_view = self._current_yolo_source_view()
        else:
            source_view = self._current_yolo_source_view()
            source_count = self._source_view_molecular_detection_count(source_view)
        has_detections = controls_enabled and source_count > 0
        self.sp_bbox_resize_margin.setEnabled(has_detections)
        self.btn_bbox_increase.setEnabled(has_detections)
        self.btn_bbox_decrease.setEnabled(has_detections)
        self.btn_bbox_reset.setEnabled(has_detections)
        view_label = "expanded aligned" if source_view == "expanded_aligned" else "raw"
        self.lbl_bbox_resize_status.setText(f"BBoxes: {view_label} {source_count}")

    def _sync_bbox_edit_controls(self) -> None:
        controls_enabled = self._series is not None and not self._is_processing()
        sam3_prompt_tool_active = self._sam3_prompt_draw_mode is not None
        self.btn_bbox_add.setEnabled(controls_enabled and not sam3_prompt_tool_active)
        if (not controls_enabled or sam3_prompt_tool_active) and self.btn_bbox_add.isChecked():
            self.btn_bbox_add.blockSignals(True)
            try:
                self.btn_bbox_add.setChecked(False)
            finally:
                self.btn_bbox_add.blockSignals(False)
            self.viewer.set_molecular_bbox_add_mode_enabled(False)

        selected_detection = self._current_selected_molecular_detection()
        has_selection = controls_enabled and selected_detection is not None
        self.btn_bbox_delete_selected.setEnabled(has_selection)
        self._sync_segmentation_controls()

        if controls_enabled and not sam3_prompt_tool_active and self.btn_bbox_add.isChecked():
            self.lbl_bbox_edit_status.setText("Add BBox: drag on image")
            return

        if selected_detection is None:
            self.lbl_bbox_edit_status.setText("No BBox selected")
            return

        view_label = "expanded aligned" if selected_detection.source_view == "expanded_aligned" else "raw"
        self.lbl_bbox_edit_status.setText(
            f"Selected BBox: frame {selected_detection.frame_index + 1}, {view_label}"
        )

    def _sync_segmentation_controls(self) -> None:
        self._sync_active_segmentation_panel()
        if self._sam2_segmentation_running:
            self.cmb_segmentation_backend.setEnabled(False)
            self.sp_sam2_mask_threshold.setEnabled(False)
            self.btn_sam2_segment_selected.setEnabled(False)
            self.btn_sam2_segment_all_current.setEnabled(False)
            self.cmb_active_segmentation.setEnabled(False)
            self._set_sam3_controls_enabled(False)
            self.lbl_segmentation_status.setText("Running SAM2 segmentation...")
            return
        if self._sam3_concept_running:
            self.cmb_segmentation_backend.setEnabled(False)
            self.sp_sam2_mask_threshold.setEnabled(False)
            self.btn_sam2_segment_selected.setEnabled(False)
            self.btn_sam2_segment_all_current.setEnabled(False)
            self.cmb_active_segmentation.setEnabled(False)
            self._set_sam3_controls_enabled(False)
            self.lbl_segmentation_status.setText("Running SAM3 concepts...")
            return
        controls_enabled = self._series is not None and not self._is_processing()
        sam3_active = self.cmb_segmentation_backend.currentText() == "SAM3"
        sam2_checkpoint_available = self._selected_sam2_checkpoint_path is not None
        selected_detection = self._current_selected_molecular_detection()
        current_count = self._current_molecular_detection_count()
        has_selection = controls_enabled and selected_detection is not None
        has_current_detections = controls_enabled and current_count > 0
        self.cmb_segmentation_backend.setEnabled(controls_enabled)
        self.sp_sam2_mask_threshold.setEnabled(
            has_current_detections and not sam3_active and sam2_checkpoint_available
        )
        self.btn_sam2_segment_selected.setEnabled(has_selection and not sam3_active and sam2_checkpoint_available)
        self.btn_sam2_segment_all_current.setEnabled(
            has_current_detections and not sam3_active and sam2_checkpoint_available
        )
        self._set_sam3_controls_enabled(controls_enabled and sam3_active)
        self.btn_sam3_commit_proposals.setEnabled(
            controls_enabled and sam3_active and self._current_sam3_preview() is not None
        )
        if not controls_enabled:
            self.lbl_segmentation_status.setText("No series loaded")
            return
        if sam3_active:
            preview = self._current_sam3_preview()
            if preview is not None:
                self.lbl_segmentation_status.setText(f"SAM3 preview: {preview.proposal_count} proposal(s)")
                return
            self.lbl_segmentation_status.setText(f"SAM3 ready: {current_count} BBox(es) in current image")
            return
        if not sam2_checkpoint_available:
            self.lbl_segmentation_status.setText("No SAM2 checkpoints found")
            return
        if current_count == 0:
            self.lbl_segmentation_status.setText("No BBox in current image")
            return
        if selected_detection is None:
            self.lbl_segmentation_status.setText(f"Ready: {current_count} BBox(es) in current image")
            return
        view_label = "expanded aligned" if selected_detection.source_view == "expanded_aligned" else "raw"
        self.lbl_segmentation_status.setText(
            f"Ready: frame {selected_detection.frame_index + 1}, {view_label}, {current_count} BBox(es)"
        )

    def _set_sam3_controls_enabled(self, enabled: bool) -> None:
        if not enabled and self._sam3_prompt_draw_mode is not None:
            self._sam3_prompt_draw_mode = None
            self._set_sam3_prompt_button_states(None)
        self.cmb_sam3_model.setEnabled(enabled)
        self.cmb_sam3_prompt_source.setEnabled(enabled)
        self.btn_sam3_add_positive_prompt.setEnabled(enabled)
        self.btn_sam3_add_negative_prompt.setEnabled(enabled)
        self.btn_sam3_clear_prompts.setEnabled(enabled)
        self._sync_sam3_prompt_status()
        self.sp_sam3_score_threshold.setEnabled(enabled)
        self.sp_sam3_mask_threshold.setEnabled(enabled)
        self.sp_sam3_duplicate_iou.setEnabled(enabled)
        self.sp_sam3_max_results.setEnabled(enabled)
        self.btn_sam3_run_concepts.setEnabled(enabled)

    def _current_sam3_preview(self):
        if self._series is None:
            return None
        preview = getattr(self._series, "sam3_preview", None)
        if preview is None:
            return None
        if not preview.matches_context(
            frame_index=self._series.active_frame_index,
            source_view=self._current_yolo_source_view(),
        ):
            return None
        return preview

    def _current_molecular_detection_count(self) -> int:
        return len(self._current_frame_molecular_detections())

    def _current_frame_molecular_detections(self) -> list:
        if self._series is None or self._series.molecular_detections is None:
            return []
        return list(
            self._series.molecular_detections.get_detections(
                self._series.active_frame_index,
                source_view=self._current_yolo_source_view(),
            )
        )

    def _current_yolo_source_view(self) -> str:
        return "expanded_aligned" if self._is_expanded_aligned_view_requested() else "raw"

    def selected_molecular_detection_id(self) -> str | None:
        return self._selected_molecular_detection_id

    def selected_molecular_segmentation_id(self) -> str | None:
        return self._selected_molecular_segmentation_id

    def sam3_prompt_draw_mode(self) -> str | None:
        return self._sam3_prompt_draw_mode

    def add_sam3_manual_prompt_bbox(
        self,
        bbox_xyxy: tuple[float, float, float, float],
        *,
        label: int,
    ) -> bool:
        if self._series is None:
            return False
        label = int(label)
        if label not in (0, 1):
            raise ValueError("SAM3 manual prompt label must be 0 or 1.")
        try:
            x1, y1, x2, y2 = (float(value) for value in bbox_xyxy)
        except (TypeError, ValueError) as exc:
            raise ValueError("SAM3 manual prompt bbox must contain four numeric values.") from exc
        bbox = self._manual_bbox_from_pixel_drag(
            (x1, y1),
            (x2, y2),
            frame_shape=self._current_bbox_frame_shape(self._current_yolo_source_view()),
        )
        if bbox is None:
            self.statusBar().showMessage("Draw a larger SAM3 prompt BBox.", 3000)
            return False

        target = (
            self._sam3_manual_positive_bboxes_by_context
            if label == 1
            else self._sam3_manual_negative_bboxes_by_context
        )
        target.setdefault(self._current_sam3_manual_prompt_context(), []).append(bbox)
        self._show_current_sam3_manual_prompt_overlays()
        self._sync_sam3_prompt_status()
        self._sync_segmentation_controls()
        return True

    def clear_sam3_manual_prompts(self) -> int:
        context = self._current_sam3_manual_prompt_context()
        positive_count = len(self._sam3_manual_positive_bboxes_by_context.pop(context, []))
        negative_count = len(self._sam3_manual_negative_bboxes_by_context.pop(context, []))
        self._show_current_sam3_manual_prompt_overlays()
        self._sync_sam3_prompt_status()
        self._sync_segmentation_controls()
        return positive_count + negative_count

    def sam3_manual_prompt_counts(self) -> tuple[int, int]:
        context = self._current_sam3_manual_prompt_context()
        return (
            len(self._sam3_manual_positive_bboxes_by_context.get(context, ())),
            len(self._sam3_manual_negative_bboxes_by_context.get(context, ())),
        )

    def sam3_manual_prompt_bboxes(self, *, label: int) -> tuple[tuple[float, float, float, float], ...]:
        label = int(label)
        if label not in (0, 1):
            raise ValueError("SAM3 manual prompt label must be 0 or 1.")
        context = self._current_sam3_manual_prompt_context()
        source = (
            self._sam3_manual_positive_bboxes_by_context
            if label == 1
            else self._sam3_manual_negative_bboxes_by_context
        )
        return tuple(source.get(context, ()))

    def _current_sam3_manual_prompt_context(self) -> tuple[int, str]:
        if self._series is None:
            return -1, self._current_yolo_source_view()
        return self._series.active_frame_index, self._current_yolo_source_view()

    def _sync_sam3_prompt_status(self) -> None:
        positive_count, negative_count = self.sam3_manual_prompt_counts()
        self.lbl_sam3_prompt_status.setText(f"Manual prompts: +{positive_count} / -{negative_count}")

    def _set_sam3_prompt_button_states(self, mode: str | None) -> None:
        for button, checked in (
            (self.btn_sam3_add_positive_prompt, mode == "positive"),
            (self.btn_sam3_add_negative_prompt, mode == "negative"),
        ):
            previous = button.blockSignals(True)
            try:
                button.setChecked(checked)
            finally:
                button.blockSignals(previous)

    def _set_sam3_prompt_draw_mode(self, mode: str | None) -> None:
        if mode not in (None, "positive", "negative"):
            raise ValueError("SAM3 prompt draw mode must be None, 'positive' or 'negative'.")
        self._sam3_prompt_draw_mode = mode
        self.viewer.set_prompt_bbox_draw_mode_enabled(mode is not None)
        if mode == "positive":
            self.viewer.set_manual_bbox_preview_color(self.viewer.sam3_manual_prompt_color(label=1))
        elif mode == "negative":
            self.viewer.set_manual_bbox_preview_color(self.viewer.sam3_manual_prompt_color(label=0))
        else:
            self.viewer.set_manual_bbox_preview_color(None)
        self._set_sam3_prompt_button_states(mode)
        if mode is not None:
            if self.btn_bbox_add.isChecked():
                self.btn_bbox_add.setChecked(False)
            else:
                self.viewer.set_molecular_bbox_add_mode_enabled(False)
            if self.btn_edit_mask.isChecked():
                self.btn_edit_mask.setChecked(False)
            else:
                self.viewer.set_mask_brush_edit_mode_enabled(False)
        self._sync_bbox_edit_controls()
        self._sync_active_segmentation_panel()
        self._sync_sam3_prompt_status()

    def _clear_sam3_prompt_draw_mode(self) -> None:
        if self._sam3_prompt_draw_mode is not None:
            self._set_sam3_prompt_draw_mode(None)

    def select_molecular_detection_at_pixel(self, x_px: float, y_px: float) -> str | None:
        return self.viewer.select_molecular_detection_at_pixel(
            x_px,
            y_px,
            source_view=self._current_yolo_source_view(),
        )

    def select_molecular_segmentation_at_pixel(self, x_px: float, y_px: float) -> str | None:
        return self.viewer.select_molecular_segmentation_at_pixel(
            x_px,
            y_px,
            source_view=self._current_yolo_source_view(),
        )

    def apply_mask_brush_at_pixel(
        self,
        x_px: float,
        y_px: float,
        *,
        mode: str,
        brush_size_px: int,
    ) -> bool:
        segmentation = self._current_selected_molecular_segmentation()
        if segmentation is None:
            self.statusBar().showMessage("No active segmentation selected.", 3000)
            self._sync_active_segmentation_panel()
            return False
        if segmentation.origin != "sam2":
            self.statusBar().showMessage("Mask editing is available for SAM2 segmentations.", 3000)
            return False
        if segmentation.mask is None:
            self.statusBar().showMessage("Active segmentation has no editable mask.", 3000)
            return False

        mode = str(mode).strip().lower()
        if mode not in ("add", "erase"):
            raise ValueError("Mask brush mode must be 'add' or 'erase'.")
        brush_size_px = int(brush_size_px)
        if brush_size_px < 0:
            raise ValueError("brush_size_px must be non-negative.")

        current_mask = np.asarray(segmentation.mask, dtype=bool)
        if segmentation.original_mask is None:
            segmentation.original_mask = current_mask.copy()
        edited_mask = current_mask.copy()
        brush_mask = self._mask_brush_pixels(
            edited_mask.shape,
            x_px=float(x_px),
            y_px=float(y_px),
            brush_size_px=brush_size_px,
        )
        if mode == "add":
            edited_mask[brush_mask] = True
        else:
            edited_mask[brush_mask] = False

        if not bool(np.any(edited_mask)):
            self.statusBar().showMessage("Mask edit rejected: mask cannot be empty.", 3000)
            self._sync_active_segmentation_panel()
            return False

        self._remember_mask_edit_state(segmentation)
        self._apply_segmentation_mask_update(
            segmentation,
            edited_mask,
            metadata={
                "edited": True,
                "edit_tool": "manual_brush",
                "edit_mode": mode,
                "brush_size_px": brush_size_px,
            },
        )
        self._show_current_frame()
        self.viewer.select_molecular_segmentation_by_id(segmentation.segmentation_id)
        self._sync_active_segmentation_panel()
        self.statusBar().showMessage(f"Edited SAM2 mask {segmentation.segmentation_id}.", 3000)
        return True

    def undo_last_mask_edit(self) -> bool:
        segmentation = self._current_selected_molecular_segmentation()
        if segmentation is None:
            self.statusBar().showMessage("No active segmentation selected.", 3000)
            return False
        stack = self._mask_edit_undo_stack_by_segmentation_id.get(segmentation.segmentation_id, [])
        if not stack:
            self.statusBar().showMessage("No mask edit to undo.", 3000)
            return False
        previous_state = stack.pop()
        self._restore_mask_edit_state(segmentation, previous_state)
        self._show_current_frame()
        self.viewer.select_molecular_segmentation_by_id(segmentation.segmentation_id)
        self._sync_active_segmentation_panel()
        self.statusBar().showMessage(f"Undo mask edit {segmentation.segmentation_id}.", 3000)
        return True

    def cancel_active_mask_edit(self) -> bool:
        segmentation = self._current_selected_molecular_segmentation()
        if segmentation is None:
            self.statusBar().showMessage("No active segmentation selected.", 3000)
            return False
        baseline = self._mask_edit_baseline_by_segmentation_id.pop(segmentation.segmentation_id, None)
        if baseline is None:
            self.statusBar().showMessage("No mask edit session to cancel.", 3000)
            return False
        self._mask_edit_undo_stack_by_segmentation_id.pop(segmentation.segmentation_id, None)
        self._restore_mask_edit_state(segmentation, baseline)
        self.btn_edit_mask.setChecked(False)
        self.viewer.set_mask_brush_edit_mode_enabled(False)
        self._show_current_frame()
        self.viewer.select_molecular_segmentation_by_id(segmentation.segmentation_id)
        self._sync_active_segmentation_panel()
        self.statusBar().showMessage(f"Cancel mask edit {segmentation.segmentation_id}.", 3000)
        return True

    def apply_active_mask_edit(self) -> bool:
        segmentation = self._current_selected_molecular_segmentation()
        if segmentation is None:
            self.statusBar().showMessage("No active segmentation selected.", 3000)
            return False
        if segmentation.segmentation_id not in self._mask_edit_baseline_by_segmentation_id:
            self.statusBar().showMessage("No mask edit session to apply.", 3000)
            return False
        self._mask_edit_baseline_by_segmentation_id.pop(segmentation.segmentation_id, None)
        self._mask_edit_undo_stack_by_segmentation_id.pop(segmentation.segmentation_id, None)
        self.btn_edit_mask.setChecked(False)
        self.viewer.set_mask_brush_edit_mode_enabled(False)
        self._sync_active_segmentation_panel()
        self.statusBar().showMessage(f"Apply mask edit {segmentation.segmentation_id}.", 3000)
        return True

    def _remember_mask_edit_state(self, segmentation) -> None:
        state = self._capture_mask_edit_state(segmentation)
        self._mask_edit_undo_stack_by_segmentation_id.setdefault(segmentation.segmentation_id, []).append(state)
        self._mask_edit_baseline_by_segmentation_id.setdefault(
            segmentation.segmentation_id,
            self._capture_mask_edit_state(segmentation),
        )

    def _begin_mask_edit_session(self, segmentation) -> None:
        self._mask_edit_baseline_by_segmentation_id.setdefault(
            segmentation.segmentation_id,
            self._capture_mask_edit_state(segmentation),
        )

    def _capture_mask_edit_state(self, segmentation) -> dict[str, object]:
        return {
            "mask": np.asarray(segmentation.mask, dtype=bool).copy(),
            "original_mask": (
                None
                if segmentation.original_mask is None
                else np.asarray(segmentation.original_mask, dtype=bool).copy()
            ),
            "bbox_xyxy": None if segmentation.bbox_xyxy is None else tuple(segmentation.bbox_xyxy),
            "polygon_xy": None if segmentation.polygon_xy is None else tuple(segmentation.polygon_xy),
            "metadata": dict(segmentation.metadata),
        }

    def _restore_mask_edit_state(self, segmentation, state: dict[str, object]) -> None:
        segmentation.mask = np.asarray(state["mask"], dtype=bool).copy()
        original_mask = state.get("original_mask")
        segmentation.original_mask = (
            None if original_mask is None else np.asarray(original_mask, dtype=bool).copy()
        )
        bbox_xyxy = state.get("bbox_xyxy")
        segmentation.bbox_xyxy = None if bbox_xyxy is None else tuple(bbox_xyxy)
        polygon_xy = state.get("polygon_xy")
        segmentation.polygon_xy = None if polygon_xy is None else tuple(polygon_xy)
        segmentation.metadata = dict(state.get("metadata", {}))

    def reset_active_segmentation_to_sam2_result(self) -> bool:
        segmentation = self._current_selected_molecular_segmentation()
        if segmentation is None:
            self.statusBar().showMessage("No active segmentation selected.", 3000)
            self._sync_active_segmentation_panel()
            return False
        if segmentation.origin != "sam2":
            self.statusBar().showMessage("Reset to SAM2 result is available for SAM2 segmentations.", 3000)
            return False
        if segmentation.original_mask is None:
            self.statusBar().showMessage("No original SAM2 result stored for this segmentation.", 3000)
            return False
        original_mask = np.asarray(segmentation.original_mask, dtype=bool).copy()
        self._mask_edit_undo_stack_by_segmentation_id.pop(segmentation.segmentation_id, None)
        self._mask_edit_baseline_by_segmentation_id.pop(segmentation.segmentation_id, None)
        self._apply_segmentation_mask_update(
            segmentation,
            original_mask,
            metadata={
                "edited": False,
                "edit_tool": "reset_to_sam2_result",
            },
        )
        self._show_current_frame()
        self.viewer.select_molecular_segmentation_by_id(segmentation.segmentation_id)
        self._sync_active_segmentation_panel()
        self.statusBar().showMessage(f"Reset SAM2 mask {segmentation.segmentation_id}.", 3000)
        return True

    def add_manual_bbox_from_pixel_drag(
        self,
        start_xy_px: tuple[float, float],
        end_xy_px: tuple[float, float],
    ):
        if self._series is None:
            return None

        source_view = self._current_yolo_source_view()
        bbox_xyxy = self._manual_bbox_from_pixel_drag(
            start_xy_px,
            end_xy_px,
            frame_shape=self._current_bbox_frame_shape(source_view),
        )
        if bbox_xyxy is None:
            self.statusBar().showMessage("Draw a larger BBox.", 3000)
            self._sync_bbox_edit_controls()
            return None

        detection_set = self._ensure_molecular_detection_set()
        detection = detection_set.add_detection(
            self._series.active_frame_index,
            bbox_xyxy,
            source_view=source_view,
            frame_shape=self._current_bbox_frame_shape(source_view),
            confidence=1.0,
            selected=True,
            model_name="manual",
            checkpoint_path="",
            origin="manual",
        )
        self._show_current_frame()
        self.viewer.select_molecular_detection_by_id(detection.detection_id)
        self._sync_yolo_controls()
        view_label = "expanded aligned" if source_view == "expanded_aligned" else "raw"
        self.statusBar().showMessage(
            f"Added manual BBox on frame {detection.frame_index + 1} ({view_label}).",
            3000,
        )
        return detection

    def _on_molecular_detection_selection_changed(self, detection_id) -> None:
        self._selected_molecular_detection_id = str(detection_id) if detection_id is not None else None
        self._sync_bbox_edit_controls()

    def _on_molecular_segmentation_selection_changed(self, segmentation_id) -> None:
        self._selected_molecular_segmentation_id = str(segmentation_id) if segmentation_id is not None else None
        self._sync_active_segmentation_panel()

    def _on_active_segmentation_combo_changed(self, _index: int) -> None:
        segmentation_id = self.cmb_active_segmentation.currentData()
        if segmentation_id is None:
            return
        self.viewer.select_molecular_segmentation_by_id(str(segmentation_id))

    def _on_edit_mask_toggled(self, checked: bool) -> None:
        enabled = bool(checked) and self.btn_edit_mask.isEnabled()
        if enabled and self.btn_bbox_add.isChecked():
            self.btn_bbox_add.setChecked(False)
        if enabled and self._sam3_prompt_draw_mode is not None:
            self._set_sam3_prompt_draw_mode(None)
        if enabled:
            segmentation = self._current_selected_molecular_segmentation()
            if segmentation is not None and segmentation.mask is not None:
                self._begin_mask_edit_session(segmentation)
        self.viewer.set_mask_brush_edit_mode_enabled(enabled)
        self.cmb_mask_brush_mode.setEnabled(enabled)
        self.sp_mask_brush_size.setEnabled(enabled)
        self._sync_active_segmentation_panel()

    def _on_manual_mask_brush_dragged(self, points) -> None:
        mode = self.cmb_mask_brush_mode.currentData() or "add"
        brush_size_px = int(self.sp_mask_brush_size.value())
        edited_any = False
        for x_px, y_px in tuple(points):
            edited_any = self.apply_mask_brush_at_pixel(
                x_px,
                y_px,
                mode=str(mode),
                brush_size_px=brush_size_px,
            ) or edited_any
        if not edited_any:
            self._sync_active_segmentation_panel()

    def _sync_active_segmentation_panel(self) -> None:
        segmentations = self._current_frame_molecular_segmentations()
        current_id = self._selected_molecular_segmentation_id
        visible_ids = [segmentation.segmentation_id for segmentation in segmentations]
        if current_id not in visible_ids:
            current_id = None
            self._selected_molecular_segmentation_id = None

        self.cmb_active_segmentation.blockSignals(True)
        try:
            self.cmb_active_segmentation.clear()
            if not segmentations:
                self.cmb_active_segmentation.addItem("No segmentations", None)
            else:
                for segmentation in segmentations:
                    self.cmb_active_segmentation.addItem(
                        self._molecular_segmentation_display_name(segmentation),
                        segmentation.segmentation_id,
                    )
                if current_id is not None:
                    index = self.cmb_active_segmentation.findData(current_id)
                    if index >= 0:
                        self.cmb_active_segmentation.setCurrentIndex(index)
        finally:
            self.cmb_active_segmentation.blockSignals(False)

        self.cmb_active_segmentation.setEnabled(bool(segmentations) and not self._is_processing())
        segmentation = self._current_selected_molecular_segmentation()
        can_edit = (
            segmentation is not None
            and segmentation.origin == "sam2"
            and not self._is_processing()
            and self._sam3_prompt_draw_mode is None
        )
        self.btn_edit_mask.setEnabled(can_edit)
        self.cmb_mask_brush_mode.setEnabled(can_edit and self.btn_edit_mask.isChecked())
        self.sp_mask_brush_size.setEnabled(can_edit and self.btn_edit_mask.isChecked())
        has_edit_session = (
            can_edit
            and segmentation.segmentation_id in self._mask_edit_baseline_by_segmentation_id
        )
        has_undo = (
            can_edit
            and bool(self._mask_edit_undo_stack_by_segmentation_id.get(segmentation.segmentation_id, []))
        )
        self.btn_undo_mask_edit.setEnabled(has_undo)
        self.btn_apply_mask_edit.setEnabled(has_edit_session)
        self.btn_cancel_mask_edit.setEnabled(has_edit_session)
        self.btn_reset_mask_to_sam2_result.setEnabled(can_edit and segmentation.original_mask is not None)
        if not can_edit and self.btn_edit_mask.isChecked():
            self.btn_edit_mask.blockSignals(True)
            try:
                self.btn_edit_mask.setChecked(False)
            finally:
                self.btn_edit_mask.blockSignals(False)
            self.viewer.set_mask_brush_edit_mode_enabled(False)
        if segmentation is None:
            self.lbl_active_segmentation_status.setText("No active segmentation")
            return
        self.lbl_active_segmentation_status.setText(self._molecular_segmentation_status_text(segmentation))

    def _current_selected_molecular_detection(self):
        if (
            self._series is None
            or self._series.molecular_detections is None
            or self._selected_molecular_detection_id is None
        ):
            return None

        detection = self._series.molecular_detections.get_detection(self._selected_molecular_detection_id)
        if detection is None:
            return None
        if detection.frame_index != self._series.active_frame_index:
            return None
        if detection.source_view != self._current_yolo_source_view():
            return None
        return detection

    def _current_frame_molecular_segmentations(self) -> list:
        if self._series is None or self._series.molecular_segmentations is None:
            return []
        return list(
            self._series.molecular_segmentations.get_segmentations(
                self._series.active_frame_index,
                source_view=self._current_yolo_source_view(),
            )
        )

    def _current_selected_molecular_segmentation(self):
        if (
            self._series is None
            or self._series.molecular_segmentations is None
            or self._selected_molecular_segmentation_id is None
        ):
            return None
        segmentation = self._series.molecular_segmentations.get_segmentation(
            self._selected_molecular_segmentation_id
        )
        if segmentation is None:
            return None
        if segmentation.frame_index != self._series.active_frame_index:
            return None
        if segmentation.source_view != self._current_yolo_source_view():
            return None
        return segmentation

    def _molecular_segmentation_display_name(self, segmentation) -> str:
        prompt = ",".join(segmentation.prompt_detection_ids) or "no prompt"
        return f"{segmentation.segmentation_id} | {segmentation.origin} | {prompt}"

    def _molecular_segmentation_status_text(self, segmentation) -> str:
        prompt = ",".join(segmentation.prompt_detection_ids) or "-"
        if segmentation.mask is not None:
            area = int(np.count_nonzero(segmentation.mask))
        else:
            area = int(segmentation.metadata.get("mask_area_px", 0) or 0)
        bbox = segmentation.bbox_xyxy
        bbox_text = "-"
        if bbox is not None:
            bbox_text = ",".join(f"{float(value):.1f}" for value in bbox)
        return (
            f"Active segmentation: {segmentation.segmentation_id} | "
            f"{segmentation.origin} | prompt {prompt} | area {area} | bbox {bbox_text}"
        )

    def _apply_segmentation_mask_update(self, segmentation, mask, *, metadata: dict | None = None) -> None:
        mask_array = np.asarray(mask, dtype=bool)
        if not bool(np.any(mask_array)):
            raise ValueError("Cannot apply an empty segmentation mask.")
        segmentation.mask = mask_array.copy()
        segmentation.bbox_xyxy = self._bbox_from_mask(mask_array)
        segmentation.polygon_xy = None
        segmentation.metadata.update(
            {
                "mask_area_px": float(np.count_nonzero(mask_array)),
                "mask_component_count": self._mask_component_count(mask_array),
            }
        )
        if metadata:
            segmentation.metadata.update(dict(metadata))

    def _mask_brush_pixels(
        self,
        mask_shape: tuple[int, int],
        *,
        x_px: float,
        y_px: float,
        brush_size_px: int,
    ) -> np.ndarray:
        height, width = mask_shape
        yy, xx = np.ogrid[:height, :width]
        center_x = int(np.floor(float(x_px)))
        center_y = int(np.floor(float(y_px)))
        radius = max(0, int(brush_size_px))
        return (xx - center_x) ** 2 + (yy - center_y) ** 2 <= radius**2

    def _bbox_from_mask(self, mask: np.ndarray) -> tuple[float, float, float, float]:
        ys, xs = np.nonzero(mask)
        if ys.size == 0 or xs.size == 0:
            raise ValueError("Cannot compute bbox for an empty mask.")
        return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)

    def _mask_component_count(self, mask: np.ndarray) -> int:
        visited = np.zeros(mask.shape, dtype=bool)
        component_count = 0
        height, width = mask.shape
        for start_y, start_x in np.argwhere(mask):
            start_y = int(start_y)
            start_x = int(start_x)
            if visited[start_y, start_x]:
                continue
            component_count += 1
            stack = [(start_y, start_x)]
            visited[start_y, start_x] = True
            while stack:
                y, x = stack.pop()
                for next_y, next_x in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if not (0 <= next_y < height and 0 <= next_x < width):
                        continue
                    if visited[next_y, next_x] or not mask[next_y, next_x]:
                        continue
                    visited[next_y, next_x] = True
                    stack.append((next_y, next_x))
        return int(component_count)

    def _source_view_molecular_detection_count(self, source_view: str) -> int:
        if self._series is None or self._series.molecular_detections is None:
            return 0
        total = 0
        for frame_index in range(self._series.frame_count):
            total += len(self._series.molecular_detections.get_detections(frame_index, source_view=source_view))
        return total

    def _is_processing(self) -> bool:
        return (
            self._registration_running
            or self._yolo_detection_running
            or self._sam2_segmentation_running
            or self._sam3_concept_running
        )

    def _yolo_model_display_name(self, model) -> str:
        return str(
            getattr(model, "display_name", None)
            or getattr(model, "name", None)
            or getattr(model, "path", model)
        )

    def _current_yolo_model(self):
        index = self.cmb_yolo_model.currentIndex()
        if index < 0:
            return None
        return self.cmb_yolo_model.itemData(index)

    def _current_yolo_model_path(self, model):
        return getattr(model, "path", model)

    def _current_yolo_frame(self, source_view: str):
        if self._series is None:
            raise RuntimeError("YOLO detection requires a loaded series.")
        frame_index = self._series.active_frame_index
        if source_view == "expanded_aligned":
            return self._ensure_expanded_aligned_stack().frames[frame_index]
        return self._series.raw_frames[frame_index]

    def _ensure_molecular_detection_set(self) -> MolecularDetectionSet:
        if self._series is None:
            raise RuntimeError("Molecular detections require a loaded series.")
        if self._series.molecular_detections is None:
            self._series.molecular_detections = MolecularDetectionSet(frame_count=self._series.frame_count)
        return self._series.molecular_detections

    def _ensure_molecular_segmentation_set(self) -> MolecularSegmentationSet:
        if self._series is None:
            raise RuntimeError("Molecular segmentations require a loaded series.")
        if self._series.molecular_segmentations is None:
            self._series.molecular_segmentations = MolecularSegmentationSet(frame_count=self._series.frame_count)
        return self._series.molecular_segmentations

    def _on_yolo_detect_current_requested(self) -> None:
        if self._series is None or self._is_processing():
            return
        model = self._current_yolo_model()
        if model is None:
            self.statusBar().showMessage("No YOLO model selected.", 3000)
            return

        source_view = self._current_yolo_source_view()
        frame_index = self._series.active_frame_index
        model_path = self._current_yolo_model_path(model)
        try:
            frame = self._current_yolo_frame(source_view)
            detections = self._yolo_detector.detect_frame(
                frame,
                frame_index=frame_index,
                checkpoint_path=model_path,
                confidence_threshold=float(self.sp_yolo_confidence.value()),
                iou_threshold=float(self.sp_yolo_iou.value()),
                source_view=source_view,
            )
            detection_set = self._ensure_molecular_detection_set()
            detection_set.set_detections(
                frame_index,
                detections,
                source_view=source_view,
                frame_shape=frame.shape[:2],
            )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "YOLO detection error", message)
            self.statusBar().showMessage("YOLO detection failed.", 3000)
            return

        self._show_current_frame()
        self._sync_yolo_controls()
        detection_word = "detection" if len(detections) == 1 else "detections"
        self.statusBar().showMessage(
            (
                f"YOLO {self._yolo_model_display_name(model)}: "
                f"{len(detections)} {detection_word} on frame {frame_index + 1}."
            ),
            5000,
        )

    def _on_yolo_detect_all_frames_requested(self) -> None:
        if self._series is None or self._is_processing():
            return
        model = self._current_yolo_model()
        if model is None:
            self.statusBar().showMessage("No YOLO model selected.", 3000)
            return

        source_view = self._current_yolo_source_view()
        try:
            frames = self._current_yolo_frames(source_view)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "YOLO detection error", message)
            self.statusBar().showMessage("YOLO detection failed.", 3000)
            return

        frame_indices = list(range(self._series.frame_count))
        model_path = self._current_yolo_model_path(model)
        self._yolo_detection_running = True
        self._yolo_detection_model_name = self._yolo_model_display_name(model)
        self._yolo_detection_source_view = source_view
        self._set_file_actions_enabled(False)
        self._yolo_detection_progress_dialog = self._show_yolo_detection_progress_dialog(
            self._yolo_detection_model_name,
            total=len(frame_indices),
        )
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"Running YOLO {self._yolo_detection_model_name} on {len(frame_indices)} frames...",
            0,
        )

        self._yolo_detection_thread = QThread(self)
        self._yolo_detection_worker = _YoloDetectAllWorker(
            self._yolo_detector,
            frames,
            frame_indices,
            checkpoint_path=model_path,
            confidence_threshold=float(self.sp_yolo_confidence.value()),
            iou_threshold=float(self.sp_yolo_iou.value()),
            source_view=source_view,
        )
        self._yolo_detection_worker.moveToThread(self._yolo_detection_thread)
        self._yolo_detection_thread.started.connect(self._yolo_detection_worker.run)
        self._yolo_detection_worker.progress.connect(self._yolo_apply_detection_progress.emit)
        self._yolo_detection_worker.finished.connect(self._yolo_apply_detection_finished.emit)
        self._yolo_detection_worker.failed.connect(self._yolo_apply_detection_failed.emit)
        self._yolo_detection_worker.finished.connect(self._yolo_detection_thread.quit)
        self._yolo_detection_worker.failed.connect(self._yolo_detection_thread.quit)
        self._yolo_detection_thread.finished.connect(self._cleanup_yolo_detection_worker)
        self._yolo_detection_thread.start()

    def _current_yolo_frames(self, source_view: str):
        if self._series is None:
            raise RuntimeError("YOLO detection requires a loaded series.")
        if source_view == "expanded_aligned":
            return self._ensure_expanded_aligned_stack().frames.copy()
        return self._series.raw_frames.copy()

    def _show_yolo_detection_progress_dialog(self, model_name: str, *, total: int) -> QProgressDialog:
        progress_dialog = QProgressDialog(
            f"Running YOLO {model_name} on frame 0 / {total}...",
            None,
            0,
            total,
            self,
        )
        progress_dialog.setWindowTitle("YOLO Detection")
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.setValue(0)
        progress_dialog.show()
        QApplication.processEvents()
        return progress_dialog

    @pyqtSlot(int, int)
    def _on_yolo_detection_progress(self, current: int, total: int) -> None:
        if not self._yolo_detection_running:
            return
        if self._yolo_detection_progress_dialog is not None:
            self._yolo_detection_progress_dialog.setLabelText(
                f"Running YOLO {self._yolo_detection_model_name} on frame {current} / {total}..."
            )
            self._yolo_detection_progress_dialog.setValue(current)
        self.statusBar().showMessage(
            f"Running YOLO {self._yolo_detection_model_name}: frame {current} / {total}...",
            0,
        )

    @pyqtSlot(object)
    def _on_yolo_detection_finished(self, results) -> None:
        self._yolo_detection_running = False
        total_detections = 0
        try:
            if self._series is not None:
                detection_set = self._ensure_molecular_detection_set()
                for frame_index, frame_shape, detections in results:
                    detection_set.set_detections(
                        frame_index,
                        detections,
                        source_view=self._yolo_detection_source_view,
                        frame_shape=frame_shape,
                    )
                    total_detections += len(detections)
        except Exception as exc:
            self._finish_yolo_detection_run()
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "YOLO detection error", message)
            self.statusBar().showMessage("YOLO detection failed.", 3000)
            return

        frame_count = len(results)
        model_name = self._yolo_detection_model_name
        final_message = f"YOLO {model_name}: {total_detections} detections on {frame_count} frames."
        self.statusBar().showMessage(final_message, 5000)
        self._finish_yolo_detection_run()
        self._show_current_frame()
        self.statusBar().showMessage(final_message, 5000)
        QTimer.singleShot(0, lambda message=final_message: self.statusBar().showMessage(message, 5000))

    @pyqtSlot(str)
    def _on_yolo_detection_failed(self, message: str) -> None:
        self._finish_yolo_detection_run()
        QMessageBox.critical(self, "YOLO detection error", message)
        failure_message = "YOLO detection failed."
        self.statusBar().showMessage(failure_message, 3000)
        QTimer.singleShot(0, lambda message=failure_message: self.statusBar().showMessage(message, 3000))

    def _finish_yolo_detection_run(self) -> None:
        self._yolo_detection_running = False
        self._set_file_actions_enabled(True)
        self._close_yolo_detection_progress_dialog()
        self._sync_navigation_controls()

    def _close_yolo_detection_progress_dialog(self) -> None:
        if self._yolo_detection_progress_dialog is None:
            return
        self._yolo_detection_progress_dialog.close()
        self._yolo_detection_progress_dialog = None

    def _cleanup_yolo_detection_worker(self) -> None:
        if self._yolo_detection_worker is not None:
            self._yolo_detection_worker.deleteLater()
            self._yolo_detection_worker = None
        if self._yolo_detection_thread is not None:
            self._yolo_detection_thread.deleteLater()
            self._yolo_detection_thread = None

    def _on_yolo_clear_current_requested(self) -> None:
        if self._series is None or self._series.molecular_detections is None:
            return
        frame_index = self._series.active_frame_index
        source_view = self._current_yolo_source_view()
        removed = self._series.molecular_detections.clear_frame(frame_index, source_view=source_view)
        self._show_current_frame()
        self._sync_yolo_controls()
        self.statusBar().showMessage(
            f"Cleared {removed} YOLO detection(s) on frame {frame_index + 1}.",
            3000,
        )

    def _on_bbox_increase_requested(self) -> None:
        self._resize_current_view_bboxes(margin_px=float(self.sp_bbox_resize_margin.value()))

    def _on_bbox_decrease_requested(self) -> None:
        self._resize_current_view_bboxes(margin_px=-float(self.sp_bbox_resize_margin.value()))

    def _on_bbox_add_toggled(self, checked: bool) -> None:
        if checked and self._sam3_prompt_draw_mode is not None:
            self._set_sam3_prompt_draw_mode(None)
        if checked:
            self.viewer.set_manual_bbox_preview_color(None)
        self.viewer.set_molecular_bbox_add_mode_enabled(bool(checked))
        self._sync_bbox_edit_controls()

    def _on_bbox_opacity_changed(self, value: int) -> None:
        opacity_percent = min(100, max(0, int(value)))
        self.lbl_bbox_opacity.setText(f"BBox opacity: {opacity_percent}%")
        self.viewer.set_molecular_detection_overlay_opacity(opacity_percent / 100.0)
        if self._series is not None:
            self._show_current_frame()

    def _on_show_centroids_toggled(self, checked: bool) -> None:
        self.viewer.set_molecular_centroid_overlay_visible(bool(checked))
        if self._series is not None:
            self._show_current_frame()

    def position_analysis_dialog(self) -> PositionAnalysisDialog | None:
        return self._position_analysis_dialog

    def _on_position_analysis_requested(self) -> None:
        if self._series is None:
            return
        plot_data = self._build_current_position_plot_data()
        if self._position_analysis_dialog is None:
            dialog = PositionAnalysisDialog(self)
            dialog.destroyed.connect(self._on_position_analysis_dialog_destroyed)
            dialog.compare_ranges_requested.connect(self._on_position_range_comparison_requested)
            self._position_analysis_dialog = dialog
        self._position_analysis_dialog.configure_frame_ranges(
            frame_count=self._series.frame_count,
            source_view=plot_data.source_view,
        )
        self._position_analysis_dialog.set_plot_data(plot_data)
        self._position_analysis_dialog.show()
        self._position_analysis_dialog.raise_()
        self._position_analysis_dialog.activateWindow()

    def _on_position_analysis_dialog_destroyed(self, _object=None) -> None:
        self._position_analysis_dialog = None

    def _on_position_range_comparison_requested(self, selection) -> None:
        if self._series is None or self._position_analysis_dialog is None:
            return
        try:
            comparison = compare_molecular_frame_ranges(self._series, selection)
        except (TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Position analysis failed", str(exc))
            return
        self._position_analysis_dialog.set_range_comparison(comparison)

    def _build_current_position_plot_data(self):
        if self._series is None:
            raise RuntimeError("Position analysis requires a loaded series.")
        frame_index = self._series.active_frame_index
        source_view = self._current_yolo_source_view()
        centroids = build_molecular_centroids(
            self._series,
            frame_index=frame_index,
            source_view=source_view,
        )
        frame_shape = self._current_bbox_frame_shape(source_view)
        scale_nm_per_px = self._current_position_scale_nm_per_px(source_view)
        return build_molecular_position_plot_data(
            centroids,
            frame_index=frame_index,
            source_view=source_view,
            frame_shape=frame_shape,
            scale_nm_per_px=scale_nm_per_px,
        )

    def _current_position_scale_nm_per_px(self, source_view: str) -> tuple[float, float] | None:
        if self._series is None:
            return None
        metadata = self._series.metadata
        if source_view == "expanded_aligned":
            expanded = self._ensure_expanded_aligned_stack()
            metadata = getattr(expanded, "metadata", metadata)
        get_pixel_size = getattr(metadata, "get_pixel_size_nm", None)
        if not callable(get_pixel_size):
            return None
        try:
            scale_x, scale_y = get_pixel_size()
            scale_x = float(scale_x)
            scale_y = float(scale_y)
        except (TypeError, ValueError):
            return None
        if not np.isfinite(scale_x) or not np.isfinite(scale_y) or scale_x <= 0.0 or scale_y <= 0.0:
            return None
        return scale_x, scale_y

    def _on_sam3_add_positive_prompt_toggled(self, checked: bool) -> None:
        if checked:
            self._set_sam3_prompt_draw_mode("positive")
        elif self._sam3_prompt_draw_mode == "positive":
            self._set_sam3_prompt_draw_mode(None)

    def _on_sam3_add_negative_prompt_toggled(self, checked: bool) -> None:
        if checked:
            self._set_sam3_prompt_draw_mode("negative")
        elif self._sam3_prompt_draw_mode == "negative":
            self._set_sam3_prompt_draw_mode(None)

    def _on_manual_molecular_bbox_drawn(self, bbox_xyxy) -> None:
        if self._sam3_prompt_draw_mode is not None:
            label = 1 if self._sam3_prompt_draw_mode == "positive" else 0
            self.add_sam3_manual_prompt_bbox(
                (float(bbox_xyxy[0]), float(bbox_xyxy[1]), float(bbox_xyxy[2]), float(bbox_xyxy[3])),
                label=label,
            )
            return
        self.add_manual_bbox_from_pixel_drag(
            (float(bbox_xyxy[0]), float(bbox_xyxy[1])),
            (float(bbox_xyxy[2]), float(bbox_xyxy[3])),
        )

    def _on_bbox_reset_requested(self) -> None:
        if self._series is None or self._series.molecular_detections is None:
            return
        source_view = self._current_yolo_source_view()
        try:
            changed = self._series.molecular_detections.reset_all_to_original(
                source_view=source_view,
                frame_shape=self._current_bbox_frame_shape(source_view),
            )
        except Exception as exc:
            self._show_bbox_resize_error(exc)
            return
        self._finish_bbox_resize(changed, verb="Reset")

    def _resize_current_view_bboxes(self, *, margin_px: float) -> None:
        if self._series is None or self._series.molecular_detections is None:
            return
        source_view = self._current_yolo_source_view()
        try:
            changed = self._series.molecular_detections.resize_all(
                margin_px=margin_px,
                source_view=source_view,
                frame_shape=self._current_bbox_frame_shape(source_view),
            )
        except Exception as exc:
            self._show_bbox_resize_error(exc)
            return
        self._finish_bbox_resize(changed, verb="Resized")

    def _on_bbox_delete_selected_requested(self) -> None:
        if self._series is None or self._series.molecular_detections is None:
            return

        detection = self._current_selected_molecular_detection()
        if detection is None:
            self._selected_molecular_detection_id = None
            self._show_current_frame()
            self._sync_yolo_controls()
            self.statusBar().showMessage("No BBox selected.", 3000)
            return

        frame_index = detection.frame_index
        source_view = detection.source_view
        self._series.molecular_detections.remove_detection(detection.detection_id)
        self._show_current_frame()
        self._sync_yolo_controls()
        view_label = "expanded aligned" if source_view == "expanded_aligned" else "raw"
        self.statusBar().showMessage(
            f"Deleted selected BBox from frame {frame_index + 1} ({view_label}).",
            3000,
        )

    def _on_segmentation_backend_changed(self, _backend: str) -> None:
        self._sync_segmentation_controls()

    def _on_sam3_run_concepts_requested(self) -> None:
        if self._series is None or self._is_processing():
            return
        source_view = self._current_yolo_source_view()
        frame_index = self._series.active_frame_index
        try:
            prompts = self._build_current_sam3_prompt_batch(source_view=source_view)
            frame = self._current_yolo_frame(source_view).copy()
        except MolTrackSam3PromptValidationError as exc:
            message = str(exc)
            self.lbl_segmentation_status.setText(message)
            self.statusBar().showMessage(message, 3000)
            return
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "SAM3 concepts error", message)
            self.statusBar().showMessage("SAM3 concepts failed.", 3000)
            return

        self._sam3_concept_running = True
        self._sam3_concept_source_view = source_view
        self._sam3_concept_frame_index = frame_index
        self._sam3_concept_duplicate_iou_threshold = float(self.sp_sam3_duplicate_iou.value())
        self._set_file_actions_enabled(False)
        self._sam3_concept_progress_dialog = self._show_sam3_concept_progress_dialog(
            model_id=self.cmb_sam3_model.currentText(),
            prompt_count=len(prompts),
        )
        self._sync_navigation_controls()
        self.statusBar().showMessage(f"Running SAM3 concepts with {len(prompts)} prompt(s)...", 0)

        self._sam3_concept_thread = QThread(self)
        self._sam3_concept_worker = _Sam3ConceptWorker(
            self._sam3_adapter,
            frame,
            prompts,
            frame_index=frame_index,
            source_view=source_view,
            model_id=self.cmb_sam3_model.currentText(),
            score_threshold=float(self.sp_sam3_score_threshold.value()),
            mask_threshold=float(self.sp_sam3_mask_threshold.value()),
            max_results=int(self.sp_sam3_max_results.value()),
        )
        self._sam3_concept_worker.moveToThread(self._sam3_concept_thread)
        self._sam3_concept_thread.started.connect(self._sam3_concept_worker.run)
        self._sam3_concept_worker.finished.connect(self._on_sam3_concept_finished)
        self._sam3_concept_worker.failed.connect(self._on_sam3_concept_failed)
        self._sam3_concept_worker.finished.connect(self._sam3_concept_thread.quit)
        self._sam3_concept_worker.failed.connect(self._sam3_concept_thread.quit)
        self._sam3_concept_thread.finished.connect(self._cleanup_sam3_concept_worker)
        self._sam3_concept_thread.start()

    def _build_current_sam3_prompt_batch(self, *, source_view: str):
        if self._series is None:
            raise MolTrackSam3PromptValidationError("SAM3 concept prompts require a loaded series.")
        detection_set = self._series.molecular_detections
        if detection_set is None:
            detection_set = MolecularDetectionSet(frame_count=self._series.frame_count)
        prompt_source = self.cmb_sam3_prompt_source.currentText()
        selected_detection_ids = None
        manual_positive_bboxes = ()
        manual_negative_bboxes = ()
        if prompt_source == SAM3_PROMPT_SOURCE_ACTIVE:
            detection = self._current_selected_molecular_detection()
            if detection is None:
                raise MolTrackSam3PromptValidationError(
                    "SAM3 concept prompts require at least one positive bbox."
                )
            positive_bbox_mode = "selected_current"
            selected_detection_ids = (detection.detection_id,)
        elif prompt_source == SAM3_PROMPT_SOURCE_SELECTED_CURRENT:
            positive_bbox_mode = "selected_current"
        elif prompt_source == SAM3_PROMPT_SOURCE_MANUAL:
            positive_bbox_mode = "manual_only"
            manual_positive_bboxes = self.sam3_manual_prompt_bboxes(label=1)
            manual_negative_bboxes = self.sam3_manual_prompt_bboxes(label=0)
        else:
            positive_bbox_mode = "all_current"
        return build_moltrack_sam3_prompt_batch(
            detection_set,
            frame_index=self._series.active_frame_index,
            source_view=source_view,
            positive_bbox_mode=positive_bbox_mode,
            selected_detection_ids=selected_detection_ids,
            manual_positive_bboxes=manual_positive_bboxes,
            manual_negative_bboxes=manual_negative_bboxes,
        )

    def _show_sam3_concept_progress_dialog(self, *, model_id: str, prompt_count: int) -> QProgressDialog:
        progress_dialog = QProgressDialog(
            f"Running SAM3 {model_id} with {prompt_count} prompt(s)...",
            None,
            0,
            0,
            self,
        )
        progress_dialog.setWindowTitle("SAM3 Concepts")
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.show()
        QApplication.processEvents()
        return progress_dialog

    @pyqtSlot(object)
    def _on_sam3_concept_finished(self, proposals) -> None:
        proposals = list(proposals)
        try:
            if self._series is None:
                raise RuntimeError("No series loaded.")
            detection_set = self._series.molecular_detections
            existing_detections = []
            if detection_set is not None:
                existing_detections = detection_set.get_detections(
                    self._sam3_concept_frame_index,
                    source_view=self._sam3_concept_source_view,
                )
            preview = build_moltrack_sam3_preview(
                proposals,
                frame_index=self._sam3_concept_frame_index,
                source_view=self._sam3_concept_source_view,
                existing_detections=existing_detections,
                score_threshold=float(self.sp_sam3_score_threshold.value()),
                mask_threshold=float(self.sp_sam3_mask_threshold.value()),
                max_results=int(self.sp_sam3_max_results.value()),
                duplicate_iou_threshold=self._sam3_concept_duplicate_iou_threshold,
            )
            self._series.sam3_preview = preview
        except Exception as exc:
            self._finish_sam3_concept_run()
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "SAM3 concepts error", message)
            self.statusBar().showMessage("SAM3 concepts failed.", 3000)
            return

        proposal_count = self._series.sam3_preview.proposal_count
        self._finish_sam3_concept_run()
        self._show_current_frame()
        final_message = f"SAM3 preview: {proposal_count} proposal(s)."
        self.lbl_segmentation_status.setText(final_message)
        self.statusBar().showMessage(final_message, 5000)

    @pyqtSlot(str)
    def _on_sam3_concept_failed(self, message: str) -> None:
        self._finish_sam3_concept_run()
        QMessageBox.critical(self, "SAM3 concepts error", message)
        self.statusBar().showMessage("SAM3 concepts failed.", 3000)

    def _finish_sam3_concept_run(self) -> None:
        self._sam3_concept_running = False
        self._set_file_actions_enabled(True)
        self._close_sam3_concept_progress_dialog()
        self._sync_navigation_controls()

    def _close_sam3_concept_progress_dialog(self) -> None:
        if self._sam3_concept_progress_dialog is None:
            return
        self._sam3_concept_progress_dialog.close()
        self._sam3_concept_progress_dialog = None
        QApplication.processEvents()

    def _cleanup_sam3_concept_worker(self) -> None:
        if self._sam3_concept_worker is not None:
            self._sam3_concept_worker.deleteLater()
            self._sam3_concept_worker = None
        if self._sam3_concept_thread is not None:
            self._sam3_concept_thread.deleteLater()
            self._sam3_concept_thread = None

    def _on_sam3_commit_proposals_requested(self) -> None:
        if self._series is None or self._is_processing():
            return
        preview = self._current_sam3_preview()
        if preview is None:
            self.statusBar().showMessage("No SAM3 preview to commit.", 3000)
            self._sync_segmentation_controls()
            return
        result = commit_moltrack_sam3_preview(
            preview,
            detection_set=self._ensure_molecular_detection_set(),
            segmentation_set=self._ensure_molecular_segmentation_set(),
            mode="both",
            duplicate_iou_threshold=float(self.sp_sam3_duplicate_iou.value()),
        )
        self._series.sam3_preview = None
        self._show_current_frame()
        self._sync_yolo_controls()
        final_message = (
            f"Committed SAM3 proposals: {result.added_bbox_count} BBox(es), "
            f"{result.added_segmentation_count} segmentation(s)."
        )
        self.statusBar().showMessage(final_message, 5000)

    def _on_sam2_segment_selected_requested(self) -> None:
        if self._sam2_segmentation_running:
            return
        detection = self._current_selected_molecular_detection()
        if self._series is None or detection is None:
            self.statusBar().showMessage("No BBox selected.", 3000)
            self._sync_segmentation_controls()
            return
        settings = self._choose_sam2_segmentation_settings(detection_count=1)
        if settings is None:
            return
        self._start_sam2_segmentation(
            [detection],
            mask_probability_threshold=settings["mask_probability_threshold"],
            checkpoint_path=settings["checkpoint_path"],
            existing_masks_policy=settings["existing_masks_policy"],
            keep_largest_component=settings["keep_largest_component"],
            min_mask_area_px=settings["min_mask_area_px"],
            scope="selected",
        )

    def _on_sam2_segment_all_current_requested(self) -> None:
        if self._sam2_segmentation_running:
            return
        detections = self._current_frame_molecular_detections()
        if self._series is None or not detections:
            self.statusBar().showMessage("No BBox in current image.", 3000)
            self._sync_segmentation_controls()
            return
        settings = self._choose_sam2_segmentation_settings(detection_count=len(detections))
        if settings is None:
            return
        self._start_sam2_segmentation(
            detections,
            mask_probability_threshold=settings["mask_probability_threshold"],
            checkpoint_path=settings["checkpoint_path"],
            existing_masks_policy=settings["existing_masks_policy"],
            keep_largest_component=settings["keep_largest_component"],
            min_mask_area_px=settings["min_mask_area_px"],
            scope="current_image",
        )

    def _choose_sam2_segmentation_settings(self, *, detection_count: int) -> dict[str, object] | None:
        dialog = self._create_sam2_segmentation_settings_dialog(detection_count=detection_count)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("SAM2 segmentation canceled.", 3000)
            return None
        mask_probability_threshold = float(dialog.mask_probability_threshold())
        checkpoint_path = dialog.checkpoint_path()
        if checkpoint_path is None:
            self.statusBar().showMessage("No SAM2 checkpoints found.", 3000)
            self._sync_segmentation_controls()
            return None
        checkpoint_path = Path(checkpoint_path)
        self._selected_sam2_checkpoint_path = checkpoint_path
        existing_masks_policy = str(dialog.existing_sam2_masks_policy())
        keep_largest_component = bool(dialog.keep_largest_component())
        min_mask_area_px = int(dialog.min_mask_area_px())
        self.sp_sam2_mask_threshold.setValue(mask_probability_threshold)
        return {
            "mask_probability_threshold": mask_probability_threshold,
            "checkpoint_path": checkpoint_path,
            "existing_masks_policy": existing_masks_policy,
            "keep_largest_component": keep_largest_component,
            "min_mask_area_px": min_mask_area_px,
        }

    def _create_sam2_segmentation_settings_dialog(self, *, detection_count: int):
        kwargs = {
            "parent": self,
            "backend": self.cmb_segmentation_backend.currentText(),
            "bbox_count": int(detection_count),
            "initial_mask_threshold": float(self.sp_sam2_mask_threshold.value()),
            "checkpoints": list(self._sam2_checkpoints),
            "selected_checkpoint_path": self._selected_sam2_checkpoint_path,
        }
        if self._sam2_settings_dialog_factory is not None:
            return self._sam2_settings_dialog_factory(**kwargs)
        return Sam2SegmentationSettingsDialog(**kwargs)

    def _start_sam2_segmentation(
        self,
        detections,
        *,
        mask_probability_threshold: float,
        checkpoint_path,
        existing_masks_policy: str,
        keep_largest_component: bool,
        min_mask_area_px: int,
        scope: str,
    ) -> None:
        detections = list(detections)
        if self._series is None or not detections:
            return
        if str(existing_masks_policy) == SAM2_EXISTING_MASK_POLICY_SKIP:
            original_count = len(detections)
            detections = [
                detection
                for detection in detections
                if not self._has_existing_sam2_segmentation_for_detection(detection)
            ]
            skipped_count = original_count - len(detections)
            if not detections:
                self.statusBar().showMessage(
                    f"SAM2 skipped {skipped_count} BBox(es) with existing masks.",
                    5000,
                )
                self._sync_segmentation_controls()
                return
        frame_index = detections[0].frame_index
        source_view = detections[0].source_view
        try:
            frame = self._current_yolo_frame(source_view).copy()
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "SAM2 segmentation error", message)
            self.statusBar().showMessage("SAM2 segmentation failed.", 3000)
            return

        self._sam2_segmentation_running = True
        self._sam2_segmentation_scope = str(scope)
        self._sam2_segmentation_existing_masks_policy = str(existing_masks_policy)
        self._set_file_actions_enabled(False)
        self._sam2_segmentation_progress_dialog = self._show_sam2_segmentation_progress_dialog(
            frame_index=frame_index,
            detection_count=len(detections),
        )
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"Running SAM2 segmentation on {len(detections)} BBox(es) from frame {frame_index + 1}...",
            0,
        )

        self._sam2_segmentation_thread = QThread(self)
        self._sam2_segmentation_worker = _Sam2SegmentWorker(
            self._sam2_segmenter,
            frame,
            detections,
            mask_probability_threshold=float(mask_probability_threshold),
            checkpoint_path=checkpoint_path,
            existing_masks_policy=str(existing_masks_policy),
            keep_largest_component=bool(keep_largest_component),
            min_mask_area_px=int(min_mask_area_px),
        )
        self._sam2_segmentation_worker.moveToThread(self._sam2_segmentation_thread)
        self._sam2_segmentation_thread.started.connect(self._sam2_segmentation_worker.run)
        self._sam2_segmentation_worker.progress.connect(self._on_sam2_segmentation_progress)
        self._sam2_segmentation_worker.finished.connect(self._on_sam2_segmentation_finished)
        self._sam2_segmentation_worker.failed.connect(self._on_sam2_segmentation_failed)
        self._sam2_segmentation_worker.finished.connect(self._sam2_segmentation_thread.quit)
        self._sam2_segmentation_worker.failed.connect(self._sam2_segmentation_thread.quit)
        self._sam2_segmentation_thread.finished.connect(self._cleanup_sam2_segmentation_worker)
        self._sam2_segmentation_thread.start()

    def _has_existing_sam2_segmentation_for_detection(self, detection) -> bool:
        if self._series is None or self._series.molecular_segmentations is None:
            return False
        prompt_ids = (detection.detection_id,)
        for segmentation in self._series.molecular_segmentations.get_segmentations(
            detection.frame_index,
            source_view=detection.source_view,
        ):
            if segmentation.origin != "sam2":
                continue
            if tuple(segmentation.prompt_detection_ids) == prompt_ids:
                return True
        return False

    def _show_sam2_segmentation_progress_dialog(self, *, frame_index: int, detection_count: int) -> QProgressDialog:
        progress_dialog = QProgressDialog(
            f"Running SAM2 segmentation: 0 / {detection_count} BBox(es) on frame {frame_index + 1}...",
            None,
            0,
            detection_count,
            self,
        )
        progress_dialog.setWindowTitle("SAM2 Segmentation")
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.setValue(0)
        progress_dialog.show()
        QApplication.processEvents()
        return progress_dialog

    @pyqtSlot(int, int)
    def _on_sam2_segmentation_progress(self, completed: int, total: int) -> None:
        if not self._sam2_segmentation_running:
            return
        label = f"Running SAM2 segmentation: {completed} / {total} BBox(es)..."
        if self._sam2_segmentation_progress_dialog is not None:
            self._sam2_segmentation_progress_dialog.setLabelText(label)
            self._sam2_segmentation_progress_dialog.setValue(int(completed))
        self.statusBar().showMessage(label, 0)

    @pyqtSlot(object)
    def _on_sam2_segmentation_finished(self, results) -> None:
        results = list(results)
        selected_detection_id = self._selected_molecular_detection_id
        try:
            if self._series is None:
                raise RuntimeError("No series loaded.")
            for detection, segmentation in results:
                if segmentation.frame_index != detection.frame_index:
                    raise ValueError("SAM2 segmentation frame_index does not match the prompt BBox.")
                if segmentation.source_view != detection.source_view:
                    raise ValueError("SAM2 segmentation source_view does not match the prompt BBox.")
            segmentation_set = self._ensure_molecular_segmentation_set()
            for _detection, segmentation in results:
                self._ensure_sam2_original_mask(segmentation)
                if self._sam2_segmentation_existing_masks_policy == SAM2_EXISTING_MASK_POLICY_REPLACE:
                    self._remove_existing_sam2_segmentations_for_prompt(segmentation_set, segmentation)
                segmentation_set.add_segmentation(segmentation)
        except Exception as exc:
            self._finish_sam2_segmentation_run()
            message = str(exc) or exc.__class__.__name__
            QMessageBox.critical(self, "SAM2 segmentation error", message)
            self.statusBar().showMessage("SAM2 segmentation failed.", 3000)
            return

        count = len(results)
        frame_index = results[0][0].frame_index if results else self._series.active_frame_index
        scope = self._sam2_segmentation_scope
        self._finish_sam2_segmentation_run()
        self._show_current_frame()
        if selected_detection_id is not None:
            self.viewer.select_molecular_detection_by_id(selected_detection_id)
        if scope == "selected" and count == 1:
            final_message = f"SAM2 segmented selected BBox on frame {frame_index + 1}."
        else:
            final_message = f"SAM2 segmented {count} BBox(es) on frame {frame_index + 1}."
        self.statusBar().showMessage(final_message, 5000)
        QTimer.singleShot(0, lambda message=final_message: self.statusBar().showMessage(message, 5000))

    def _ensure_sam2_original_mask(self, segmentation) -> None:
        if segmentation.origin != "sam2" or segmentation.mask is None or segmentation.original_mask is not None:
            return
        segmentation.original_mask = np.asarray(segmentation.mask, dtype=bool).copy()

    @pyqtSlot(str)
    def _on_sam2_segmentation_failed(self, message: str) -> None:
        self._finish_sam2_segmentation_run()
        QMessageBox.critical(self, "SAM2 segmentation error", message)
        failure_message = "SAM2 segmentation failed."
        self.statusBar().showMessage(failure_message, 3000)
        QTimer.singleShot(0, lambda message=failure_message: self.statusBar().showMessage(message, 3000))

    def _finish_sam2_segmentation_run(self) -> None:
        self._sam2_segmentation_running = False
        self._sam2_segmentation_scope = ""
        self._sam2_segmentation_existing_masks_policy = SAM2_EXISTING_MASK_POLICY_REPLACE
        self._set_file_actions_enabled(True)
        self._close_sam2_segmentation_progress_dialog()
        self._sync_navigation_controls()

    def _remove_existing_sam2_segmentations_for_prompt(self, segmentation_set, new_segmentation) -> int:
        prompt_ids = tuple(new_segmentation.prompt_detection_ids)
        if not prompt_ids:
            return 0
        to_remove = [
            segmentation.segmentation_id
            for segmentation in segmentation_set.get_segmentations(
                new_segmentation.frame_index,
                source_view=new_segmentation.source_view,
            )
            if segmentation.origin == "sam2"
            and tuple(segmentation.prompt_detection_ids) == prompt_ids
        ]
        for segmentation_id in to_remove:
            segmentation_set.remove_segmentation(segmentation_id)
        return len(to_remove)

    def _close_sam2_segmentation_progress_dialog(self) -> None:
        if self._sam2_segmentation_progress_dialog is None:
            return
        self._sam2_segmentation_progress_dialog.close()
        self._sam2_segmentation_progress_dialog = None
        QApplication.processEvents()

    def _cleanup_sam2_segmentation_worker(self) -> None:
        if self._sam2_segmentation_worker is not None:
            self._sam2_segmentation_worker.deleteLater()
            self._sam2_segmentation_worker = None
        if self._sam2_segmentation_thread is not None:
            self._sam2_segmentation_thread.deleteLater()
            self._sam2_segmentation_thread = None

    def _manual_bbox_from_pixel_drag(
        self,
        start_xy_px: tuple[float, float],
        end_xy_px: tuple[float, float],
        *,
        frame_shape: tuple[int, int],
    ) -> tuple[float, float, float, float] | None:
        height, width = (int(value) for value in frame_shape)
        x0 = min(float(start_xy_px[0]), float(end_xy_px[0]))
        y0 = min(float(start_xy_px[1]), float(end_xy_px[1]))
        x1 = max(float(start_xy_px[0]), float(end_xy_px[0]))
        y1 = max(float(start_xy_px[1]), float(end_xy_px[1]))
        x0 = min(max(x0, 0.0), float(width))
        x1 = min(max(x1, 0.0), float(width))
        y0 = min(max(y0, 0.0), float(height))
        y1 = min(max(y1, 0.0), float(height))
        if (x1 - x0) < MIN_MANUAL_BBOX_SIZE_PX or (y1 - y0) < MIN_MANUAL_BBOX_SIZE_PX:
            return None
        return x0, y0, x1, y1

    def _current_bbox_frame_shape(self, source_view: str) -> tuple[int, int]:
        if self._series is None:
            raise RuntimeError("BBox resize requires a loaded series.")
        if source_view == "expanded_aligned":
            expanded = self._ensure_expanded_aligned_stack()
            return int(expanded.frames.shape[1]), int(expanded.frames.shape[2])
        return self._series.frame_shape

    def _finish_bbox_resize(self, changed: int, *, verb: str) -> None:
        self._show_current_frame()
        self._sync_yolo_controls()
        source_label = "expanded aligned" if self._current_yolo_source_view() == "expanded_aligned" else "raw"
        self.statusBar().showMessage(f"{verb} {changed} BBox(es) in {source_label}.", 3000)

    def _show_bbox_resize_error(self, exc: Exception) -> None:
        message = str(exc) or exc.__class__.__name__
        QMessageBox.critical(self, "BBox resize failed", message)
        self.statusBar().showMessage("BBox resize failed.", 3000)

    def _show_current_frame(self) -> None:
        if self._series is None:
            self.viewer.clear()
            return
        if self._is_expanded_aligned_view_requested():
            try:
                expanded = self._ensure_expanded_aligned_stack()
            except Exception as exc:
                self._set_registration_view_mode("Show raw")
                QMessageBox.critical(self, "Expanded aligned view failed", str(exc))
                self.statusBar().showMessage("Expanded aligned view failed.", 3000)
            else:
                self.viewer.show_expanded_aligned_frame(
                    self._series,
                    expanded,
                    self._series.active_frame_index,
                )
                self._show_current_sam3_manual_prompt_overlays()
                self.metadata_panel.set_image_series(self._series)
                self._refresh_position_analysis_dialog_if_open()
                return
        self.viewer.show_frame(self._series.active_frame_index)
        self._show_current_sam3_manual_prompt_overlays()
        self._refresh_position_analysis_dialog_if_open()

    def _refresh_position_analysis_dialog_if_open(self) -> None:
        if self._position_analysis_dialog is None or self._series is None:
            return
        self._position_analysis_dialog.set_plot_data(self._build_current_position_plot_data())

    def _show_current_sam3_manual_prompt_overlays(self) -> None:
        if self._series is None:
            self.viewer.clear_sam3_manual_prompt_overlays()
            return
        self.viewer.show_sam3_manual_prompts(
            self.sam3_manual_prompt_bboxes(label=1),
            self.sam3_manual_prompt_bboxes(label=0),
        )

    def _on_frame_selected(self, frame_index: int) -> None:
        if self._series is None:
            return
        previous_frame_index = self._series.active_frame_index
        self._series.set_active_frame(int(frame_index))
        if self._series.active_frame_index != previous_frame_index:
            self._clear_sam3_prompt_draw_mode()
        self._sync_navigation_controls()
        self._show_current_frame()
        self.metadata_panel.set_active_frame(int(frame_index))

    def _on_remove_current_frame_requested(self) -> None:
        if self._series is None:
            return
        try:
            self._series.remove_frame()
        except ValueError as exc:
            QMessageBox.critical(self, "Remove frame failed", str(exc))
            self.statusBar().showMessage("Remove frame failed.", 3000)
            return
        self._set_registration_view_mode("Show raw")
        self._sync_navigation_controls()
        self._show_current_frame()
        self.metadata_panel.set_image_series(self._series)
        self.statusBar().showMessage("Removed current frame.", 3000)

    def _on_run_registration_requested(self) -> None:
        if self._series is None or self._registration_running:
            return
        settings = MolTrackRegistrationSettings(
            backend=self.cmb_registration_backend.currentText(),
        )
        self._registration_running = True
        self._set_file_actions_enabled(False)
        self._registration_progress_dialog = self._show_registration_progress_dialog(settings)
        self._sync_navigation_controls()
        self.lbl_registration_status.setText(f"Running {settings.backend} registration...")
        self.statusBar().showMessage(f"Running {settings.backend} registration...", 0)

        self._registration_thread = QThread(self)
        self._registration_worker = _RegistrationRunWorker(self._registration_runner, self._series, settings)
        self._registration_worker.moveToThread(self._registration_thread)
        self._registration_thread.started.connect(self._registration_worker.run)
        self._registration_worker.finished.connect(self._on_registration_finished)
        self._registration_worker.failed.connect(self._on_registration_failed)
        self._registration_worker.finished.connect(self._registration_thread.quit)
        self._registration_worker.failed.connect(self._registration_thread.quit)
        self._registration_thread.finished.connect(self._cleanup_registration_worker)
        self._registration_thread.start()

    def _on_registration_finished(self, result_set) -> None:
        if self._series is not None and self._series.registration_results is None:
            self._series.registration_results = result_set
        self._registration_running = False
        self._set_file_actions_enabled(True)
        self._close_registration_progress_dialog()
        self._sync_navigation_controls()
        self.lbl_registration_status.setText(
            f"Registered {result_set.result_count} frames with {result_set.settings.backend}"
        )
        self.cmb_registration_view_mode.setEnabled(True)
        self.statusBar().showMessage(
            f"Registration finished for {result_set.result_count} frames.",
            5000,
        )

    def _on_registration_failed(self, message: str) -> None:
        self._registration_running = False
        self._set_file_actions_enabled(True)
        self._close_registration_progress_dialog()
        self._sync_navigation_controls()
        QMessageBox.critical(self, "Registration failed", message)
        self.lbl_registration_status.setText(f"Registration failed: {message}")
        self.statusBar().showMessage("Registration failed.", 3000)

    def _show_registration_progress_dialog(self, settings: MolTrackRegistrationSettings) -> QProgressDialog:
        progress_dialog = QProgressDialog(
            f"Running {settings.backend} registration...",
            None,
            0,
            0,
            self,
        )
        progress_dialog.setWindowTitle("Registration")
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.show()
        QApplication.processEvents()
        return progress_dialog

    def _close_registration_progress_dialog(self) -> None:
        if self._registration_progress_dialog is None:
            return
        self._registration_progress_dialog.close()
        self._registration_progress_dialog = None
        QApplication.processEvents()

    def _cleanup_registration_worker(self) -> None:
        if self._registration_worker is not None:
            self._registration_worker.deleteLater()
            self._registration_worker = None
        if self._registration_thread is not None:
            self._registration_thread.deleteLater()
            self._registration_thread = None

    def _set_file_actions_enabled(self, enabled: bool) -> None:
        self.action_open_stm.setEnabled(enabled)
        self.action_open_stm_reverse.setEnabled(enabled)
        self.action_open_state.setEnabled(enabled)
        can_save_state = enabled and self._series is not None
        self.action_save_state.setEnabled(can_save_state)
        self.action_save_state_as.setEnabled(can_save_state)

    def _sync_registration_status(self) -> None:
        if self._series is None or self._series.registration_results is None:
            self.lbl_registration_status.setText("No registration results")
            return
        result_set = self._series.registration_results
        self.lbl_registration_status.setText(
            f"Registered {result_set.result_count} frames with {result_set.settings.backend}"
        )

    def _on_registration_view_mode_changed(self, _mode: str) -> None:
        if self._series is None:
            return
        self._clear_sam3_prompt_draw_mode()
        self._show_current_frame()
        self._sync_yolo_controls()

    def _is_expanded_aligned_view_requested(self) -> bool:
        return self.cmb_registration_view_mode.currentText() == "Show expanded aligned"

    def _set_registration_view_mode(self, mode: str) -> None:
        previous = self.cmb_registration_view_mode.blockSignals(True)
        try:
            index = self.cmb_registration_view_mode.findText(mode)
            if index >= 0:
                self.cmb_registration_view_mode.setCurrentIndex(index)
        finally:
            self.cmb_registration_view_mode.blockSignals(previous)

    def _ensure_expanded_aligned_stack(self):
        if self._series is None:
            raise RuntimeError("expanded aligned view requires a loaded series.")
        if self._series.registration_results is None:
            raise RuntimeError("expanded aligned view requires registration results.")
        if self._series.expanded_aligned_stack is None:
            self._series.expanded_aligned_stack = self._expanded_aligned_builder(self._series)
        return self._series.expanded_aligned_stack

    def _on_open_stm_requested(self) -> None:
        self._choose_and_open_stm(reverse_frame_order=False)

    def _on_open_stm_reverse_requested(self) -> None:
        self._choose_and_open_stm(reverse_frame_order=True)

    def _on_open_state_requested(self) -> None:
        self._choose_and_open_state()

    def _on_save_state_requested(self) -> None:
        if self._session_path is None:
            self._choose_and_save_state()
            return
        self.save_state(self._session_path)

    def _on_save_state_as_requested(self) -> None:
        self._choose_and_save_state()

    def _choose_and_save_state(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save State",
            "",
            "MolTrack state (*.moltrack.json);;JSON files (*.json)",
        )
        if not path:
            return
        self.save_state(path)

    def save_state(self, path) -> None:
        if self._series is None:
            return
        try:
            self._session_saver(path, self._series, self._current_ui_state())
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.statusBar().showMessage(f"Save State failed: {message}", 5000)
            QMessageBox.critical(self, "Save State failed", message)
            return
        self._session_path = str(path)
        self.statusBar().showMessage(f"Saved state {path}", 5000)

    def _current_ui_state(self) -> dict[str, str | int]:
        return {
            "registration_view_mode": self.cmb_registration_view_mode.currentText(),
            "bbox_opacity_percent": self.slider_bbox_opacity.value(),
        }

    def _choose_and_open_state(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open State",
            "",
            "MolTrack state (*.moltrack.json *.json);;JSON files (*.json)",
        )
        if not path:
            return
        self.open_state(path)

    def open_state(self, path) -> None:
        try:
            session = self._session_loader(path)
            series = self._session_restorer(session)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.statusBar().showMessage(f"Open State failed: {message}", 5000)
            QMessageBox.critical(self, "Open State failed", message)
            return

        registration_view_mode = getattr(session, "registration_view_mode", "Show raw")
        bbox_opacity_percent = getattr(session, "bbox_opacity_percent", 100)
        self.set_image_series(series)
        self._session_path = str(path)
        self._set_registration_view_mode(registration_view_mode)
        self.slider_bbox_opacity.setValue(int(bbox_opacity_percent))
        self._sync_navigation_controls()
        self._show_current_frame()
        self.metadata_panel.set_image_series(series)
        self.statusBar().showMessage(f"Loaded state {path}", 5000)

    def _choose_and_open_stm(self, *, reverse_frame_order: bool) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open STM",
            "",
            "MPP files (*.mpp *.MPP)",
        )
        if not path:
            return
        try:
            self.open_stm_source(path, reverse_frame_order=reverse_frame_order)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.statusBar().showMessage(f"Open STM failed: {message}", 5000)
            QMessageBox.critical(self, "Open STM failed", message)
