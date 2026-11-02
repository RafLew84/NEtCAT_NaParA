"""A raw image in pixel coordinates, with fitting, zoom and panning."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QLabel, QWidget

from stmdomains.core.display import RenderedImage


class ImageView(QGraphicsView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imageView")
        scene = QGraphicsScene(self)
        self.setScene(scene)
        self._picture = QGraphicsPixmapItem()
        scene.addItem(self._picture)
        self._fit_mode = True
        self._message = QLabel("Otwórz zapis MolTrack, aby przeglądać obrazy.", self.viewport())
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._message.setStyleSheet("color: white; background: transparent; padding: 20px;")
        self._message.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def set_image(self, rendered: RenderedImage) -> None:
        pixels = rendered.rgba
        height, width = pixels.shape[:2]
        previous = self._picture.pixmap().size()
        size_changed = previous.width() != width or previous.height() != height
        image = QImage(pixels.tobytes(), width, height, pixels.strides[0],
                       QImage.Format.Format_RGBA8888).copy()
        self._picture.setPixmap(QPixmap.fromImage(image))
        self.setSceneRect(0, 0, width, height)
        self._message.setText("Brak skończonych próbek obrazu w tej klatce.")
        self._message.setVisible(not rendered.has_data)
        if self._fit_mode or size_changed:
            self.fit_to_window()

    def fit_to_window(self) -> None:
        self._fit_mode = True
        if not self._picture.pixmap().isNull():
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_by(self, factor: float) -> None:
        if self._picture.pixmap().isNull():
            return
        resulting_scale = self.transform().m11() * factor
        if 0.0001 <= resulting_scale <= 256:
            self._fit_mode = False
            self.scale(factor, factor)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is not None:
            self.zoom_by(1.2 ** (event.angleDelta().y() / 120))
            event.accept()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        viewport = self.viewport()
        if viewport is not None:
            self._message.setGeometry(viewport.rect())
        if self._fit_mode:
            self.fit_to_window()
