from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PreprocessingActionsPanel(QWidget):
    """Sidebar panel exposing preprocessing entry points."""

    preview_requested = pyqtSignal()
    apply_all_requested = pyqtSignal()
    repair_preview_requested = pyqtSignal()
    repair_apply_all_requested = pyqtSignal()
    show_denoised_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence_loaded = False
        self._processing = False
        self._cached_preprocessing_available = False
        self._build()
        self.set_sequence_loaded(False)

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setMinimumWidth(360)
        content_layout = QVBoxLayout(self.content_widget)

        group = QGroupBox("Preprocessing", self.content_widget)
        group_layout = QVBoxLayout(group)

        self.lbl_method = QLabel("Methods: Horizontal Repair -> BM3D", self)
        self.lbl_status = QLabel("No sequence loaded", self)

        repair_group = QGroupBox("Repair Horizontal Dropout Artifacts", self.content_widget)
        repair_form = QFormLayout(repair_group)
        self.sp_repair_threshold = QDoubleSpinBox(self.content_widget)
        self.sp_repair_threshold.setRange(0.5, 10.0)
        self.sp_repair_threshold.setSingleStep(0.1)
        self.sp_repair_threshold.setValue(3.0)
        self.sp_repair_min_width = QDoubleSpinBox(self.content_widget)
        self.sp_repair_min_width.setRange(0.5, 50.0)
        self.sp_repair_min_width.setSingleStep(0.5)
        self.sp_repair_min_width.setValue(2.0)
        self.sp_repair_max_width = QDoubleSpinBox(self.content_widget)
        self.sp_repair_max_width.setRange(1.0, 100.0)
        self.sp_repair_max_width.setSingleStep(1.0)
        self.sp_repair_max_width.setValue(20.0)
        self.sp_repair_thickness = QSpinBox(self.content_widget)
        self.sp_repair_thickness.setRange(1, 10)
        self.sp_repair_thickness.setValue(3)
        self.sp_repair_gap = QSpinBox(self.content_widget)
        self.sp_repair_gap.setRange(0, 20)
        self.sp_repair_gap.setValue(3)
        self.cmb_repair_mode = QComboBox(self.content_widget)
        self.cmb_repair_mode.addItems(["Vertical interpolation", "Inpaint"])
        self.btn_repair_preview = QPushButton("Preview Repair", self.content_widget)
        self.btn_repair_apply_all = QPushButton("Apply Repair to All Frames", self.content_widget)

        repair_form.addRow("Threshold sigma:", self.sp_repair_threshold)
        repair_form.addRow("Min width (%):", self.sp_repair_min_width)
        repair_form.addRow("Max width (%):", self.sp_repair_max_width)
        repair_form.addRow("Max thickness (px):", self.sp_repair_thickness)
        repair_form.addRow("Gap closing (px):", self.sp_repair_gap)
        repair_form.addRow("Repair mode:", self.cmb_repair_mode)

        bm3d_group = QGroupBox("BM3D", self.content_widget)
        bm3d_form = QFormLayout(bm3d_group)
        self.sp_bm3d_sigma = QDoubleSpinBox(self.content_widget)
        self.sp_bm3d_sigma.setRange(0.1, 5.0)
        self.sp_bm3d_sigma.setSingleStep(0.1)
        self.sp_bm3d_sigma.setValue(1.0)
        self.btn_preview = QPushButton("Preview BM3D", self.content_widget)
        self.btn_apply_all = QPushButton("Apply BM3D to All Frames", self.content_widget)
        self.chk_show_denoised = QCheckBox("Show cached preprocessing in main view", self.content_widget)

        bm3d_form.addRow("Sigma factor:", self.sp_bm3d_sigma)

        self.btn_repair_preview.clicked.connect(self.repair_preview_requested.emit)
        self.btn_repair_apply_all.clicked.connect(self.repair_apply_all_requested.emit)
        self.btn_preview.clicked.connect(self.preview_requested.emit)
        self.btn_apply_all.clicked.connect(self.apply_all_requested.emit)
        self.chk_show_denoised.toggled.connect(self.show_denoised_toggled.emit)

        group_layout.addWidget(self.lbl_method)
        group_layout.addWidget(self.lbl_status)
        group_layout.addWidget(repair_group)
        group_layout.addWidget(self.btn_repair_preview)
        group_layout.addWidget(self.btn_repair_apply_all)
        group_layout.addWidget(bm3d_group)
        group_layout.addWidget(self.btn_preview)
        group_layout.addWidget(self.btn_apply_all)
        group_layout.addWidget(self.chk_show_denoised)

        content_layout.addWidget(group)
        content_layout.addStretch(1)
        self.scroll_area.setWidget(self.content_widget)

        layout.addWidget(self.scroll_area, 1)

    def set_sequence_loaded(self, loaded: bool) -> None:
        self._sequence_loaded = loaded
        if not loaded:
            self.set_cached_preprocessing_available(False)
        self._apply_enabled_state()
        if not loaded:
            self.lbl_status.setText("No sequence loaded")

    def set_processing(self, processing: bool) -> None:
        self._processing = processing
        self._apply_enabled_state()

    def bm3d_sigma_factor(self) -> float:
        return float(self.sp_bm3d_sigma.value())

    def repair_parameters(self) -> dict[str, float | int | str]:
        return {
            "threshold_sigma": float(self.sp_repair_threshold.value()),
            "min_width_frac": float(self.sp_repair_min_width.value()) / 100.0,
            "max_width_frac": float(self.sp_repair_max_width.value()) / 100.0,
            "max_thickness_px": int(self.sp_repair_thickness.value()),
            "gap_closing_px": int(self.sp_repair_gap.value()),
            "repair_mode": "vertical_interp" if self.cmb_repair_mode.currentIndex() == 0 else "inpaint",
        }

    def set_cached_preprocessing_available(self, available: bool) -> None:
        self._cached_preprocessing_available = available
        if not available:
            with QSignalBlocker(self.chk_show_denoised):
                self.chk_show_denoised.setChecked(False)
        self._apply_enabled_state()

    def show_denoised_checked(self) -> bool:
        return bool(self.chk_show_denoised.isChecked())

    def set_preview_status(self, text: str) -> None:
        self.lbl_status.setText(text)

    def _apply_enabled_state(self) -> None:
        enabled = self._sequence_loaded and not self._processing
        self.sp_repair_threshold.setEnabled(enabled)
        self.sp_repair_min_width.setEnabled(enabled)
        self.sp_repair_max_width.setEnabled(enabled)
        self.sp_repair_thickness.setEnabled(enabled)
        self.sp_repair_gap.setEnabled(enabled)
        self.cmb_repair_mode.setEnabled(enabled)
        self.btn_repair_preview.setEnabled(enabled)
        self.btn_repair_apply_all.setEnabled(enabled)
        self.sp_bm3d_sigma.setEnabled(enabled)
        self.btn_preview.setEnabled(enabled)
        self.btn_apply_all.setEnabled(enabled)
        self.chk_show_denoised.setEnabled(enabled and self._cached_preprocessing_available)
