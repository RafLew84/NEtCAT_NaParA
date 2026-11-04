"""Passive row directions and metric neighborhoods in the image coordinate system."""

from math import cos, sin, radians
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.core.geometry import MoleculeGeometry, PixelCalibration


def row_segments(record: MoleculeGeometry, scale: PixelCalibration, origin: tuple[float, float]) -> list[QLineF]:
    """Physical Y-up row direction → raw pixel Y-down → aligned translation."""
    x, y = record.center_xy
    center = QPointF(x+origin[0], y+origin[1])
    length = (record.radius or 0.) * .3
    segments = []
    for axis in record.axes:
        theta = radians(axis.row_angle_deg)
        delta = QPointF(length*cos(theta)/scale.x, -length*sin(theta)/scale.y)
        segments.append(QLineF(center-delta, center+delta))
    return segments


class GeometryOverlay(QGraphicsObject):
    def __init__(self) -> None:
        super().__init__()
        self.view: PresentedFrame | None = None
        self.selected_id: str | None = None
        self.show_all = False
        self.show_neighborhood = True
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setVisible(False)

    def set_frame(self, view: PresentedFrame) -> None:
        self.prepareGeometryChange()
        self.view = view
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(*self.view.field_rect) if self.view else QRectF()

    def paint(self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None,
              widget: QWidget | None = None) -> None:
        if painter is None or self.view is None or self.view.geometry is None:
            return
        geometry = self.view.geometry
        origin = self.view.field_rect[:2]
        painter.save()
        painter.setClipRect(self.boundingRect())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for record in geometry.molecules.values():
            selected = record.detection_id == self.selected_id
            if not selected and not self.show_all:
                continue
            pen = QPen()
            pen.setCosmetic(True)
            pen.setWidthF(2.5 if selected else 1.4)
            for index, line in enumerate(row_segments(record, geometry.calibration, origin)):
                pen.setColor(QColor('#5cf1ed' if index == 0 else '#ffca78'))
                painter.setPen(pen)
                painter.drawLine(line)
            if selected and self.show_neighborhood and record.radius is not None:
                pen.setColor(QColor('#ffffff'))
                pen.setWidthF(1.)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                x, y = record.center_xy
                painter.drawEllipse(QPointF(x+origin[0], y+origin[1]),
                                    record.radius/geometry.calibration.x, record.radius/geometry.calibration.y)
        painter.restore()
