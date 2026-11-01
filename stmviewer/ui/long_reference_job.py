"""Cancellable far-reference measurement against one unchanged window baseline."""
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphTrial
from stmviewer.registration import RegistrationCancelled


class LongReferenceJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, frames: tuple[ImageFrame, ...], base: GraphTrial, parent: QObject, *,
                 references: tuple[int, ...], target_start: int, target_end: int,
                 robust_revision: str | None, deep_options: DeepMatcherOptions) -> None:
        super().__init__(parent)
        self._frames, self._base = frames, base
        self._references, self._start, self._end = references, target_start, target_end
        self._robust_revision, self._options = robust_revision, deep_options
        self._cancelled = Event()
        self.result: GraphTrial | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            from stmviewer.long_references import extend_graph
            result = extend_graph(self._frames, self._base, references=self._references,
                                  target_start=self._start, target_end=self._end,
                                  robust_revision=self._robust_revision, deep_options=self._options,
                                  progress=self.progress.emit, cancelled=self.was_cancelled)
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
