"""Asynchronous controller for molecular stacking analysis."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from moltrack.analysis import (
    MolecularOrientationFrameData,
    MolecularOrientationStore,
    MolecularStackingDisplayResult,
    analyze_molecular_stacking,
    build_molecular_orientation_prototype_analysis,
)


def analyze_molecular_stacking_display(
    frames: tuple[MolecularOrientationFrameData, ...],
) -> MolecularStackingDisplayResult:
    prototypes = build_molecular_orientation_prototype_analysis(frames)
    stacking = analyze_molecular_stacking(frames, prototypes)
    return MolecularStackingDisplayResult(
        frames=frames,
        prototype_analysis=prototypes,
        stacking_analysis=stacking,
    )


def build_molecular_stacking_input_frames(
    frame_results,
    store: MolecularOrientationStore,
    *,
    source_view: str,
) -> tuple[MolecularOrientationFrameData, ...]:
    if not isinstance(store, MolecularOrientationStore):
        raise TypeError("store must be a MolecularOrientationStore.")
    normalized_source_view = str(source_view)
    frames_by_index: dict[int, MolecularOrientationFrameData] = {}
    for frame_result in frame_results:
        if str(frame_result.source_view) != normalized_source_view:
            continue
        m6 = frame_result.m6_orientation_analysis
        rows = (
            None
            if m6 is None
            else m6.lattice_row_assignment_analysis
        )
        if rows is None:
            continue
        frame_index = int(frame_result.frame_index)
        frame = MolecularOrientationFrameData(
            frame_index=frame_index,
            row_assignment=rows,
            measurements=tuple(
                measurement
                for measurement in store.measurements_for_frame(
                    frame_index,
                    source_view=normalized_source_view,
                )
                if (
                    measurement.provenance.orientation_reference
                    == "sample_x_axis_counterclockwise"
                )
            ),
        )
        previous = frames_by_index.get(frame_index)
        if previous is not None and previous != frame:
            raise ValueError(
                "Duplicate stacking frame has inconsistent M6 data."
            )
        frames_by_index[frame_index] = frame
    return tuple(
        frames_by_index[index]
        for index in sorted(frames_by_index)
    )


class _MolecularStackingWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        analyzer,
        frames: tuple[MolecularOrientationFrameData, ...],
    ) -> None:
        super().__init__()
        self._analyzer = analyzer
        self._frames = tuple(frames)

    def run(self) -> None:
        try:
            result = self._analyzer(self._frames)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.finished.emit(result)


class MolecularStackingAnalysisController(QObject):
    """Own one current stacking result and its worker thread."""

    running_changed = pyqtSignal(bool)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        analyzer=analyze_molecular_stacking_display,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._analyzer = analyzer
        self._running = False
        self._series = None
        self._m6_context = None
        self._display_result: MolecularStackingDisplayResult | None = None
        self._thread: QThread | None = None
        self._worker: _MolecularStackingWorker | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def bound_m6_context(self):
        return self._m6_context

    def current_result(
        self,
        *,
        series,
        m6_context,
    ) -> MolecularStackingDisplayResult | None:
        if (
            series is None
            or self._series is not series
            or self._m6_context is not m6_context
        ):
            return None
        return self._display_result

    def start(
        self,
        frames: tuple[MolecularOrientationFrameData, ...],
        *,
        series,
        m6_context,
    ) -> bool:
        normalized_frames = tuple(frames)
        if self._running or not normalized_frames or series is None:
            return False
        self._running = True
        self._series = series
        self._m6_context = m6_context
        self._display_result = None

        thread = QThread(self)
        worker = _MolecularStackingWorker(
            self._analyzer,
            normalized_frames,
        )
        self._thread = thread
        self._worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self.failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._cleanup)
        self.running_changed.emit(True)
        thread.start()
        return True

    def invalidate(self) -> None:
        if self._running:
            raise RuntimeError(
                "Cannot invalidate stacking during active analysis."
            )
        self._series = None
        self._m6_context = None
        self._display_result = None

    def _on_finished(self, result) -> None:
        if not isinstance(result, MolecularStackingDisplayResult):
            self.failed.emit(
                "Stacking analyzer returned an invalid result."
            )
            return
        self._display_result = result
        self.finished.emit(result)

    def _cleanup(self) -> None:
        self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self._running = False
        self.running_changed.emit(False)


__all__ = [
    "MolecularStackingAnalysisController",
    "analyze_molecular_stacking_display",
    "build_molecular_stacking_input_frames",
]
