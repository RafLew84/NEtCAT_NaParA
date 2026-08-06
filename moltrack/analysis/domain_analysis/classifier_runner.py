from __future__ import annotations

from collections.abc import Callable
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
    ClassifierOutcomeStatus,
    MoleculeClassification,
)
from .events import emit_event
from .geometry import DomainAnalysisSeries, GeometryMode, M6CanonicalFrame
from .models import DomainAnalysisEvent, DomainAnalysisResult, M6FrameGate, M6Gate


@dataclass(frozen=True)
class _ClassifierGateComputation:
    classifications: tuple[MoleculeClassification, ...]
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...]


def run_gated_classifier(
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
) -> DomainAnalysisResult:
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
    except ClassifierCancellationRequested:
        return _canceled_result(gate, configuration, on_event=on_event)
    except ClassifierAnalysisError as exc:
        return _failed_result(gate, configuration, exc, on_event=on_event)
    domain_summaries = aggregate_domain_summaries(
        gate, computation.classifications, configuration,
    )
    return _completed_result(
        gate, configuration, computation.classifications,
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
    canonical_by_index = {
        value.frame_index: value for value in canonical_frames
    }
    validate_required_raw_frames(series, gate)
    results: list[MoleculeClassification] = []
    provenance: list[ClassifierFrameResultProvenance] = []
    for gate_frame in _ordered_gate_frames(gate):
        _raise_if_canceled(is_cancelled)
        frame_results, frame_provenance, disposition = classify_or_reuse_frame(
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
    if is_cancelled is not None and bool(is_cancelled()):
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


def _canceled_result(
    gate: M6Gate,
    configuration: ClassifierConfiguration,
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    outcome = _outcome(configuration, "canceled", ())
    emit_event(
        on_event,
        configuration.identity.classifier_id,
        "canceled",
        "Classifier canceled before atomic range publication.",
    )
    emit_event(on_event, "run", "canceled", "Domain Analysis canceled.")
    return DomainAnalysisResult(
        run_status="canceled",
        m6_gate=gate,
        classifier_status="canceled",
        classifier_outcomes=(outcome,),
    )


def _failed_result(
    gate: M6Gate,
    configuration: ClassifierConfiguration,
    error: ClassifierAnalysisError,
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    message = str(error).strip() or error.__class__.__name__
    outcome = _outcome(
        configuration,
        "failed",
        (),
        error_message=message,
    )
    emit_event(on_event, configuration.identity.classifier_id, "failed", message)
    emit_event(
        on_event,
        "run",
        "completed_with_errors",
        "Domain Analysis completed with classifier errors.",
    )
    return DomainAnalysisResult(
        run_status="completed_with_errors",
        m6_gate=gate,
        classifier_status="completed_with_errors",
        classifier_outcomes=(outcome,),
    )


def _completed_result(
    gate: M6Gate,
    configuration: ClassifierConfiguration,
    classifications: tuple[MoleculeClassification, ...],
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...],
    domain_summaries: tuple[DomainLabelSummary, ...],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
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
    emit_event(on_event, "run", "completed", "Domain Analysis completed.")
    return DomainAnalysisResult(
        run_status="completed",
        m6_gate=gate,
        classifier_status="completed",
        classifier_outcomes=(outcome,),
    )


def _outcome(
    configuration: ClassifierConfiguration,
    status: ClassifierOutcomeStatus,
    classifications: tuple[MoleculeClassification, ...],
    *,
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...] = (),
    domain_summaries: tuple[DomainLabelSummary, ...] = (),
    error_message: str | None = None,
) -> ClassifierOutcome:
    return ClassifierOutcome(
        status=status,
        configuration=configuration,
        molecule_classifications=classifications,
        frame_result_provenance=frame_result_provenance,
        domain_summaries=domain_summaries,
        error_message=error_message,
    )
