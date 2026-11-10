"""Inspect the actual neighbours saved with a result, translated with the image."""

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from stmdomains.analysis.freud_settings import METHOD
from stmdomains.core.frame_presentation import PresentedFrame


class FreudOverlay(QGraphicsObject):
    def __init__(self) -> None:
        super().__init__()
        self.view: PresentedFrame | None = None
        self.selected_id: str | None = None
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def set_frame(self, view: PresentedFrame) -> None:
        self.prepareGeometryChange()
        self.view = view
        self.selected_id = None
        self.update()

    def select(self, identity: str | None) -> None:
        self.selected_id = identity
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(*self.view.field_rect) if self.view else QRectF()

    def segments(self) -> tuple[QLineF, ...]:
        view = self.view
        result = view.result if view else None
        if view is None or result is None or result.parameters.get('domain_method') != METHOD:
            return ()
        item = result.assignments.get(self.selected_id or '')
        if item is None:
            return ()
        details = item.metadata.get('freud_environment', {})
        center = item.metadata.get('geometry', {}).get('center_xy')
        if center is None:
            return ()
        x, y = view.field_rect[:2]
        origin = QPointF(center[0]+x, center[1]+y)
        return tuple(QLineF(origin, QPointF(px+x, py+y)) for px, py in details.get('neighbor_centers', ()))

    def paint(self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None,
              widget: QWidget | None = None) -> None:
        if painter is None:
            return
        painter.save()
        painter.setClipRect(self.boundingRect())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor('#ffdc73'), 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for line in self.segments():
            painter.drawLine(line)
            painter.drawEllipse(line.p2(), 1.5, 1.5)
        painter.restore()
