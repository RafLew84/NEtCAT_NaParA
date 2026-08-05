from __future__ import annotations

from typing import Literal

from .classifier_models import ClassifierIdentity, MoleculeClassification
from .domain_label_models import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    DomainAggregationPreset,
    DomainLabel,
    DomainLabelSummary,
    ResolvedOrientationLabel,
)
from .models import M6Gate, M6PublishedComponent


_CLASS_KEYS: tuple[ResolvedOrientationLabel, ...] = ("A", "B", "C")
_UNKNOWN: Literal["Unknown orientation"] = "Unknown orientation"
_MIXED: Literal["Mixed"] = "Mixed"


def aggregate_domain_summaries(
    gate: M6Gate,
    classifications: tuple[MoleculeClassification, ...],
    identity: ClassifierIdentity,
    preset: DomainAggregationPreset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
) -> tuple[DomainLabelSummary, ...]:
    """Summarize only complete M6 domains from immutable molecule evidence."""

    by_domain = _classifications_by_domain(classifications)
    summaries = tuple(
        _aggregate_domain(
            gate_frame.frame_index,
            gate_frame.physical_frame_id,
            gate_frame.m6_gate_fingerprint,
            domain,
            by_domain.get((gate_frame.frame_index, domain.lattice_domain_id), ()),
            identity,
            preset,
        )
        for gate_frame in gate.frames
        for domain in gate_frame.full_domains
    )
    expected_keys = {
        (gate_frame.frame_index, domain.lattice_domain_id)
        for gate_frame in gate.frames
        for domain in gate_frame.full_domains
    }
    if set(by_domain) != expected_keys:
        raise ValueError("Full-domain classifications must match the published M6 gate.")
    return summaries


def _classifications_by_domain(
    classifications: tuple[MoleculeClassification, ...],
) -> dict[tuple[int, str], tuple[MoleculeClassification, ...]]:
    grouped: dict[tuple[int, str], list[MoleculeClassification]] = {}
    for value in classifications:
        if value.m6_partition != "full_domain":
            continue
        if value.lattice_domain_id is None:
            raise ValueError("Full-domain evidence requires a lattice domain ID.")
        grouped.setdefault(
            (value.frame_index, value.lattice_domain_id),
            [],
        ).append(value)
    return {
        key: tuple(sorted(values, key=lambda value: value.source_id))
        for key, values in grouped.items()
    }


def _aggregate_domain(
    frame_index: int,
    physical_frame_id: str,
    m6_gate_fingerprint: str,
    domain: M6PublishedComponent,
    molecules: tuple[MoleculeClassification, ...],
    identity: ClassifierIdentity,
    preset: DomainAggregationPreset,
) -> DomainLabelSummary:
    source_ids = tuple(value.source_id for value in molecules)
    if source_ids != domain.source_ids:
        raise ValueError("Domain summary requires every M6-gated molecule exactly once.")
    total = len(domain.source_ids)
    counts = {
        key: sum(value.orientation_label == key for value in molecules)
        for key in (*_CLASS_KEYS, _UNKNOWN)
    }
    evidence: dict[ResolvedOrientationLabel, float] = {
        key: sum(
            value.evidence_strength
            for value in molecules
            if value.orientation_label == key
        )
        / total
        for key in _CLASS_KEYS
    }
    coherent_evidence: dict[ResolvedOrientationLabel, float] = {
        key: _largest_component_evidence(molecules, key) / total
        for key in _CLASS_KEYS
    }
    resolved_count = total - counts[_UNKNOWN]
    resolved_evidence = sum(evidence.values())
    ranked = sorted(_CLASS_KEYS, key=lambda key: (-evidence[key], key))
    dominant: ResolvedOrientationLabel | None = (
        ranked[0] if evidence[ranked[0]] > 0.0 else None
    )
    dominance_margin = (
        0.0 if dominant is None else evidence[dominant] - evidence[ranked[1]]
    )
    label, reason = _domain_label(
        dominant,
        evidence,
        coherent_evidence,
        dominance_margin,
        resolved_evidence,
        preset,
    )
    return DomainLabelSummary(
        frame_index=frame_index,
        physical_frame_id=physical_frame_id,
        m6_gate_fingerprint=m6_gate_fingerprint,
        lattice_domain_id=domain.lattice_domain_id,
        label=label,
        molecule_count=total,
        counts=tuple((key, counts[key]) for key in (*_CLASS_KEYS, _UNKNOWN)),
        evidence=tuple((key, evidence[key]) for key in _CLASS_KEYS),
        coherent_evidence=tuple(
            (key, coherent_evidence[key]) for key in _CLASS_KEYS
        ),
        resolved_fraction=resolved_count / total,
        resolved_evidence=resolved_evidence,
        dominant_class=dominant,
        dominance_margin=dominance_margin,
        reason=reason,
        aggregation_preset_id=preset.preset_id,
        aggregation_preset_fingerprint=preset.fingerprint,
        classifier_id=identity.classifier_id,
        classifier_settings_fingerprint=identity.settings_fingerprint,
        classifier_algorithm_version=identity.algorithm_version,
    )


def _domain_label(
    dominant: ResolvedOrientationLabel | None,
    evidence: dict[ResolvedOrientationLabel, float],
    coherent_evidence: dict[ResolvedOrientationLabel, float],
    dominance_margin: float,
    resolved_evidence: float,
    preset: DomainAggregationPreset,
) -> tuple[DomainLabel, str]:
    if resolved_evidence < preset.minimum_resolved_evidence:
        return _UNKNOWN, "accepted evidence is too sparse after Unknown and confidence"
    if dominant is not None and _passes_single_class_gate(
        dominant,
        evidence,
        coherent_evidence,
        dominance_margin,
        preset,
    ):
        return dominant, "one class passes support, lead, confidence, and coherence gates"
    if _passes_mixed_gate(evidence, coherent_evidence, preset):
        return _MIXED, "at least two spatially coherent classes have material evidence"
    return _UNKNOWN, "evidence is sufficient to inspect but not to name a coherent class"


def _largest_component_evidence(
    molecules: tuple[MoleculeClassification, ...],
    class_key: ResolvedOrientationLabel,
) -> float:
    totals: dict[str, float] = {}
    for value in molecules:
        if value.orientation_label != class_key:
            continue
        if value.component_id is None:
            raise ValueError("Resolved classifier evidence requires a component ID.")
        totals[value.component_id] = (
            totals.get(value.component_id, 0.0) + value.evidence_strength
        )
    return max(totals.values(), default=0.0)


def _passes_single_class_gate(
    dominant: ResolvedOrientationLabel,
    evidence: dict[ResolvedOrientationLabel, float],
    coherent_evidence: dict[ResolvedOrientationLabel, float],
    dominance_margin: float,
    preset: DomainAggregationPreset,
) -> bool:
    return (
        evidence[dominant] >= preset.minimum_dominant_evidence
        and dominance_margin >= preset.minimum_dominance_margin
        and coherent_evidence[dominant]
        >= preset.minimum_dominant_coherent_evidence
    )


def _passes_mixed_gate(
    evidence: dict[ResolvedOrientationLabel, float],
    coherent_evidence: dict[ResolvedOrientationLabel, float],
    preset: DomainAggregationPreset,
) -> bool:
    supported = (
        key
        for key in _CLASS_KEYS
        if evidence[key] >= preset.minimum_mixed_class_evidence
        and coherent_evidence[key] >= preset.minimum_mixed_coherent_evidence
    )
    return sum(1 for _ in supported) >= 2
