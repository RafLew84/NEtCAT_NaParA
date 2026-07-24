"""Asynchronous hierarchical molecular-order classification for the GUI."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from moltrack.analysis import (
    MolecularFrameRangeAnalysisScope,
    MolecularOrderHierarchy,
    MolecularOrderTypeClassificationResult,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeSessionState,
    MolecularOrderTypeSummary,
    MolecularStackingDisplayResult,
    build_molecular_order_hierarchy,
    build_molecular_order_type_summary,
    classify_molecular_order_types,
    molecular_order_hierarchy_fingerprint,
)
from moltrack.visualization.molecular_order_type_plot_data import (
    MolecularOrderOrientationDistributionData,
    build_molecular_order_orientation_distribution_data,
)


@dataclass(frozen=True)
class MolecularOrderTypeAnalysisResult:
    hierarchy: MolecularOrderHierarchy
    classification: MolecularOrderTypeClassificationResult
    summary: MolecularOrderTypeSummary
    orientation_distribution: MolecularOrderOrientationDistributionData

    def __post_init__(self) -> None:
        if not isinstance(self.hierarchy, MolecularOrderHierarchy):
            raise TypeError("hierarchy must be MolecularOrderHierarchy.")
        if not isinstance(
            self.classification,
            MolecularOrderTypeClassificationResult,
        ):
            raise TypeError(
                "classification must be MolecularOrderTypeClassificationResult."
            )
        if not isinstance(self.summary, MolecularOrderTypeSummary):
            raise TypeError("summary must be MolecularOrderTypeSummary.")
        if not isinstance(
            self.orientation_distribution,
            MolecularOrderOrientationDistributionData,
        ):
            raise TypeError(
                "orientation_distribution has an invalid type."
            )
        if (
            self.classification.hierarchy_fingerprint
            != molecular_order_hierarchy_fingerprint(self.hierarchy)
        ):
            raise ValueError(
                "Classification must reference the result hierarchy."
            )
        if self.summary.classification is not self.classification:
            raise ValueError(
                "Summary must contain the exact result classification."
            )


def analyze_molecular_order_types(
    hierarchy: MolecularOrderHierarchy,
    analysis_scope: MolecularFrameRangeAnalysisScope,
    settings: MolecularOrderTypeClassificationSettings,
    display_result: MolecularStackingDisplayResult | None = None,
) -> MolecularOrderTypeAnalysisResult:
    classification = classify_molecular_order_types(
        hierarchy,
        analysis_scope=analysis_scope,
        settings=settings,
    )
    return MolecularOrderTypeAnalysisResult(
        hierarchy=hierarchy,
        classification=classification,
        summary=build_molecular_order_type_summary(classification),
        orientation_distribution=(
            build_molecular_order_orientation_distribution_data(
                classification,
                display_result=display_result,
            )
        ),
    )


def build_molecular_order_hierarchy_from_frame_results(
    frame_results,
    display_result: MolecularStackingDisplayResult,
) -> MolecularOrderHierarchy:
    """Join current M6 lattice results with the exact stacking display."""

    if not isinstance(display_result, MolecularStackingDisplayResult):
        raise TypeError(
            "display_result must be MolecularStackingDisplayResult."
        )
    analyses_by_frame = {}
    for frame_result in tuple(frame_results):
        frame_index = int(frame_result.frame_index)
        analysis = frame_result.m6_orientation_analysis
        if analysis is None:
            continue
        previous = analyses_by_frame.get(frame_index)
        if previous is not None and previous != analysis:
            raise ValueError(
                "Duplicate frame results contain inconsistent M6 analyses."
            )
        analyses_by_frame[frame_index] = analysis

    lattice_analyses = {}
    row_analyses = {}
    for frame in display_result.frames:
        try:
            analysis = analyses_by_frame[frame.frame_index]
        except KeyError as exc:
            raise ValueError(
                "Stacking display references a frame without M6 analysis."
            ) from exc
        lattice = analysis.lattice_domain_analysis
        rows = analysis.lattice_row_assignment_analysis
        if lattice is None or rows is None:
            raise ValueError(
                "Hierarchical types require lattice domains and row "
                "assignments for every stacking frame."
            )
        if rows != frame.row_assignment:
            raise ValueError(
                "Stacking display row assignments do not match current M6."
            )
        lattice_analyses[frame.frame_index] = lattice
        row_analyses[frame.frame_index] = rows
    return build_molecular_order_hierarchy(
        lattice_analyses,
        row_analyses,
        display_result.stacking_analysis,
    )


@dataclass(frozen=True)
class _WorkerSuccess:
    context_token: object
    result: MolecularOrderTypeAnalysisResult


@dataclass(frozen=True)
class _WorkerFailure:
    context_token: object
    message: str


class _MolecularOrderTypeWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(
        self,
        analyzer,
        hierarchy: MolecularOrderHierarchy | None,
        frame_results: tuple[object, ...],
        hierarchy_builder,
        restore_state: MolecularOrderTypeSessionState | None,
        analysis_scope: MolecularFrameRangeAnalysisScope,
        settings: MolecularOrderTypeClassificationSettings,
        context_token: object,
        display_result: MolecularStackingDisplayResult | None,
    ) -> None:
        super().__init__()
        self._analyzer = analyzer
        self._hierarchy = hierarchy
        self._frame_results = frame_results
        self._hierarchy_builder = hierarchy_builder
        self._restore_state = restore_state
        self._analysis_scope = analysis_scope
        self._settings = settings
        self._context_token = context_token
        self._display_result = display_result

    def run(self) -> None:
        try:
            hierarchy = self._hierarchy
            if hierarchy is None:
                hierarchy = self._hierarchy_builder(
                    self._frame_results,
                    self._display_result,
                )
            if self._restore_state is None:
                result = self._analyzer(
                    hierarchy,
                    self._analysis_scope,
                    self._settings,
                    self._display_result,
                )
            else:
                classification = (
                    self._restore_state.restore_classification_for(hierarchy)
                )
                if classification is None:
                    raise ValueError(
                        "Saved hierarchical type result does not match "
                        "the current M6 and stacking dependencies."
                    )
                result = MolecularOrderTypeAnalysisResult(
                    hierarchy=hierarchy,
                    classification=classification,
                    summary=build_molecular_order_type_summary(
                        classification
                    ),
                    orientation_distribution=(
                        build_molecular_order_orientation_distribution_data(
                            classification,
                            display_result=self._display_result,
                        )
                    ),
                )
            if not isinstance(result, MolecularOrderTypeAnalysisResult):
                raise TypeError(
                    "Molecular-order analyzer returned an invalid result."
                )
        except Exception as exc:
            self.failed.emit(
                _WorkerFailure(
                    self._context_token,
                    str(exc) or exc.__class__.__name__,
                )
            )
            return
        self.finished.emit(_WorkerSuccess(self._context_token, result))


class MolecularOrderTypeAnalysisController(QObject):
    """Own one result bound by identity to one stacking display."""

    running_changed = pyqtSignal(bool)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        analyzer=analyze_molecular_order_types,
        hierarchy_builder=(
            build_molecular_order_hierarchy_from_frame_results
        ),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._analyzer = analyzer
        self._hierarchy_builder = hierarchy_builder
        self._running = False
        self._context_token = None
        self._result: MolecularOrderTypeAnalysisResult | None = None
        self._thread: QThread | None = None
        self._worker: _MolecularOrderTypeWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def current_result(
        self,
        context_token: object,
    ) -> MolecularOrderTypeAnalysisResult | None:
        if context_token is None or context_token is not self._context_token:
            return None
        return self._result

    def start(
        self,
        hierarchy: MolecularOrderHierarchy,
        analysis_scope: MolecularFrameRangeAnalysisScope,
        settings: MolecularOrderTypeClassificationSettings,
        *,
        context_token: object,
        display_result: MolecularStackingDisplayResult | None = None,
    ) -> bool:
        return self._start(
            hierarchy=hierarchy,
            frame_results=(),
            analysis_scope=analysis_scope,
            settings=settings,
            context_token=context_token,
            display_result=display_result,
            restore_state=None,
        )

    def start_from_frame_results(
        self,
        frame_results,
        analysis_scope: MolecularFrameRangeAnalysisScope,
        settings: MolecularOrderTypeClassificationSettings,
        *,
        context_token: object,
        display_result: MolecularStackingDisplayResult,
    ) -> bool:
        return self._start(
            hierarchy=None,
            frame_results=tuple(frame_results),
            analysis_scope=analysis_scope,
            settings=settings,
            context_token=context_token,
            display_result=display_result,
            restore_state=None,
        )

    def restore_from_frame_results(
        self,
        state: MolecularOrderTypeSessionState,
        frame_results,
        *,
        context_token: object,
        display_result: MolecularStackingDisplayResult,
    ) -> bool:
        if (
            not isinstance(state, MolecularOrderTypeSessionState)
            or state.cache_record is None
        ):
            return False
        return self._start(
            hierarchy=None,
            frame_results=tuple(frame_results),
            analysis_scope=state.analysis_scope,
            settings=state.classification_settings,
            context_token=context_token,
            display_result=display_result,
            restore_state=state,
        )

    def restore(
        self,
        state: MolecularOrderTypeSessionState,
        hierarchy: MolecularOrderHierarchy,
        *,
        context_token: object,
        display_result: MolecularStackingDisplayResult | None = None,
    ) -> bool:
        if (
            self._running
            or context_token is None
            or not isinstance(state, MolecularOrderTypeSessionState)
        ):
            return False
        classification = state.restore_classification_for(hierarchy)
        if classification is None:
            return False
        self._context_token = context_token
        self._result = MolecularOrderTypeAnalysisResult(
            hierarchy=hierarchy,
            classification=classification,
            summary=build_molecular_order_type_summary(classification),
            orientation_distribution=(
                build_molecular_order_orientation_distribution_data(
                    classification,
                    display_result=display_result,
                )
            ),
        )
        return True

    def _start(
        self,
        *,
        hierarchy: MolecularOrderHierarchy | None,
        frame_results: tuple[object, ...],
        analysis_scope: MolecularFrameRangeAnalysisScope,
        settings: MolecularOrderTypeClassificationSettings,
        context_token: object,
        display_result: MolecularStackingDisplayResult | None,
        restore_state: MolecularOrderTypeSessionState | None,
    ) -> bool:
        if self._running or context_token is None:
            return False
        if hierarchy is None and (
            not frame_results
            or not isinstance(display_result, MolecularStackingDisplayResult)
        ):
            return False
        self._running = True
        self._context_token = context_token
        self._result = None
        thread = QThread(self)
        worker = _MolecularOrderTypeWorker(
            self._analyzer,
            hierarchy,
            frame_results,
            self._hierarchy_builder,
            restore_state,
            analysis_scope,
            settings,
            context_token,
            display_result,
        )
        self._thread = thread
        self._worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._cleanup)
        self.running_changed.emit(True)
        thread.start()
        return True

    def invalidate(self) -> None:
        self._context_token = None
        self._result = None

    def _on_finished(self, success: _WorkerSuccess) -> None:
        if success.context_token is not self._context_token:
            return
        self._result = success.result
        self.finished.emit(success.result)

    def _on_failed(self, failure: _WorkerFailure) -> None:
        if failure.context_token is self._context_token:
            self.failed.emit(failure.message)

    def _cleanup(self) -> None:
        self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self._running = False
        self.running_changed.emit(False)


__all__ = [
    "MolecularOrderTypeAnalysisController",
    "MolecularOrderTypeAnalysisResult",
    "analyze_molecular_order_types",
    "build_molecular_order_hierarchy_from_frame_results",
]
