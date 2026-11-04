"""A raw image in pixel coordinates, with fitting, zoom and panning."""

from collections.abc import Mapping
from typing import Any
import numpy as np

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPen, QPixmap, QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsView, QLabel, QWidget,
)

from stmdomains.core.display import RenderedImage
from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.annotation_overlay import AnnotationOverlay
from stmdomains.ui.domain_overlay import DomainOverlay
from stmdomains.ui.geometry_overlay import GeometryOverlay


def image_pixmap(rendered: RenderedImage) -> QPixmap:
    pixels = rendered.rgba
    height, width = pixels.shape[:2]
    image = QImage(pixels.tobytes(), width, height, pixels.strides[0],
                   QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(image)


class ImageView(QGraphicsView):
    annotation_selected = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imageView")
        scene = QGraphicsScene(self)
        self.setScene(scene)
        self._picture = QGraphicsPixmapItem()
        scene.addItem(self._picture)
        self._field_background = QGraphicsRectItem()
        self._field_background.setBrush(QColor("#1a252c"))
        self._field_background.setPen(QPen(Qt.PenStyle.NoPen))
        self._field_background.setZValue(-1)
        scene.addItem(self._field_background)
        self._mask_clip = QGraphicsRectItem()
        self._mask_clip.setPen(QPen(Qt.PenStyle.NoPen))
        self._mask_clip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        self._mask_clip.setZValue(1)
        scene.addItem(self._mask_clip)
        self._mask_picture = QGraphicsPixmapItem(self._mask_clip)
        self._mask_picture.setOpacity(0.45)
        self._mask_picture.setVisible(False)
        self._domains = DomainOverlay()
        self._domains.setZValue(1.5)
        scene.addItem(self._domains)
        self._barrier_clip = QGraphicsRectItem()
        self._barrier_clip.setPen(QPen(Qt.PenStyle.NoPen))
        self._barrier_clip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        self._barrier_clip.setZValue(2.5)
        self._barrier_clip.setVisible(False)
        scene.addItem(self._barrier_clip)
        self._barrier_picture = QGraphicsPixmapItem(self._barrier_clip)
        self._field_border = QGraphicsRectItem()
        pen = QPen(QColor("#9bb4c5"), 1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._field_border.setPen(pen)
        self._field_border.setZValue(2)
        scene.addItem(self._field_border)
        self._overlay = AnnotationOverlay()
        self._overlay.setZValue(3)
        scene.addItem(self._overlay)
        for item in (self._picture, self._field_background, self._mask_clip,
                     self._mask_picture, self._field_border, self._barrier_clip, self._barrier_picture):
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.geometry_overlay = GeometryOverlay()
        self.geometry_overlay.setZValue(4)
        scene.addItem(self.geometry_overlay)
        self._press_position: QPoint | None = None
        self._mode = "raw"
        self._fit_mode = True
        self._message = QLabel("Otwórz projekt lub zapis MolTrack, aby przeglądać obrazy.", self.viewport())
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
        self._picture.setPixmap(image_pixmap(rendered))
        self.setSceneRect(0, 0, width, height)
        self._message.setText("Brak skończonych próbek obrazu w tej klatce.")
        self._message.setVisible(not rendered.has_data)
        if self._fit_mode or size_changed:
            self.fit_to_window()

    def set_frame(self, view: PresentedFrame) -> None:
        mode_changed = self._mode != view.mode
        self._mode = view.mode
        self.set_image(view.rendered)
        field = QRectF(*view.field_rect)
        self._field_background.setRect(field)
        self._mask_clip.setRect(field)
        self._field_border.setRect(field)
        self._field_border.setVisible(view.mode == "expanded_aligned")
        self._mask_picture.setPixmap(image_pixmap(view.masks) if view.masks is not None else QPixmap())
        self._overlay.set_frame(view)
        self.geometry_overlay.set_frame(view)
        self._domains.set_frame(view)
        self._barrier_clip.setRect(field)
        mask = view.result.barrier_mask if view.result is not None else None
        if mask is not None:
            rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
            rgba[mask] = (255, 142, 46, 180)
            self._barrier_picture.setPixmap(image_pixmap(RenderedImage(rgba, bool(mask.any()))))
            self._barrier_picture.setPos(field.topLeft())
        else:
            self._barrier_picture.setPixmap(QPixmap())
        if mode_changed:
            self.fit_to_window()

    def set_layers(self, *, centers: bool, boxes: bool, masks: bool, opacity: float) -> None:
        self._overlay.centers = centers
        self._overlay.boxes = boxes
        self._overlay.masks = masks
        self._overlay.mask_opacity = opacity
        self._mask_picture.setVisible(masks)
        self._mask_picture.setOpacity(opacity)
        self._overlay.update()

    def set_assignment_mode(self, mode: str) -> None:
        if mode not in ("domains", "classes", "input"):
            raise ValueError("Unknown assignment display mode")
        self._overlay.assignment_mode = mode
        self._overlay.update()
        self._domains.set_mode(mode)

    def set_domain_layers(self, *, fill: bool, outlines: bool, numbers: bool, opacity: float) -> None:
        self._domains.set_layers(fill=fill, outlines=outlines, numbers=numbers, opacity=opacity)

    def set_barriers_visible(self, visible: bool) -> None:
        self._barrier_clip.setVisible(visible)

    def visible_image_rect(self) -> tuple[float, float, float, float]:
        viewport = self.viewport()
        rect = self.mapToScene(viewport.rect()).boundingRect().intersected(self.sceneRect()) if viewport else self.sceneRect()
        return rect.x(), rect.y(), rect.width(), rect.height()

    def view_state(self) -> dict:
        viewport = self.viewport()
        center = self.mapToScene(viewport.rect().center()) if viewport else self.sceneRect().center()
        return {'fit': self._fit_mode, 'scale': self.transform().m11(), 'center': [center.x(), center.y()]}

    def restore_view_state(self, state: Mapping[str, Any]) -> None:
        if state['fit']:
            self.fit_to_window()
        else:
            self._fit_mode = False
            self.resetTransform()
            self.scale(state['scale'], state['scale'])
            self.centerOn(*state['center'])

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        super().mouseReleaseEvent(event)
        if event is None or event.button() != Qt.MouseButton.LeftButton:
            return
        start, self._press_position = self._press_position, None
        if start is None or (event.position().toPoint() - start).manhattanLength() > QApplication.startDragDistance():
            return
        selected = self._overlay.pick(self.mapToScene(event.position().toPoint()))
        self._overlay.selected_id = getattr(selected, "detection_id", None)
        self._overlay.update()
        self.annotation_selected.emit(selected)

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
