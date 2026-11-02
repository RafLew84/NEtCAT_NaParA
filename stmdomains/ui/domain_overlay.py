"""Display the final domain raster in raw coordinates, translated with the image."""

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.result_style import assignment_color
from stmdomains.ui.domain_shapes import domain_shapes


class DomainOverlay(QGraphicsObject):
    """Keep only the current result's coloured image; display choices never fit a model."""

    def __init__(self) -> None:
        super().__init__()
        self._result: FrameAnalysis | None = None
        self._rect = QRectF()
        self._pixmap = QPixmap()
        self._shapes: dict[int, tuple[QPainterPath, QPointF]] = {}
        self._colors: dict[int, QColor] = {}
        self._mode = "domains"
        self._fill = True
        self._outlines = True
        self._numbers = True
        self._opacity = .35
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:
        return self._rect

    def set_frame(self, view: PresentedFrame) -> None:
        self.prepareGeometryChange()
        x, y, width, height = view.field_rect
        self._rect = QRectF(0, 0, width, height)
        self.setPos(x, y)
        result = view.result
        if result is not None and (result.status != "complete" or result.domain_labels is None):
            result = None
        if result is not self._result:
            self._result = result
            self._shapes = (domain_shapes(result.domain_labels)
                            if result is not None and result.domain_labels is not None else {})
            self._recolor()
        self.update()

    def set_mode(self, mode: str) -> None:
        if mode != self._mode:
            self._mode = mode
            self._recolor()
            self.update()

    def set_layers(self, *, fill: bool, outlines: bool, numbers: bool, opacity: float) -> None:
        self._fill, self._outlines, self._numbers = fill, outlines, numbers
        self._opacity = min(1., max(0., opacity))
        self.update()

    def _recolor(self) -> None:
        self._pixmap = QPixmap()
        self._colors = {}
        result = self._result
        if result is None or result.domain_labels is None or self._mode == "input":
            return
        labels = result.domain_labels
        palette = np.zeros((int(labels.max(initial=0)) + 1, 4), dtype=np.uint8)
        for identity, member in result.assignments.items():
            if 0 < member.domain_local_id < len(palette):
                color = QColor(assignment_color(result, identity, self._mode))
                palette[member.domain_local_id] = (color.red(), color.green(), color.blue(), 255)
                self._colors[member.domain_local_id] = color
        rgba = palette[labels]
        height, width = labels.shape
        image = QImage(rgba.tobytes(), width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
        self._pixmap = QPixmap.fromImage(image)

    def paint(
        self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None or self._result is None or self._mode == "input":
            return
        painter.save()
        painter.setClipRect(self._rect)
        if self._fill:
            painter.setOpacity(self._opacity)
            painter.drawPixmap(QPointF(0, 0), self._pixmap)
        painter.setOpacity(1)
        for identity, (path, anchor) in self._shapes.items():
            if self._outlines:
                pen = QPen(self._colors[identity], 1.2)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            if self._numbers:
                # Keep text readable in screen pixels while the anchor follows zoom/translation.
                painter.save()
                position = painter.worldTransform().map(anchor)
                painter.resetTransform()
                painter.translate(position)
                text = f"D{identity}"
                bounds = QRectF(painter.fontMetrics().boundingRect(text)).adjusted(-3, -2, 3, 2)
                bounds.moveCenter(QPointF(0, 0))
                painter.fillRect(bounds, QColor(15, 25, 30, 205))
                painter.setPen(QColor("white"))
                painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, text)
                painter.restore()
        painter.restore()
