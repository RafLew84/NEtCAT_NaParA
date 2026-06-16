from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moltrack.io import load_moltrack_image_series
from moltrack.ui.widgets import STMSeriesViewer, SeriesMetadataPanel


class MolTrackMainWindow(QMainWindow):
    """Initial empty workspace for MolTrack."""

    def __init__(self, parent=None, *, series_loader=load_moltrack_image_series):
        super().__init__(parent)
        self._series = None
        self._series_loader = series_loader
        self.setWindowTitle("MolTrack")
        self.resize(1280, 860)
        self._build_actions()
        self._build_central_widget()
        self._connect_signals()
        self._update_navigation_enabled(False)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self.action_open_stm = QAction("Open STM...", self)
        self.action_open_stm.setToolTip("Load one MPP movie into MolTrack")
        self.action_open_stm_reverse = QAction("Open STM Reverse...", self)
        self.action_open_stm_reverse.setToolTip("Load one MPP movie with reversed frame order")
        file_menu.addAction(self.action_open_stm)
        file_menu.addAction(self.action_open_stm_reverse)

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

        sidebar_content = QWidget(self)
        sidebar_layout = QVBoxLayout(sidebar_content)
        self.metadata_panel = SeriesMetadataPanel(sidebar_content)
        sidebar_layout.addWidget(self.metadata_panel)
        sidebar_layout.addStretch(1)

        sidebar = QScrollArea(self)
        sidebar.setWidgetResizable(True)
        sidebar.setFrameShape(QScrollArea.Shape.NoFrame)
        sidebar.setWidget(sidebar_content)

        central.addWidget(viewer_container)
        central.addWidget(sidebar)
        central.setStretchFactor(0, 1)
        central.setStretchFactor(1, 0)
        central.setSizes([980, 300])
        self.setCentralWidget(central)

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)

    def _connect_signals(self) -> None:
        self.action_open_stm.triggered.connect(self._on_open_stm_requested)
        self.action_open_stm_reverse.triggered.connect(self._on_open_stm_reverse_requested)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)

    def set_image_series(self, series) -> None:
        self._series = series
        self._sync_navigation_controls()
        self.viewer.set_image_series(series)
        self.metadata_panel.set_image_series(series)

    def open_stm_source(self, source_path, *, reverse_frame_order: bool = False) -> None:
        series = self._series_loader(source_path, reverse_frame_order=reverse_frame_order)
        self.set_image_series(series)
        self.statusBar().showMessage(f"Loaded {series.source_path}", 3000)

    def _sync_navigation_controls(self) -> None:
        if self._series is None:
            self.lbl_frame.setText("Frame: - / -")
            self._update_navigation_enabled(False)
            return

        self._update_navigation_enabled(True)
        self.slider_frame.blockSignals(True)
        try:
            self.slider_frame.setRange(0, self._series.frame_count - 1)
            self.slider_frame.setValue(self._series.active_frame_index)
        finally:
            self.slider_frame.blockSignals(False)
        self.lbl_frame.setText(f"Frame: {self._series.active_frame_index + 1} / {self._series.frame_count}")

    def _show_current_frame(self) -> None:
        if self._series is None:
            self.viewer.clear()
            return
        self.viewer.show_frame(self._series.active_frame_index)

    def _on_frame_selected(self, frame_index: int) -> None:
        if self._series is None:
            return
        self._series.set_active_frame(int(frame_index))
        self._sync_navigation_controls()
        self._show_current_frame()
        self.metadata_panel.set_active_frame(int(frame_index))

    def _on_open_stm_requested(self) -> None:
        self._choose_and_open_stm(reverse_frame_order=False)

    def _on_open_stm_reverse_requested(self) -> None:
        self._choose_and_open_stm(reverse_frame_order=True)

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
