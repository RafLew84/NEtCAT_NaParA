"""A registration attempt publishes one complete result after its thread finishes."""

from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.frame import ImageFrame
from stmviewer.registration import RegistrationCancelled, RegistrationResult, ShiftBackend, register_series


class RegistrationJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QObject,
                 backend: ShiftBackend | None = None, *, method: str = "phase_correlation") -> None:
        super().__init__(parent)
        self._frames = frames
        self._backend = backend
        self._method = method
        self._cancelled = Event()
        self.result: RegistrationResult | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            result = register_series(self._frames, method=self._method, backend=self._backend,
                                     progress=self.progress.emit, cancelled=self.was_cancelled)
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            # Thread boundary: never let a backend/allocation error terminate Qt.
            self.error = str(error) or type(error).__name__
