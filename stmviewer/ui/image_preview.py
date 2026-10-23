"""Image navigation and display, separate from the frame's measurement values."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPaintEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from stmviewer.frame import ImageFrame
from stmviewer.ui.raster import draw_frame, frame_aspect, frame_image


class ImagePreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imagePreview")
        self.setMinimumSize(240, 200)
        self.setToolTip("Kółko: zoom pod kursorem. Przeciągnij lewym przyciskiem, aby przesunąć obraz.")
        self._frame: ImageFrame | None = None
        self._gamma = 1.0
        self._pixel_proportions = False
        self._image: QImage | None = None
        self._aspect = 1.0
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag_position: QPointF | None = None
        self._empty = QLabel("Brak otwartego obrazu.", self)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self._empty)

    def set_frame(self, frame: ImageFrame, *, reset_view: bool = True,
                  reset_settings: bool = False) -> None:
        gamma = 1.0 if reset_settings else self._gamma
        image = frame_image(frame, gamma=gamma)
        pixels = False if reset_settings else self._pixel_proportions
        aspect = frame_aspect(frame, pixel_proportions=pixels)
        self._gamma = gamma
        self._pixel_proportions = pixels
        self._frame = frame
        self._image = image
        self._aspect = aspect
        self._empty.hide()
        if reset_view:
            self.fit_image()
        else:
            self.update()

    def clear_frame(self) -> None:
        """Release the last measurement and return to the empty preview."""
        self._frame = None
        self._image = None
        self._aspect = 1.0
        self.fit_image()
        self.unsetCursor()
        self._empty.show()

    def set_pixel_proportions(self, enabled: bool) -> None:
        """Ignore header scale in the view while retaining all source metadata."""
        if self._frame is not None:
            self._aspect = frame_aspect(self._frame, pixel_proportions=enabled)
        self._pixel_proportions = enabled
        self.update()

    def set_gamma(self, gamma: float) -> None:
        """Change display brightness without modifying measurement values or geometry."""
        if not 0.1 <= gamma <= 4.0:
            raise ValueError("Gamma musi mieścić się w zakresie 0,1–4.")
        if self._frame is not None:
            self._image = frame_image(self._frame, gamma=gamma)
        self._gamma = gamma
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
        self._zoom_at(1.2 ** steps, event.position())
        event.accept()

    def zoom_in(self) -> None:
        self._zoom_at(1.2, QPointF(self.width() / 2, self.height() / 2))

    def zoom_out(self) -> None:
        self._zoom_at(1 / 1.2, QPointF(self.width() / 2, self.height() / 2))

    def _zoom_at(self, factor: float, position: QPointF) -> None:
        if self._image is None:
            return
        zoom = max(0.1, min(64.0, self._zoom * factor))
        cursor = position - QPointF(self.width() / 2, self.height() / 2)
        self._pan = cursor + (self._pan - cursor) * (zoom / self._zoom)
        self._zoom = zoom
        self.update()

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
        draw_frame(painter, target.translated(self._pan), self._image)
