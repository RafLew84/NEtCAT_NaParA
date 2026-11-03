"""Cancellable reconstruction publishes a corrected movie only after success."""

from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.manual_movie import apply_movie_correction, remove_movie_correction
from stmviewer.pair_comparison import PairTrial
from stmviewer.registration import RegistrationCancelled, RegistrationResult


class ManualMovieJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, result: RegistrationResult, parent: QObject, *,
                 trial: PairTrial | None = None, remove_index: int | None = None) -> None:
        super().__init__(parent)
        self._source = result
        self.trial = trial
        self._remove_index = remove_index
        self._cancelled = Event()
        self.result: RegistrationResult | None = None
        self.error: str | None = None
        self.checked_device: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            if self.trial is not None:
                result = apply_movie_correction(self._source, self.trial,
                                                progress=self.progress.emit, cancelled=self.was_cancelled)
            elif self._remove_index is not None:
                result = remove_movie_correction(self._source, self._remove_index,
                                                 progress=self.progress.emit, cancelled=self.was_cancelled)
            else:
                raise ValueError('Brak korekty do zastosowania.')
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
