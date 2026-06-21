from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moltrack.core import (
    MolecularDetectionSet,
    MolTrackRegistrationSettings,
    SUPPORTED_REGISTRATION_BACKENDS,
    build_moltrack_expanded_aligned_stack,
    run_moltrack_registration,
)
from moltrack.io import load_moltrack_image_series
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from moltrack.ui.widgets import STMSeriesViewer, SeriesMetadataPanel
from moltrack.yolo import MolTrackYoloDetector, discover_yolo_models


MIN_MANUAL_BBOX_SIZE_PX = 1.0


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
        self._yolo_models = []
        self._yolo_detection_running = False
        self._yolo_detection_progress_dialog: QProgressDialog | None = None
        self._yolo_detection_thread: QThread | None = None
        self._yolo_detection_worker: _YoloDetectAllWorker | None = None
        self._yolo_detection_model_name = ""
        self._yolo_detection_source_view = "raw"
        self._selected_molecular_detection_id: str | None = None
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
        sidebar_layout.addWidget(self.bbox_edit_group)

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
        self.viewer.molecular_detection_selection_changed.connect(self._on_molecular_detection_selection_changed)
        self.viewer.manual_molecular_bbox_drawn.connect(self._on_manual_molecular_bbox_drawn)

    def set_image_series(self, series) -> None:
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
            self._set_registration_view_mode("Show raw")
            self.lbl_registration_status.setText("No registration results")
            self._sync_yolo_controls()
            return

        controls_enabled = not self._is_processing()
        self._update_navigation_enabled(controls_enabled)
        self.btn_remove_current_frame.setEnabled(controls_enabled and self._series.frame_count > 1)
        self.cmb_registration_backend.setEnabled(controls_enabled)
        self.btn_run_registration.setEnabled(controls_enabled)
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
        self.btn_bbox_add.setEnabled(controls_enabled)
        if not controls_enabled and self.btn_bbox_add.isChecked():
            self.btn_bbox_add.blockSignals(True)
            try:
                self.btn_bbox_add.setChecked(False)
            finally:
                self.btn_bbox_add.blockSignals(False)
            self.viewer.set_molecular_bbox_add_mode_enabled(False)

        selected_detection = self._current_selected_molecular_detection()
        has_selection = controls_enabled and selected_detection is not None
        self.btn_bbox_delete_selected.setEnabled(has_selection)

        if controls_enabled and self.btn_bbox_add.isChecked():
            self.lbl_bbox_edit_status.setText("Add BBox: drag on image")
            return

        if selected_detection is None:
            self.lbl_bbox_edit_status.setText("No BBox selected")
            return

        view_label = "expanded aligned" if selected_detection.source_view == "expanded_aligned" else "raw"
        self.lbl_bbox_edit_status.setText(
            f"Selected BBox: frame {selected_detection.frame_index + 1}, {view_label}"
        )

    def _current_molecular_detection_count(self) -> int:
        if self._series is None or self._series.molecular_detections is None:
            return 0
        return len(
            self._series.molecular_detections.get_detections(
                self._series.active_frame_index,
                source_view=self._current_yolo_source_view(),
            )
        )

    def _current_yolo_source_view(self) -> str:
        return "expanded_aligned" if self._is_expanded_aligned_view_requested() else "raw"

    def selected_molecular_detection_id(self) -> str | None:
        return self._selected_molecular_detection_id

    def select_molecular_detection_at_pixel(self, x_px: float, y_px: float) -> str | None:
        return self.viewer.select_molecular_detection_at_pixel(
            x_px,
            y_px,
            source_view=self._current_yolo_source_view(),
        )

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

    def _source_view_molecular_detection_count(self, source_view: str) -> int:
        if self._series is None or self._series.molecular_detections is None:
            return 0
        total = 0
        for frame_index in range(self._series.frame_count):
            total += len(self._series.molecular_detections.get_detections(frame_index, source_view=source_view))
        return total

    def _is_processing(self) -> bool:
        return self._registration_running or self._yolo_detection_running

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
        self.viewer.set_molecular_bbox_add_mode_enabled(bool(checked))
        self._sync_bbox_edit_controls()

    def _on_manual_molecular_bbox_drawn(self, bbox_xyxy) -> None:
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
                self.metadata_panel.set_image_series(self._series)
                return
        self.viewer.show_frame(self._series.active_frame_index)

    def _on_frame_selected(self, frame_index: int) -> None:
        if self._series is None:
            return
        self._series.set_active_frame(int(frame_index))
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

    def _current_ui_state(self) -> dict[str, str]:
        return {
            "registration_view_mode": self.cmb_registration_view_mode.currentText(),
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
        self.set_image_series(series)
        self._session_path = str(path)
        self._set_registration_view_mode(registration_view_mode)
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
