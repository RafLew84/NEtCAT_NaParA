"""Advance a batch one outcome at a time, applying backpressure at the GUI thread."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from threading import Event
from types import MappingProxyType
from uuid import uuid4

from PyQt6.QtCore import QCoreApplication, QObject, QThreadPool, pyqtSignal, pyqtSlot

from stmdomains.analysis.series_analysis import FrameOutcome, analyze_series, validate_shared_catalogue
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.ui.tasks import Task


@dataclass(frozen=True)
class FrameRunStatus:
    status: str = "pending"
    message: str = ""
    assigned: int = 0
    active: int = 0
    domains: int = 0


@dataclass(frozen=True)
class SeriesRun:
    series_id: str
    plan: SeriesAnalysisPlan
    indices: tuple[int, ...]
    phase: str = "fitting"
    message: str = "Przygotowanie wspólnych klas…"
    catalogue: ClassCatalogue | None = None
    frames: Mapping[int, FrameRunStatus] = field(default_factory=dict)
    identifier: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", MappingProxyType(dict(self.frames)))

    @property
    def processed_count(self) -> int:
        return sum(item.status in ("complete", "no_annotations", "insufficient_data", "error")
                   for item in self.frames.values())


class SeriesRunner(QObject):
    changed = pyqtSignal()
    catalogue_ready = pyqtSignal(object)
    frame_ready = pyqtSignal(object)
    failed = pyqtSignal(str)
    _progress_reported = pyqtSignal(int, str)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.state: SeriesRun | None = None
        self._pool = QThreadPool(QCoreApplication.instance())
        self._pool.setMaxThreadCount(1)
        self._tasks: dict[int, Task] = {}
        self._token: int | None = None
        self._counter = 0
        self._generation = 0
        self._cancelled = Event()
        self._iterator: Iterator[ClassCatalogue | FrameOutcome] | None = None
        self._closed = False
        self._progress_reported.connect(self._progress)

    @property
    def running(self) -> bool:
        return self.state is not None and self.state.phase in ("fitting", "analysing")

    @property
    def pending_task_count(self) -> int:
        return len(self._tasks)

    def start(self, presenter: FramePresenter, plan: SeriesAnalysisPlan, catalogue: ClassCatalogue | None) -> None:
        if self._closed or self.running:
            return
        series = presenter.series
        indices, fit = plan.indices(series.frame_count), plan.fit_settings(series.frame_count)
        if fit is None:
            validate_shared_catalogue(catalogue, series.identity, plan.k)
        self._cancelled = Event()
        self._generation += 1
        generation = self._generation
        self.state = SeriesRun(series.identity, plan, indices,
                               frames={index: FrameRunStatus() for index in indices})
        # The generator's cancellation event belongs to this run, not the next one.
        self._iterator = analyze_series(
            presenter.analysis_input, frame_count=series.frame_count, series_id=series.identity,
            plan=plan, catalogue=catalogue, run_id=self.state.identifier, cancelled=self._cancelled.is_set,
            progress=lambda text: self._progress_reported.emit(generation, text),
        )
        self.changed.emit()
        self._advance()

    def _advance(self) -> None:
        iterator = self._iterator
        if not self.running or iterator is None:
            return
        if self.state is not None and self.state.phase == "analysing":
            index = next((i for i, row in self.state.frames.items() if row.status == "pending"), None)
            if index is not None:
                self.state = replace(self.state, frames={**self.state.frames, index: FrameRunStatus("analysing")})
                self.changed.emit()
        if not self.running:
            return
        self._counter += 1
        task = Task(self._counter, lambda cancelled, report: next(iterator, None))
        self._token = task.token
        self._tasks[task.token] = task
        task.signals.result.connect(self._receive)
        task.signals.error.connect(self._failed)
        task.signals.finished.connect(self._finished)
        self._pool.start(task)

    @pyqtSlot(int, object)
    def _receive(self, token: int, event: object) -> None:
        if token != self._token or not self.running or self.state is None:
            return
        if isinstance(event, ClassCatalogue):
            self.state = replace(self.state, catalogue=event, phase="analysing", message="Analiza domen…")
            self.catalogue_ready.emit(event)
        elif isinstance(event, FrameOutcome):
            result = event.result
            status = FrameRunStatus("error", event.error) if result is None else FrameRunStatus(
                result.status, result.message, result.assigned_count, result.active_count, result.domain_count)
            self.state = replace(self.state, frames={**self.state.frames, event.index: status})
            self.frame_ready.emit(event)
        elif event is None:
            errors = sum(row.status == "error" for row in self.state.frames.values())
            self.state = replace(self.state, phase="complete",
                                 message=f"Zakończono {self.state.processed_count}/{len(self.state.indices)} klatek · błędy: {errors}")
            self._iterator = None
            self._token = None
        self.changed.emit()
        self._advance()

    @pyqtSlot(int, str)
    def _progress(self, generation: int, text: str) -> None:
        if generation == self._generation and self.running and self.state is not None:
            self.state = replace(self.state, message=text)
            self.changed.emit()

    @pyqtSlot(int, str)
    def _failed(self, token: int, message: str) -> None:
        if token != self._token or self.state is None:
            return
        self._stop("failed", message)
        self.failed.emit(message)

    @pyqtSlot(int)
    def _finished(self, token: int) -> None:
        self._tasks.pop(token, None)

    def _stop(self, phase: str, message: str) -> None:
        self._cancelled.set()
        if self._token in self._tasks:
            self._tasks[self._token].cancelled.set()
        self._token = None
        self._iterator = None
        if self.state is not None:
            self.state = replace(self.state, phase=phase, message=message, frames={
                index: FrameRunStatus("not_run", message) if row.status in ("pending", "analysing") else row
                for index, row in self.state.frames.items()})
        self.changed.emit()

    def cancel(self) -> None:
        if self.running and self.state is not None:
            self._stop("cancelled", f"Anulowano · ukończono {self.state.processed_count}/{len(self.state.indices)} klatek")

    def reset(self) -> None:
        self.cancel()
        self.state = None
        self.changed.emit()

    def shutdown(self) -> None:
        self._closed = True
        self.cancel()

    def wait_for_workers(self) -> None:
        self._pool.waitForDone()
