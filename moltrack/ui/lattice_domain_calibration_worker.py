"""Responsive worker lifecycle for final M3/M6 domain calibration."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from moltrack.analysis import (
    LatticeDomainCalibrationCanceled,
    LatticeDomainCalibrationReferenceDataset,
    LatticeDomainCalibrationReport,
    LatticeDomainCalibrationSweepSettings,
    M6DomainTypeAnalysisSource,
    run_lattice_domain_calibration_for_source,
    write_lattice_domain_calibration_report,
)


@dataclass(frozen=True)
class LatticeDomainCalibrationExecution:
    report: LatticeDomainCalibrationReport
    report_paths: dict[str, Path]


class _LatticeDomainCalibrationWorker(QObject):
    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(
        self,
        reference: LatticeDomainCalibrationReferenceDataset,
        sweep: LatticeDomainCalibrationSweepSettings,
        source: M6DomainTypeAnalysisSource,
        *,
        source_file_name: str,
        report_directory: str | Path,
        runner=run_lattice_domain_calibration_for_source,
        report_writer=write_lattice_domain_calibration_report,
    ) -> None:
        super().__init__()
        self._reference = reference
        self._sweep = sweep
        self._source = source
        self._source_file_name = str(source_file_name)
        self._report_directory = Path(report_directory)
        self._runner = runner
        self._report_writer = report_writer
        self._cancel_requested = threading.Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested.is_set()

    def cancel(self) -> None:
        self._cancel_requested.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            if self.cancel_requested:
                raise LatticeDomainCalibrationCanceled()
            report = self._runner(
                self._reference,
                self._sweep,
                self._source,
                source_file_name=self._source_file_name,
                progress_callback=self.progress.emit,
                cancel_callback=self._cancel_requested.is_set,
            )
            if self.cancel_requested:
                raise LatticeDomainCalibrationCanceled()
            paths = self._report_writer(report, self._report_directory)
            if self.cancel_requested:
                raise LatticeDomainCalibrationCanceled()
        except LatticeDomainCalibrationCanceled:
            self.canceled.emit()
        except Exception as exc:
            if self.cancel_requested:
                self.canceled.emit()
            else:
                self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.finished.emit(
                LatticeDomainCalibrationExecution(
                    report=report,
                    report_paths=dict(paths),
                )
            )


class LatticeDomainCalibrationController(QObject):
    """Own one calibration thread and expose cooperative cancellation."""

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()
    running_changed = pyqtSignal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        runner=run_lattice_domain_calibration_for_source,
        report_writer=write_lattice_domain_calibration_report,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._report_writer = report_writer
        self._thread: QThread | None = None
        self._worker: _LatticeDomainCalibrationWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None

    def start(
        self,
        reference: LatticeDomainCalibrationReferenceDataset,
        sweep: LatticeDomainCalibrationSweepSettings,
        source: M6DomainTypeAnalysisSource,
        *,
        source_file_name: str,
        report_directory: str | Path,
    ) -> bool:
        if self.is_running:
            return False
        thread = QThread(self)
        worker = _LatticeDomainCalibrationWorker(
            reference,
            sweep,
            source,
            source_file_name=source_file_name,
            report_directory=report_directory,
            runner=self._runner,
            report_writer=self._report_writer,
        )
        self._thread = thread
        self._worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress.emit)
        worker.finished.connect(self.finished.emit)
        worker.failed.connect(self.failed.emit)
        worker.canceled.connect(self.canceled.emit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.canceled.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.canceled.connect(thread.quit)
        thread.finished.connect(self._cleanup)
        self.running_changed.emit(True)
        thread.start()
        return True

    def cancel(self) -> bool:
        if self._worker is None:
            return False
        self._worker.cancel()
        return True

    def shutdown(self) -> bool:
        return not self.is_running

    @pyqtSlot()
    def _cleanup(self) -> None:
        self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self.running_changed.emit(False)
