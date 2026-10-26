"""Keep file I/O outside the GUI thread, including cancellation and rollback."""
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.frame import ImageFrame
from stmviewer.mpp_export import ExportCancelled, save_original_mpp, save_aligned_mpp
from stmviewer.registration import RegistrationResult


class MppExportJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, path: Path, frames: tuple[ImageFrame, ...], parent: QObject, *, overwrite: bool,
                 registration: RegistrationResult | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self._frames = frames
        self._registration = registration
        self._overwrite = overwrite
        self._cancelled = Event()
        self.result: Path | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            # A late cancel must not turn a completed publication into a reported cancellation.
            if self._registration is None:
                self.result = save_original_mpp(self._path, self._frames, overwrite=self._overwrite,
                                                progress=self.progress.emit, cancelled=self._cancelled.is_set)
            else:
                self.result = save_aligned_mpp(self._path, self._registration, overwrite=self._overwrite,
                                               progress=self.progress.emit, cancelled=self._cancelled.is_set)
        except ExportCancelled:
            pass
        except Exception as error:
            # Thread boundary: a filesystem/allocation failure must not terminate Qt.
            self.error = f'{self._path}: {str(error) or type(error).__name__}'
