from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from threading import RLock
from typing import Callable, Literal

from ._m6_context_fingerprint import m6_context_fingerprint
from .frame_ranges import MolecularFrameRange, MolecularFrameRangeAnalysisScope
from .m6_domain_type_classifier import classify_m6_domain_types
from .m6_domain_type_observations import (
    M6DomainTypeObservation,
    extract_m6_domain_type_observations,
)
from .m6_domain_type_range_comparison import (
    M6DomainTypeRangeComparison,
    build_m6_domain_type_range_comparison,
)
from .m6_domain_type_results import M6DomainTypeClassificationResult
from .m6_domain_type_settings import M6DomainTypeClassificationSettings
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .m6_single_range_domain_type_summary import (
    M6SingleRangeDomainTypeSummary,
    build_m6_single_range_domain_type_summary,
)
from .range_analysis import MolecularFrameRangeAnalysis
from .range_comparison import MolecularFrameRangeComparison


M6DomainTypeAnalysisMode = Literal["single_range", "compare_ranges"]
M6DomainTypeAnalysisStatus = Literal[
    "ready",
    "m6_unavailable",
    "no_valid_domain_types",
]
M6DomainTypeTableResult = (
    M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison
)
M6DomainTypeAnalysisComputePhase = Literal[
    "extracting_observations",
    "complete_linkage",
    "aggregating",
]
M6_DOMAIN_TYPE_ANALYSIS_COMPUTE_PHASES: tuple[
    M6DomainTypeAnalysisComputePhase,
    ...,
] = (
    "extracting_observations",
    "complete_linkage",
    "aggregating",
)
M6DomainTypeAnalysisProgressCallback = Callable[
    [M6DomainTypeAnalysisComputePhase],
    None,
]

_FINGERPRINT_VERSION = "m6-domain-type-analysis-context-v1"


@dataclass(frozen=True)
class M6DomainTypeNamedRangeResult:
    """One named completed range exposed uniformly by either analysis mode."""

    analysis: MolecularFrameRangeAnalysis

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, MolecularFrameRangeAnalysis):
            raise TypeError("analysis must be MolecularFrameRangeAnalysis.")

    @property
    def name(self) -> str:
        return self.analysis.frame_range.name

    @property
    def frame_range(self) -> MolecularFrameRange:
        return self.analysis.frame_range


@dataclass(frozen=True)
class M6DomainTypeAnalysisSource:
    """Completed Position Analysis result used without recomputing M6."""

    analysis_mode: M6DomainTypeAnalysisMode
    frame_count: int
    source_view: str
    use_segmentation_centroids: bool
    m6_settings: MolecularM6OrientationAnalysisSettings | None
    named_ranges: tuple[M6DomainTypeNamedRangeResult, ...]

    def __post_init__(self) -> None:
        if self.analysis_mode not in {"single_range", "compare_ranges"}:
            raise ValueError("Unsupported domain type analysis_mode.")
        if isinstance(self.frame_count, bool) or not isinstance(self.frame_count, int):
            raise TypeError("frame_count must be an integer.")
        if self.frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        source_view = str(self.source_view).strip()
        if not source_view:
            raise ValueError("source_view must not be empty.")
        if not isinstance(self.use_segmentation_centroids, bool):
            raise TypeError("use_segmentation_centroids must be a boolean.")
        if self.m6_settings is not None and not isinstance(
            self.m6_settings,
            MolecularM6OrientationAnalysisSettings,
        ):
            raise TypeError("m6_settings must be M6 settings or None.")
        named_ranges = tuple(self.named_ranges)
        expected_count = 1 if self.analysis_mode == "single_range" else 2
        if len(named_ranges) != expected_count:
            raise ValueError(
                f"{self.analysis_mode} requires {expected_count} named range result(s)."
            )
        if any(
            not isinstance(value, M6DomainTypeNamedRangeResult)
            for value in named_ranges
        ):
            raise TypeError("named_ranges must contain named range results.")
        if len({value.frame_range for value in named_ranges}) != len(named_ranges):
            raise ValueError("Named range results must describe distinct ranges.")
        for named_range in named_ranges:
            analysis = named_range.analysis
            if analysis.source_view != source_view:
                raise ValueError("Every range result must use source_view.")
            if analysis.frame_range.start_frame < 0 or (
                analysis.frame_range.end_frame >= self.frame_count
            ):
                raise ValueError("Every range must fit within frame_count.")
            if (
                analysis.use_segmentation_centroids
                != self.use_segmentation_centroids
            ):
                raise ValueError("Every range must use one centroid mode.")
            _validate_completed_range(analysis, expected_settings=self.m6_settings)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "named_ranges", named_ranges)

    @property
    def analysis_scope(self) -> MolecularFrameRangeAnalysisScope:
        return MolecularFrameRangeAnalysisScope(
            analysis_mode=self.analysis_mode,
            frame_count=self.frame_count,
            source_view=self.source_view,
            ranges=tuple(value.frame_range for value in self.named_ranges),
        )

    @property
    def range_analyses(self) -> tuple[MolecularFrameRangeAnalysis, ...]:
        return tuple(value.analysis for value in self.named_ranges)

    @property
    def centroid_mode(self) -> Literal["segmentation_preferred", "bbox_centers"]:
        return (
            "segmentation_preferred"
            if self.use_segmentation_centroids
            else "bbox_centers"
        )


@dataclass(frozen=True)
class M6DomainTypeFrameResultFingerprint:
    """Stable identity of exactly the per-frame values consumed by type analysis."""

    range_name: str
    working_frame_index: int
    source_frame_index: int
    fingerprint: str

    def __post_init__(self) -> None:
        range_name = str(self.range_name).strip()
        if not range_name:
            raise ValueError("range_name must not be empty.")
        for field_name in ("working_frame_index", "source_frame_index"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
        fingerprint = str(self.fingerprint).strip()
        if not fingerprint:
            raise ValueError("fingerprint must not be empty.")
        object.__setattr__(self, "range_name", range_name)
        object.__setattr__(self, "fingerprint", fingerprint)


@dataclass(frozen=True)
class M6DomainTypeAnalysisContext:
    """Immutable classification snapshot and its complete reuse identity."""

    source: M6DomainTypeAnalysisSource
    classification_settings: M6DomainTypeClassificationSettings
    observations: tuple[M6DomainTypeObservation, ...]
    frame_result_fingerprints: tuple[M6DomainTypeFrameResultFingerprint, ...]
    available_m6_frame_count: int
    shared_m6_context_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, M6DomainTypeAnalysisSource):
            raise TypeError("source must be M6DomainTypeAnalysisSource.")
        if not isinstance(
            self.classification_settings,
            M6DomainTypeClassificationSettings,
        ):
            raise TypeError("classification_settings must be domain type settings.")
        observations = tuple(self.observations)
        if any(not isinstance(value, M6DomainTypeObservation) for value in observations):
            raise TypeError("observations must contain domain type observations.")
        frame_fingerprints = tuple(self.frame_result_fingerprints)
        if any(
            not isinstance(value, M6DomainTypeFrameResultFingerprint)
            for value in frame_fingerprints
        ):
            raise TypeError("frame_result_fingerprints must contain frame identities.")
        expected_frame_count = sum(
            len(value.frame_range.frame_indices) for value in self.source.named_ranges
        )
        if len(frame_fingerprints) != expected_frame_count:
            raise ValueError("Every selected frame requires one result fingerprint.")
        if (
            isinstance(self.available_m6_frame_count, bool)
            or not isinstance(self.available_m6_frame_count, int)
            or not 0 <= self.available_m6_frame_count <= expected_frame_count
        ):
            raise ValueError("available_m6_frame_count is invalid.")
        if self.available_m6_frame_count == 0:
            if self.shared_m6_context_fingerprint is not None:
                raise ValueError("Unavailable M6 cannot have a shared context.")
        elif not isinstance(self.shared_m6_context_fingerprint, str) or not (
            self.shared_m6_context_fingerprint.strip()
        ):
            raise ValueError("Available M6 requires a shared context fingerprint.")
        fingerprint = str(self.fingerprint).strip()
        if not fingerprint:
            raise ValueError("fingerprint must not be empty.")
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "frame_result_fingerprints", frame_fingerprints)
        object.__setattr__(self, "fingerprint", fingerprint)

    @property
    def analysis_scope(self) -> MolecularFrameRangeAnalysisScope:
        return self.source.analysis_scope


@dataclass(frozen=True)
class M6DomainTypeAnalysisOutcome:
    """Current table result or a controlled empty status for one exact context."""

    status: M6DomainTypeAnalysisStatus
    status_message: str
    context_fingerprint: str
    analysis_scope: MolecularFrameRangeAnalysisScope
    available_m6_frame_count: int
    classification: M6DomainTypeClassificationResult | None
    table_result: M6DomainTypeTableResult | None
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.status not in {
            "ready",
            "m6_unavailable",
            "no_valid_domain_types",
        }:
            raise ValueError("Unsupported domain type analysis status.")
        message = str(self.status_message).strip()
        fingerprint = str(self.context_fingerprint).strip()
        if not message or not fingerprint:
            raise ValueError("Status message and context fingerprint are required.")
        if not isinstance(self.analysis_scope, MolecularFrameRangeAnalysisScope):
            raise TypeError("analysis_scope must be a frame range analysis scope.")
        if (
            isinstance(self.available_m6_frame_count, bool)
            or not isinstance(self.available_m6_frame_count, int)
            or self.available_m6_frame_count < 0
        ):
            raise ValueError("available_m6_frame_count must be non-negative.")
        if self.status == "m6_unavailable":
            if self.available_m6_frame_count != 0:
                raise ValueError("m6_unavailable requires zero available M6 frames.")
            if self.classification is not None or self.table_result is not None:
                raise ValueError("m6_unavailable cannot expose classification data.")
        else:
            if not isinstance(
                self.classification,
                M6DomainTypeClassificationResult,
            ):
                raise TypeError("A completed status requires classification.")
            if not isinstance(
                self.table_result,
                (M6SingleRangeDomainTypeSummary, M6DomainTypeRangeComparison),
            ):
                raise TypeError("A completed status requires a table result.")
            has_types = _table_has_domain_types(self.table_result)
            if (self.status == "ready") != has_types:
                raise ValueError("Status must reflect whether valid domain types exist.")
            if self.classification.analysis_scope != self.analysis_scope:
                raise ValueError("Classification and outcome scopes must match.")
            expected_table_type = (
                M6SingleRangeDomainTypeSummary
                if self.analysis_scope.analysis_mode == "single_range"
                else M6DomainTypeRangeComparison
            )
            if not isinstance(self.table_result, expected_table_type):
                raise TypeError("Table result must match the active analysis mode.")
            if (
                self.table_result.classification_input_fingerprint
                != self.classification.input_fingerprint
            ):
                raise ValueError("Table result must use the outcome classification.")
        object.__setattr__(self, "status_message", message)
        object.__setattr__(self, "context_fingerprint", fingerprint)
        object.__setattr__(self, "uses_tracking", False)


@dataclass(frozen=True)
class M6DomainTypeAnalysisComputation:
    """A complete result that has not yet been published to the active store."""

    context: M6DomainTypeAnalysisContext
    outcome: M6DomainTypeAnalysisOutcome

    def __post_init__(self) -> None:
        if not isinstance(self.context, M6DomainTypeAnalysisContext):
            raise TypeError("context must be an M6 domain type analysis context.")
        if not isinstance(self.outcome, M6DomainTypeAnalysisOutcome):
            raise TypeError("outcome must be an M6 domain type analysis outcome.")
        if self.outcome.context_fingerprint != self.context.fingerprint:
            raise ValueError("Outcome and context fingerprints must match.")
        if self.outcome.analysis_scope != self.context.analysis_scope:
            raise ValueError("Outcome and context scopes must match.")


class M6DomainTypeAnalysisStore:
    """Keep at most one type result and expose it only for its exact context."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._current: M6DomainTypeAnalysisOutcome | None = None
        self._current_context: M6DomainTypeAnalysisContext | None = None

    @property
    def current(self) -> M6DomainTypeAnalysisOutcome | None:
        with self._lock:
            return self._current

    def clear(self) -> None:
        with self._lock:
            self._current = None
            self._current_context = None

    def current_for(
        self,
        source: M6DomainTypeAnalysisSource,
        *,
        classification_settings: M6DomainTypeClassificationSettings,
    ) -> M6DomainTypeAnalysisOutcome | None:
        current, _ = self._snapshot_for_source(source, classification_settings)
        if current is not None:
            return current
        context = build_m6_domain_type_analysis_context(
            source,
            classification_settings=classification_settings,
        )
        with self._lock:
            if self._current is None or (
                self._current.context_fingerprint != context.fingerprint
            ):
                return None
            self._current_context = context
            return self._current

    def analyze(
        self,
        source: M6DomainTypeAnalysisSource,
        *,
        classification_settings: M6DomainTypeClassificationSettings,
        progress_callback: M6DomainTypeAnalysisProgressCallback | None = None,
    ) -> M6DomainTypeAnalysisOutcome:
        computation = self.compute(
            source,
            classification_settings=classification_settings,
            progress_callback=progress_callback,
        )
        return self.publish(computation)

    def compute(
        self,
        source: M6DomainTypeAnalysisSource,
        *,
        classification_settings: M6DomainTypeClassificationSettings,
        progress_callback: M6DomainTypeAnalysisProgressCallback | None = None,
    ) -> M6DomainTypeAnalysisComputation:
        """Build a complete immutable result without changing the published result."""

        _report_compute_phase(progress_callback, "extracting_observations")
        current, current_context = self._snapshot_for_source(
            source,
            classification_settings,
        )
        if current is not None:
            assert current_context is not None
            _report_compute_phase(progress_callback, "complete_linkage")
            _report_compute_phase(progress_callback, "aggregating")
            return M6DomainTypeAnalysisComputation(
                context=current_context,
                outcome=current,
            )
        context = build_m6_domain_type_analysis_context(
            source,
            classification_settings=classification_settings,
        )
        with self._lock:
            current = self._current
        if current is not None and (
            current.context_fingerprint == context.fingerprint
        ):
            _report_compute_phase(progress_callback, "complete_linkage")
            _report_compute_phase(progress_callback, "aggregating")
            return M6DomainTypeAnalysisComputation(
                context=context,
                outcome=current,
            )
        outcome = _analyze_context(
            context,
            progress_callback=progress_callback,
        )
        return M6DomainTypeAnalysisComputation(
            context=context,
            outcome=outcome,
        )

    def publish(
        self,
        computation: M6DomainTypeAnalysisComputation,
    ) -> M6DomainTypeAnalysisOutcome:
        """Atomically replace the visible result with one completed computation."""

        if not isinstance(computation, M6DomainTypeAnalysisComputation):
            raise TypeError("computation must be an M6 domain type computation.")
        with self._lock:
            self._current = computation.outcome
            self._current_context = computation.context
            return computation.outcome

    def _snapshot_for_source(
        self,
        source: M6DomainTypeAnalysisSource,
        classification_settings: M6DomainTypeClassificationSettings,
    ) -> tuple[
        M6DomainTypeAnalysisOutcome | None,
        M6DomainTypeAnalysisContext | None,
    ]:
        with self._lock:
            if (
                self._current is not None
                and self._current_context is not None
                and source is self._current_context.source
                and classification_settings
                == self._current_context.classification_settings
            ):
                return self._current, self._current_context
            return None, None


def adapt_m6_domain_type_analysis_source(
    result: MolecularFrameRangeAnalysis | MolecularFrameRangeComparison,
    *,
    frame_count: int,
) -> M6DomainTypeAnalysisSource:
    """Adapt one completed active-mode result without invoking analysis backends."""

    if isinstance(result, MolecularFrameRangeAnalysis):
        analysis_mode: M6DomainTypeAnalysisMode = "single_range"
        analyses = (result,)
    elif isinstance(result, MolecularFrameRangeComparison):
        analysis_mode = "compare_ranges"
        analyses = (result.first_analysis, result.second_analysis)
        if result.source_view != result.first_analysis.source_view or (
            result.source_view != result.second_analysis.source_view
        ):
            raise ValueError("Comparison and range source views must match.")
    else:
        raise TypeError("result must be a completed range or range comparison.")

    centroid_modes = {value.use_segmentation_centroids for value in analyses}
    if len(centroid_modes) != 1:
        raise ValueError("All completed ranges must use one centroid mode.")
    settings_values = tuple(_range_m6_settings(value) for value in analyses)
    concrete_settings = {value for value in settings_values if value is not None}
    if len(concrete_settings) > 1:
        raise ValueError("All completed ranges must use one M6 settings context.")
    m6_settings = next(iter(concrete_settings), None)
    return M6DomainTypeAnalysisSource(
        analysis_mode=analysis_mode,
        frame_count=frame_count,
        source_view=analyses[0].source_view,
        use_segmentation_centroids=next(iter(centroid_modes)),
        m6_settings=m6_settings,
        named_ranges=tuple(
            M6DomainTypeNamedRangeResult(analysis=value) for value in analyses
        ),
    )


def build_m6_domain_type_analysis_context(
    source: M6DomainTypeAnalysisSource,
    *,
    classification_settings: M6DomainTypeClassificationSettings,
) -> M6DomainTypeAnalysisContext:
    """Snapshot completed M6 values and build their complete reuse fingerprint."""

    if not isinstance(source, M6DomainTypeAnalysisSource):
        raise TypeError("source must be M6DomainTypeAnalysisSource.")
    if not isinstance(
        classification_settings,
        M6DomainTypeClassificationSettings,
    ):
        raise TypeError("classification_settings must be domain type settings.")
    observations = tuple(
        observation
        for range_analysis in source.range_analyses
        for observation in extract_m6_domain_type_observations(
            range_analysis,
            settings=classification_settings,
        )
    )
    observations_by_frame = _observations_by_frame(observations)
    frame_fingerprints = []
    available_contexts = set()
    for named_range in source.named_ranges:
        for frame_result in named_range.analysis.frame_results:
            m6_analysis = frame_result.m6_orientation_analysis
            if m6_analysis is not None:
                available_contexts.add(m6_context_fingerprint(m6_analysis))
            frame_observations = observations_by_frame.get(
                (named_range.name, frame_result.frame_index),
                (),
            )
            frame_fingerprints.append(
                _frame_result_fingerprint(
                    named_range,
                    frame_result,
                    frame_observations,
                )
            )
    if len(available_contexts) > 1:
        raise ValueError("Completed M6 frames do not share one analysis context.")
    shared_context = next(iter(available_contexts), None)
    payload = {
        "version": _FINGERPRINT_VERSION,
        "analysis_mode": source.analysis_mode,
        "frame_count": source.frame_count,
        "source_view": source.source_view,
        "centroid_mode": source.centroid_mode,
        "ranges": [
            {
                "name": value.name,
                "start_frame": value.frame_range.start_frame,
                "end_frame": value.frame_range.end_frame,
            }
            for value in source.named_ranges
        ],
        "m6_settings": (
            None if source.m6_settings is None else source.m6_settings.to_dict()
        ),
        "classification_settings": classification_settings.to_dict(),
        "frame_result_fingerprints": [
            asdict(value) for value in frame_fingerprints
        ],
    }
    return M6DomainTypeAnalysisContext(
        source=source,
        classification_settings=classification_settings,
        observations=observations,
        frame_result_fingerprints=tuple(frame_fingerprints),
        available_m6_frame_count=len(_available_m6_contexts_for_frames(source)),
        shared_m6_context_fingerprint=shared_context,
        fingerprint=_json_fingerprint(payload),
    )


def _analyze_context(
    context: M6DomainTypeAnalysisContext,
    *,
    progress_callback: M6DomainTypeAnalysisProgressCallback | None = None,
) -> M6DomainTypeAnalysisOutcome:
    _report_compute_phase(progress_callback, "complete_linkage")
    if context.available_m6_frame_count == 0:
        _report_compute_phase(progress_callback, "aggregating")
        return M6DomainTypeAnalysisOutcome(
            status="m6_unavailable",
            status_message="No completed M6 frame is available for domain types.",
            context_fingerprint=context.fingerprint,
            analysis_scope=context.analysis_scope,
            available_m6_frame_count=0,
            classification=None,
            table_result=None,
        )
    m6_settings = context.source.m6_settings
    m6_context = context.shared_m6_context_fingerprint
    if m6_settings is None or m6_context is None:
        raise RuntimeError("Available M6 context is incomplete.")
    classification = classify_m6_domain_types(
        context.observations,
        analysis_scope=context.analysis_scope,
        classification_settings=context.classification_settings,
        m6_settings=m6_settings,
        m6_context_fingerprint=m6_context,
    )
    _report_compute_phase(progress_callback, "aggregating")
    if context.source.analysis_mode == "single_range":
        table_result: M6DomainTypeTableResult = (
            build_m6_single_range_domain_type_summary(
                classification,
                context.source.range_analyses[0],
            )
        )
    else:
        table_result = build_m6_domain_type_range_comparison(
            classification,
            context.source.range_analyses[0],
            context.source.range_analyses[1],
        )
    if _table_has_domain_types(table_result):
        status: M6DomainTypeAnalysisStatus = "ready"
        message = "Domain type classification is ready."
    else:
        status = "no_valid_domain_types"
        message = "No domain observations satisfy the type classification settings."
    return M6DomainTypeAnalysisOutcome(
        status=status,
        status_message=message,
        context_fingerprint=context.fingerprint,
        analysis_scope=context.analysis_scope,
        available_m6_frame_count=context.available_m6_frame_count,
        classification=classification,
        table_result=table_result,
    )


def _report_compute_phase(
    callback: M6DomainTypeAnalysisProgressCallback | None,
    phase: M6DomainTypeAnalysisComputePhase,
) -> None:
    if callback is not None:
        callback(phase)


def _table_has_domain_types(table_result: M6DomainTypeTableResult) -> bool:
    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        return table_result.domain_type_count > 0
    return bool(table_result.rows)


def _range_m6_settings(
    analysis: MolecularFrameRangeAnalysis,
) -> MolecularM6OrientationAnalysisSettings | None:
    declared = analysis.m6_orientation_settings
    available = tuple(
        value.m6_orientation_analysis.settings
        for value in analysis.frame_results
        if value.m6_orientation_analysis is not None
    )
    available_settings = set(available)
    if len(available_settings) > 1:
        raise ValueError("One range cannot contain multiple M6 settings contexts.")
    inferred = next(iter(available_settings), None)
    if declared is not None and inferred is not None and declared != inferred:
        raise ValueError("Declared M6 settings do not match completed frame results.")
    return declared if declared is not None else inferred


def _validate_completed_range(
    analysis: MolecularFrameRangeAnalysis,
    *,
    expected_settings: MolecularM6OrientationAnalysisSettings | None,
) -> None:
    expected_indices = analysis.frame_range.frame_indices
    actual_indices = tuple(value.frame_index for value in analysis.frame_results)
    if actual_indices != expected_indices:
        raise ValueError("Completed frame results must cover their range in order.")
    allowed_statuses = {
        "disabled",
        "available",
        "unavailable_missing_analysis",
        "unavailable_blocking_graph_qc",
    }
    for frame_result in analysis.frame_results:
        if frame_result.source_view != analysis.source_view:
            raise ValueError("Completed frame source_view must match its range.")
        source_frame_index = frame_result.source_frame_index
        if (
            isinstance(source_frame_index, bool)
            or not isinstance(source_frame_index, int)
            or source_frame_index < 0
        ):
            raise ValueError("source_frame_index must be a non-negative integer.")
        status = frame_result.m6_orientation_availability_status
        reason = frame_result.m6_orientation_unavailability_reason
        m6_analysis = frame_result.m6_orientation_analysis
        if status not in allowed_statuses:
            raise ValueError("Unsupported completed M6 frame status.")
        if status == "available":
            if m6_analysis is None or reason is not None:
                raise ValueError("Available M6 status requires one completed result.")
        elif m6_analysis is not None:
            raise ValueError("Unavailable M6 status cannot contain an M6 result.")
        elif status == "disabled" and reason is not None:
            raise ValueError("Disabled M6 status cannot have an unavailable reason.")
        elif status.startswith("unavailable_") and not str(reason).strip():
            raise ValueError("Unavailable M6 status requires a reason.")
        if m6_analysis is not None and m6_analysis.source_view != analysis.source_view:
            raise ValueError("Completed M6 source_view must match its range.")
    actual_settings = _range_m6_settings(analysis)
    if actual_settings != expected_settings:
        raise ValueError("Every range must use one M6 settings context.")


def _observations_by_frame(
    observations: tuple[M6DomainTypeObservation, ...],
) -> dict[tuple[str, int], tuple[M6DomainTypeObservation, ...]]:
    grouped: dict[tuple[str, int], list[M6DomainTypeObservation]] = {}
    for observation in observations:
        grouped.setdefault(
            (observation.range_name, observation.frame_index),
            [],
        ).append(observation)
    return {
        key: tuple(sorted(values, key=lambda value: value.stable_key))
        for key, values in grouped.items()
    }


def _frame_result_fingerprint(
    named_range: M6DomainTypeNamedRangeResult,
    frame_result,
    observations: tuple[M6DomainTypeObservation, ...],
) -> M6DomainTypeFrameResultFingerprint:
    m6_analysis = frame_result.m6_orientation_analysis
    payload = {
        "range": {
            "name": named_range.name,
            "start_frame": named_range.frame_range.start_frame,
            "end_frame": named_range.frame_range.end_frame,
        },
        "working_frame_index": frame_result.frame_index,
        "source_frame_index": frame_result.source_frame_index,
        "source_view": frame_result.source_view,
        "m6_availability_status": frame_result.m6_orientation_availability_status,
        "m6_unavailability_reason": frame_result.m6_orientation_unavailability_reason,
        "m6_context_fingerprint": (
            None if m6_analysis is None else m6_context_fingerprint(m6_analysis)
        ),
        "m6_frame_aggregates": (
            None if m6_analysis is None else _frame_aggregate_payload(m6_analysis)
        ),
        "domain_observations": [asdict(value) for value in observations],
    }
    return M6DomainTypeFrameResultFingerprint(
        range_name=named_range.name,
        working_frame_index=frame_result.frame_index,
        source_frame_index=frame_result.source_frame_index,
        fingerprint=_json_fingerprint(payload),
    )


def _frame_aggregate_payload(m6_analysis) -> dict[str, object]:
    aggregates = m6_analysis.frame_aggregates
    return {
        "valid_representative_count": aggregates.valid_representative_count,
        "valid_fov_area_nm2": aggregates.valid_fov_area_nm2,
        "full_domain_count": aggregates.full_domain_count,
        "full_domain_molecule_fraction": aggregates.full_domain_molecule_fraction,
        "full_domain_footprint_fraction": aggregates.full_domain_footprint_fraction,
    }


def _available_m6_contexts_for_frames(
    source: M6DomainTypeAnalysisSource,
) -> tuple[str, ...]:
    return tuple(
        m6_context_fingerprint(frame_result.m6_orientation_analysis)
        for analysis in source.range_analyses
        for frame_result in analysis.frame_results
        if frame_result.m6_orientation_analysis is not None
    )


def _json_fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
