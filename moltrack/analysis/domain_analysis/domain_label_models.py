from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from .fingerprints import canonical_sha256


DomainLabel = Literal["A", "B", "C", "Mixed", "Unknown orientation"]
ResolvedOrientationLabel = Literal["A", "B", "C"]


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
        object.__setattr__(self, "preset_id", _text(self.preset_id, "preset_id"))
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
                _fraction(getattr(self, field_name), field_name),
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
    evidence: tuple[tuple[str, float], ...]
    coherent_evidence: tuple[tuple[str, float], ...]
    resolved_fraction: float
    resolved_evidence: float
    dominant_class: ResolvedOrientationLabel | None
    dominance_margin: float
    reason: str
    aggregation_preset_id: str
    aggregation_preset_fingerprint: str
    classifier_id: str
    classifier_settings_fingerprint: str
    classifier_algorithm_version: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.frame_index, bool)
            or int(self.frame_index) != self.frame_index
            or int(self.frame_index) < 0
        ):
            raise ValueError("frame_index must be a non-negative integer.")
        object.__setattr__(self, "frame_index", int(self.frame_index))
        for field_name in (
            "physical_frame_id",
            "m6_gate_fingerprint",
            "lattice_domain_id",
            "reason",
            "aggregation_preset_id",
            "aggregation_preset_fingerprint",
            "classifier_id",
            "classifier_settings_fingerprint",
            "classifier_algorithm_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if self.label not in {"A", "B", "C", "Mixed", "Unknown orientation"}:
            raise ValueError(f"Unsupported domain label: {self.label!r}.")
        if self.dominant_class not in {"A", "B", "C", None}:
            raise ValueError(f"Unsupported dominant class: {self.dominant_class!r}.")
        if (
            isinstance(self.molecule_count, bool)
            or int(self.molecule_count) != self.molecule_count
            or int(self.molecule_count) < 1
        ):
            raise ValueError("molecule_count must be a positive integer.")
        object.__setattr__(self, "molecule_count", int(self.molecule_count))
        object.__setattr__(
            self,
            "counts",
            _counts(self.counts, self.molecule_count),
        )
        object.__setattr__(self, "evidence", _fractions(self.evidence, "evidence"))
        object.__setattr__(
            self,
            "coherent_evidence",
            _fractions(self.coherent_evidence, "coherent_evidence"),
        )
        for field_name in (
            "resolved_fraction",
            "resolved_evidence",
            "dominance_margin",
        ):
            object.__setattr__(
                self,
                field_name,
                _fraction(getattr(self, field_name), field_name),
            )


def _counts(
    values: tuple[tuple[str, int], ...],
    molecule_count: int,
) -> tuple[tuple[str, int], ...]:
    normalized = tuple(
        (str(key), _non_negative_integer(value, "counts"))
        for key, value in values
    )
    expected_keys = ("A", "B", "C", "Unknown orientation")
    if tuple(key for key, _ in normalized) != expected_keys:
        raise ValueError("counts must contain A, B, C and Unknown orientation.")
    if any(value < 0 for _, value in normalized):
        raise ValueError("counts cannot contain negative values.")
    if sum(value for _, value in normalized) != molecule_count:
        raise ValueError("counts must sum to molecule_count.")
    return normalized


def _fractions(
    values: tuple[tuple[str, float], ...],
    name: str,
) -> tuple[tuple[str, float], ...]:
    normalized = tuple((str(key), _fraction(value, name)) for key, value in values)
    if tuple(key for key, _ in normalized) != ("A", "B", "C"):
        raise ValueError(f"{name} must contain A, B and C.")
    return normalized


def _fraction(value: float, name: str) -> float:
    normalized = float(value)
    if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must lie between 0 and 1.")
    return normalized


def _non_negative_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or int(value) != value or int(value) < 0:
        raise ValueError(f"{name} must contain non-negative integers.")
    return int(value)


def _text(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1 = DomainAggregationPreset()


def classifier_configuration_fingerprint(
    *,
    classifier_id: str,
    classifier_settings_fingerprint: str,
    classifier_algorithm_version: str,
    aggregation_preset_id: str,
    aggregation_preset_fingerprint: str,
) -> str:
    """Bind molecule evidence and domain aggregation into one configuration."""

    return canonical_sha256({
        "classifier_id": classifier_id,
        "classifier_settings_fingerprint": classifier_settings_fingerprint,
        "classifier_algorithm_version": classifier_algorithm_version,
        "aggregation_preset_id": aggregation_preset_id,
        "aggregation_preset_fingerprint": aggregation_preset_fingerprint,
    })
