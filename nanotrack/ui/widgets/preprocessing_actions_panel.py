from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget


class PreprocessingActionsPanel(QWidget):
    """Sidebar panel exposing preprocessing entry points."""

    preview_requested = pyqtSignal()
    apply_all_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
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

        self.btn_preview.clicked.connect(self.preview_requested.emit)
        self.btn_apply_all.clicked.connect(self.apply_all_requested.emit)

        group_layout.addWidget(self.lbl_method)
        group_layout.addWidget(self.lbl_status)
        form.addRow("Sigma factor:", self.sp_bm3d_sigma)
        group_layout.addLayout(form)
        group_layout.addWidget(self.btn_preview)
        group_layout.addWidget(self.btn_apply_all)

        layout.addWidget(group)
        layout.addStretch(1)

    def set_sequence_loaded(self, loaded: bool) -> None:
        self.sp_bm3d_sigma.setEnabled(loaded)
        self.btn_preview.setEnabled(loaded)
        self.btn_apply_all.setEnabled(loaded)
        if not loaded:
            self.lbl_status.setText("No sequence loaded")

    def bm3d_sigma_factor(self) -> float:
        return float(self.sp_bm3d_sigma.value())

    def set_preview_status(self, text: str) -> None:
        self.lbl_status.setText(text)
