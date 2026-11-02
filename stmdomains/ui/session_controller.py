"""Commit a validated import atomically and discard obsolete frame requests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QCoreApplication, QObject, QThreadPool, QTimer, Qt, pyqtSignal, pyqtSlot

from stmdomains.core.frame_presentation import FramePresenter, PresentedFrame
from stmdomains.core.series import Series
from stmdomains.io.moltrack_import import ImportCandidate, SourceRequest, prepare_import
from stmdomains.ui.import_prompts import ImportPrompts
from stmdomains.ui.tasks import Task


@dataclass(frozen=True)
class PreparedImport:
    candidate: ImportCandidate
    presenter: FramePresenter
    view: PresentedFrame


class SessionController(QObject):
    series_changed = pyqtSignal(object)
    frame_changed = pyqtSignal(object)
    busy_changed = pyqtSignal(bool, str)
    playback_changed = pyqtSignal(bool)

    def __init__(self, prompts: ImportPrompts, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.prompts = prompts
        self.series: Series | None = None
        self.presenter: FramePresenter | None = None
        self.view_mode = "raw"
        self._requested_mode = "raw"
        self.gamma = self._requested_gamma = 1.0
        self.current_index = 0
        self._requested_index = 0
        self._pool = QThreadPool(QCoreApplication.instance())
        self._pool.setMaxThreadCount(2)
        self._tasks: dict[int, Task] = {}
        self._counter = 0
        self._open_token: int | None = None
        self._frame_token: int | None = None
        self._opening_path: Path | None = None
        self._closed = False
        self.is_playing = False
        self.playback_rate = 5
        self._automatic_token: int | None = None
        self._play_timer = QTimer(self)
        self._play_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._play_timer.setSingleShot(True)
        self._play_timer.timeout.connect(self._advance_playback)

    @property
    def is_busy(self) -> bool:
        return self._open_token is not None or self._frame_token is not None

    @property
    def can_play(self) -> bool:
        return (self.series is not None and self.series.frame_count > 1
                and self._open_token is None and not self._closed)

    @property
    def pending_task_count(self) -> int:
        """Includes abandoned, noninterruptible reads that are still finishing."""
        return len(self._tasks)

    def _submit(self, operation: Callable[[Event, Callable[[str], None]], object]) -> int:
        self._counter += 1
        task = Task(self._counter, operation)
        self._tasks[task.token] = task
        task.signals.result.connect(self._receive)
        task.signals.error.connect(self._failed)
        task.signals.progress.connect(self._progress)
        task.signals.finished.connect(self._finished)
        self._pool.start(task)
        return task.token

    def _abandon(self, token: int | None) -> None:
        if token is not None and token in self._tasks:
            self._tasks[token].cancelled.set()

    def _busy(self, text: str = "") -> None:
        if not text:
            text = "Otwieranie zapisu…" if self._open_token is not None else (
                f"Przygotowanie klatki {self._requested_index + 1}…"
                if self._frame_token is not None else "Gotowe"
            )
        self.busy_changed.emit(self.is_busy, text)

    def open_session(self, path: Path | None = None) -> None:
        self.pause()
        self._abandon(self._open_token)
        self._open_token = None
        self._busy()
        chosen = path if path is not None else self.prompts.choose_session()
        if chosen is not None and not self._closed:
            self._opening_path = Path(chosen)
            self._start_import()

    def _start_import(self, source: Path | None = None) -> None:
        path = self._opening_path
        if path is None:
            return
        gamma = self.gamma

        def read(cancelled: Event, report: Callable[[str], None]) -> object:
            result = prepare_import(path, source, cancelled=cancelled.is_set, progress=report)
            if isinstance(result, SourceRequest):
                return result
            report("Przygotowanie pierwszego obrazu…")
            presenter = FramePresenter(result.series)
            return PreparedImport(result, presenter, presenter.present(
                result.series.active_frame_index, presenter.initial_mode, gamma=gamma,
            ))

        self._open_token = self._submit(read)
        self._busy()

    def show_frame(self, index: int) -> None:
        self.pause()
        self._request_frame(index)

    def _request_frame(self, index: int, *, automatic: bool = False) -> None:
        series = self.series
        presenter = self.presenter
        if series is None or presenter is None or not 0 <= index < series.frame_count or self._closed:
            return
        self._abandon(self._frame_token)
        self._requested_index = index
        mode = self._requested_mode
        gamma = self._requested_gamma
        self._frame_token = self._submit(lambda cancelled, report: presenter.present(index, mode, gamma))
        self._automatic_token = self._frame_token if automatic else None
        self._busy()

    def set_view_mode(self, mode: str) -> None:
        if mode not in ("raw", "expanded_aligned") or self.presenter is None:
            return
        if mode == "expanded_aligned" and not self.presenter.registration.available:
            return
        self.pause()
        self._requested_mode = mode
        self._request_frame(self._requested_index)

    def set_gamma(self, gamma: float) -> None:
        if not isfinite(gamma) or gamma <= 0:
            raise ValueError("Gamma musi być dodatnią, skończoną liczbą.")
        self.pause()
        self._requested_gamma = gamma
        self._request_frame(self._requested_index)

    def step_frame(self, step: int) -> None:
        self.pause()
        self.show_frame(self._requested_index + step)

    def play(self) -> None:
        if (self.series is None or self.series.frame_count < 2 or self._closed
                or self._open_token is not None or self.is_playing):
            return
        self.is_playing = True
        self.playback_changed.emit(True)
        if self.current_index == self.series.frame_count - 1 and self._frame_token is None:
            self._request_frame(0, automatic=True)
        else:
            self._schedule_playback()

    def restart(self) -> None:
        self.pause()
        if (self.series is None or self.series.frame_count < 2 or self._closed
                or self._open_token is not None):
            return
        self.is_playing = True
        self.playback_changed.emit(True)
        self._request_frame(0, automatic=True)

    def pause(self) -> None:
        self._play_timer.stop()
        was_playing = self.is_playing
        self.is_playing = False
        if self._automatic_token is not None and self._automatic_token == self._frame_token:
            self._abandon(self._frame_token)
            self._frame_token = None
            self._requested_index = self.current_index
            self._requested_mode = self.view_mode
            self._requested_gamma = self.gamma
            self._busy()
        self._automatic_token = None
        if was_playing:
            self.playback_changed.emit(False)

    def set_playback_rate(self, rate: int) -> None:
        if rate not in (1, 2, 5, 10, 20):
            raise ValueError("Dostępne szybkości: 1, 2, 5, 10 i 20 kl./s.")
        self.playback_rate = rate
        if self._play_timer.isActive():
            self._schedule_playback()

    def _schedule_playback(self) -> None:
        if not self.is_playing or self.series is None or self.is_busy:
            return
        if self.current_index >= self.series.frame_count - 1:
            self.pause()
        else:
            self._play_timer.start(round(1000 / self.playback_rate))

    def _advance_playback(self) -> None:
        if self.is_playing and not self.is_busy:
            self._request_frame(self.current_index + 1, automatic=True)

    def cancel(self) -> None:
        self.pause()
        if self._open_token is not None:
            self._abandon(self._open_token)
            self._open_token = None
        else:
            self._abandon(self._frame_token)
            self._frame_token = None
            self._requested_index = self.current_index
            self._requested_mode = self.view_mode
            self._requested_gamma = self.gamma
        self._busy()

    @pyqtSlot(int, object)
    def _receive(self, token: int, result: object) -> None:
        if self._closed:
            return
        if token == self._open_token:
            if isinstance(result, SourceRequest):
                selected = self.prompts.choose_source(result.message, result.suggested_path)
                if token != self._open_token or self._closed:
                    return
                self._open_token = None
                if selected is not None:
                    self._start_import(selected)
                else:
                    self._busy()
                return
            if not isinstance(result, PreparedImport):
                return
            candidate = result.candidate
            if candidate.confirmation_reasons:
                accepted = self.prompts.confirm_source(
                    candidate.series.source_path, candidate.confirmation_reasons,
                )
                if token != self._open_token or self._closed:
                    return
                if not accepted:
                    self._open_token = None
                    self._busy()
                    return
            self._open_token = None
            self._abandon(self._frame_token)
            self._frame_token = None
            self.series = candidate.series
            self.presenter = result.presenter
            self.series_changed.emit(self.series)
            self._publish(result.view)
        elif token == self._frame_token and isinstance(result, PresentedFrame):
            self._frame_token = None
            if self.series is not None and result.series_id == self.series.identity:
                self._publish(result)

    def _publish(self, frame: PresentedFrame) -> None:
        self._automatic_token = None
        self.current_index = frame.frame.working_index
        self._requested_index = self.current_index
        self.view_mode = self._requested_mode = frame.mode
        self.gamma = self._requested_gamma = frame.gamma
        self.frame_changed.emit(frame)
        self._busy()
        self._schedule_playback()

    @pyqtSlot(int, str)
    def _failed(self, token: int, message: str) -> None:
        if self._closed or token not in (self._open_token, self._frame_token):
            return
        if token == self._open_token:
            self._open_token = None
        else:
            self._frame_token = None
            self._requested_index = self.current_index
            self._requested_mode = self.view_mode
            self._requested_gamma = self.gamma
        self.pause()
        self._busy()
        self.prompts.show_error(message)

    @pyqtSlot(int, str)
    def _progress(self, token: int, text: str) -> None:
        if token == self._open_token or (self._open_token is None and token == self._frame_token):
            self._busy(text)

    @pyqtSlot(int)
    def _finished(self, token: int) -> None:
        self._tasks.pop(token, None)

    def shutdown(self) -> None:
        self.pause()
        self._closed = True
        for task in self._tasks.values():
            task.cancelled.set()
        self._open_token = self._frame_token = None
