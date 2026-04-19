from __future__ import annotations

import os

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from nanotrack.core import STMSequence
from napara.gui.widgets.viewer_widget import ViewerWidget


class SequenceViewerWidget(QWidget):
    """Main frame viewer for NanoTrack sequences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_title = QLabel("No sequence loaded", self)
        self.lbl_meta = QLabel("-", self)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_meta)

        self.viewer = ViewerWidget(self)
        layout.addWidget(self.viewer, 1)

    def clear(self) -> None:
        self._sequence = None
        self.lbl_title.setText("No sequence loaded")
        self.lbl_meta.setText("-")
        self.viewer.clear()

    def set_sequence(self, sequence: STMSequence) -> None:
        self._sequence = sequence
        self.show_frame(sequence.active_frame_index, preserve_zoom=False)

    def show_frame(self, frame_index: int, preserve_zoom: bool = True) -> None:
        if self._sequence is None:
            self.clear()
            return

        self._sequence.set_active_frame(frame_index)
        frame = self._sequence.active_frame
        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        self.viewer.set_image(
            frame,
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )

        file_name = os.path.basename(self._sequence.source_path)
        current = self._sequence.active_frame_index + 1
        total = self._sequence.frame_count
        self.lbl_title.setText(f"{file_name} | Frame {current}/{total}")

        time_s = self._sequence.active_frame_time_s
        if time_s is None:
            time_txt = "n/a"
        else:
            time_txt = f"{time_s:.4g} s"

        self.lbl_meta.setText(
            f"Shape: {frame.shape[1]}x{frame.shape[0]} px | "
            f"Channel: {self._sequence.metadata.image_type} | "
            f"Time: {time_txt}"
        )
