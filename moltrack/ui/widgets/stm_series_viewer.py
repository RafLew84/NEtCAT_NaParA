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
        file_name = os.path.basename(self._series.source_path)
        current = self._series.active_frame_index + 1
        total = self._series.frame_count
        image_type = getattr(self._series.metadata, "image_type", "") or "n/a"
        self.show_image(
            frame,
            title=f"{file_name} | Frame {current}/{total}",
            meta=f"Shape: {frame.shape[1]}x{frame.shape[0]} px | Channel: {image_type}",
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
        )

    def show_expanded_aligned_frame(self, series, expanded_stack, frame_index: int, *, preserve_zoom: bool = True) -> None:
        self._series = series
        self._series.set_active_frame(frame_index)
        metadata = getattr(expanded_stack, "metadata", self._series.metadata)
        get_pixel_size = getattr(metadata, "get_pixel_size_nm", None)
        px_x, px_y = get_pixel_size() if callable(get_pixel_size) else self._series.pixel_size_nm
        frame = expanded_stack.frames[self._series.active_frame_index]
        file_name = os.path.basename(self._series.source_path)
        current = self._series.active_frame_index + 1
        total = self._series.frame_count
        left, top, right, bottom = expanded_stack.padding_ltrb
        self.show_image(
            frame,
            title=f"{file_name} | Expanded aligned frame {current}/{total}",
            meta=(
                f"Shape: {frame.shape[1]}x{frame.shape[0]} px | "
                f"Padding: {left},{top},{right},{bottom} px"
            ),
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
        )

    def show_image(
        self,
        frame,
        *,
        title: str,
        meta: str,
        scale_nm_per_px: tuple[float | None, float | None],
        preserve_zoom: bool = True,
    ) -> None:
        self.viewer.set_image(
            frame,
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )
        self.lbl_title.setText(str(title))
        self.lbl_meta.setText(str(meta))
