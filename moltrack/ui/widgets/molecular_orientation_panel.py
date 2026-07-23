"""Controls for molecular-orientation estimation and manual audit."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from moltrack.analysis import MolecularOrientationMeasurement


class MolecularOrientationPanel(QGroupBox):
    """Right-sidebar controls with no estimation logic."""

    estimate_current_requested = pyqtSignal()
    estimate_range_requested = pyqtSignal(int)
    estimate_all_requested = pyqtSignal()
    set_angle_requested = pyqtSignal(float)
    rotate_requested = pyqtSignal(float)
    reset_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Molecular Orientation", parent)
        self._measurement: MolecularOrientationMeasurement | None = None
        self._running = False
        self._frame_count = 0
        self._active_frame_index = 0
        self._current_segmentation_count = 0
        self._total_segmentation_count = 0
        self._selected_segmentation_available = False
        self._build()
        self._connect()
        self._sync_controls()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.chk_show_axes = QCheckBox("Show molecular axes", self)
        self.chk_show_axes.setChecked(True)
        layout.addWidget(self.chk_show_axes)

        self.btn_estimate_current = QPushButton("Estimate Current Frame", self)
        layout.addWidget(self.btn_estimate_current)

        self.sp_range_end_frame = QSpinBox(self)
        self.sp_range_end_frame.setPrefix("End frame ")
        layout.addWidget(self.sp_range_end_frame)
        self.btn_estimate_range = QPushButton("Estimate Frames In Range", self)
        layout.addWidget(self.btn_estimate_range)

        self.btn_estimate_all = QPushButton("Estimate All Frames", self)
        layout.addWidget(self.btn_estimate_all)

        self.lbl_result = QLabel("No orientation selected", self)
        self.lbl_result.setWordWrap(True)
        layout.addWidget(self.lbl_result)

        self.sp_manual_angle_deg = QDoubleSpinBox(self)
        self.sp_manual_angle_deg.setRange(0.0, 179.9)
        self.sp_manual_angle_deg.setDecimals(1)
        self.sp_manual_angle_deg.setSingleStep(1.0)
        self.sp_manual_angle_deg.setSuffix(" deg")
        layout.addWidget(self.sp_manual_angle_deg)
        self.btn_set_angle = QPushButton("Set Selected Angle", self)
        layout.addWidget(self.btn_set_angle)

        rotate_layout = QHBoxLayout()
        self.sp_rotate_step_deg = QDoubleSpinBox(self)
        self.sp_rotate_step_deg.setRange(0.1, 90.0)
        self.sp_rotate_step_deg.setDecimals(1)
        self.sp_rotate_step_deg.setSingleStep(1.0)
        self.sp_rotate_step_deg.setValue(5.0)
        self.sp_rotate_step_deg.setSuffix(" deg")
        rotate_layout.addWidget(self.sp_rotate_step_deg, 1)
        self.btn_rotate_negative = QPushButton("- Rotate", self)
        self.btn_rotate_negative.setToolTip(
            "Rotate the selected molecular axis counterclockwise"
        )
        rotate_layout.addWidget(self.btn_rotate_negative)
        self.btn_rotate_positive = QPushButton("+ Rotate", self)
        self.btn_rotate_positive.setToolTip(
            "Rotate the selected molecular axis clockwise"
        )
        rotate_layout.addWidget(self.btn_rotate_positive)
        layout.addLayout(rotate_layout)

        self.btn_reset = QPushButton("Reset Selected To Automatic", self)
        layout.addWidget(self.btn_reset)

    def _connect(self) -> None:
        self.btn_estimate_current.clicked.connect(
            self.estimate_current_requested
        )
        self.btn_estimate_range.clicked.connect(
            lambda: self.estimate_range_requested.emit(
                self.sp_range_end_frame.value() - 1
            )
        )
        self.btn_estimate_all.clicked.connect(self.estimate_all_requested)
        self.btn_set_angle.clicked.connect(
            lambda: self.set_angle_requested.emit(
                self.sp_manual_angle_deg.value()
            )
        )
        self.btn_rotate_negative.clicked.connect(
            lambda: self.rotate_requested.emit(
                -self.sp_rotate_step_deg.value()
            )
        )
        self.btn_rotate_positive.clicked.connect(
            lambda: self.rotate_requested.emit(
                self.sp_rotate_step_deg.value()
            )
        )
        self.btn_reset.clicked.connect(self.reset_requested)

    def set_context(
        self,
        *,
        frame_count: int,
        active_frame_index: int,
        current_segmentation_count: int,
        total_segmentation_count: int | None = None,
        selected_segmentation_available: bool = False,
        running: bool,
    ) -> None:
        self._frame_count = max(0, int(frame_count))
        self._active_frame_index = max(0, int(active_frame_index))
        self._current_segmentation_count = max(
            0,
            int(current_segmentation_count),
        )
        self._total_segmentation_count = max(
            0,
            int(
                current_segmentation_count
                if total_segmentation_count is None
                else total_segmentation_count
            ),
        )
        self._selected_segmentation_available = bool(
            selected_segmentation_available
        )
        self._running = bool(running)
        minimum_frame_number = min(
            self._frame_count,
            self._active_frame_index + 1,
        )
        self.sp_range_end_frame.blockSignals(True)
        try:
            previous = self.sp_range_end_frame.value()
            self.sp_range_end_frame.setRange(
                max(1, minimum_frame_number),
                max(1, self._frame_count),
            )
            self.sp_range_end_frame.setValue(
                max(minimum_frame_number, previous)
            )
        finally:
            self.sp_range_end_frame.blockSignals(False)
        self._sync_controls()

    def set_measurement(
        self,
        measurement: MolecularOrientationMeasurement | None,
    ) -> None:
        if measurement is not None and not isinstance(
            measurement,
            MolecularOrientationMeasurement,
        ):
            raise TypeError(
                "measurement must be a MolecularOrientationMeasurement."
            )
        self._measurement = measurement
        if measurement is None:
            self.lbl_result.setText("No orientation selected")
        else:
            angle = (
                "unavailable"
                if measurement.angle_deg is None
                else f"{measurement.angle_deg:.1f} deg"
            )
            confidence = (
                "-"
                if measurement.confidence is None
                else f"{measurement.confidence:.2f}"
            )
            details = (
                f"{angle} | confidence {confidence} | "
                f"{measurement.method} | {measurement.status}"
            )
            if measurement.manual_correction is not None:
                original = measurement.manual_correction.original_result
                original_angle = (
                    "unavailable"
                    if original.angle_deg is None
                    else f"{original.angle_deg:.1f} deg"
                )
                details += (
                    f" | automatic {original_angle} ({original.method})"
                )
            self.lbl_result.setText(details)
            if measurement.angle_deg is not None:
                self.sp_manual_angle_deg.setValue(measurement.angle_deg)
        self._sync_controls()

    def _sync_controls(self) -> None:
        has_series = self._frame_count > 0
        has_current = self._current_segmentation_count > 0
        has_any = self._total_segmentation_count > 0
        can_set = (
            self._selected_segmentation_available
            or self._measurement is not None
        ) and not self._running
        editable = self._measurement is not None and not self._running
        self.btn_estimate_current.setEnabled(
            has_series and has_current and not self._running
        )
        self.sp_range_end_frame.setEnabled(
            has_series and has_any and not self._running
        )
        self.btn_estimate_range.setEnabled(
            has_series and has_any and not self._running
        )
        self.btn_estimate_all.setEnabled(
            has_series and has_any and not self._running
        )
        self.sp_manual_angle_deg.setEnabled(can_set)
        self.btn_set_angle.setEnabled(can_set)
        self.sp_rotate_step_deg.setEnabled(editable)
        self.btn_rotate_negative.setEnabled(editable)
        self.btn_rotate_positive.setEnabled(editable)
        self.btn_reset.setEnabled(
            editable and bool(self._measurement.is_manually_corrected)
        )
