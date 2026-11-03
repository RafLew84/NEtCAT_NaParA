"""Write exports in a worker, with one bounded GUI-render request at a time."""

from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from threading import Event

from PyQt6.QtCore import QCoreApplication, QObject, QThreadPool, pyqtSignal, pyqtSlot

from stmdomains.core.export import ExportOptions
from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.core.project import ProjectSnapshot
from stmdomains.io.export_results import export_results
from stmdomains.io.export_tables import identity
from stmdomains.io.project_archive import checkpoint
from stmdomains.ui.export_png import render_export_png
from stmdomains.ui.tasks import Task


@dataclass
class RenderRequest:
    frame: PresentedFrame
    snapshot: ProjectSnapshot
    options: ExportOptions
    cancelled: Event
    response: Queue[bytes | Exception] = field(default_factory=lambda: Queue(maxsize=1))


class ExportRunner(QObject):
    changed = pyqtSignal()
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    render_requested = pyqtSignal(object)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(QCoreApplication.instance())
        self._pool.setMaxThreadCount(1)
        self._tasks: dict[int, Task] = {}
        self._active: Task | None = None
        self._counter = 0
        self.message = ''
        self._closed = False
        self.render_requested.connect(self._render)

    @property
    def running(self) -> bool:
        return self._active is not None

    @property
    def pending_task_count(self) -> int:
        return len(self._tasks)

    def start(self, path: Path, snapshot: ProjectSnapshot, indices: tuple[int, ...], options: ExportOptions) -> None:
        if self.running or self._closed:
            return
        self._counter += 1
        def work(cancelled, report):
            def png(frame):
                request = RenderRequest(frame, snapshot, options, cancelled)
                self.render_requested.emit(request)
                while True:
                    checkpoint(cancelled.is_set)
                    try:
                        response = request.response.get(timeout=.05)
                        if isinstance(response, Exception):
                            raise response
                        return response
                    except Empty:
                        continue
            return export_results(path, snapshot, indices, options, render_png=png,
                                  cancelled=cancelled.is_set, progress=report)
        task = Task(self._counter, work)
        self._tasks[task.token] = self._active = task
        task.signals.result.connect(self._done)
        task.signals.error.connect(self._failed)
        task.signals.progress.connect(self._progress)
        task.signals.finished.connect(self._finished)
        self.message = 'Przygotowanie eksportu…'
        self.changed.emit()
        self._pool.start(task)

    @pyqtSlot(object)
    def _render(self, request: RenderRequest) -> None:
        if self._closed or request.cancelled.is_set():
            return
        try:
            response: bytes | Exception = render_export_png(request.frame, request.snapshot.view, request.options,
                context=identity(request.snapshot, request.frame.frame.working_index, request.frame.result))
        except Exception as error:
            response = error
        request.response.put_nowait(response)

    @pyqtSlot(int, object)
    def _done(self, token: int, path: Path) -> None:
        if self._active is not None and token == self._active.token:
            self._active = None
            self.message = f'Zapisano eksport: {path}'
            self.changed.emit()
            self.completed.emit(path)

    @pyqtSlot(int, str)
    def _failed(self, token: int, message: str) -> None:
        if self._active is not None and token == self._active.token:
            self._active = None
            self.message = 'Błąd eksportu: ' + message
            self.changed.emit()
            self.failed.emit(message)

    @pyqtSlot(int, str)
    def _progress(self, token: int, message: str) -> None:
        if self._active is not None and token == self._active.token:
            self.message = message
            self.changed.emit()

    @pyqtSlot(int)
    def _finished(self, token: int) -> None:
        self._tasks.pop(token, None)

    def cancel(self) -> None:
        if self._active is not None:
            self._active.cancelled.set()
            self._active = None
            self.message = 'Anulowano eksport. Otwarta praca pozostaje bez zmian.'
            self.changed.emit()

    def shutdown(self) -> None:
        self._closed = True
        self.cancel()

    def wait_for_workers(self) -> None:
        self._pool.waitForDone()
