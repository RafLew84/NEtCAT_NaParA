from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from napara.gui.widgets.viewer_widget import ViewerWidget


class STMSeriesViewer(QWidget):
    """Minimal STM image-series viewer for MolTrack."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_title = QLabel("No STM series loaded", self)
        self.lbl_meta = QLabel("-", self)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_meta)

        self.viewer = ViewerWidget(self)
        layout.addWidget(self.viewer, 1)

    def clear(self) -> None:
        self._series = None
        self.lbl_title.setText("No STM series loaded")
        self.lbl_meta.setText("-")
        self.viewer.clear()

    def set_image_series(self, series) -> None:
        self._series = series
        self.show_frame(series.active_frame_index, preserve_zoom=False)

    def show_frame(self, frame_index: int, *, preserve_zoom: bool = True) -> None:
        if self._series is None:
            self.clear()
            return

        self._series.set_active_frame(frame_index)
        px_x, px_y = self._series.pixel_size_nm
        frame = self._series.active_frame
        self.viewer.set_image(
            frame,
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )

        file_name = os.path.basename(self._series.source_path)
        current = self._series.active_frame_index + 1
        total = self._series.frame_count
        self.lbl_title.setText(f"{file_name} | Frame {current}/{total}")

        image_type = getattr(self._series.metadata, "image_type", "") or "n/a"
        self.lbl_meta.setText(
            f"Shape: {frame.shape[1]}x{frame.shape[0]} px | "
            f"Channel: {image_type}"
        )
