"""Scene-coordinate centre selection; display transforms never change IDs."""

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsPathItem

from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.image_view import ImageView


class ManualSelection(QObject):
    selected = pyqtSignal(object, str)
    escape = pyqtSignal()

    def __init__(self, view: ImageView) -> None:
        super().__init__(view)
        self.view = view
        self.frame: PresentedFrame | None = None
        self.enabled = False
        self.tool = 'lasso'
        self.mode = 'replace'
        self.eligible_ids: frozenset[str] | None = None
        self._ids: tuple[str, ...] = ()
        self._path: list[QPointF] = []
        self._space = False
        self._gesture_mode = 'replace'
        self._frame_key: tuple[str, int, str] | None = None
        self.marks = QGraphicsPathItem()
        self.lasso = QGraphicsPathItem()
        for item, color in ((self.marks, '#fff179'), (self.lasso, '#ffdf49')):
            pen = QPen(QColor(color), 2)
            pen.setCosmetic(True)
            item.setPen(pen)
            item.setZValue(8)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            scene = view.scene()
            if scene is not None:
                scene.addItem(item)
        viewport = view.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)
        view.installEventFilter(self)

    def set_frame(self, frame: PresentedFrame) -> None:
        key = frame.series_id, frame.frame.working_index, frame.mode
        if key != self._frame_key:
            self._path = []
            self.lasso.setPath(QPainterPath())
        self._frame_key = key
        self.frame = frame
        self.set_selected(self._ids)

    def configure(self, enabled: bool, tool: str, mode: str) -> None:
        self.enabled, self.tool, self.mode = enabled, tool, mode
        self.marks.setVisible(enabled)
        if not enabled:
            self._path = []
            self.lasso.setPath(QPainterPath())
            self._space = False

    def set_selected(self, identifiers: tuple[str, ...]) -> None:
        self._ids = identifiers
        path = QPainterPath()
        if self.frame is not None:
            for detection in self.frame.annotations.detections:
                if detection.detection_id in identifiers:
                    path.addEllipse(QPointF(*detection.center_xy), 3., 3.)
        self.marks.setPath(path)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if event is None or not self.enabled:
            return False
        if isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Space:
                self._space = event.type() == QEvent.Type.KeyPress
                return True
            if event.key() == Qt.Key.Key_Escape and event.type() == QEvent.Type.KeyPress:
                self._path = []
                self.lasso.setPath(QPainterPath())
                self.escape.emit()
                return True
        if not isinstance(event, QMouseEvent) or self.frame is None:
            return False
        if self._space or self.tool == 'pan':
            return False
        position = self.view.mapToScene(event.position().toPoint())
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.view.setFocus()
            modifiers = event.modifiers()
            self._gesture_mode = ('subtract' if modifiers & Qt.KeyboardModifier.AltModifier else
                'add' if modifiers & Qt.KeyboardModifier.ShiftModifier else
                'toggle' if modifiers & Qt.KeyboardModifier.ControlModifier else self.mode)
            self._path = [position]
            return True
        if self._path and event.type() == QEvent.Type.MouseMove:
            self._path.append(position)
            if self.tool == 'lasso':
                path = QPainterPath(self._path[0])
                for point in self._path[1:]:
                    path.lineTo(point)
                path.closeSubpath()
                self.lasso.setPath(path)
            return True
        if self._path and event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            polygon = QPolygonF(self._path + [position])
            detections = tuple(d for d in self.frame.annotations.detections
                               if self.eligible_ids is None or d.detection_id in self.eligible_ids)
            if self.tool == 'lasso' and len(self._path) >= 3:
                selected = tuple(d.detection_id for d in detections
                                 if polygon.containsPoint(QPointF(*d.center_xy), Qt.FillRule.OddEvenFill))
            else:
                distances = [((self.view.mapFromScene(QPointF(*d.center_xy)) - event.position().toPoint()).manhattanLength(), d.detection_id)
                             for d in detections]
                nearest = min(distances, default=(100, ''))
                selected = (nearest[1],) if nearest[0] <= 14 else ()
            self._path = []
            self.lasso.setPath(QPainterPath())
            self.selected.emit(selected, self._gesture_mode)
            return True
        return False
