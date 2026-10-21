"""Image navigation and display, separate from the frame's measurement values."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPaintEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from stmviewer.frame import ImageFrame
from stmviewer.ui.raster import frame_aspect, frame_image


class ImagePreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imagePreview")
        self.setMinimumSize(240, 200)
        self.setToolTip("Kółko: zoom pod kursorem. Przeciągnij lewym przyciskiem, aby przesunąć obraz.")
        self._image: QImage | None = None
        self._aspect = 1.0
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag_position: QPointF | None = None
        self._empty = QLabel("Brak otwartego obrazu.", self)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self._empty)

    def set_frame(self, frame: ImageFrame, *, reset_view: bool = True) -> None:
        image = frame_image(frame)
        aspect = frame_aspect(frame)
        self._image = image
        self._aspect = aspect
        self._empty.hide()
        if reset_view:
            self.fit_image()
        else:
            self.update()

    def fit_image(self) -> None:
        """Restore the complete, centered image after navigation or a new import."""
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag_position = None
        if self._image is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is None:
            return
        if self._image is None:
            event.ignore()
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if not delta:
            event.ignore()
            return
        steps = max(-60.0, min(60.0, delta / 120))
        zoom = max(0.1, min(64.0, self._zoom * 1.2 ** steps))
        cursor = event.position() - QPointF(self.width() / 2, self.height() / 2)
        self._pan = cursor + (self._pan - cursor) * (zoom / self._zoom)
        self._zoom = zoom
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._image is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._drag_position is not None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._pan += event.position() - self._drag_position
                self._drag_position = event.position()
                self.update()
                event.accept()
                return
            self._drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if (event is not None and self._drag_position is not None
                and event.button() == Qt.MouseButton.LeftButton):
            # Include a final move even if the platform coalesced mouse-move events.
            self._pan += event.position() - self._drag_position
            self._drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        if self._image is None:
            return
        width = min(float(self.width()), self.height() * self._aspect) * self._zoom
        height = width / self._aspect
        target = QRectF((self.width() - width) / 2, (self.height() - height) / 2,
                        width, height)
        painter.drawImage(target.translated(self._pan), self._image)
