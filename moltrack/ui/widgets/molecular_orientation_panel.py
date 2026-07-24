"""Controls for molecular-orientation estimation and manual audit."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from moltrack.analysis import (
    MolecularOrientationMeasurement,
    MolecularStackingInspection,
)


class MolecularOrientationPanel(QGroupBox):
    """Right-sidebar controls with no estimation logic."""

    estimate_current_requested = pyqtSignal()
    estimate_range_requested = pyqtSignal(int)
    estimate_all_requested = pyqtSignal()
    set_angle_requested = pyqtSignal(float)
    rotate_requested = pyqtSignal(float)
    reset_requested = pyqtSignal()
    analyze_stacking_requested = pyqtSignal()
    orientation_view_changed = pyqtSignal()
    ab_states_view_changed = pyqtSignal()
    stacking_subdomains_view_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Molecular Orientation", parent)
        self._measurement: MolecularOrientationMeasurement | None = None
        self._running = False
        self._frame_count = 0
        self._active_frame_index = 0
        self._current_segmentation_count = 0
        self._total_segmentation_count = 0
        self._selected_segmentation_available = False
        self._stacking_can_analyze = False
        self._stacking_computed = False
        self._stacking_running = False
        self._stacking_inspection: MolecularStackingInspection | None = None
        self._build()
        self._connect()
        self._sync_controls()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.chk_show_axes = QCheckBox("Molecular orientation", self)
        self.chk_show_axes.setChecked(True)
        self.slider_orientation_opacity = self._overlay_row(
            layout,
            self.chk_show_axes,
            value=85,
        )

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

        stacking_title = QLabel("Stacking", self)
        font = stacking_title.font()
        font.setBold(True)
        stacking_title.setFont(font)
        layout.addWidget(stacking_title)

        self.chk_show_ab_states = QCheckBox("AB states", self)
        self.chk_show_ab_states.setChecked(True)
        self.slider_ab_states_opacity = self._overlay_row(
            layout,
            self.chk_show_ab_states,
            value=70,
        )

        self.chk_show_stacking_subdomains = QCheckBox(
            "Stacking subdomains",
            self,
        )
        self.chk_show_stacking_subdomains.setChecked(True)
        self.slider_stacking_subdomains_opacity = self._overlay_row(
            layout,
            self.chk_show_stacking_subdomains,
            value=30,
        )

        self.btn_analyze_stacking = QPushButton("Analyze Stacking", self)
        layout.addWidget(self.btn_analyze_stacking)
        self.lbl_stacking_status = QLabel("Stacking not computed", self)
        self.lbl_stacking_status.setWordWrap(True)
        layout.addWidget(self.lbl_stacking_status)
        self.lbl_stacking_selection = QLabel(
            "No stacking selection",
            self,
        )
        self.lbl_stacking_selection.setWordWrap(True)
        self.lbl_stacking_selection.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.lbl_stacking_selection)

    def _overlay_row(
        self,
        layout: QVBoxLayout,
        checkbox: QCheckBox,
        *,
        value: int,
    ) -> QSlider:
        row = QHBoxLayout()
        row.addWidget(checkbox)
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setRange(0, 100)
        slider.setValue(int(value))
        slider.setToolTip(f"{checkbox.text()} opacity")
        row.addWidget(slider, 1)
        layout.addLayout(row)
        return slider

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
        self.btn_analyze_stacking.clicked.connect(
            self.analyze_stacking_requested
        )
        self.chk_show_axes.toggled.connect(
            self.orientation_view_changed
        )
        self.slider_orientation_opacity.valueChanged.connect(
            self.orientation_view_changed
        )
        self.chk_show_ab_states.toggled.connect(
            self.ab_states_view_changed
        )
        self.slider_ab_states_opacity.valueChanged.connect(
            self.ab_states_view_changed
        )
        self.chk_show_stacking_subdomains.toggled.connect(
            self.stacking_subdomains_view_changed
        )
        self.slider_stacking_subdomains_opacity.valueChanged.connect(
            self.stacking_subdomains_view_changed
        )

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

    def set_stacking_context(
        self,
        *,
        can_analyze: bool,
        computed: bool,
        running: bool,
        status_text: str,
    ) -> None:
        self._stacking_can_analyze = bool(can_analyze)
        self._stacking_computed = bool(computed)
        self._stacking_running = bool(running)
        self.lbl_stacking_status.setText(str(status_text))
        if not self._stacking_computed:
            self.set_stacking_inspection(None)
        self._sync_controls()

    def set_stacking_inspection(
        self,
        inspection: MolecularStackingInspection | None,
    ) -> None:
        if inspection is not None and not isinstance(
            inspection,
            MolecularStackingInspection,
        ):
            raise TypeError(
                "inspection must be MolecularStackingInspection or None."
            )
        self._stacking_inspection = inspection
        self.lbl_stacking_selection.setText(
            "No stacking selection"
            if inspection is None
            else _format_stacking_inspection(inspection)
        )

    def orientation_overlay_visible(self) -> bool:
        return self.chk_show_axes.isChecked()

    def orientation_opacity_percent(self) -> int:
        return self.slider_orientation_opacity.value()

    def ab_states_overlay_visible(self) -> bool:
        return self.chk_show_ab_states.isChecked()

    def ab_states_opacity_percent(self) -> int:
        return self.slider_ab_states_opacity.value()

    def stacking_subdomains_overlay_visible(self) -> bool:
        return self.chk_show_stacking_subdomains.isChecked()

    def stacking_subdomains_opacity_percent(self) -> int:
        return self.slider_stacking_subdomains_opacity.value()

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
        stacking_busy = self._running or self._stacking_running
        self.btn_analyze_stacking.setEnabled(
            self._stacking_can_analyze and not stacking_busy
        )
        self.btn_analyze_stacking.setText(
            "Analyzing Stacking..."
            if self._stacking_running
            else "Analyze Stacking"
        )
        self.chk_show_axes.setEnabled(has_series)
        self.slider_orientation_opacity.setEnabled(has_series)
        for control in (
            self.chk_show_ab_states,
            self.slider_ab_states_opacity,
            self.chk_show_stacking_subdomains,
            self.slider_stacking_subdomains_opacity,
        ):
            control.setEnabled(self._stacking_computed)


def _format_stacking_inspection(
    inspection: MolecularStackingInspection,
) -> str:
    state = inspection.state_label or "n/a"
    axis = (
        "n/a"
        if inspection.axis_angle_deg is None
        else (
            f"{inspection.axis_angle_deg:.1f} deg "
            f"(candidate {inspection.axis_candidate_index})"
        )
    )
    prototypes = (
        "n/a"
        if inspection.prototype_a_angle_deg is None
        else (
            f"A {inspection.prototype_a_angle_deg:.1f} deg"
            + (
                ""
                if inspection.prototype_b_angle_deg is None
                else f", B {inspection.prototype_b_angle_deg:.1f} deg"
            )
        )
    )
    parent_score = (
        "n/a"
        if inspection.parent_score is None
        else f"{inspection.parent_score:.3f}"
    )
    parent_qc = ", ".join(inspection.parent_qc_reasons) or "OK"
    score = (
        "n/a"
        if inspection.score is None
        else f"{inspection.score:.3f}"
    )
    qc = ", ".join(inspection.qc_reasons) or "OK"
    mode_phase = "/".join(
        value
        for value in (inspection.mode, inspection.phase)
        if value is not None
    ) or "n/a"
    lines = [
        (
            f"Parent: {inspection.parent_lattice_domain_id} | "
            f"{inspection.parent_pattern}"
        ),
        (
            f"Parent score: {parent_score} | confidence "
            f"{inspection.parent_confidence:.3f} | coverage "
            f"{inspection.parent_coverage_fraction:.3f}"
        ),
        f"Parent QC: {parent_qc}",
        (
            "Subdomain: n/a"
            if inspection.subdomain_id is None
            else (
                f"Subdomain: {inspection.subdomain_id} | "
                f"{inspection.pattern} | {mode_phase}"
            )
        ),
        f"A/B state: {state}",
        f"Row axis: {axis}",
        f"Prototypes: {prototypes}",
    ]
    if inspection.subdomain_id is not None:
        lines.extend(
            (
                (
                    f"Subdomain score: {score} | confidence "
                    f"{inspection.confidence:.3f} | coverage "
                    f"{inspection.coverage_fraction:.3f}"
                ),
                f"Subdomain QC: {qc}",
            )
        )
    return "\n".join(lines)
