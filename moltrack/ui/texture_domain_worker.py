from __future__ import annotations

from dataclasses import dataclass
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from moltrack.analysis import (
    MolecularFrameRange,
    TextureDomainAnalysisSettings,
    analyze_texture_domain_range,
)
from moltrack.core import MolTrackImageSeries


@dataclass(frozen=True)
class TextureDomainAnalysisProgress:
    completed_count: int
    total_count: int
    frame_index: int

    def __post_init__(self) -> None:
        completed = int(self.completed_count)
        total = int(self.total_count)
        frame_index = int(self.frame_index)
        if completed < 0 or total < 0 or completed > total or frame_index < 0:
            raise ValueError("Texture-domain progress is invalid.")
        object.__setattr__(self, "completed_count", completed)
        object.__setattr__(self, "total_count", total)
        object.__setattr__(self, "frame_index", frame_index)


class _TextureDomainAnalysisWorker(QObject):
    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(
        self,
        analyzer,
        series: MolTrackImageSeries,
        frame_range: MolecularFrameRange,
        *,
        source_view: str,
        settings: TextureDomainAnalysisSettings,
        use_segmentation_centroids: bool,
    ) -> None:
        super().__init__()
        self._analyzer = analyzer
        self._series = series
        self._frame_range = frame_range
        self._source_view = source_view
        self._settings = settings
        self._use_segmentation_centroids = bool(use_segmentation_centroids)
        self._cancel_requested = Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested.is_set()

    def cancel(self) -> None:
        self._cancel_requested.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._analyzer(
                self._series,
                self._frame_range,
                source_view=self._source_view,
                settings=self._settings,
                use_segmentation_centroids=self._use_segmentation_centroids,
                progress_callback=self._report_progress,
                cancel_requested=self._cancel_requested.is_set,
            )
        except Exception as exc:
            if self.cancel_requested:
                self.canceled.emit()
            else:
                self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        if self.cancel_requested:
            self.canceled.emit()
            return
        self.finished.emit(result)

    def _report_progress(
        self,
        completed_count: int,
        total_count: int,
        frame_index: int,
    ) -> None:
        if self.cancel_requested:
            raise RuntimeError("Texture-domain analysis canceled.")
        self.progress.emit(
            TextureDomainAnalysisProgress(
                completed_count=completed_count,
                total_count=total_count,
                frame_index=frame_index,
            )
        )


class TextureDomainAnalysisController(QObject):
    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()
    running_changed = pyqtSignal(bool)

    def __init__(
        self,
        *,
        analyzer=analyze_texture_domain_range,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._analyzer = analyzer
        self._thread: QThread | None = None
        self._worker: _TextureDomainAnalysisWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None

    def start(
        self,
        series: MolTrackImageSeries,
        frame_range: MolecularFrameRange,
        *,
        source_view: str,
        settings: TextureDomainAnalysisSettings,
        use_segmentation_centroids: bool,
    ) -> bool:
        if self.is_running:
            return False
        thread = QThread(self)
        worker = _TextureDomainAnalysisWorker(
            self._analyzer,
            series,
            frame_range,
            source_view=source_view,
            settings=settings,
            use_segmentation_centroids=use_segmentation_centroids,
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

    def shutdown(self, *, wait_ms: int = 5000) -> bool:
        if self._worker is None:
            return True
        self._worker.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.quit()
        return bool(thread.wait(max(0, int(wait_ms))))

    @pyqtSlot()
    def _cleanup(self) -> None:
        self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self.running_changed.emit(False)
