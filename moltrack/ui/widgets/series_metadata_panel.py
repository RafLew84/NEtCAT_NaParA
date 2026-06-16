from __future__ import annotations

import os
from typing import Any

from PyQt6.QtWidgets import QGroupBox, QLabel, QVBoxLayout


class SeriesMetadataPanel(QGroupBox):
    """Read-only metadata summary for the active MolTrack image series."""

    def __init__(self, parent=None):
        super().__init__("Metadata", parent)
        self._series = None
        self._build()
        self.clear()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.lbl_metadata = QLabel(self)
        self.lbl_metadata.setWordWrap(True)
        layout.addWidget(self.lbl_metadata)

    def clear(self) -> None:
        self._series = None
        self.lbl_metadata.setText("No series loaded")

    def set_image_series(self, series) -> None:
        self._series = series
        self._refresh()

    def set_active_frame(self, frame_index: int) -> None:
        if self._series is None:
            return
        self._series.set_active_frame(frame_index)
        self._refresh()

    def metadata_text(self) -> str:
        return self.lbl_metadata.text()

    def _refresh(self) -> None:
        if self._series is None:
            self.lbl_metadata.setText("No series loaded")
            return

        metadata = self._series.metadata
        height, width = self._series.frame_shape
        px_x, px_y = self._series.pixel_size_nm
        self.lbl_metadata.setText(
            "\n".join(
                [
                    f"Source: {os.path.basename(self._series.source_path)}",
                    f"Frames: {self._series.frame_count}",
                    f"Active frame: {self._series.active_frame_index + 1} / {self._series.frame_count}",
                    f"Shape: {width}x{height} px",
                    f"Physical size: {_format_positive_number(getattr(metadata, 'size_nm_x', None))} nm x "
                    f"{_format_positive_number(getattr(metadata, 'size_nm_y', None))} nm",
                    f"Pixel size: {_format_number(px_x)} nm/px x {_format_number(px_y)} nm/px",
                    f"Channel: {_format_text(getattr(metadata, 'image_type', None))}",
                    f"Bias: {_format_number(getattr(metadata, 'bias_v', None))} V",
                    f"Setpoint: {_format_number(getattr(metadata, 'setpoint_a', None))} A",
                    f"Scan angle: {_format_number(getattr(metadata, 'scan_angle_deg', None))} deg",
                    f"Frame interval: {_format_number(getattr(metadata, 'frame_interval_s', None))} s",
                ]
            )
        )


def _format_text(value: Any) -> str:
    if value is None:
        return "n/a"
    text = str(value).strip()
    return text or "n/a"


def _format_number(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:.6g}"


def _format_positive_number(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if number <= 0.0:
        return "n/a"
    return f"{number:.6g}"
