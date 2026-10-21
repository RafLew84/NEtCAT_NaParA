"""Fitted preview. Rendering never changes the frame's measurement values."""

import numpy as np
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QImage, QPaintEvent, QPainter
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from stmviewer.frame import ImageFrame


class ImagePreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imagePreview")
        self.setMinimumSize(240, 200)
        self._image: QImage | None = None
        self._aspect = 1.0
        self._empty = QLabel("Brak otwartego obrazu.", self)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self._empty)

    def set_frame(self, frame: ImageFrame) -> None:
        data = frame.data
        finite = np.isfinite(data)
        raster = np.zeros(data.shape, dtype=np.uint8)
        if finite.any():
            values = data[finite]
            low, high = float(values.min()), float(values.max())
            if low == high:
                raster[finite] = 127
            else:
                # Scaling first also handles opposite finite float64 extremes.
                scale = max(abs(low), abs(high))
                values = (values / scale - low / scale) / (high / scale - low / scale)
                raster[finite] = np.clip(values * 255, 0, 255).astype(np.uint8)
        height, width = raster.shape
        image = QImage(raster.tobytes(), width, height, raster.strides[0],
                       QImage.Format.Format_Grayscale8).copy()
        aspect = width / height
        if frame.size_x_nm is not None and frame.size_y_nm is not None:
            aspect = frame.size_x_nm / frame.size_y_nm
        self._image = image
        self._aspect = aspect
        self._empty.hide()
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        if self._image is None:
            return
        width = min(float(self.width()), self.height() * self._aspect)
        height = width / self._aspect
        target = QRectF((self.width() - width) / 2, (self.height() - height) / 2,
                        width, height)
        painter.drawImage(target, self._image)
