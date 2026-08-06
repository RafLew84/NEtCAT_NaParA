from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal

from .fingerprints import canonical_sha256

if TYPE_CHECKING:
    from .classifier_models import MoleculeClassification
    from .models import M6Gate, M6PublishedComponent


DomainLabel = Literal["A", "B", "C", "Mixed", "Unknown orientation"]
ResolvedOrientationLabel = Literal["A", "B", "C"]
DomainLabelReason = Literal[
    "insufficient_resolved_evidence",
    "dominant_class_passed",
    "multiple_coherent_classes",
    "no_publishable_label",
]


def validated_text(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def validated_unit_interval(value: float, name: str) -> float:
    normalized = float(value)
    if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must lie between 0 and 1.")
    return normalized


def validated_non_negative_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or int(value) != value or int(value) < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return int(value)


def validated_finite_pair(value: tuple[float, float], name: str) -> tuple[float, float]:
    pair = tuple(float(item) for item in value)
    if len(pair) != 2 or not all(isfinite(item) for item in pair):
        raise ValueError(f"{name} must be a finite pair.")
    return pair


@dataclass(frozen=True)
class ClassifierIdentity:
    """Versioned molecule-classifier identity."""

    classifier_id: str
    schema_version: str
    settings_fingerprint: str
    algorithm_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "classifier_id",
            "schema_version",
            "settings_fingerprint",
            "algorithm_version",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class DomainAggregationPreset:
    """Versioned conservative rule for one complete M6 domain."""

    preset_id: str = "abc-domain-summary-conservative-v1"
    minimum_resolved_evidence: float = 0.40
    minimum_dominant_evidence: float = 0.50
    minimum_dominance_margin: float = 0.20
    minimum_dominant_coherent_evidence: float = 0.40
    minimum_mixed_class_evidence: float = 0.20
    minimum_mixed_coherent_evidence: float = 0.15

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "preset_id",
            validated_text(self.preset_id, "preset_id"),
        )
        for field_name in (
            "minimum_resolved_evidence",
            "minimum_dominant_evidence",
            "minimum_dominance_margin",
            "minimum_dominant_coherent_evidence",
            "minimum_mixed_class_evidence",
            "minimum_mixed_coherent_evidence",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_unit_interval(getattr(self, field_name), field_name),
            )

    def as_dict(self) -> dict[str, str | float]:
        return {
            "preset_id": self.preset_id,
            "minimum_resolved_evidence": self.minimum_resolved_evidence,
            "minimum_dominant_evidence": self.minimum_dominant_evidence,
            "minimum_dominance_margin": self.minimum_dominance_margin,
            "minimum_dominant_coherent_evidence": (
                self.minimum_dominant_coherent_evidence
            ),
            "minimum_mixed_class_evidence": self.minimum_mixed_class_evidence,
            "minimum_mixed_coherent_evidence": (
                self.minimum_mixed_coherent_evidence
            ),
        }

    @property
    def fingerprint(self) -> str:
        return canonical_sha256(self.as_dict())


ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1 = DomainAggregationPreset()


@dataclass(frozen=True)
class ClassifierConfiguration:
    """One immutable, fingerprinted molecule and domain-label configuration."""

    identity: ClassifierIdentity
    aggregation_preset: DomainAggregationPreset

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ClassifierIdentity):
            raise TypeError("identity must be ClassifierIdentity.")
        if not isinstance(self.aggregation_preset, DomainAggregationPreset):
            raise TypeError("aggregation_preset must be DomainAggregationPreset.")

    @property
    def fingerprint(self) -> str:
        return canonical_sha256({
            "classifier_id": self.identity.classifier_id,
            "classifier_schema_version": self.identity.schema_version,
            "classifier_settings_fingerprint": self.identity.settings_fingerprint,
            "classifier_algorithm_version": self.identity.algorithm_version,
            "aggregation_preset_id": self.aggregation_preset.preset_id,
            "aggregation_preset_fingerprint": self.aggregation_preset.fingerprint,
        })


@dataclass(frozen=True)
class DomainLabelSummary:
    """Auditable classifier summary for one complete M6 domain."""

    frame_index: int
    physical_frame_id: str
    m6_gate_fingerprint: str
    lattice_domain_id: str
    label: DomainLabel
    molecule_count: int
    counts: tuple[tuple[str, int], ...]
    evidence_fraction_of_domain: tuple[tuple[str, float], ...]
    coherent_evidence_fraction_of_domain: tuple[tuple[str, float], ...]
    resolved_fraction: float
    resolved_evidence_fraction_of_domain: float
    dominant_class: ResolvedOrientationLabel | None
    dominance_margin: float
    reason: DomainLabelReason
    configuration: ClassifierConfiguration

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "frame_index",
            validated_non_negative_integer(self.frame_index, "frame_index"),
        )
        for field_name in (
            "physical_frame_id",
            "m6_gate_fingerprint",
            "lattice_domain_id",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_text(getattr(self, field_name), field_name),
            )
        if self.label not in {"A", "B", "C", "Mixed", "Unknown orientation"}:
            raise ValueError(f"Unsupported domain label: {self.label!r}.")
        if self.dominant_class not in {"A", "B", "C", None}:
            raise ValueError(f"Unsupported dominant class: {self.dominant_class!r}.")
        if self.reason not in {
            "insufficient_resolved_evidence",
            "dominant_class_passed",
            "multiple_coherent_classes",
            "no_publishable_label",
        }:
            raise ValueError(f"Unsupported domain label reason: {self.reason!r}.")
        molecule_count = validated_non_negative_integer(
            self.molecule_count,
            "molecule_count",
        )
        if molecule_count < 1:
            raise ValueError("molecule_count must be a positive integer.")
        object.__setattr__(self, "molecule_count", molecule_count)
        object.__setattr__(self, "counts", _counts(self.counts, molecule_count))
        for field_name in (
            "evidence_fraction_of_domain",
            "coherent_evidence_fraction_of_domain",
        ):
            object.__setattr__(
                self,
                field_name,
                _class_fractions(getattr(self, field_name), field_name),
            )
        for field_name in (
            "resolved_fraction",
            "resolved_evidence_fraction_of_domain",
            "dominance_margin",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_unit_interval(getattr(self, field_name), field_name),
            )
        if not isinstance(self.configuration, ClassifierConfiguration):
            raise TypeError("configuration must be ClassifierConfiguration.")

    @property
    def classifier_id(self) -> str:
        return self.configuration.identity.classifier_id

    @property
    def classifier_settings_fingerprint(self) -> str:
        return self.configuration.identity.settings_fingerprint

    @property
    def classifier_algorithm_version(self) -> str:
        return self.configuration.identity.algorithm_version

    @property
    def aggregation_preset_id(self) -> str:
        return self.configuration.aggregation_preset.preset_id

    @property
    def aggregation_preset_fingerprint(self) -> str:
        return self.configuration.aggregation_preset.fingerprint

    @property
    def classifier_configuration_fingerprint(self) -> str:
        return self.configuration.fingerprint


def _counts(
    values: tuple[tuple[str, int], ...],
    molecule_count: int,
) -> tuple[tuple[str, int], ...]:
    normalized = tuple(
        (str(key), validated_non_negative_integer(value, "counts"))
        for key, value in values
    )
    expected_keys = ("A", "B", "C", "Unknown orientation")
    if tuple(key for key, _ in normalized) != expected_keys:
        raise ValueError("counts must contain A, B, C and Unknown orientation.")
    if sum(value for _, value in normalized) != molecule_count:
        raise ValueError("counts must sum to molecule_count.")
    return normalized


def _class_fractions(
    values: tuple[tuple[str, float], ...],
    name: str,
) -> tuple[tuple[str, float], ...]:
    normalized = tuple(
        (str(key), validated_unit_interval(value, name)) for key, value in values
    )
    if tuple(key for key, _ in normalized) != ("A", "B", "C"):
        raise ValueError(f"{name} must contain A, B and C.")
    return normalized


_CLASS_KEYS: tuple[ResolvedOrientationLabel, ...] = ("A", "B", "C")
_UNKNOWN: Literal["Unknown orientation"] = "Unknown orientation"
_MIXED: Literal["Mixed"] = "Mixed"


def aggregate_domain_summaries(
    gate: M6Gate,
    classifications: tuple[MoleculeClassification, ...],
    configuration: ClassifierConfiguration,
) -> tuple[DomainLabelSummary, ...]:
    """Summarize only complete M6 domains from immutable molecule evidence."""

    if not isinstance(configuration, ClassifierConfiguration):
        raise TypeError("configuration must be ClassifierConfiguration.")
    by_domain = _classifications_by_domain(classifications)
    summaries = tuple(
        _aggregate_domain(
            gate_frame.frame_index,
            gate_frame.physical_frame_id,
            gate_frame.m6_gate_fingerprint,
            domain,
            by_domain.get((gate_frame.frame_index, domain.lattice_domain_id), ()),
            configuration,
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
    configuration: ClassifierConfiguration,
) -> DomainLabelSummary:
    source_ids = tuple(value.source_id for value in molecules)
    if source_ids != domain.source_ids:
        raise ValueError("Domain summary requires every M6-gated molecule exactly once.")
    total = len(domain.source_ids)
    counts = {
        key: sum(value.orientation_label == key for value in molecules)
        for key in (*_CLASS_KEYS, _UNKNOWN)
    }
    evidence_fraction_of_domain: dict[ResolvedOrientationLabel, float] = {
        key: sum(
            value.evidence_strength
            for value in molecules
            if value.orientation_label == key
        )
        / total
        for key in _CLASS_KEYS
    }
    coherent_evidence_fraction_of_domain = {
        key: _largest_component_evidence(molecules, key) / total
        for key in _CLASS_KEYS
    }
    resolved_count = total - counts[_UNKNOWN]
    resolved_evidence_fraction_of_domain = sum(evidence_fraction_of_domain.values())
    ranked = sorted(
        _CLASS_KEYS,
        key=lambda key: (-evidence_fraction_of_domain[key], key),
    )
    dominant: ResolvedOrientationLabel | None = (
        ranked[0] if evidence_fraction_of_domain[ranked[0]] > 0.0 else None
    )
    dominance_margin = (
        0.0
        if dominant is None
        else (
            evidence_fraction_of_domain[dominant]
            - evidence_fraction_of_domain[ranked[1]]
        )
    )
    label, reason = _domain_label(
        dominant,
        evidence_fraction_of_domain,
        coherent_evidence_fraction_of_domain,
        dominance_margin,
        resolved_evidence_fraction_of_domain,
        configuration.aggregation_preset,
    )
    return DomainLabelSummary(
        frame_index=frame_index,
        physical_frame_id=physical_frame_id,
        m6_gate_fingerprint=m6_gate_fingerprint,
        lattice_domain_id=domain.lattice_domain_id,
        label=label,
        molecule_count=total,
        counts=tuple((key, counts[key]) for key in (*_CLASS_KEYS, _UNKNOWN)),
        evidence_fraction_of_domain=tuple(
            (key, evidence_fraction_of_domain[key]) for key in _CLASS_KEYS
        ),
        coherent_evidence_fraction_of_domain=tuple(
            (key, coherent_evidence_fraction_of_domain[key])
            for key in _CLASS_KEYS
        ),
        resolved_fraction=resolved_count / total,
        resolved_evidence_fraction_of_domain=(
            resolved_evidence_fraction_of_domain
        ),
        dominant_class=dominant,
        dominance_margin=dominance_margin,
        reason=reason,
        configuration=configuration,
    )


def _domain_label(
    dominant: ResolvedOrientationLabel | None,
    evidence_fraction_of_domain: dict[ResolvedOrientationLabel, float],
    coherent_evidence_fraction_of_domain: dict[
        ResolvedOrientationLabel,
        float,
    ],
    dominance_margin: float,
    resolved_evidence_fraction_of_domain: float,
    preset: DomainAggregationPreset,
) -> tuple[DomainLabel, DomainLabelReason]:
    if resolved_evidence_fraction_of_domain < preset.minimum_resolved_evidence:
        return _UNKNOWN, "insufficient_resolved_evidence"
    if dominant is not None and _passes_single_class_gate(
        dominant,
        evidence_fraction_of_domain,
        coherent_evidence_fraction_of_domain,
        dominance_margin,
        preset,
    ):
        return dominant, "dominant_class_passed"
    if _passes_mixed_gate(
        evidence_fraction_of_domain,
        coherent_evidence_fraction_of_domain,
        preset,
    ):
        return _MIXED, "multiple_coherent_classes"
    return _UNKNOWN, "no_publishable_label"


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
    evidence_fraction_of_domain: dict[ResolvedOrientationLabel, float],
    coherent_evidence_fraction_of_domain: dict[
        ResolvedOrientationLabel,
        float,
    ],
    dominance_margin: float,
    preset: DomainAggregationPreset,
) -> bool:
    return (
        evidence_fraction_of_domain[dominant]
        >= preset.minimum_dominant_evidence
        and dominance_margin >= preset.minimum_dominance_margin
        and coherent_evidence_fraction_of_domain[dominant]
        >= preset.minimum_dominant_coherent_evidence
    )


def _passes_mixed_gate(
    evidence_fraction_of_domain: dict[ResolvedOrientationLabel, float],
    coherent_evidence_fraction_of_domain: dict[
        ResolvedOrientationLabel,
        float,
    ],
    preset: DomainAggregationPreset,
) -> bool:
    supported = (
        key
        for key in _CLASS_KEYS
        if evidence_fraction_of_domain[key]
        >= preset.minimum_mixed_class_evidence
        and coherent_evidence_fraction_of_domain[key]
        >= preset.minimum_mixed_coherent_evidence
    )
    return sum(1 for _ in supported) >= 2
