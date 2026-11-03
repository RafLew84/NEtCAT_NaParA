"""Cancellable application/restoration renders originals before publishing a movie."""
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphTrial
from stmviewer.registration import RegistrationCancelled, RegistrationResult


class GraphApplicationJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QObject, *,
                 previous: RegistrationResult | None, graph: GraphTrial | None = None,
                 robust_revision: str | None = None) -> None:
        super().__init__(parent)
        self._frames, self._previous, self._graph = frames, previous, graph
        self._robust_revision = robust_revision
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
            from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
            if self._graph is not None:
                result = apply_graph_to_movie(self._frames, self._graph, previous=self._previous,
                                               robust_revision=self._robust_revision,
                                               progress=self.progress.emit, cancelled=self.was_cancelled)
            elif self._previous is not None:
                result = restore_movie_result(self._frames, self._previous,
                                               progress=self.progress.emit, cancelled=self.was_cancelled)
            else:
                raise ValueError('Brak zachowanego wyniku do przywrócenia.')
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
