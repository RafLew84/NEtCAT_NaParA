from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QLabel, QGroupBox, QVBoxLayout, QWidget

from nanotrack.core import STMSequence

MAX_FILENAME_DISPLAY_CHARS = 12


class SequenceMetadataPanel(QWidget):
    """Sidebar panel with sequence-level metadata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Sequence Metadata", self)
        form = QFormLayout(group)

        self.lbl_file = QLabel("-", self)
        self.lbl_frames = QLabel("-", self)
        self.lbl_shape = QLabel("-", self)
        self.lbl_size_nm = QLabel("-", self)
        self.lbl_scale_nm = QLabel("-", self)
        self.lbl_channel = QLabel("-", self)
        self.lbl_bias = QLabel("-", self)
        self.lbl_setpoint = QLabel("-", self)
        self.lbl_angle = QLabel("-", self)
        self.lbl_time = QLabel("-", self)

        form.addRow("File:", self.lbl_file)
        form.addRow("Frames:", self.lbl_frames)
        form.addRow("Shape:", self.lbl_shape)
        form.addRow("Size (nm):", self.lbl_size_nm)
        form.addRow("Scale (nm/px):", self.lbl_scale_nm)
        form.addRow("Channel:", self.lbl_channel)
        form.addRow("Bias (V):", self.lbl_bias)
        form.addRow("Setpoint (A):", self.lbl_setpoint)
        form.addRow("Angle (deg):", self.lbl_angle)
        form.addRow("Current time:", self.lbl_time)

        layout.addWidget(group)
        layout.addStretch(1)

    def clear(self) -> None:
        for label in (
            self.lbl_file,
            self.lbl_frames,
            self.lbl_shape,
            self.lbl_size_nm,
            self.lbl_scale_nm,
            self.lbl_channel,
            self.lbl_bias,
            self.lbl_setpoint,
            self.lbl_angle,
            self.lbl_time,
        ):
            label.setText("-")
        self.lbl_file.setToolTip("")

    def _format_filename(self, filename: str) -> str:
        if len(filename) <= MAX_FILENAME_DISPLAY_CHARS:
            return filename
        return f"{filename[:MAX_FILENAME_DISPLAY_CHARS]}..."

    def set_sequence(self, sequence: STMSequence | None) -> None:
        if sequence is None:
            self.clear()
            return

        px_x, px_y = sequence.metadata.get_pixel_size_nm()
        time_s = sequence.active_frame_time_s

        self.lbl_file.setText(self._format_filename(sequence.file_name))
        self.lbl_file.setToolTip(sequence.file_name)
        self.lbl_frames.setText(str(sequence.frame_count))
        self.lbl_shape.setText(f"{sequence.frame_shape[1]} x {sequence.frame_shape[0]} px")
        self.lbl_size_nm.setText(
            f"{sequence.metadata.size_nm_x:.4g} x {sequence.metadata.size_nm_y:.4g}"
            if sequence.metadata.size_nm_x > 0 and sequence.metadata.size_nm_y > 0
            else "-"
        )
        self.lbl_scale_nm.setText(
            f"{px_x:.4g} / {px_y:.4g}" if px_x is not None and px_y is not None else "-"
        )
        self.lbl_channel.setText(sequence.metadata.image_type or "-")
        self.lbl_bias.setText(f"{sequence.metadata.bias_v:.4g}" if sequence.metadata.bias_v else "0")
        self.lbl_setpoint.setText(
            f"{sequence.metadata.setpoint_a:.4g}" if sequence.metadata.setpoint_a is not None else "-"
        )
        self.lbl_angle.setText(f"{sequence.metadata.scan_angle_deg:.4g}")
        self.lbl_time.setText(f"{time_s:.4g} s" if time_s is not None else "-")
