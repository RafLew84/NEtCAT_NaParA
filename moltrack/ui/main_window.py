from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QMainWindow


class MolTrackMainWindow(QMainWindow):
    """Initial empty workspace for MolTrack."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MolTrack")
        self.resize(1280, 860)
        self.setCentralWidget(QLabel("MolTrack workspace", self))
        self.statusBar().showMessage("Ready")
