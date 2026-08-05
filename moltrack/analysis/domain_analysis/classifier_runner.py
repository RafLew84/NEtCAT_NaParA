from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np

from .classifier_models import (
    ClassifierIdentity,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    ClassifierOutcome,
    ClassifierOutcomeStatus,
    M6Partition,
    MoleculeClassification,
    MoleculeClassificationStatus,
    OrientationLabel,
)
from .events import emit_event
from .geometry import DomainAnalysisSeries, M6AnalyzedMolecule, M6CanonicalFrame
from .models import (
    DomainAnalysisEvent,
    DomainAnalysisResult,
    M6FrameGate,
    M6Gate,
    M6PublishedComponent,
)


class MoleculeClassifierAdapter(Protocol):
    @property
    def classifier_id(self) -> str: ...

    @property
    def classifier_settings_fingerprint(self) -> str: ...

    @property
    def classifier_algorithm_version(self) -> str: ...

    def classify_domain(
        self,
        raw_frame: np.ndarray,
        *,
        frame_index: int,
        physical_frame_id: str,
        lattice_domain_id: str,
        molecules: tuple[ClassifierMoleculeInput, ...],
    ) -> tuple[ClassifierMoleculePrediction, ...]: ...


class ClassifierAnalysisError(RuntimeError):
    """Expected classifier failure that must preserve the published M6 gate."""


def run_gated_classifier(
    series: DomainAnalysisSeries,
    classifier_id: str,
    gate: M6Gate,
    canonical_frames: tuple[M6CanonicalFrame, ...],
    adapter: MoleculeClassifierAdapter,
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    identity = ClassifierIdentity(
        classifier_id=adapter.classifier_id,
        settings_fingerprint=adapter.classifier_settings_fingerprint,
        algorithm_version=adapter.classifier_algorithm_version,
    )
    if identity.classifier_id != classifier_id:
        raise ValueError("Classifier adapter ID does not match its registry key.")
    emit_event(
        on_event,
        classifier_id,
        "started",
        "Classifier received the immutable published M6 gate.",
    )
    try:
        classifications = _classify_gate(
            series,
            gate,
            canonical_frames,
            adapter,
            identity,
        )
    except ClassifierAnalysisError as exc:
        return _failed_result(gate, identity, exc, on_event=on_event)
    return _completed_result(
        gate,
        identity,
        classifications,
        on_event=on_event,
    )


def _failed_result(
    gate: M6Gate,
    identity: ClassifierIdentity,
    error: ClassifierAnalysisError,
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    message = str(error).strip() or error.__class__.__name__
    outcome = _outcome(identity, "failed", (), error_message=message)
    emit_event(on_event, identity.classifier_id, "failed", message)
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
    identity: ClassifierIdentity,
    classifications: tuple[MoleculeClassification, ...],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    outcome = _outcome(identity, "completed", classifications)
    emit_event(
        on_event,
        identity.classifier_id,
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
    identity: ClassifierIdentity,
    status: ClassifierOutcomeStatus,
    classifications: tuple[MoleculeClassification, ...],
    *,
    error_message: str | None = None,
) -> ClassifierOutcome:
    return ClassifierOutcome(
        classifier_id=identity.classifier_id,
        status=status,
        classifier_settings_fingerprint=identity.settings_fingerprint,
        classifier_algorithm_version=identity.algorithm_version,
        molecule_classifications=classifications,
        error_message=error_message,
    )


def _classify_gate(
    series: DomainAnalysisSeries,
    gate: M6Gate,
    canonical_frames: tuple[M6CanonicalFrame, ...],
    adapter: MoleculeClassifierAdapter,
    identity: ClassifierIdentity,
) -> tuple[MoleculeClassification, ...]:
    canonical_by_index = {
        value.frame_index: value for value in canonical_frames
    }
    raw_by_index = _required_raw_frames(series, gate)
    results = tuple(
        classification
        for gate_frame in gate.frames
        for classification in _classify_frame(
            gate_frame,
            canonical_by_index[gate_frame.frame_index],
            raw_by_index.get(gate_frame.frame_index),
            adapter,
            identity,
        )
    )
    return tuple(sorted(
        results,
        key=lambda value: (value.frame_index, value.source_id),
    ))


def _required_raw_frames(
    series: DomainAnalysisSeries,
    gate: M6Gate,
) -> dict[int, np.ndarray]:
    frames: dict[int, np.ndarray] = {}
    for gate_frame in gate.frames:
        if not gate_frame.full_domains:
            continue
        raw_frame = series.frame(gate_frame.frame_index).raw_frame
        if raw_frame is None:
            raise ClassifierAnalysisError(
                "Classifier requires the exact raw frame for physical frame "
                f"{gate_frame.physical_frame_id!r}."
            )
        frames[gate_frame.frame_index] = raw_frame
    return frames


def _classify_frame(
    gate_frame: M6FrameGate,
    canonical_frame: M6CanonicalFrame,
    raw_frame: np.ndarray | None,
    adapter: MoleculeClassifierAdapter,
    identity: ClassifierIdentity,
) -> tuple[MoleculeClassification, ...]:
    not_gated = _not_gated_classifications(gate_frame, identity)
    if not gate_frame.full_domains:
        return not_gated
    if raw_frame is None:
        raise ClassifierAnalysisError("Gated classification requires a raw frame.")
    molecule_by_id = {
        value.source_id: value for value in canonical_frame.molecules
    }
    classified = tuple(
        value
        for domain in gate_frame.full_domains
        for value in _classify_domain(
            gate_frame,
            domain,
            molecule_by_id,
            raw_frame,
            adapter,
            identity,
        )
    )
    return classified + not_gated


def _classify_domain(
    gate_frame: M6FrameGate,
    domain: M6PublishedComponent,
    molecule_by_id: dict[str, M6AnalyzedMolecule],
    raw_frame: np.ndarray,
    adapter: MoleculeClassifierAdapter,
    identity: ClassifierIdentity,
) -> tuple[MoleculeClassification, ...]:
    inputs = tuple(
        ClassifierMoleculeInput(
            source_id=source_id,
            raw_centroid_xy=molecule_by_id[source_id].raw_centroid_xy,
        )
        for source_id in domain.source_ids
    )
    predictions = adapter.classify_domain(
        raw_frame,
        frame_index=gate_frame.frame_index,
        physical_frame_id=gate_frame.physical_frame_id,
        lattice_domain_id=domain.lattice_domain_id,
        molecules=inputs,
    )
    prediction_by_id = _validated_predictions(predictions, inputs)
    return tuple(
        _classification_from_prediction(
            gate_frame,
            domain.lattice_domain_id,
            prediction_by_id[source_id],
            identity,
        )
        for source_id in domain.source_ids
    )


def _not_gated_classifications(
    gate_frame: M6FrameGate,
    identity: ClassifierIdentity,
) -> tuple[MoleculeClassification, ...]:
    island_by_source_id = {
        source_id: island.lattice_domain_id
        for island in gate_frame.small_ordered_islands
        for source_id in island.source_ids
    }
    return tuple(
        _classification(
            gate_frame,
            source_id,
            identity,
            partition=(
                "small_ordered_island"
                if source_id in island_by_source_id
                else "outside"
            ),
            lattice_domain_id=island_by_source_id.get(source_id),
        )
        for source_id in sorted(
            set(island_by_source_id).union(gate_frame.outside_source_ids)
        )
    )


def _validated_predictions(
    predictions: tuple[ClassifierMoleculePrediction, ...],
    inputs: tuple[ClassifierMoleculeInput, ...],
) -> dict[str, ClassifierMoleculePrediction]:
    values = tuple(predictions)
    if any(not isinstance(value, ClassifierMoleculePrediction) for value in values):
        raise TypeError(
            "Classifier adapter must return ClassifierMoleculePrediction values."
        )
    prediction_by_id = {value.source_id: value for value in values}
    if len(prediction_by_id) != len(values):
        raise ValueError("Classifier predictions must have unique source IDs.")
    expected_ids = {value.source_id for value in inputs}
    if set(prediction_by_id) != expected_ids:
        raise ValueError(
            "Classifier predictions must cover exactly the gated molecules."
        )
    return prediction_by_id


def _classification_from_prediction(
    gate_frame: M6FrameGate,
    lattice_domain_id: str,
    prediction: ClassifierMoleculePrediction,
    identity: ClassifierIdentity,
) -> MoleculeClassification:
    label = prediction.orientation_label
    return _classification(
        gate_frame,
        prediction.source_id,
        identity,
        partition="full_domain",
        lattice_domain_id=lattice_domain_id,
        status="classified" if label is not None else "unknown_orientation",
        label=label if label is not None else "Unknown orientation",
        evidence_strength=prediction.evidence_strength,
        component_id=prediction.component_id,
    )


def _classification(
    gate_frame: M6FrameGate,
    source_id: str,
    identity: ClassifierIdentity,
    *,
    partition: M6Partition,
    lattice_domain_id: str | None = None,
    status: MoleculeClassificationStatus = "not_gated",
    label: OrientationLabel | None = None,
    evidence_strength: float = 0.0,
    component_id: str | None = None,
) -> MoleculeClassification:
    return MoleculeClassification(
        frame_index=gate_frame.frame_index,
        physical_frame_id=gate_frame.physical_frame_id,
        m6_gate_fingerprint=gate_frame.m6_gate_fingerprint,
        lattice_domain_id=lattice_domain_id,
        source_id=source_id,
        m6_partition=partition,
        classification_status=status,
        orientation_label=label,
        evidence_strength=evidence_strength,
        component_id=component_id,
        classifier_id=identity.classifier_id,
        classifier_settings_fingerprint=identity.settings_fingerprint,
        classifier_algorithm_version=identity.algorithm_version,
    )
