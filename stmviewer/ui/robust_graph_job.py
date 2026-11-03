"""Cancellable Huber solve using already stored graph measurements only."""
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from stmviewer.graph_types import GraphTrial
from stmviewer.robust_graph_types import RobustConfig, RobustTrial
from stmviewer.registration import RegistrationCancelled


class RobustGraphJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, graph: GraphTrial, config: RobustConfig, parent: QObject) -> None:
        super().__init__(parent)
        self._graph, self._config = graph, config
        self._cancelled = Event()
        self.result: RobustTrial | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def was_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self) -> None:
        try:
            from stmviewer.robust_graph import solve_robust_graph
            result = solve_robust_graph(self._graph, self._config, progress=self.progress.emit,
                                        cancelled=self.was_cancelled)
            if not self.was_cancelled():
                self.result = result
        except RegistrationCancelled:
            pass
        except Exception as error:
            self.error = str(error) or type(error).__name__
