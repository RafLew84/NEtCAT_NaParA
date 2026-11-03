"""Background session IO and thumbnail preparation before replacing the workspace."""
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from stmviewer.session_archive import SessionCancelled, load_session, save_session
from stmviewer.session_state import SessionState
from stmviewer.ui.raster import frame_thumbnail


class SessionJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, path: Path, parent: QObject, *, state: SessionState | None = None) -> None:
        super().__init__(parent)
        self.path, self.state = path, state
        self.loaded: SessionState | None = None
        self.saved: Path | None = None
        self.thumbnails: tuple[QImage, ...] = ()
        self.error: str | None = None
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            if self.state is not None:
                self.saved = save_session(self.path, self.state, progress=self.progress.emit,
                                          cancelled=self._cancelled.is_set)
                return
            state = load_session(self.path, progress=self.progress.emit, cancelled=self._cancelled.is_set)
            thumbnails = []
            for index, frame in enumerate(state.frames):
                if self._cancelled.is_set():
                    raise SessionCancelled
                thumbnails.append(frame_thumbnail(frame))
                self.progress.emit(index + 1, len(state.frames), 'Przygotowanie podglądu sesji…')
            if self._cancelled.is_set():
                raise SessionCancelled
            self.loaded, self.thumbnails = state, tuple(thumbnails)
        except SessionCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
