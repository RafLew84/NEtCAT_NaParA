"""Cancellable document IO; source fingerprints never block the GUI thread."""
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.frame import ImageFrame
from stmviewer.trial_document import TrialDocument, TrialCancelled, load_trial, save_trial


class TrialJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, path: Path, frames: tuple[ImageFrame, ...], parent: QObject,
                 *, document: TrialDocument | None = None) -> None:
        super().__init__(parent)
        self.path, self.frames, self.document = path, frames, document
        self.result: TrialDocument | None = None
        self.error: str | None = None
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            if self.document is None:
                self.result = load_trial(self.path, self.frames, progress=self.progress.emit,
                                         cancelled=self._cancelled.is_set)
            else:
                self.result = save_trial(self.path, self.document, self.frames,
                                         progress=self.progress.emit, cancelled=self._cancelled.is_set)
        except TrialCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
