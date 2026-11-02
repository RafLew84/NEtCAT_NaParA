"""Paint and inspect annotations in the exact image scene coordinates."""

from math import floor

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from stmdomains.core.annotations import Detection, Segmentation
from stmdomains.core.frame_presentation import PresentedFrame


class AnnotationOverlay(QGraphicsObject):
    def __init__(self) -> None:
        super().__init__()
        self.view: PresentedFrame | None = None
        self.centers = True
        self.boxes = False
        self.masks = False
        self.mask_opacity = 0.45
        self.selected_id: str | None = None
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def set_frame(self, view: PresentedFrame) -> None:
        self.prepareGeometryChange()
        self.view = view
        self.selected_id = None
        self.update()

    def boundingRect(self) -> QRectF:
        if self.view is None:
            return QRectF()
        height, width = self.view.rendered.rgba.shape[:2]
        return QRectF(0, 0, width, height)

    def paint(
        self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None or self.view is None:
            return
        painter.save()
        painter.setClipRect(QRectF(*self.view.field_rect).intersected(self.boundingRect()))
        pen = QPen(QColor(70, 230, 190))
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        if self.boxes:
            for segmentation in self.view.annotations.segmentations:
                if segmentation.bbox_xyxy is not None:
                    x1, y1, x2, y2 = segmentation.bbox_xyxy
                    painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
        if self.masks:
            painter.setOpacity(self.mask_opacity)
            for segmentation in self.view.annotations.segmentations:
                if segmentation.polygon_xy:
                    painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in segmentation.polygon_xy]))
            painter.setOpacity(1)
        for detection in self.view.annotations.detections:
            if detection.outside_field:
                continue
            x1, y1, x2, y2 = detection.bbox_xyxy
            selected = detection.detection_id == self.selected_id
            pen.setColor(QColor("#ffdb71") if selected else QColor(70, 230, 190))
            pen.setWidthF(2 if selected else 1.2)
            painter.setPen(pen)
            if self.boxes or selected:
                painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
            if self.centers:
                painter.setBrush(pen.color())
                painter.drawEllipse(QPointF(*detection.center_xy), 0.8, 0.8)
                painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.restore()

    def pick(self, point: QPointF) -> Detection | Segmentation | None:
        if self.view is None or not QRectF(*self.view.field_rect).contains(point):
            return None
        if self.centers or self.boxes:
            candidates = []
            for detection in self.view.annotations.detections:
                x1, y1, x2, y2 = detection.bbox_xyxy
                if not detection.outside_field and x1 <= point.x() <= x2 and y1 <= point.y() <= y2:
                    candidates.append(detection)
            if candidates:
                return min(candidates, key=lambda d: (d.bbox_xyxy[2] - d.bbox_xyxy[0])
                           * (d.bbox_xyxy[3] - d.bbox_xyxy[1]))
        if self.boxes:
            for segmentation in self.view.annotations.segmentations:
                if segmentation.bbox_xyxy is not None:
                    x1, y1, x2, y2 = segmentation.bbox_xyxy
                    if x1 <= point.x() <= x2 and y1 <= point.y() <= y2:
                        return segmentation
        if self.masks and self.mask_opacity > 0:
            x, y = floor(point.x()), floor(point.y())
            for segmentation in self.view.annotations.segmentations:
                mask = segmentation.mask
                if mask is not None and 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and mask[y, x]:
                    return segmentation
                if segmentation.polygon_xy:
                    polygon = QPolygonF([QPointF(px, py) for px, py in segmentation.polygon_xy])
                    if polygon.containsPoint(point, Qt.FillRule.OddEvenFill):
                        return segmentation
        return None
