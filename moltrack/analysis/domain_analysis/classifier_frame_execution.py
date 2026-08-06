from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .cache import (
    ClassifierCacheDisposition,
    ClassifierFrameCache,
    ClassifierFrameCacheKey,
    ClassifierFrameCacheRecord,
    RawFrameFingerprintMemo,
    classifications_for_frame_index,
    classifier_frame_cache_key,
    classifier_frame_cache_key_fingerprint,
    classifier_frame_cache_record,
)
from .classifier_contract import (
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAggregationPreset,
)
from .classifier_models import (
    ClassifierFrameResultProvenance,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    M6Partition,
    MoleculeClassification,
    MoleculeClassificationStatus,
    OrientationLabel,
)
from .geometry import (
    DomainAnalysisSeries,
    GeometryMode,
    M6AnalyzedMolecule,
    M6CanonicalFrame,
)
from .models import M6FrameGate, M6Gate, M6PublishedComponent


class MoleculeClassifierAdapter(Protocol):
    @property
    def classifier_id(self) -> str: ...

    @property
    def classifier_schema_version(self) -> str: ...

    @property
    def classifier_settings_fingerprint(self) -> str: ...

    @property
    def classifier_algorithm_version(self) -> str: ...

    @property
    def domain_aggregation_preset(self) -> DomainAggregationPreset: ...

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


class ClassifierCancellationRequested(RuntimeError):
    """Internal control flow at a safe per-frame cancellation boundary."""


@dataclass(frozen=True)
class _FrameCacheLookup:
    key: ClassifierFrameCacheKey
    raw_frame: np.ndarray | None
    disposition: ClassifierCacheDisposition
    record: ClassifierFrameCacheRecord | None


def classify_or_reuse_frame(
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
    lookup = _lookup_frame_cache(
        series, gate_frame, canonical_frame, configuration,
        geometry_mode=geometry_mode, frame_cache=frame_cache,
        raw_fingerprint_memo=raw_fingerprint_memo,
    )
    record = lookup.record
    if record is None:
        classifications = _classify_frame(
            gate_frame, canonical_frame, lookup.raw_frame,
            adapter, configuration.identity,
        )
        record = classifier_frame_cache_record(classifications)
        frame_cache.put(lookup.key, record)
    else:
        classifications = classifications_for_frame_index(
            record, gate_frame.frame_index,
        )
    return classifications, _frame_provenance(gate_frame, lookup.key, record), (
        lookup.disposition
    )


def _lookup_frame_cache(
    series: DomainAnalysisSeries,
    gate_frame: M6FrameGate,
    canonical_frame: M6CanonicalFrame,
    configuration: ClassifierConfiguration,
    *,
    geometry_mode: GeometryMode,
    frame_cache: ClassifierFrameCache,
    raw_fingerprint_memo: RawFrameFingerprintMemo,
) -> _FrameCacheLookup:
    raw_frame = _required_raw_frame(series, gate_frame)
    raw_fingerprint = (
        None
        if raw_frame is None
        else raw_fingerprint_memo.fingerprint(
            gate_frame.physical_frame_id,
            raw_frame,
        )
    )
    key = classifier_frame_cache_key(
        gate_frame, canonical_frame, configuration,
        geometry_mode=geometry_mode,
        raw_frame_fingerprint=raw_fingerprint,
    )
    disposition, record = frame_cache.lookup(key)
    return _FrameCacheLookup(key, raw_frame, disposition, record)


def _frame_provenance(
    gate_frame: M6FrameGate,
    key: ClassifierFrameCacheKey,
    record: ClassifierFrameCacheRecord,
) -> ClassifierFrameResultProvenance:
    return ClassifierFrameResultProvenance(
        frame_index=gate_frame.frame_index,
        physical_frame_id=gate_frame.physical_frame_id,
        cache_key_fingerprint=classifier_frame_cache_key_fingerprint(key),
        frame_result_fingerprint=record.result_fingerprint,
    )


def validate_required_raw_frames(
    series: DomainAnalysisSeries,
    gate: M6Gate,
) -> None:
    for gate_frame in gate.frames:
        _required_raw_frame(series, gate_frame)


def _required_raw_frame(
    series: DomainAnalysisSeries,
    gate_frame: M6FrameGate,
) -> np.ndarray | None:
    if not gate_frame.full_domains:
        return None
    raw_frame = series.frame(gate_frame.frame_index).raw_frame
    if raw_frame is None:
        raise ClassifierAnalysisError(
            "Classifier requires the exact raw frame for physical frame "
            f"{gate_frame.physical_frame_id!r}."
        )
    return raw_frame


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
            gate_frame, domain, molecule_by_id, raw_frame, adapter, identity,
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
            gate_frame, domain.lattice_domain_id,
            prediction_by_id[source_id], identity,
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
        identity=identity,
    )
