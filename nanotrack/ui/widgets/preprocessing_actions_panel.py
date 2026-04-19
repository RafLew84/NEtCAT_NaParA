from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget


class PreprocessingActionsPanel(QWidget):
    """Sidebar panel exposing preprocessing entry points."""

    preview_requested = pyqtSignal()
    apply_all_requested = pyqtSignal()
    show_denoised_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence_loaded = False
        self._processing = False
        self._denoised_available = False
        self._build()
        self.set_sequence_loaded(False)

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Preprocessing", self)
        group_layout = QVBoxLayout(group)
        form = QFormLayout()

        self.lbl_method = QLabel("Method: BM3D", self)
        self.lbl_status = QLabel("No sequence loaded", self)
        self.sp_bm3d_sigma = QDoubleSpinBox(self)
        self.sp_bm3d_sigma.setRange(0.1, 5.0)
        self.sp_bm3d_sigma.setSingleStep(0.1)
        self.sp_bm3d_sigma.setValue(1.0)
        self.btn_preview = QPushButton("Preview Current Frame", self)
        self.btn_apply_all = QPushButton("Apply to All Frames", self)
        self.chk_show_denoised = QCheckBox("Show BM3D in main view", self)

        self.btn_preview.clicked.connect(self.preview_requested.emit)
        self.btn_apply_all.clicked.connect(self.apply_all_requested.emit)
        self.chk_show_denoised.toggled.connect(self.show_denoised_toggled.emit)

        group_layout.addWidget(self.lbl_method)
        group_layout.addWidget(self.lbl_status)
        form.addRow("Sigma factor:", self.sp_bm3d_sigma)
        group_layout.addLayout(form)
        group_layout.addWidget(self.btn_preview)
        group_layout.addWidget(self.btn_apply_all)
        group_layout.addWidget(self.chk_show_denoised)

        layout.addWidget(group)
        layout.addStretch(1)

    def set_sequence_loaded(self, loaded: bool) -> None:
        self._sequence_loaded = loaded
        if not loaded:
            self.set_denoised_available(False)
        self._apply_enabled_state()
        if not loaded:
            self.lbl_status.setText("No sequence loaded")

    def set_processing(self, processing: bool) -> None:
        self._processing = processing
        self._apply_enabled_state()

    def bm3d_sigma_factor(self) -> float:
        return float(self.sp_bm3d_sigma.value())

    def set_denoised_available(self, available: bool) -> None:
        self._denoised_available = available
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
        self.sp_bm3d_sigma.setEnabled(enabled)
        self.btn_preview.setEnabled(enabled)
        self.btn_apply_all.setEnabled(enabled)
        self.chk_show_denoised.setEnabled(enabled and self._denoised_available)
