from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .cache import (
    ClassifierCacheDisposition,
    ClassifierFrameCache,
    RawFrameFingerprintMemo,
)
from .classifier_contract import (
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAggregationPreset,
    DomainLabelSummary,
    aggregate_domain_summaries,
)
from .classifier_frame_execution import (
    ClassifierAnalysisError,
    ClassifierCancellationRequested,
    MoleculeClassifierAdapter,
    classify_or_reuse_frame,
    validate_required_raw_frames,
)
from .classifier_models import (
    ClassifierFrameResultProvenance,
    ClassifierOutcome,
    MoleculeClassification,
)
from .events import (
    ClassifierOutcomeStatus,
    cancellation_requested,
    emit_event,
)
from .geometry import DomainAnalysisSeries, GeometryMode, M6CanonicalFrame
from .models import DomainAnalysisEvent, DomainAnalysisResult, M6FrameGate, M6Gate


@dataclass(frozen=True)
class _ClassifierGateComputation:
    classifications: tuple[MoleculeClassification, ...]
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...]


def run_requested_classifiers(
    series: DomainAnalysisSeries,
    classifier_ids: tuple[str, ...],
    gate: M6Gate,
    canonical_frames: tuple[M6CanonicalFrame, ...],
    adapters: Mapping[str, MoleculeClassifierAdapter],
    *,
    geometry_mode: GeometryMode,
    frame_cache: ClassifierFrameCache,
    raw_fingerprint_memo: RawFrameFingerprintMemo,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    is_cancelled: Callable[[], bool] | None,
) -> DomainAnalysisResult:
    outcomes: list[ClassifierOutcome] = []
    for position, classifier_id in enumerate(classifier_ids):
        if cancellation_requested(is_cancelled):
            outcomes.extend(not_run_classifier_outcomes(
                classifier_ids[position:], adapters, on_event=on_event,
            ) or ())
            return _canceled_run_result(gate, tuple(outcomes), on_event=on_event)
        outcome = _run_gated_classifier(
            series, classifier_id, gate, canonical_frames,
            adapters[classifier_id], geometry_mode=geometry_mode,
            frame_cache=frame_cache,
            raw_fingerprint_memo=raw_fingerprint_memo,
            on_event=on_event, is_cancelled=is_cancelled,
        )
        outcomes.append(outcome)
        if outcome.status == "canceled":
            outcomes.extend(not_run_classifier_outcomes(
                classifier_ids[position + 1:], adapters, on_event=on_event,
            ) or ())
            return _canceled_run_result(gate, tuple(outcomes), on_event=on_event)
    return _completed_run_result(gate, tuple(outcomes), on_event=on_event)


def _run_gated_classifier(
    series: DomainAnalysisSeries,
    classifier_id: str,
    gate: M6Gate,
    canonical_frames: tuple[M6CanonicalFrame, ...],
    adapter: MoleculeClassifierAdapter,
    *,
    geometry_mode: GeometryMode,
    frame_cache: ClassifierFrameCache,
    raw_fingerprint_memo: RawFrameFingerprintMemo,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    is_cancelled: Callable[[], bool] | None,
) -> ClassifierOutcome:
    configuration = _classifier_configuration(adapter, classifier_id)
    emit_event(
        on_event,
        classifier_id,
        "started",
        "Classifier received the immutable published M6 gate.",
    )
    try:
        computation = _classify_gate(
            series, gate, canonical_frames, adapter, configuration,
            geometry_mode=geometry_mode, frame_cache=frame_cache,
            raw_fingerprint_memo=raw_fingerprint_memo,
            on_event=on_event, is_cancelled=is_cancelled,
        )
        domain_summaries = aggregate_domain_summaries(
            gate, computation.classifications, configuration,
        )
        _raise_if_canceled(is_cancelled)
    except ClassifierCancellationRequested:
        return _canceled_outcome(configuration, on_event=on_event)
    except ClassifierAnalysisError as exc:
        return _failed_outcome(configuration, exc, on_event=on_event)
    return _completed_outcome(
        configuration, computation.classifications,
        computation.frame_result_provenance, domain_summaries,
        on_event=on_event,
    )


def _classify_gate(
    series: DomainAnalysisSeries,
    gate: M6Gate,
    canonical_frames: tuple[M6CanonicalFrame, ...],
    adapter: MoleculeClassifierAdapter,
    configuration: ClassifierConfiguration,
    *,
    geometry_mode: GeometryMode,
    frame_cache: ClassifierFrameCache,
    raw_fingerprint_memo: RawFrameFingerprintMemo,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    is_cancelled: Callable[[], bool] | None,
) -> _ClassifierGateComputation:
    canonical_by_index = {value.frame_index: value for value in canonical_frames}
    _raise_if_canceled(is_cancelled)
    validate_required_raw_frames(series, gate)
    results: list[MoleculeClassification] = []
    provenance: list[ClassifierFrameResultProvenance] = []
    for gate_frame in _ordered_gate_frames(gate):
        _raise_if_canceled(is_cancelled)
        frame_results, frame_provenance, disposition = _classify_gate_frame(
            series, gate_frame, canonical_by_index[gate_frame.frame_index],
            adapter, configuration, geometry_mode=geometry_mode,
            frame_cache=frame_cache, raw_fingerprint_memo=raw_fingerprint_memo,
        )
        results.extend(frame_results)
        provenance.append(frame_provenance)
        _emit_frame_progress(
            on_event, configuration.identity.classifier_id,
            disposition, gate_frame.frame_index,
        )
        _raise_if_canceled(is_cancelled)
    return _ClassifierGateComputation(
        classifications=tuple(sorted(
            results,
            key=lambda value: (value.frame_index, value.source_id),
        )),
        frame_result_provenance=tuple(provenance),
    )


def _classify_gate_frame(
    series: DomainAnalysisSeries,
    gate_frame: M6FrameGate,
    canonical_frame: M6CanonicalFrame,
    adapter: MoleculeClassifierAdapter,
    configuration: ClassifierConfiguration,
    *,
    geometry_mode: GeometryMode,
    frame_cache: ClassifierFrameCache,
    raw_fingerprint_memo: RawFrameFingerprintMemo,
) -> tuple[
    tuple[MoleculeClassification, ...],
    ClassifierFrameResultProvenance,
    ClassifierCacheDisposition,
]:
    try:
        return classify_or_reuse_frame(
            series, gate_frame, canonical_frame, adapter, configuration,
            geometry_mode=geometry_mode, frame_cache=frame_cache,
            raw_fingerprint_memo=raw_fingerprint_memo,
        )
    except ClassifierAnalysisError as exc:
        raise ClassifierAnalysisError(
            str(exc), frame_index=gate_frame.frame_index,
        ) from exc


def _ordered_gate_frames(gate: M6Gate) -> tuple[M6FrameGate, ...]:
    return tuple(sorted(gate.frames, key=lambda value: value.physical_frame_id))


def _emit_frame_progress(
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    classifier_id: str,
    disposition: ClassifierCacheDisposition,
    frame_index: int,
) -> None:
    emit_event(
        on_event,
        classifier_id,
        "progress",
        (
            "Classifier frame reused from cache."
            if disposition == "available"
            else "Classifier frame completed without partial publication."
        ),
        frame_index=frame_index,
    )


def _raise_if_canceled(
    is_cancelled: Callable[[], bool] | None,
) -> None:
    if cancellation_requested(is_cancelled):
        raise ClassifierCancellationRequested


def _classifier_configuration(
    adapter: MoleculeClassifierAdapter,
    classifier_id: str,
) -> ClassifierConfiguration:
    identity = ClassifierIdentity(
        classifier_id=adapter.classifier_id,
        schema_version=adapter.classifier_schema_version,
        settings_fingerprint=adapter.classifier_settings_fingerprint,
        algorithm_version=adapter.classifier_algorithm_version,
    )
    if identity.classifier_id != classifier_id:
        raise ValueError("Classifier adapter ID does not match its registry key.")
    preset = adapter.domain_aggregation_preset
    if not isinstance(preset, DomainAggregationPreset):
        raise TypeError(
            "Classifier adapters require a DomainAggregationPreset configuration."
        )
    return ClassifierConfiguration(identity=identity, aggregation_preset=preset)


def _canceled_outcome(
    configuration: ClassifierConfiguration,
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> ClassifierOutcome:
    outcome = _outcome(configuration, "canceled", ())
    emit_event(
        on_event,
        configuration.identity.classifier_id,
        "canceled",
        "Classifier canceled before atomic range publication.",
    )
    return outcome


def _failed_outcome(
    configuration: ClassifierConfiguration,
    error: ClassifierAnalysisError,
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> ClassifierOutcome:
    message = str(error).strip() or error.__class__.__name__
    outcome = _outcome(
        configuration,
        "failed",
        (),
        error_message=message,
        failure_frame_index=error.frame_index,
    )
    emit_event(
        on_event, configuration.identity.classifier_id, "failed", message,
        frame_index=error.frame_index,
    )
    return outcome


def _completed_outcome(
    configuration: ClassifierConfiguration,
    classifications: tuple[MoleculeClassification, ...],
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...],
    domain_summaries: tuple[DomainLabelSummary, ...],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> ClassifierOutcome:
    outcome = _outcome(
        configuration,
        "completed",
        classifications,
        frame_result_provenance=frame_result_provenance,
        domain_summaries=domain_summaries,
    )
    emit_event(
        on_event,
        configuration.identity.classifier_id,
        "published",
        "Full classifier payload published atomically.",
    )
    return outcome


def not_run_classifier_outcomes(
    classifier_ids: tuple[str, ...],
    adapters: Mapping[str, MoleculeClassifierAdapter],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> tuple[ClassifierOutcome, ...] | None:
    if not classifier_ids:
        return None
    outcomes = tuple(
        _outcome(_classifier_configuration(adapters[value], value), "not_run", ())
        for value in classifier_ids
    )
    for outcome in outcomes:
        emit_event(
            on_event, outcome.classifier_id, "not_run",
            "Classifier was not run.",
        )
    return outcomes


def _canceled_run_result(
    gate: M6Gate,
    outcomes: tuple[ClassifierOutcome, ...],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    emit_event(on_event, "run", "canceled", "Domain Analysis canceled.")
    return DomainAnalysisResult(
        run_status="canceled",
        m6_gate=gate,
        classifier_status="canceled",
        classifier_outcomes=outcomes,
    )


def _completed_run_result(
    gate: M6Gate,
    outcomes: tuple[ClassifierOutcome, ...],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    has_errors = any(outcome.status == "failed" for outcome in outcomes)
    if has_errors:
        emit_event(
            on_event, "run", "completed_with_errors",
            "Domain Analysis completed with classifier errors.",
        )
        return DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=gate,
            classifier_status="completed_with_errors",
            classifier_outcomes=outcomes,
        )
    emit_event(on_event, "run", "completed", "Domain Analysis completed.")
    return DomainAnalysisResult(
        run_status="completed",
        m6_gate=gate,
        classifier_status="completed",
        classifier_outcomes=outcomes,
    )


def _outcome(
    configuration: ClassifierConfiguration,
    status: ClassifierOutcomeStatus,
    classifications: tuple[MoleculeClassification, ...],
    *,
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...] = (),
    domain_summaries: tuple[DomainLabelSummary, ...] = (),
    error_message: str | None = None,
    failure_frame_index: int | None = None,
) -> ClassifierOutcome:
    return ClassifierOutcome(
        status=status,
        configuration=configuration,
        molecule_classifications=classifications,
        frame_result_provenance=frame_result_provenance,
        domain_summaries=domain_summaries,
        error_message=error_message,
        failure_frame_index=failure_frame_index,
    )
