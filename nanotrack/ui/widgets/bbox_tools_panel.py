from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import BBoxXYXY


class BBoxToolsPanel(QWidget):
    """Sidebar tools for placing and correcting a single draft bbox per frame."""

    place_mode_toggled = pyqtSignal(bool)
    default_size_changed = pyqtSignal(int, int)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence_loaded = False
        self._processing_busy = False
        self._build()
        self._connect_signals()
        self._update_enabled_state()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("BBox Tools", self)
        group_layout = QVBoxLayout(group)

        self.lbl_hint = QLabel("Click the image to place a bbox, then drag or resize it for manual correction.", group)
        self.lbl_hint.setWordWrap(True)
        group_layout.addWidget(self.lbl_hint)

        form = QFormLayout()
        self.sp_width = QSpinBox(group)
        self.sp_width.setRange(1, 8192)
        self.sp_width.setValue(48)
        self.sp_width.setSuffix(" px")
        form.addRow("Default width", self.sp_width)

        self.sp_height = QSpinBox(group)
        self.sp_height.setRange(1, 8192)
        self.sp_height.setValue(48)
        self.sp_height.setSuffix(" px")
        form.addRow("Default height", self.sp_height)
        group_layout.addLayout(form)

        button_row = QHBoxLayout()
        self.btn_place = QPushButton("Place BBox", group)
        self.btn_place.setCheckable(True)
        self.btn_clear = QPushButton("Clear Current", group)
        button_row.addWidget(self.btn_place)
        button_row.addWidget(self.btn_clear)
        group_layout.addLayout(button_row)

        self.lbl_frame = QLabel("Frame: -", group)
        self.lbl_bbox = QLabel("No bbox on current frame", group)
        self.lbl_bbox.setWordWrap(True)
        group_layout.addWidget(self.lbl_frame)
        group_layout.addWidget(self.lbl_bbox)

        layout.addWidget(group)
        layout.addStretch(0)

    def _connect_signals(self) -> None:
        self.btn_place.toggled.connect(self.place_mode_toggled)
        self.btn_clear.clicked.connect(self.clear_requested)
        self.sp_width.valueChanged.connect(self._emit_default_size_changed)
        self.sp_height.valueChanged.connect(self._emit_default_size_changed)

    def _emit_default_size_changed(self) -> None:
        self.default_size_changed.emit(self.sp_width.value(), self.sp_height.value())

    def _update_enabled_state(self) -> None:
        enabled = self._sequence_loaded and not self._processing_busy
        self.sp_width.setEnabled(enabled)
        self.sp_height.setEnabled(enabled)
        self.btn_place.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)

    def default_size_px(self) -> tuple[int, int]:
        return self.sp_width.value(), self.sp_height.value()

    def set_place_mode_active(self, active: bool) -> None:
        blocked = self.btn_place.blockSignals(True)
        self.btn_place.setChecked(active)
        self.btn_place.blockSignals(blocked)

    def set_current_bbox(self, frame_index: int | None, bbox: BBoxXYXY | None) -> None:
        if frame_index is None:
            self.lbl_frame.setText("Frame: -")
            self.lbl_bbox.setText("No sequence loaded")
            return

        self.lbl_frame.setText(f"Frame: {frame_index + 1}")
        if bbox is None:
            self.lbl_bbox.setText("No bbox on current frame")
            return

        self.lbl_bbox.setText(
            "x0={:.1f}, y0={:.1f}, x1={:.1f}, y1={:.1f} | {:.1f}x{:.1f} px".format(
                bbox.x0,
                bbox.y0,
                bbox.x1,
                bbox.y1,
                bbox.width,
                bbox.height,
            )
        )

    def clear(self) -> None:
        self.set_place_mode_active(False)
        self.lbl_frame.setText("Frame: -")
        self.lbl_bbox.setText("No sequence loaded")

    def set_sequence_loaded(self, loaded: bool) -> None:
        self._sequence_loaded = bool(loaded)
        if not self._sequence_loaded:
            self.clear()
        else:
            self.lbl_bbox.setText("No bbox on current frame")
        self._update_enabled_state()

    def set_processing(self, busy: bool) -> None:
        self._processing_busy = bool(busy)
        self._update_enabled_state()
