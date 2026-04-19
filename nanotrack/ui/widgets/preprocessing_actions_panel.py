from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget


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

        self.lbl_method = QLabel("Method: BM3D", self)
        self.lbl_status = QLabel("No sequence loaded", self)
        self.btn_preview = QPushButton("Preview Current Frame", self)
        self.btn_apply_all = QPushButton("Apply to All Frames", self)

        self.btn_preview.clicked.connect(self.preview_requested.emit)
        self.btn_apply_all.clicked.connect(self.apply_all_requested.emit)

        group_layout.addWidget(self.lbl_method)
        group_layout.addWidget(self.lbl_status)
        group_layout.addWidget(self.btn_preview)
        group_layout.addWidget(self.btn_apply_all)

        layout.addWidget(group)
        layout.addStretch(1)

    def set_sequence_loaded(self, loaded: bool) -> None:
        self.btn_preview.setEnabled(loaded)
        self.btn_apply_all.setEnabled(loaded)
        self.lbl_status.setText(
            "BM3D actions ready" if loaded else "No sequence loaded"
        )
