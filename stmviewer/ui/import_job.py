"""Cancellable background decoding; only finished jobs expose a complete result."""

from dataclasses import dataclass
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from stmviewer.frame import ImageFrame
from stmviewer.series import ImportCancelled, open_frame_series
from stmviewer.ui.raster import frame_thumbnail


@dataclass(frozen=True)
class ImportedSeries:
    frames: tuple[ImageFrame, ...]
    thumbnails: tuple[QImage, ...]


class ImportJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, paths: list[str], parent: QObject) -> None:
        super().__init__(parent)
        self._paths = paths
        self._cancelled = Event()
        self.result: ImportedSeries | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def _read_progress(self, done: int, total: int, path: Path) -> None:
        suffix = ' · weryfikacja metadanych' if done == total and path.suffix.lower() == '.mpp' else ''
        self.progress.emit(done, total * 2, f"Odczyt {done}/{total}: {path.name}{suffix}")

    def run(self) -> None:
        try:
            frames = open_frame_series(self._paths, progress=self._read_progress,
                                     cancelled=self.was_cancelled)
            thumbnails = []
            for index, frame in enumerate(frames, 1):
                if self.was_cancelled():
                    raise ImportCancelled
                try:
                    thumbnails.append(frame_thumbnail(frame))
                except Exception as error:
                    raise ValueError(f"{frame.source}: nie można przygotować miniatury: {error}") from error
                self.progress.emit(len(frames) + index, len(frames) * 2,
                                   f"Miniatury {index}/{len(frames)}: {frame.source.name}")
            if not self.was_cancelled():
                self.result = ImportedSeries(frames, tuple(thumbnails))
        except ImportCancelled:
            pass
        except Exception as error:
            # This is the thread boundary: report failures without terminating Qt.
            self.error = str(error) or type(error).__name__
