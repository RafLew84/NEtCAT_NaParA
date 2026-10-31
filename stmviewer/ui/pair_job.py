"""Background pair estimation; no complete-series aligned is materialized."""

from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.registration_masks import FrameMask
from stmviewer.pair_comparison import PairTrial, estimate_pair
from stmviewer.registration import RegistrationCancelled, ShiftBackend


class PairJob(QThread):
    progress = pyqtSignal(str)

    def __init__(self, reference: ImageFrame, moving: ImageFrame, parent: QObject, *,
                 method: str, deep_options: DeepMatcherOptions,
                 backend: ShiftBackend | None = None, reference_mask: FrameMask | None = None,
                 moving_mask: FrameMask | None = None, use_masks: bool = True) -> None:
        super().__init__(parent)
        self._reference, self._moving = reference, moving
        self._method, self._options, self._backend = method, deep_options, backend
        self._reference_mask, self._moving_mask, self._use_masks = reference_mask, moving_mask, use_masks
        self._cancelled = Event()
        self.result: PairTrial | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            result = estimate_pair(self._reference, self._moving, method=self._method,
                                   deep_options=self._options, backend=self._backend,
                                   reference_mask=self._reference_mask, moving_mask=self._moving_mask,
                                   use_masks=self._use_masks,
                                   cancelled=self.was_cancelled, progress=self.progress.emit)
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
