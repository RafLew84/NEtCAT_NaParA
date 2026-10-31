"""Original-image mask drawing, with navigation shared by ordinary previews."""

import math
from typing import Literal

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPaintEvent, QPainter, QPen, QWheelEvent

from PyQt6.QtWidgets import QWidget

from stmviewer.frame import ImageFrame
from stmviewer.registration_masks import FrameMask, MaskRectangle
from stmviewer.ui.image_preview import ImagePreview


class MaskPreview(ImagePreview):
    rectangle_created = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('maskPreview')
        self._original: ImageFrame | None = None
        self._definition = FrameMask()
        self._mask_image: QImage | None = None
        self._overlay_visible = True
        self._mode: Literal['pan', 'use', 'omit'] = 'pan'
        self._editing_enabled = True
        self._start: QPointF | None = None
        self._end: QPointF | None = None
        self._selected = -1

    def set_original(self, frame: ImageFrame, mask: FrameMask, *, reset_view: bool = False) -> None:
        self._start = self._end = None
        self._original = frame
        self.set_frame(frame, reset_view=reset_view)
        self.set_definition(mask)
        self._update_cursor()

    def set_definition(self, mask: FrameMask) -> None:
        self._definition = mask
        if self._original is not None:
            valid = mask.raster(self._original.data)
            rgba = np.empty((*valid.shape, 4), dtype=np.uint8)
            rgba[:] = (220, 45, 45, 90)
            rgba[valid] = (30, 210, 80, 45)
            height, width = valid.shape
            self._mask_image = QImage(rgba.tobytes(), width, height, rgba.strides[0],
                                     QImage.Format.Format_RGBA8888).copy()
        self.update()

    def set_overlay_visible(self, visible: bool) -> None:
        self._overlay_visible = visible
        self.update()

    def set_selected(self, index: int) -> None:
        self._selected = index
        self.update()

    def set_mode(self, mode: Literal['pan', 'use', 'omit']) -> None:
        if mode not in ('pan', 'use', 'omit'):
            raise ValueError('Nieznany tryb edycji maski.')
        self._mode = mode
        self._start = self._end = None
        self._update_cursor()
        self.update()

    def set_editing_enabled(self, enabled: bool) -> None:
        self._editing_enabled = enabled
        self._start = self._end = None
        self._update_cursor()
        self.update()

    def _update_cursor(self) -> None:
        drawing = self._editing_enabled and self._mode != 'pan'
        self.setCursor(Qt.CursorShape.CrossCursor if drawing else Qt.CursorShape.OpenHandCursor)
        self.setToolTip('Przeciągnij, aby dodać prostokąt w pikselach original. Kółko: zoom.'
                        if drawing else 'Przeciągnij, aby przesunąć podgląd. Kółko: zoom.')

    def _point(self, position: QPointF, *, clip: bool) -> QPointF | None:
        rect = self.image_rect()
        if rect is None or self._original is None:
            return None
        if not clip and not rect.contains(position):
            return None
        height, width = self._original.data.shape
        x = (position.x() - rect.x()) * width / rect.width()
        y = (position.y() - rect.y()) * height / rect.height()
        return QPointF(min(width, max(0, x)), min(height, max(0, y)))

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if (event is not None and self._editing_enabled and self._mode != 'pan'
                and event.button() == Qt.MouseButton.LeftButton):
            self._start = self._point(event.position(), clip=False)
            self._end = self._start
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._start is not None:
            self._end = self._point(event.position(), clip=True)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            start, end = self._start, self._point(event.position(), clip=True)
            self._start = self._end = None
            if (end is not None and self._original is not None and self._mode != 'pan'
                    and end.x() != start.x() and end.y() != start.y()):
                x0, y0 = math.floor(min(start.x(), end.x())), math.floor(min(start.y(), end.y()))
                x1, y1 = math.ceil(max(start.x(), end.x())), math.ceil(max(start.y(), end.y()))
                if x1 > x0 and y1 > y0:
                    self.rectangle_created.emit(MaskRectangle(x0, y0, x1, y1, self._mode))
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def fit_image(self) -> None:
        self._start = self._end = None
        super().fit_image()
        self._update_cursor()

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        self._start = self._end = None
        super().wheelEvent(event)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        target = self.image_rect()
        if target is None or self._original is None:
            return
        painter = QPainter(self)
        painter.setClipRect(self.rect())
        if self._overlay_visible and self._mask_image is not None:
            painter.drawImage(target, self._mask_image)
        height, width = self._original.data.shape
        sx, sy = target.width() / width, target.height() / height
        for index, rectangle in enumerate(self._definition.rectangles):
            color = QColor(255, 220, 0) if index == self._selected else (
                QColor(50, 240, 100) if rectangle.kind == 'use' else QColor(255, 80, 80))
            painter.setPen(QPen(color, 2 if index == self._selected else 1))
            painter.drawRect(QRectF(target.x() + rectangle.x0 * sx, target.y() + rectangle.y0 * sy,
                                    (rectangle.x1 - rectangle.x0) * sx, (rectangle.y1 - rectangle.y0) * sy))
        if self._start is not None and self._end is not None:
            painter.setPen(QPen(QColor(255, 220, 0), 1, Qt.PenStyle.DashLine))
            painter.drawRect(QRectF(QPointF(target.x() + self._start.x() * sx, target.y() + self._start.y() * sy),
                                    QPointF(target.x() + self._end.x() * sx, target.y() + self._end.y() * sy)).normalized())
