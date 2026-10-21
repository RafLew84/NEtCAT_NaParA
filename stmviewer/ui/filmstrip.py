"""A horizontal, virtualized list of original-frame thumbnails."""

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QListView, QWidget

from stmviewer.frame import ImageFrame


class FrameListModel(QAbstractListModel):
    def __init__(self, frames: tuple[ImageFrame, ...], thumbnails: tuple[QImage, ...],
                 parent: QWidget) -> None:
        super().__init__(parent)
        self._frames = frames
        self._thumbnails = thumbnails
        self._icons: dict[int, QIcon] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._frames)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._frames):
            return None
        row = index.row()
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{row + 1} · {self._frames[row].source.name}"
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(self._frames[row].source)
        if role == Qt.ItemDataRole.DecorationRole:
            if row not in self._icons:
                self._icons[row] = QIcon(QPixmap.fromImage(self._thumbnails[row]))
            return self._icons[row]
        return None


class Filmstrip(QListView):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("frameThumbnails")
        self.setAccessibleName("Miniatury klatek")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(96, 72))
        self.setGridSize(QSize(132, 104))
        self.setFixedHeight(130)
        self.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setModel(FrameListModel((), (), self))

    def set_series(self, frames: tuple[ImageFrame, ...], thumbnails: tuple[QImage, ...]) -> None:
        model = self.model()
        selection = self.selectionModel()
        self.setModel(FrameListModel(frames, thumbnails, self))
        if model is not None:
            model.deleteLater()
        if selection is not None:
            selection.deleteLater()
