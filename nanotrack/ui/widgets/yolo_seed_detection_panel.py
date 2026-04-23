from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nanotrack.yolo import YoloModelInfo, discover_yolo_models


class YoloSeedDetectionPanel(QWidget):
    """Sidebar tools for creating seed bbox proposals from local YOLO models."""

    detect_current_requested = pyqtSignal()
    detect_all_requested = pyqtSignal()
    select_all_current_requested = pyqtSignal()
    deselect_all_current_requested = pyqtSignal()
    select_all_global_requested = pyqtSignal()
    deselect_all_global_requested = pyqtSignal()
    convert_selected_current_requested = pyqtSignal()
    convert_selected_all_requested = pyqtSignal()
    clear_detections_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._models: list[YoloModelInfo] = []
        self._sequence_loaded = False
        self._processing_busy = False
        self._detect_current_available = True
        self._detect_all_available = False
        self._current_selection_actions_available = False
        self._global_selection_actions_available = False
        self._conversion_actions_available = False
        self._clear_action_available = False
        self._current_detection_count = 0
        self._total_detection_count = 0
        self._current_selected_count = 0
        self._total_selected_count = 0
        self._build()
        self._connect_signals()
        self.refresh_models()
        self._update_enabled_state()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("YOLO Seed Detection", self)
        group_layout = QVBoxLayout(group)

        self.lbl_hint = QLabel(
            "Load a local YOLO checkpoint, detect bbox proposals on the current frame or the whole sequence, "
            "then decide which detections should become seeds.",
            group,
        )
        self.lbl_hint.setWordWrap(True)
        group_layout.addWidget(self.lbl_hint)

        self.cmb_model = QComboBox(group)
        self.cmb_model.setToolTip("Choose a YOLO checkpoint discovered in nanotrack/yolo_models.")
        group_layout.addWidget(self.cmb_model)

        threshold_row = QHBoxLayout()
        self.sp_confidence = QDoubleSpinBox(group)
        self.sp_confidence.setRange(0.01, 1.0)
        self.sp_confidence.setSingleStep(0.05)
        self.sp_confidence.setDecimals(2)
        self.sp_confidence.setValue(0.25)
        self.sp_confidence.setPrefix("Conf ")
        self.sp_confidence.setToolTip("Confidence threshold passed to YOLO detection.")
        self.sp_iou = QDoubleSpinBox(group)
        self.sp_iou.setRange(0.01, 1.0)
        self.sp_iou.setSingleStep(0.05)
        self.sp_iou.setDecimals(2)
        self.sp_iou.setValue(0.45)
        self.sp_iou.setPrefix("IoU ")
        self.sp_iou.setToolTip("Non-maximum-suppression IoU threshold passed to YOLO detection.")
        threshold_row.addWidget(self.sp_confidence)
        threshold_row.addWidget(self.sp_iou)
        group_layout.addLayout(threshold_row)

        detect_row = QHBoxLayout()
        self.btn_detect_current = QPushButton("Detect Current Frame", group)
        self.btn_detect_all = QPushButton("Detect All Frames", group)
        detect_row.addWidget(self.btn_detect_current)
        detect_row.addWidget(self.btn_detect_all)
        group_layout.addLayout(detect_row)

        current_row = QHBoxLayout()
        self.btn_select_all_current = QPushButton("Select All (Current)", group)
        self.btn_deselect_all_current = QPushButton("Deselect All (Current)", group)
        current_row.addWidget(self.btn_select_all_current)
        current_row.addWidget(self.btn_deselect_all_current)
        group_layout.addLayout(current_row)

        global_row = QHBoxLayout()
        self.btn_select_all_global = QPushButton("Select All (All Frames)", group)
        self.btn_deselect_all_global = QPushButton("Deselect All (All Frames)", group)
        global_row.addWidget(self.btn_select_all_global)
        global_row.addWidget(self.btn_deselect_all_global)
        group_layout.addLayout(global_row)

        convert_row = QHBoxLayout()
        self.btn_convert_current = QPushButton("Convert Selected to Seeds (Current)", group)
        self.btn_convert_all = QPushButton("Convert Selected to Seeds (All Frames)", group)
        convert_row.addWidget(self.btn_convert_current)
        convert_row.addWidget(self.btn_convert_all)
        group_layout.addLayout(convert_row)

        self.btn_clear = QPushButton("Clear YOLO Detections", group)
        group_layout.addWidget(self.btn_clear)

        self.lbl_frame = QLabel("Frame: -", group)
        self.lbl_models = QLabel("No YOLO models found", group)
        self.lbl_detections = QLabel("Detections: current 0 (selected 0) | all 0 (selected 0)", group)
        self.lbl_models.setWordWrap(True)
        self.lbl_detections.setWordWrap(True)
        group_layout.addWidget(self.lbl_frame)
        group_layout.addWidget(self.lbl_models)
        group_layout.addWidget(self.lbl_detections)

        layout.addWidget(group)
        layout.addStretch(0)

    def _connect_signals(self) -> None:
        self.btn_detect_current.clicked.connect(self.detect_current_requested)
        self.btn_detect_all.clicked.connect(self.detect_all_requested)
        self.btn_select_all_current.clicked.connect(self.select_all_current_requested)
        self.btn_deselect_all_current.clicked.connect(self.deselect_all_current_requested)
        self.btn_select_all_global.clicked.connect(self.select_all_global_requested)
        self.btn_deselect_all_global.clicked.connect(self.deselect_all_global_requested)
        self.btn_convert_current.clicked.connect(self.convert_selected_current_requested)
        self.btn_convert_all.clicked.connect(self.convert_selected_all_requested)
        self.btn_clear.clicked.connect(self.clear_detections_requested)

    def _update_enabled_state(self) -> None:
        can_configure = not self._processing_busy and bool(self._models)
        can_detect = self._sequence_loaded and can_configure

        self.cmb_model.setEnabled(can_configure)
        self.sp_confidence.setEnabled(not self._processing_busy)
        self.sp_iou.setEnabled(not self._processing_busy)
        self.btn_detect_current.setEnabled(can_detect and self._detect_current_available)
        self.btn_detect_all.setEnabled(can_detect and self._detect_all_available)
        self.btn_select_all_current.setEnabled(
            can_detect and self._current_selection_actions_available and self._current_detection_count > 0
        )
        self.btn_deselect_all_current.setEnabled(
            can_detect and self._current_selection_actions_available and self._current_detection_count > 0
        )
        self.btn_select_all_global.setEnabled(
            can_detect and self._global_selection_actions_available and self._total_detection_count > 0
        )
        self.btn_deselect_all_global.setEnabled(
            can_detect and self._global_selection_actions_available and self._total_detection_count > 0
        )
        self.btn_convert_current.setEnabled(
            can_detect and self._conversion_actions_available and self._current_selected_count > 0
        )
        self.btn_convert_all.setEnabled(
            can_detect and self._conversion_actions_available and self._total_selected_count > 0
        )
        self.btn_clear.setEnabled(can_detect and self._clear_action_available and self._total_detection_count > 0)

    def refresh_models(self, models: list[YoloModelInfo] | None = None) -> None:
        current_path = self.current_model_path()
        self._models = list(discover_yolo_models() if models is None else models)

        self.cmb_model.clear()
        selected_index = -1
        for index, model in enumerate(self._models):
            model_path = str(model.path)
            self.cmb_model.addItem(model.display_name, model_path)
            if current_path is not None and model_path == current_path:
                selected_index = index

        if selected_index >= 0:
            self.cmb_model.setCurrentIndex(selected_index)
        elif self._models:
            self.cmb_model.setCurrentIndex(0)

        if self._models:
            self.lbl_models.setText(f"Models available: {len(self._models)}")
        else:
            self.lbl_models.setText("No YOLO models found in nanotrack/yolo_models")
        self._update_enabled_state()

    def set_sequence_loaded(self, loaded: bool) -> None:
        self._sequence_loaded = bool(loaded)
        if not self._sequence_loaded:
            self.clear_detection_state()
            self.lbl_frame.setText("Frame: -")
        self._update_enabled_state()

    def set_processing(self, busy: bool) -> None:
        self._processing_busy = bool(busy)
        self._update_enabled_state()

    def set_detect_all_available(self, available: bool) -> None:
        self._detect_all_available = bool(available)
        self._update_enabled_state()

    def set_current_selection_actions_available(self, available: bool) -> None:
        self._current_selection_actions_available = bool(available)
        self._update_enabled_state()

    def set_global_selection_actions_available(self, available: bool) -> None:
        self._global_selection_actions_available = bool(available)
        self._update_enabled_state()

    def set_conversion_actions_available(self, available: bool) -> None:
        self._conversion_actions_available = bool(available)
        self._update_enabled_state()

    def set_clear_action_available(self, available: bool) -> None:
        self._clear_action_available = bool(available)
        self._update_enabled_state()

    def set_frame_context(self, frame_index: int | None, frame_count: int | None = None) -> None:
        if frame_index is None or frame_count is None or frame_count <= 0:
            self.lbl_frame.setText("Frame: -")
        else:
            self.lbl_frame.setText(f"Frame: {frame_index + 1} / {frame_count}")

    def set_detection_counts(
        self,
        *,
        current_detection_count: int,
        total_detection_count: int,
        current_selected_count: int,
        total_selected_count: int,
    ) -> None:
        self._current_detection_count = max(0, int(current_detection_count))
        self._total_detection_count = max(0, int(total_detection_count))
        self._current_selected_count = max(0, int(current_selected_count))
        self._total_selected_count = max(0, int(total_selected_count))
        self.lbl_detections.setText(
            "Detections: current {} (selected {}) | all {} (selected {})".format(
                self._current_detection_count,
                self._current_selected_count,
                self._total_detection_count,
                self._total_selected_count,
            )
        )
        self._update_enabled_state()

    def clear_detection_state(self) -> None:
        self.set_detection_counts(
            current_detection_count=0,
            total_detection_count=0,
            current_selected_count=0,
            total_selected_count=0,
        )

    def current_model_name(self) -> str | None:
        index = self.cmb_model.currentIndex()
        if index < 0 or index >= len(self._models):
            return None
        return self._models[index].name

    def current_model_path(self) -> str | None:
        data = self.cmb_model.currentData()
        return None if data is None else str(data)

    def confidence_threshold(self) -> float:
        return float(self.sp_confidence.value())

    def nms_iou_threshold(self) -> float:
        return float(self.sp_iou.value())
