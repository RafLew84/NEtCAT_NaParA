"""Commit a validated import atomically and discard obsolete frame requests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QCoreApplication, QObject, QThreadPool, QTimer, Qt, pyqtSignal, pyqtSlot

from stmdomains.core.frame_presentation import FramePresenter, PresentedFrame
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.series import Series
from stmdomains.analysis import analyze_frame, recalculate_domains, discover_classes, recalculate_class_acceptance, recalculate_order
from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.analysis.series_analysis import FrameOutcome
from stmdomains.io.moltrack_import import ImportCandidate, SourceRequest, prepare_import
from stmdomains.ui.import_prompts import ImportPrompts
from stmdomains.ui.tasks import Task
from stmdomains.ui.series_runner import SeriesRun, SeriesRunner


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
    series_analysis_changed = pyqtSignal()

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
        self._analysis_token: int | None = None
        self._results: dict[int, FrameAnalysis] = {}
        self._previous_results: dict[int, FrameAnalysis] = {}
        self._selected_versions: dict[int, str] = {}
        self._active_catalogue: ClassCatalogue | None = None
        self._published: PresentedFrame | None = None
        self._opening_path: Path | None = None
        self._closed = False
        self.is_playing = False
        self.playback_rate = 5
        self._automatic_token: int | None = None
        self._play_timer = QTimer(self)
        self._play_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._play_timer.setSingleShot(True)
        self._play_timer.timeout.connect(self._advance_playback)
        self._series_runner = SeriesRunner(self)
        self._series_runner.changed.connect(self._series_changed)
        self._series_runner.catalogue_ready.connect(self._accept_series_catalogue)
        self._series_runner.frame_ready.connect(self._accept_series_frame)
        self._series_runner.failed.connect(self.prompts.show_error)

    @property
    def is_busy(self) -> bool:
        return self.series_running or any(token is not None for token in (
            self._open_token, self._frame_token, self._analysis_token,
        ))

    @property
    def result(self) -> FrameAnalysis | None:
        return self.previous_result if self.result_version == "previous" else self.latest_result

    @property
    def latest_result(self) -> FrameAnalysis | None:
        return self._results.get(self.current_index)

    @property
    def previous_result(self) -> FrameAnalysis | None:
        return self._previous_results.get(self.current_index)

    @property
    def result_version(self) -> str:
        return self._selected_versions.get(self.current_index, "new")

    @property
    def active_catalogue(self) -> ClassCatalogue | None:
        return self._active_catalogue

    @property
    def catalogue_status(self) -> str:
        if self.result is None:
            return "unanalysed"
        catalogue = self.result.catalogue
        if catalogue is None:
            return "unavailable"
        if self.active_catalogue is not None and catalogue.identifier != self.active_catalogue.identifier:
            return "earlier"
        return "current"

    def select_result(self, version: str) -> None:
        if self.is_busy or version not in ("new", "previous") or self._closed:
            return
        if version == "previous" and self.previous_result is None:
            return
        self.pause()
        self._selected_versions[self.current_index] = version
        if self.result is not None and self.result.catalogue is not None:
            self._active_catalogue = self.result.catalogue
        self._refresh_result()
        self._busy()

    @property
    def can_analyze(self) -> bool:
        return self.presenter is not None and self._published is not None and not self.is_busy and not self._closed

    @property
    def can_tune_acceptance(self) -> bool:
        result = self.result
        return self.can_analyze and result is not None and result.status == "complete" and result.catalogue is not None

    @property
    def can_tune_order(self) -> bool:
        return self.can_tune_acceptance

    @property
    def current_order_settings(self) -> OrderSettings:
        return OrderSettings.from_parameters(self.result.parameters) if self.result else OrderSettings()

    @property
    def can_play(self) -> bool:
        return (self.series is not None and self.series.frame_count > 1
                and self._open_token is None and self._analysis_token is None
                and not self.series_running and not self._closed)

    @property
    def pending_task_count(self) -> int:
        """Includes abandoned, noninterruptible reads that are still finishing."""
        return len(self._tasks) + self._series_runner.pending_task_count

    @property
    def series_running(self) -> bool:
        return self._series_runner.running

    @property
    def series_run(self) -> SeriesRun | None:
        return self._series_runner.state

    def start_series_analysis(self, plan: SeriesAnalysisPlan) -> None:
        self.pause()
        if not self.can_analyze or self.presenter is None:
            return
        try:
            self._series_runner.start(self.presenter, plan, self.active_catalogue)
        except ValueError as error:
            self.prompts.show_error(str(error))

    def _series_changed(self) -> None:
        self.series_analysis_changed.emit()
        self._busy()

    def _accept_series_catalogue(self, catalogue: ClassCatalogue) -> None:
        if self.series is not None and catalogue.series_id == self.series.identity:
            self._active_catalogue = catalogue

    def _accept_series_frame(self, outcome: FrameOutcome) -> None:
        result = outcome.result
        if result is None or self.series is None or result.series_id != self.series.identity:
            return
        index = result.working_index
        previous = self._results.get(index)
        if previous is not None and previous.status == "complete":
            if result.status != "complete":
                return  # Keep the earlier result; the run table shows this attempt's refusal.
            self._previous_results[index] = previous
        else:
            self._previous_results.pop(index, None)
        self._results[index] = result
        self._selected_versions[index] = "new"
        if index == self.current_index and self._frame_token is None:
            self._refresh_result()

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
                self.series_run.message if self.series_running and self.series_run is not None else
                "Analiza klatki…" if self._analysis_token is not None else
                f"Przygotowanie klatki {self._requested_index + 1}…"
                if self._frame_token is not None else "Gotowe"
            )
        self.busy_changed.emit(self.is_busy, text)

    def open_session(self, path: Path | None = None) -> None:
        self.pause()
        self._series_runner.cancel()
        self._cancel_analysis()
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
        if index != self.current_index:
            self._cancel_analysis()
        self._abandon(self._frame_token)
        self._requested_index = index
        mode = self._requested_mode
        gamma = self._requested_gamma
        self._frame_token = self._submit(lambda cancelled, report: presenter.present(index, mode, gamma))
        self._automatic_token = self._frame_token if automatic else None
        self._busy()

    def analyze_current_frame(self) -> None:
        self.pause()
        if not self.can_analyze or self.presenter is None:
            return
        presenter, index = self.presenter, self.current_index
        settings = DomainSettings.from_parameters(self.result.parameters) if self.result else DomainSettings()
        acceptance = ClassAcceptanceSettings.from_parameters(self.result.parameters) if self.result else ClassAcceptanceSettings()
        order_settings = self.current_order_settings
        active = self.active_catalogue
        catalogue = active if active is not None and active.scope != "current_frame" else None
        k = active.k if active else 5
        self._analysis_token = self._submit(lambda cancelled, report: analyze_frame(
            presenter.analysis_input(index), settings=settings, k=k, catalogue=catalogue, acceptance=acceptance,
            order_settings=order_settings,
            cancelled=cancelled.is_set, progress=report,
        ))
        self._busy()

    def fit_current_classes(self, settings: ClassFitSettings) -> None:
        self.pause()
        if not self.can_analyze or self.presenter is None or self.series is None:
            return
        presenter, index, count = self.presenter, self.current_index, self.series.frame_count
        domain_settings = DomainSettings.from_parameters(self.result.parameters) if self.result else DomainSettings()
        order_settings = self.current_order_settings
        self._analysis_token = self._submit(lambda cancelled, report: discover_classes(
            presenter.analysis_input, frame_count=count, current_index=index, settings=settings,
            domain_settings=domain_settings, order_settings=order_settings, cancelled=cancelled.is_set, progress=report,
        ))
        self._busy()

    def recalculate_domains(self, settings: DomainSettings) -> None:
        self.pause()
        if not self.can_analyze or self.presenter is None:
            return
        presenter, index, previous = self.presenter, self.current_index, self.result
        active = self.active_catalogue

        def calculate(cancelled: Event, report: Callable[[str], None]) -> FrameAnalysis:
            data = presenter.analysis_input(index)
            if previous is None:
                return analyze_frame(data, settings=settings, k=active.k if active else 5,
                                     catalogue=active if active and active.scope != "current_frame" else None,
                                     cancelled=cancelled.is_set, progress=report)
            return recalculate_domains(data, previous, settings, cancelled=cancelled.is_set, progress=report)

        self._analysis_token = self._submit(calculate)
        self._busy()

    def _cancel_analysis(self) -> None:
        self._abandon(self._analysis_token)
        self._analysis_token = None

    def recalculate_class_acceptance(self, settings: ClassAcceptanceSettings) -> None:
        self.pause()
        if not self.can_tune_acceptance or self.presenter is None or self.result is None:
            return
        presenter, index, previous = self.presenter, self.current_index, self.result
        self._analysis_token = self._submit(lambda cancelled, report: recalculate_class_acceptance(
            presenter.analysis_input(index), previous, settings, cancelled=cancelled.is_set, progress=report,
        ))
        self._busy()

    def recalculate_order(self, settings: OrderSettings) -> None:
        self.pause()
        if not self.can_tune_order or self.presenter is None or self.result is None:
            return
        presenter, index, previous = self.presenter, self.current_index, self.result
        self._analysis_token = self._submit(lambda cancelled, report: recalculate_order(
            presenter.analysis_input(index), previous, settings, cancelled=cancelled.is_set, progress=report,
        ))
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
        if not self.can_play or self.series is None or self.is_playing:
            return
        self.is_playing = True
        self.playback_changed.emit(True)
        if self._frame_token is not None:
            # The requested frame becomes playback's first step, cancellable by pause.
            self._automatic_token = self._frame_token
        elif self.current_index == self.series.frame_count - 1:
            self._request_frame(0, automatic=True)
        else:
            self._schedule_playback()

    def restart(self) -> None:
        self.pause()
        if not self.can_play:
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
        self._series_runner.cancel()
        self._cancel_analysis()
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
        self._refresh_result()

    @pyqtSlot(int, object)
    def _receive(self, token: int, result: object) -> None:
        if self._closed:
            return
        if token == self._analysis_token and isinstance(result, FrameAnalysis):
            if (self.series is not None and result.series_id == self.series.identity
                    and result.working_index == self.current_index == self._requested_index
                    and result.source_index == self.series.frame(self.current_index).source_index):
                previous = self.latest_result
                if previous is not None and previous.status == "complete" and result.status != "complete":
                    self._failed(token, result.message)
                    return
                if (previous is not None and previous.status == result.status == "complete"
                        and previous.metadata.get("input_sha256") == result.metadata.get("input_sha256")):
                    self._previous_results[self.current_index] = previous
                else:
                    self._previous_results.pop(self.current_index, None)
                self._results[self.current_index] = result
                self._selected_versions[self.current_index] = "new"
                if result.catalogue is not None:
                    self._active_catalogue = result.catalogue
                if self._frame_token is None:
                    self._refresh_result()
            self._analysis_token = None
            self._busy()
        elif token == self._open_token:
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
            self._results.clear()
            self._previous_results.clear()
            self._selected_versions.clear()
            self._active_catalogue = None
            self._series_runner.reset()
            self._published = None
            self.series_changed.emit(self.series)
            self._publish(result.view)
        elif token == self._frame_token and isinstance(result, PresentedFrame):
            self._frame_token = None
            if self.series is not None and result.series_id == self.series.identity:
                self._publish(result)

    def _publish(self, frame: PresentedFrame) -> None:
        index = frame.frame.working_index
        result = (self._previous_results.get(index) if self._selected_versions.get(index) == "previous"
                  else self._results.get(index))
        frame = replace(frame, result=result)
        self._published = frame
        self._automatic_token = None
        self.current_index = frame.frame.working_index
        self._requested_index = self.current_index
        self.view_mode = self._requested_mode = frame.mode
        self.gamma = self._requested_gamma = frame.gamma
        self.frame_changed.emit(frame)
        self._busy()
        self._schedule_playback()

    def _refresh_result(self) -> None:
        if self._published is not None and self._published.result is not self.result:
            self._published = replace(self._published, result=self.result)
            self.frame_changed.emit(self._published)

    @pyqtSlot(int, str)
    def _failed(self, token: int, message: str) -> None:
        if self._closed or token not in (self._open_token, self._frame_token, self._analysis_token):
            return
        if token == self._analysis_token:
            self._analysis_token = None
        elif token == self._open_token:
            self._open_token = None
        else:
            self._frame_token = None
            self._requested_index = self.current_index
            self._requested_mode = self.view_mode
            self._requested_gamma = self.gamma
        self.pause()
        self._busy()
        self._refresh_result()
        self.prompts.show_error(message)

    @pyqtSlot(int, str)
    def _progress(self, token: int, text: str) -> None:
        if token == self._open_token or (self._open_token is None and (
            token == self._analysis_token or (self._analysis_token is None and token == self._frame_token)
        )):
            self._busy(text)

    @pyqtSlot(int)
    def _finished(self, token: int) -> None:
        self._tasks.pop(token, None)

    def shutdown(self) -> None:
        self.pause()
        self._series_runner.shutdown()
        self._closed = True
        for task in self._tasks.values():
            task.cancelled.set()
        self._open_token = self._frame_token = self._analysis_token = None

    def wait_for_workers(self) -> None:
        """Join cancelled work before Qt destroys the signals used by run()."""
        self._pool.waitForDone()
        self._series_runner.wait_for_workers()
