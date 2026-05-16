from __future__ import annotations

import os

import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from napara.core.data_models import STMImage


class ImagePreviewWidget(QWidget):
    def __init__(self, panel_title: str = "Image", parent=None):
        super().__init__(parent)
        self._panel_title = panel_title
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_panel = QLabel(self._panel_title, self)
        self.lbl_title = QLabel("No file selected", self)
        self.lbl_meta = QLabel("-", self)
        layout.addWidget(self.lbl_panel)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_meta)

        self.viewer = pg.ImageView(self)
        self.viewer.ui.roiBtn.hide()
        self.viewer.ui.menuBtn.hide()
        self.viewer.getView().setAspectLocked(True)
        layout.addWidget(self.viewer, 1)

    def set_panel_title(self, title: str) -> None:
        self.lbl_panel.setText(title)

    def clear(self) -> None:
        self.lbl_title.setText("No file selected")
        self.lbl_meta.setText("-")
        self.viewer.getImageItem().clear()

    def view_box(self):
        return self.viewer.getView()

    def set_image(self, image: STMImage) -> None:
        arr = image.data
        self.viewer.setImage(arr, autoRange=True, autoLevels=True)

        file_name = os.path.basename(str(image.file_name))
        px_x, px_y = image.get_pixel_size_nm()
        scale_txt = (
            f"{px_x:.4g} / {px_y:.4g} nm/px"
            if px_x is not None and px_y is not None
            else "unknown"
        )
        self.lbl_title.setText(file_name)
        self.lbl_meta.setText(
            f"Shape: {arr.shape[1]}x{arr.shape[0]} px | Channel: {image.image_type} | Scale: {scale_txt}"
        )
