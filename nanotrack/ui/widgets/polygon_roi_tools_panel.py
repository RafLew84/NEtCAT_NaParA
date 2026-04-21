from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import PolygonROI


class PolygonRoiToolsPanel(QWidget):
    """Sidebar tools for drawing and editing a polygon ROI per frame."""

    draw_mode_toggled = pyqtSignal(bool)
    finish_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    preview_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence_loaded = False
        self._processing_busy = False
        self._draw_mode_active = False
        self._has_polygon = False
        self._build()
        self._connect_signals()
        self._update_enabled_state()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Polygon ROI Tools", self)
        group_layout = QVBoxLayout(group)

        self.lbl_hint = QLabel(
            "Click successive vertices on the image, then use Finish Polygon to close the ROI. "
            "After finishing, drag the vertex handles to edit the polygon.",
            group,
        )
        self.lbl_hint.setWordWrap(True)
        group_layout.addWidget(self.lbl_hint)

        button_row = QHBoxLayout()
        self.btn_draw = QPushButton("Draw Polygon ROI", group)
        self.btn_draw.setCheckable(True)
        self.btn_finish = QPushButton("Finish Polygon", group)
        self.btn_clear = QPushButton("Clear Current", group)
        self.btn_preview = QPushButton("Preview Edge Detection", group)
        button_row.addWidget(self.btn_draw)
        button_row.addWidget(self.btn_finish)
        button_row.addWidget(self.btn_clear)
        button_row.addWidget(self.btn_preview)
        group_layout.addLayout(button_row)

        self.lbl_frame = QLabel("Frame: -", group)
        self.lbl_polygon = QLabel("No polygon ROI on current frame", group)
        self.lbl_polygon.setWordWrap(True)
        group_layout.addWidget(self.lbl_frame)
        group_layout.addWidget(self.lbl_polygon)

        layout.addWidget(group)
        layout.addStretch(0)

    def _connect_signals(self) -> None:
        self.btn_draw.toggled.connect(self.draw_mode_toggled)
        self.btn_finish.clicked.connect(self.finish_requested)
        self.btn_clear.clicked.connect(self.clear_requested)
        self.btn_preview.clicked.connect(self.preview_requested)

    def _update_enabled_state(self) -> None:
        enabled = self._sequence_loaded and not self._processing_busy
        self.btn_draw.setEnabled(enabled)
        self.btn_finish.setEnabled(enabled and self._draw_mode_active)
        self.btn_clear.setEnabled(enabled and (self._draw_mode_active or self._has_polygon))
        self.btn_preview.setEnabled(enabled and self._has_polygon and not self._draw_mode_active)

    def set_draw_mode_active(self, active: bool) -> None:
        self._draw_mode_active = bool(active)
        blocked = self.btn_draw.blockSignals(True)
        self.btn_draw.setChecked(self._draw_mode_active)
        self.btn_draw.blockSignals(blocked)
        self._update_enabled_state()

    def set_current_polygon(self, frame_index: int | None, polygon: PolygonROI | None) -> None:
        if frame_index is None:
            self.lbl_frame.setText("Frame: -")
            self.lbl_polygon.setText("No sequence loaded")
            self._has_polygon = False
            self._update_enabled_state()
            return

        self.lbl_frame.setText(f"Frame: {frame_index + 1}")
        if polygon is None:
            self.lbl_polygon.setText("No polygon ROI on current frame")
            self._has_polygon = False
            self._update_enabled_state()
            return

        x0, y0, x1, y1 = polygon.bounds_xyxy
        self.lbl_polygon.setText(
            "Vertices: {} | bounds x=[{:.1f}, {:.1f}], y=[{:.1f}, {:.1f}]".format(
                polygon.vertex_count,
                x0,
                x1,
                y0,
                y1,
            )
        )
        self._has_polygon = True
        self._update_enabled_state()

    def clear(self) -> None:
        self.set_draw_mode_active(False)
        self.lbl_frame.setText("Frame: -")
        self.lbl_polygon.setText("No sequence loaded")
        self._has_polygon = False
        self._update_enabled_state()

    def set_sequence_loaded(self, loaded: bool) -> None:
        self._sequence_loaded = bool(loaded)
        if not self._sequence_loaded:
            self.clear()
        else:
            self.lbl_polygon.setText("No polygon ROI on current frame")
            self._has_polygon = False
        self._update_enabled_state()

    def set_processing(self, busy: bool) -> None:
        self._processing_busy = bool(busy)
        self._update_enabled_state()
