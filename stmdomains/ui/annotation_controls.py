"""View and overlay choices; rendering stays in the image view."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QSlider, QWidget


class AnnotationControls(QWidget):
    layers_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Widok:"))
        self.view_mode = QComboBox()
        self.view_mode.addItem("Oryginał", "raw")
        self.view_mode.addItem("Wyrównany", "expanded_aligned")
        self.view_mode.setEnabled(False)
        row.addWidget(self.view_mode)
        self.centers = QCheckBox("Centra")
        self.boxes = QCheckBox("Ramki")
        self.masks = QCheckBox("Maski / obrysy")
        self.centers.setChecked(True)
        for control in (self.centers, self.boxes, self.masks):
            control.setEnabled(False)
            control.toggled.connect(self.layers_changed)
            row.addWidget(control)
        row.addStretch()
        row.addWidget(QLabel("Krycie masek:"))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(45)
        self.opacity.setMaximumWidth(140)
        self.opacity.setAccessibleName("Krycie masek")
        self.opacity.setEnabled(False)
        self.opacity_label = QLabel("45%")
        self.opacity.valueChanged.connect(lambda value: self.opacity_label.setText(f"{value}%"))
        self.opacity.valueChanged.connect(self.layers_changed)
        row.addWidget(self.opacity)
        row.addWidget(self.opacity_label)

    def set_availability(
        self, *, aligned: bool, detections: bool, boxes: bool, segmentations: bool,
    ) -> None:
        self.view_mode.setEnabled(aligned)
        self.centers.setEnabled(detections)
        self.boxes.setEnabled(boxes)
        self.masks.setEnabled(segmentations)
        self.opacity.setEnabled(segmentations)
