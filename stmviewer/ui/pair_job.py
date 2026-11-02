"""Background pair estimation; no complete-series aligned is materialized."""

from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.local_consensus import LocalDiagnostics, LocalConsensusError
from stmviewer.pair_comparison import PairTrial, estimate_pair
from stmviewer.registration import RegistrationCancelled, ShiftBackend


class PairJob(QThread):
    progress = pyqtSignal(str)

    def __init__(self, reference: ImageFrame, moving: ImageFrame, parent: QObject, *,
                 method: str, deep_options: DeepMatcherOptions,
                 backend: ShiftBackend | None = None) -> None:
        super().__init__(parent)
        self._reference, self._moving = reference, moving
        self._method, self._options, self._backend = method, deep_options, backend
        self._cancelled = Event()
        self.result: PairTrial | None = None
        self.error: str | None = None
        self.local_failure: LocalDiagnostics | None = None
        self.correspondence_failure: CorrespondenceDiagnostics | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            result = estimate_pair(self._reference, self._moving, method=self._method,
                                   deep_options=self._options, backend=self._backend,
                                   cancelled=self.was_cancelled, progress=self.progress.emit)
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except CorrespondenceRefusal as error:
            if not self.was_cancelled():
                self.correspondence_failure = error.diagnostics
                self.error = str(error)
        except LocalConsensusError as error:
            if not self.was_cancelled():
                self.local_failure = error.diagnostics
                self.error = str(error)
        except Exception as error:
            self.error = str(error) or type(error).__name__
