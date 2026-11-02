"""Virtual horizontal navigation with a bounded, lazily filled image cache."""

from collections import OrderedDict

from PyQt6.QtCore import (
    QAbstractListModel, QCoreApplication, QModelIndex, QSize, Qt,
    QThreadPool, QTimer, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import QIcon, QImage, QKeyEvent, QMouseEvent, QPixmap, QResizeEvent, QShowEvent
from PyQt6.QtWidgets import QListView, QWidget

from stmdomains.core.display import RenderedImage
from stmdomains.core.series import Series
from stmdomains.core.thumbnails import render_thumbnail
from stmdomains.ui.tasks import Task


class _ThumbnailModel(QAbstractListModel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.count = 0
        self.cache: OrderedDict[int, tuple[QIcon, int, bool]] = OrderedDict()
        self.errors: dict[int, str] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self.count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < self.count:
            return None
        item = self.cache.get(index.row())
        if role == Qt.ItemDataRole.DisplayRole:
            if index.row() in self.errors:
                return f"{index.row() + 1} · błąd miniatury"
            return str(index.row() + 1) if item is None or item[2] else f"{index.row() + 1} · brak próbek"
        if role == Qt.ItemDataRole.DecorationRole:
            return item[0] if item is not None else None
        if role == Qt.ItemDataRole.ToolTipRole:
            if index.row() in self.errors:
                return self.errors[index.row()]
            state = "ładowanie miniatury" if item is None else (
                "oryginał · gamma 1" if item[2] else "brak skończonych próbek"
            )
            return f"Klatka {index.row() + 1} — {state}"
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(108, 88)
        return None

    def reset_series(self, count: int) -> None:
        self.beginResetModel()
        self.count = count
        self.cache.clear()
        self.errors.clear()
        self.endResetModel()

    def insert(self, row: int, rendered: RenderedImage) -> None:
        pixels = rendered.rgba
        height, width = pixels.shape[:2]
        image = QImage(pixels.tobytes(), width, height, pixels.strides[0],
                       QImage.Format.Format_RGBA8888).copy()
        self.cache[row] = (QIcon(QPixmap.fromImage(image)), pixels.nbytes, rendered.has_data)
        self._trim_cache()
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0))

    def mark_failed(self, row: int, message: str) -> None:
        self.cache[row] = (QIcon(), 0, False)
        self.errors[row] = message
        self._trim_cache()
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0))

    def _trim_cache(self) -> None:
        while len(self.cache) > 64:
            removed, _ = self.cache.popitem(last=False)
            self.errors.pop(removed, None)
            self.dataChanged.emit(self.index(removed, 0), self.index(removed, 0))


class Filmstrip(QListView):
    frame_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filmstrip")
        self.setAccessibleName("Miniatury klatek")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(108, 88))
        self.setIconSize(QSize(96, 64))
        self.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(110)
        self._model = _ThumbnailModel(self)
        self.setModel(self._model)
        self._series: Series | None = None
        self._current_index = -1
        self._wanted: list[int] = []
        self._task: Task | None = None
        self._task_request: tuple[str, int] | None = None
        self._counter = 0
        self._closed = False
        self._pool = QThreadPool(QCoreApplication.instance())
        self._pool.setMaxThreadCount(1)
        self._refresh = QTimer(self)
        self._refresh.setSingleShot(True)
        self._refresh.timeout.connect(self._request_visible)
        scrollbar = self.horizontalScrollBar()
        if scrollbar is not None:
            scrollbar.valueChanged.connect(lambda: self._refresh.start(0))

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def cache_info(self) -> tuple[int, int]:
        return len(self._model.cache), sum(entry[1] for entry in self._model.cache.values())

    @property
    def pending_task_count(self) -> int:
        return int(self._task is not None)

    def is_ready(self, index: int) -> bool:
        return index in self._model.cache

    def set_series(self, series: Series) -> None:
        if self._closed:
            return
        if self._task is not None:
            self._task.cancelled.set()
        self._series = series
        self._wanted.clear()
        self._current_index = -1
        self._model.reset_series(series.frame_count)
        self._refresh.start(0)

    def set_current_index(self, index: int) -> None:
        if self._series is None or not 0 <= index < self._series.frame_count or self._closed:
            return
        self._current_index = index
        item = self._model.index(index, 0)
        self.setCurrentIndex(item)
        self.scrollTo(item, QListView.ScrollHint.EnsureVisible)
        self._refresh.start(0)

    def _request_visible(self) -> None:
        if self._series is None or self._closed or not self.isVisible():
            return
        scrollbar, viewport = self.horizontalScrollBar(), self.viewport()
        if scrollbar is None or viewport is None:
            return
        first = max(0, scrollbar.value() // 108 - 1)
        count = min(64, viewport.width() // 108 + 4)
        self._wanted = list(range(first, min(self._series.frame_count, first + count)))
        if self._current_index in self._wanted:
            self._wanted.remove(self._current_index)
            self._wanted.insert(0, self._current_index)
        for row in self._wanted:
            if row in self._model.cache:
                self._model.cache.move_to_end(row)
        self._launch_next()

    def _launch_next(self) -> None:
        series = self._series
        if self._task is not None or self._closed or series is None:
            return
        row = next((index for index in self._wanted if not self.is_ready(index)), None)
        if row is None:
            return
        self._counter += 1
        task = Task(self._counter, lambda cancelled, report: (
            series.identity, row, render_thumbnail(series.frame(row).image),
        ))
        task.signals.result.connect(self._receive)
        task.signals.error.connect(self._failed)
        task.signals.finished.connect(self._finished)
        self._task = task
        self._task_request = (series.identity, row)
        self._pool.start(task)

    @pyqtSlot(int, object)
    def _receive(self, token: int, result: object) -> None:
        if self._closed or self._series is None or not isinstance(result, tuple):
            return
        identity, row, rendered = result
        if identity == self._series.identity and row in self._wanted:
            self._model.insert(row, rendered)

    @pyqtSlot(int, str)
    def _failed(self, token: int, message: str) -> None:
        if self._closed or self._series is None or self._task_request is None:
            return
        identity, row = self._task_request
        if identity == self._series.identity and row in self._wanted:
            self._model.mark_failed(row, message)

    @pyqtSlot(int)
    def _finished(self, token: int) -> None:
        if self._task is not None and self._task.token == token:
            self._task = None
            self._task_request = None
        self._launch_next()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self.frame_selected.emit(index.row())
            event.accept()
            return
        if event is not None:
            event.accept()  # Other buttons must not select a frame behind the controller.

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is not None:
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        self.mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and self._series is not None:
            targets: dict[int, int] = {
                Qt.Key.Key_Left: self._current_index - 1, Qt.Key.Key_Right: self._current_index + 1,
                Qt.Key.Key_Home: 0, Qt.Key.Key_End: self._series.frame_count - 1,
            }
            target = targets.get(event.key())
            if target is not None:
                if 0 <= target < self._series.frame_count:
                    self.frame_selected.emit(target)
                event.accept()
                return
        if event is not None:
            event.ignore()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_refresh"):
            self._refresh.start(0)

    def showEvent(self, event: QShowEvent | None) -> None:
        super().showEvent(event)
        self._refresh.start(0)

    def shutdown(self) -> None:
        self._closed = True
        self._refresh.stop()
        if self._task is not None:
            self._task.cancelled.set()

    def wait_for_workers(self) -> None:
        """Join cancelled work while its Qt signal objects are still alive."""
        self._pool.waitForDone()
