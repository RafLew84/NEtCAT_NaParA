"""Cancellable background work; only results cross into the UI."""

from collections.abc import Callable
from threading import Event

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from stmdomains.io.moltrack_import import ImportCancelled


class TaskSignals(QObject):
    result = pyqtSignal(int, object)
    error = pyqtSignal(int, str)
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(int)


class Task(QRunnable):
    def __init__(
        self, token: int, operation: Callable[[Event, Callable[[str], None]], object],
    ) -> None:
        super().__init__()
        self.token = token
        self.operation = operation
        self.cancelled = Event()
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            if self.cancelled.is_set():
                return
            result = self.operation(
                self.cancelled, lambda text: self.signals.progress.emit(self.token, text),
            )
            if not self.cancelled.is_set():
                self.signals.result.emit(self.token, result)
        except ImportCancelled:
            pass
        except Exception as exc:
            if not self.cancelled.is_set():
                self.signals.error.emit(self.token, f"{type(exc).__name__}: {exc}")
        finally:
            self.signals.finished.emit(self.token)
