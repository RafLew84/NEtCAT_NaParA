from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Literal

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from moltrack.analysis import (
    M6_DOMAIN_TYPE_ANALYSIS_COMPUTE_PHASES,
    M6DomainTypeAnalysisComputation,
    M6DomainTypeAnalysisComputePhase,
    M6DomainTypeAnalysisContext,
    M6DomainTypeAnalysisOutcome,
    M6DomainTypeAnalysisSource,
    M6DomainTypeAnalysisStore,
    M6DomainTypeClassificationSettings,
)


M6DomainTypeAnalysisPhase = M6DomainTypeAnalysisComputePhase | Literal["publishing"]
M6_DOMAIN_TYPE_ANALYSIS_PHASES: tuple[M6DomainTypeAnalysisPhase, ...] = (
    *M6_DOMAIN_TYPE_ANALYSIS_COMPUTE_PHASES,
    "publishing",
)

_PHASE_MESSAGES = {
    "extracting_observations": "Extracting domain observations...",
    "complete_linkage": "Classifying domain types with complete-linkage...",
    "aggregating": "Aggregating domain type statistics...",
    "publishing": "Publishing domain type result...",
}


@dataclass(frozen=True)
class M6DomainTypeAnalysisProgress:
    phase: M6DomainTypeAnalysisPhase
    phase_number: int
    total_phase_count: int = len(M6_DOMAIN_TYPE_ANALYSIS_PHASES)
    message: str = ""

    def __post_init__(self) -> None:
        if self.phase not in M6_DOMAIN_TYPE_ANALYSIS_PHASES:
            raise ValueError("Unsupported M6 domain type analysis phase.")
        expected_count = M6_DOMAIN_TYPE_ANALYSIS_PHASES.index(self.phase) + 1
        if self.phase_number != expected_count:
            raise ValueError("phase_number must match phase order.")
        if self.total_phase_count != len(M6_DOMAIN_TYPE_ANALYSIS_PHASES):
            raise ValueError("total_phase_count must match the phase contract.")
        message = str(self.message).strip()
        if not message:
            object.__setattr__(self, "message", _PHASE_MESSAGES[self.phase])


class _M6DomainTypeAnalysisCanceled(RuntimeError):
    pass


class _M6DomainTypeAnalysisWorker(QObject):
    progress = pyqtSignal(object)
    computed = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(
        self,
        store: M6DomainTypeAnalysisStore,
        source: M6DomainTypeAnalysisSource,
        classification_settings: M6DomainTypeClassificationSettings,
    ) -> None:
        super().__init__()
        self._store = store
        self._source = source
        self._classification_settings = classification_settings
        self._cancel_requested = threading.Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested.is_set()

    def cancel(self) -> None:
        self._cancel_requested.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self._raise_if_canceled()
            computation = self._store.compute(
                self._source,
                classification_settings=self._classification_settings,
                progress_callback=self._report_progress,
            )
            self._raise_if_canceled()
        except _M6DomainTypeAnalysisCanceled:
            self.canceled.emit()
        except Exception as exc:
            if self.cancel_requested:
                self.canceled.emit()
            else:
                self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.computed.emit(computation)

    def _report_progress(self, phase: str) -> None:
        self._raise_if_canceled()
        self.progress.emit(_progress_for_phase(phase))

    def _raise_if_canceled(self) -> None:
        if self.cancel_requested:
            raise _M6DomainTypeAnalysisCanceled()


class M6DomainTypeAnalysisController(QObject):
    """Own one classification thread and publish only its still-current result."""

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()
    running_changed = pyqtSignal(bool)
    state_changed = pyqtSignal(object)

    def __init__(
        self,
        store: M6DomainTypeAnalysisStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._thread: QThread | None = None
        self._worker: _M6DomainTypeAnalysisWorker | None = None
        self._pending_restore: tuple[
            M6DomainTypeAnalysisContext,
            M6DomainTypeAnalysisOutcome,
        ] | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None

    def start(
        self,
        source: M6DomainTypeAnalysisSource,
        *,
        classification_settings: M6DomainTypeClassificationSettings,
    ) -> bool:
        if self.is_running:
            return False
        thread = QThread(self)
        worker = _M6DomainTypeAnalysisWorker(
            self._store,
            source,
            classification_settings,
        )
        self._thread = thread
        self._worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress.emit)
        worker.computed.connect(self._on_computed)
        worker.failed.connect(self.failed.emit)
        worker.canceled.connect(self.canceled.emit)
        worker.computed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.canceled.connect(worker.deleteLater)
        worker.computed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.canceled.connect(thread.quit)
        thread.finished.connect(self._cleanup)
        self.running_changed.emit(True)
        thread.start()
        return True

    def cancel_for_series_change(self) -> bool:
        return self._cancel_active()

    def clear_for_series_change(self) -> None:
        self._cancel_active()
        self._pending_restore = None
        self._store.clear()
        self.state_changed.emit(self._store.state)

    def invalidate(self, reason: str) -> bool:
        self._pending_restore = None
        canceled = self._cancel_active()
        invalidated = self._store.invalidate(reason)
        if invalidated:
            self.state_changed.emit(self._store.state)
        return canceled or invalidated

    def restore_persisted(
        self,
        context: M6DomainTypeAnalysisContext,
        outcome: M6DomainTypeAnalysisOutcome,
    ) -> None:
        if self.is_running:
            self._cancel_active()
            self._pending_restore = (context, outcome)
            return
        self._store.restore(context, outcome)
        self.state_changed.emit(self._store.state)

    def mark_out_of_date(self, reason: str) -> None:
        self._pending_restore = None
        if self.is_running:
            self._cancel_active()
        self._store.mark_out_of_date(reason)
        self.state_changed.emit(self._store.state)

    def shutdown(self) -> bool:
        return not self.is_running

    def _cancel_active(self) -> bool:
        if self._worker is None:
            return False
        self._worker.cancel()
        return True

    @pyqtSlot(object)
    def _on_computed(self, computation: M6DomainTypeAnalysisComputation) -> None:
        worker = self._worker
        if worker is None or worker.cancel_requested:
            self.canceled.emit()
            return
        self.progress.emit(_progress_for_phase("publishing"))
        if self._worker is not worker or worker.cancel_requested:
            self.canceled.emit()
            return
        try:
            outcome = self._store.publish(computation)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.state_changed.emit(self._store.state)
        self.finished.emit(outcome)

    @pyqtSlot()
    def _cleanup(self) -> None:
        self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        pending_restore = self._pending_restore
        self._pending_restore = None
        if pending_restore is not None:
            try:
                self._store.restore(*pending_restore)
            except Exception as exc:
                self.failed.emit(str(exc) or exc.__class__.__name__)
            else:
                self.state_changed.emit(self._store.state)
        self.running_changed.emit(False)


def _progress_for_phase(phase: str) -> M6DomainTypeAnalysisProgress:
    try:
        phase_index = M6_DOMAIN_TYPE_ANALYSIS_PHASES.index(phase)
    except ValueError as exc:
        raise ValueError(f"Unsupported M6 domain type analysis phase: {phase}") from exc
    return M6DomainTypeAnalysisProgress(
        phase=M6_DOMAIN_TYPE_ANALYSIS_PHASES[phase_index],
        phase_number=phase_index + 1,
    )
