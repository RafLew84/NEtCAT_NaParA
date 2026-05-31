from __future__ import annotations

from pathlib import Path
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QLabel, QMainWindow, QMessageBox, QSlider, QVBoxLayout, QWidget

from moltrack.core import MolTrackProject
from moltrack.io import import_image_series
from moltrack.persistence import load_project, save_project
from napara.gui.widgets.viewer_widget import ViewerWidget


class MolTrackWorkspace(QMainWindow):
    """Top-level MolTrack workspace window."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("moltrack-workspace")
        self.setWindowTitle("MolTrack Workspace")
        self._project: MolTrackProject | None = None
        self._project_path: Path | None = None
        self._active_working_frame_index = 0
        self._displayed_frame: np.ndarray | None = None
        self._build_menu()

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.lbl_title = QLabel("MolTrack Workspace", central)
        self.lbl_frame_index = QLabel("No project loaded", central)
        self.lbl_frame_index.setObjectName("moltrack-frame-index-label")

        self.viewer = ViewerWidget(central)

        self.frame_slider = QSlider(Qt.Orientation.Horizontal, central)
        self.frame_slider.setObjectName("moltrack-frame-slider")
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self.set_active_working_frame_index)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_frame_index)
        layout.addWidget(self.viewer, 1)
        layout.addWidget(self.frame_slider)
        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        self.import_image_series_action = QAction("Import Image Series...", self)
        self.import_image_series_action.triggered.connect(self._on_import_image_series)
        file_menu.addAction(self.import_image_series_action)

        self.import_reversed_order_action = QAction("Import Reversed Order", self)
        self.import_reversed_order_action.setCheckable(True)
        file_menu.addAction(self.import_reversed_order_action)

        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self._on_open_project)
        file_menu.addAction(self.open_project_action)

        self.save_project_action = QAction("Save Project", self)
        self.save_project_action.triggered.connect(self._on_save_project)
        file_menu.addAction(self.save_project_action)

        self.save_project_as_action = QAction("Save Project As...", self)
        self.save_project_as_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(self.save_project_as_action)

    def set_project(self, project: MolTrackProject) -> None:
        self._project = project
        frame_count = project.working_series.frame_count
        self.frame_slider.setEnabled(frame_count > 1)
        self.frame_slider.setRange(0, frame_count - 1)
        self.set_active_working_frame_index(0)

    def set_active_working_frame_index(self, working_frame_index: int) -> None:
        if self._project is None:
            return
        working_frame_index = int(working_frame_index)
        working_frame = self._project.working_series.get_working_frame(working_frame_index)

        self._active_working_frame_index = working_frame_index
        if self.frame_slider.value() != working_frame_index:
            self.frame_slider.setValue(working_frame_index)

        if self._project.source_series.raw_frames is None:
            self._displayed_frame = None
            self.viewer.clear()
            suffix = " | Images not loaded"
        else:
            frame = self._project.source_series.get_frame(working_frame.source_frame_index)
            self._displayed_frame = np.asarray(frame)
            self.viewer.set_image(
                self._displayed_frame,
                scale_nm_per_px=(None, None),
                preserve_zoom=True,
                auto_levels=True,
            )
            suffix = ""
        self.lbl_frame_index.setText(
            f"Working {working_frame_index + 1}/{self._project.working_series.frame_count} | "
            f"Source {working_frame.source_frame_index + 1}/{self._project.source_series.frame_count}"
            f"{suffix}"
        )

    def active_working_frame_index(self) -> int:
        return self._active_working_frame_index

    def active_source_frame_index(self) -> int:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        return self._project.working_series.get_source_frame_index(self._active_working_frame_index)

    def displayed_frame(self) -> np.ndarray:
        if self._displayed_frame is None:
            raise ValueError("No frame is displayed.")
        return self._displayed_frame

    def frame_index_text(self) -> str:
        return self.lbl_frame_index.text()

    def current_project(self) -> MolTrackProject | None:
        return self._project

    def current_project_path(self):
        return self._project_path

    def save_project_to(self, path) -> None:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        save_project(path, self._project)
        self._project_path = Path(path)

    def save_project(self) -> None:
        if self._project_path is None:
            self._on_save_project_as()
            return
        self.save_project_to(self._project_path)

    def open_project_file(self, path) -> None:
        project = load_project(path)
        self._project_path = Path(path)
        self.set_project(project)

    def import_image_series_from(self, source_paths, *, reverse_frame_order: bool = False) -> None:
        project = import_image_series(source_paths, reverse_frame_order=reverse_frame_order)
        self._project_path = None
        self.set_project(project)

    def _on_import_image_series(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Import Image Series",
            "",
            "STM Image Series (*.mpp *.stp *.s94);;MPP Movies (*.mpp);;Frame Series (*.stp *.s94);;All Files (*)",
        )
        if not paths:
            return
        source_paths = paths[0] if len(paths) == 1 else paths
        try:
            self.import_image_series_from(
                source_paths,
                reverse_frame_order=self.import_reversed_order_action.isChecked(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import image series failed", str(exc))

    def _on_open_project(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open MolTrack Project",
            "",
            "MolTrack Projects (*.moltrack);;All Files (*)",
        )
        if path:
            try:
                self.open_project_file(path)
            except Exception as exc:
                QMessageBox.critical(self, "Open project failed", str(exc))

    def _on_save_project(self) -> None:
        try:
            self.save_project()
        except Exception as exc:
            QMessageBox.critical(self, "Save project failed", str(exc))

    def _on_save_project_as(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save MolTrack Project",
            "",
            "MolTrack Projects (*.moltrack);;All Files (*)",
        )
        if path:
            try:
                self.save_project_to(path)
            except Exception as exc:
                QMessageBox.critical(self, "Save project failed", str(exc))
