"""Cancellable measurement and graph solving without a full image-stack render."""
from threading import Event
from stmviewer.method_parameters import MethodProfiles

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.graph_registration import register_graph
from stmviewer.graph_types import GraphTrial
from stmviewer.registration import RegistrationCancelled


class GraphJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QObject, *, window: int,
                 deep_options: DeepMatcherOptions, previous: GraphTrial | None,
                 method: str = 'deep_matcher_translation', method_profiles: MethodProfiles = MethodProfiles()) -> None:
        super().__init__(parent)
        self._frames, self._window, self._options = frames, window, deep_options
        self._previous, self._method = previous, method
        self._profiles = method_profiles
        self._cancelled = Event()
        self.result: GraphTrial | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            result = register_graph(self._frames, window=self._window, method=self._method, deep_options=self._options,
                                    previous=self._previous, progress=self.progress.emit, method_profiles=self._profiles,
                                    cancelled=self.was_cancelled)
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
