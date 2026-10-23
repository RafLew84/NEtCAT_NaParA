"""A horizontal, virtualized list of original-frame thumbnails."""

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QListView, QWidget

from stmviewer.frame import ImageFrame
from stmviewer.ui.raster import frame_thumbnail
from stmviewer.ui.frame_source import frame_source_name, frame_source_text


class FrameListModel(QAbstractListModel):
    def __init__(self, frames: tuple[ImageFrame, ...], thumbnails: tuple[QImage, ...],
                 parent: QWidget) -> None:
        super().__init__(parent)
        self._frames = frames
        self._thumbnails = thumbnails
        self._warnings = tuple("" for _ in frames)
        self._icons: dict[int, QIcon] = {}
        self._pixel_proportions = False

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._frames)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._frames):
            return None
        row = index.row()
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{'⚠ ' if self._warnings[row] else ''}{row + 1} · {frame_source_name(self._frames[row])}"
        if role == Qt.ItemDataRole.ToolTipRole:
            source = frame_source_text(self._frames[row])
            return source + ("\n" + self._warnings[row] if self._warnings[row] else "")
        if role == Qt.ItemDataRole.DecorationRole:
            if row not in self._icons:
                thumbnail = (frame_thumbnail(self._frames[row], pixel_proportions=True)
                             if self._pixel_proportions else self._thumbnails[row])
                self._icons[row] = QIcon(QPixmap.fromImage(thumbnail))
            return self._icons[row]
        return None


    def remove_frame(self, index: int) -> None:
        """Keep frame/thumbnail pairs and renumber their display positions together."""
        frames = self._frames[:index] + self._frames[index + 1:]
        thumbnails = self._thumbnails[:index] + self._thumbnails[index + 1:]
        self.beginResetModel()
        self._frames = frames
        self._thumbnails = thumbnails
        self._warnings = self._warnings[:index] + self._warnings[index + 1:]
        self._icons.clear()
        self.endResetModel()

    def set_warnings(self, warnings: tuple[str, ...]) -> None:
        if len(warnings) != len(self._frames):
            raise ValueError("Warnings must match the frame series.")
        self._warnings = warnings
        if warnings:
            self.dataChanged.emit(self.index(0), self.index(len(warnings) - 1),
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole])

    def set_pixel_proportions(self, enabled: bool) -> None:
        if self._pixel_proportions == enabled:
            return
        self._pixel_proportions = enabled
        self._icons.clear()
        if self._frames:
            self.dataChanged.emit(self.index(0), self.index(len(self._frames) - 1),
                                  [Qt.ItemDataRole.DecorationRole])


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

    def set_pixel_proportions(self, enabled: bool) -> None:
        model = self.model()
        assert isinstance(model, FrameListModel)
        model.set_pixel_proportions(enabled)

    def remove_frame(self, index: int) -> None:
        model = self.model()
        assert isinstance(model, FrameListModel)
        model.remove_frame(index)

    def set_warnings(self, warnings: tuple[str, ...]) -> None:
        model = self.model()
        assert isinstance(model, FrameListModel)
        model.set_warnings(warnings)
