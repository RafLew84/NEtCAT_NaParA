from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .classifier_models import MoleculeClassification
from .models import DomainAnalysisResult
from .manual_domain_models import EffectiveM6Domain, ManualDomainIntent, ManualDomainRecord


EffectiveOrientationSource = Literal["automatic", "manual", "none"]
ManualOrientationOperation = Literal["assign", "reset"]


@dataclass(frozen=True)
class ManualOrientationIntent:
    physical_frame_id: str
    source_ids: tuple[str, ...]
    operation: ManualOrientationOperation
    orientation_label: str | None = None
    reason_code: str | None = None

    @classmethod
    def assign(
        cls,
        *,
        physical_frame_id: str,
        source_ids: tuple[str, ...],
        orientation_label: str,
        reason_code: str | None = None,
    ) -> ManualOrientationIntent:
        return cls(
            physical_frame_id=physical_frame_id,
            source_ids=source_ids,
            operation="assign",
            orientation_label=orientation_label,
            reason_code=reason_code,
        )

    @classmethod
    def reset(
        cls,
        *,
        physical_frame_id: str,
        source_ids: tuple[str, ...],
    ) -> ManualOrientationIntent:
        return cls(
            physical_frame_id=physical_frame_id,
            source_ids=source_ids,
            operation="reset",
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "physical_frame_id",
            _text(self.physical_frame_id, "physical_frame_id"),
        )
        source_ids = tuple(sorted({
            _text(value, "source_id") for value in self.source_ids
        }))
        if not source_ids:
            raise ValueError("source_ids must not be empty.")
        object.__setattr__(self, "source_ids", source_ids)
        if self.operation not in {"assign", "reset"}:
            raise ValueError(f"Unsupported orientation operation: {self.operation!r}.")
        if self.operation == "reset":
            if self.orientation_label is not None or self.reason_code is not None:
                raise ValueError("Reset orientation cannot carry a target or reason.")
            return
        label = _orientation_label(self.orientation_label)
        reason = _optional_text(self.reason_code)
        if label == "Unresolvable" and reason is None:
            raise ValueError("Unresolvable orientation requires a reason_code.")
        object.__setattr__(self, "orientation_label", label)
        object.__setattr__(self, "reason_code", reason)


@dataclass(frozen=True)
class ManualOrientationDecision:
    physical_frame_id: str
    source_id: str
    orientation_label: str
    reason_code: str | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "physical_frame_id",
            _text(self.physical_frame_id, "physical_frame_id"),
        )
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        label = _orientation_label(self.orientation_label)
        reason = _optional_text(self.reason_code)
        if label == "Unresolvable" and reason is None:
            raise ValueError("Unresolvable orientation requires a reason_code.")
        object.__setattr__(self, "orientation_label", label)
        object.__setattr__(self, "reason_code", reason)


@dataclass(frozen=True)
class DomainCorrectionWorkspace:
    automatic_fingerprint: str
    revision: int
    orientation_decisions: tuple[ManualOrientationDecision, ...] = ()
    manual_domains: tuple[ManualDomainRecord, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "automatic_fingerprint",
            _text(self.automatic_fingerprint, "automatic_fingerprint"),
        )
        if isinstance(self.revision, bool) or self.revision < 0:
            raise ValueError("revision must be a non-negative integer.")
        decisions = tuple(sorted(
            self.orientation_decisions,
            key=lambda value: (value.physical_frame_id, value.source_id),
        ))
        if any(not isinstance(value, ManualOrientationDecision) for value in decisions):
            raise TypeError("orientation_decisions must contain manual decisions.")
        keys = tuple((value.physical_frame_id, value.source_id) for value in decisions)
        if len(keys) != len(set(keys)):
            raise ValueError("orientation_decisions must have unique molecule keys.")
        object.__setattr__(self, "orientation_decisions", decisions)
        domains = tuple(sorted(
            self.manual_domains,
            key=lambda value: (value.physical_frame_id, value.manual_domain_id),
        ))
        if any(not isinstance(value, ManualDomainRecord) for value in domains):
            raise TypeError("manual_domains must contain ManualDomainRecord values.")
        domain_ids = tuple(value.manual_domain_id for value in domains)
        if len(domain_ids) != len(set(domain_ids)):
            raise ValueError("manual_domains must have globally unique UUIDs.")
        object.__setattr__(self, "manual_domains", domains)


@dataclass(frozen=True)
class PreparedDomainCorrection:
    expected_revision: int
    automatic_fingerprint: str
    intent: ManualOrientationIntent | ManualDomainIntent
    changed_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if isinstance(self.expected_revision, bool) or self.expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer.")
        object.__setattr__(
            self,
            "automatic_fingerprint",
            _text(self.automatic_fingerprint, "automatic_fingerprint"),
        )
        if not isinstance(self.intent, (ManualOrientationIntent, ManualDomainIntent)):
            raise TypeError("intent must be a supported Domain Correction intent.")
        changed = tuple(sorted({
            _text(value, "source_id") for value in self.changed_source_ids
        }))
        validates_selected_sources = (
            isinstance(self.intent, ManualOrientationIntent)
            or self.intent.operation in {"create", "move"}
        )
        if validates_selected_sources and any(
            value not in self.intent.source_ids for value in changed
        ):
            raise ValueError(
                "changed_source_ids must belong to the prepared intent."
            )
        object.__setattr__(self, "changed_source_ids", changed)


@dataclass(frozen=True)
class ApplyPreparedDomainCorrection:
    preview: PreparedDomainCorrection

    def __post_init__(self) -> None:
        if not isinstance(self.preview, PreparedDomainCorrection):
            raise TypeError("preview must be a PreparedDomainCorrection.")


@dataclass(frozen=True)
class EffectiveMoleculeOrientation:
    physical_frame_id: str
    source_id: str
    m6_partition: str
    effective_domain_id: str | None
    automatic_classification: MoleculeClassification | None
    manual_decision: ManualOrientationDecision | None
    effective_orientation: str | None
    effective_orientation_source: EffectiveOrientationSource
    effective_confidence: float | None
    raw_orientation_evidence: object | None
    is_boundary: bool | None
    footprint_pixels_xy: tuple[tuple[int, int], ...] | None


@dataclass(frozen=True)
class EffectiveOrientationSubdomain:
    physical_frame_id: str
    lattice_domain_id: str
    orientation_label: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class EffectiveDomainProjection:
    automatic_result: DomainAnalysisResult
    correction_revision: int
    molecules: tuple[EffectiveMoleculeOrientation, ...]
    orientation_subdomains: tuple[EffectiveOrientationSubdomain, ...]
    domains: tuple[EffectiveM6Domain, ...] = ()

    def molecule(
        self,
        physical_frame_id: str,
        source_id: str,
    ) -> EffectiveMoleculeOrientation:
        key = (physical_frame_id, source_id)
        try:
            return next(
                value
                for value in self.molecules
                if (value.physical_frame_id, value.source_id) == key
            )
        except StopIteration as error:
            raise ValueError(f"Unknown effective molecule: {key!r}.") from error

    def domain(
        self,
        physical_frame_id: str,
        lattice_domain_id: str,
    ) -> EffectiveM6Domain:
        key = (physical_frame_id, lattice_domain_id)
        try:
            return next(
                value
                for value in self.domains
                if (value.physical_frame_id, value.lattice_domain_id) == key
            )
        except StopIteration as error:
            raise ValueError(f"Unknown effective domain: {key!r}.") from error


def _orientation_label(value: object) -> str:
    if value == "Unresolvable":
        return value
    label = _text(value, "orientation_label")
    if len(label) != 1 or not "A" <= label <= "Z":
        raise ValueError("orientation_label must be A-Z or Unresolvable.")
    return label


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value, "reason_code")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "ApplyPreparedDomainCorrection",
    "DomainCorrectionWorkspace",
    "EffectiveDomainProjection",
    "EffectiveMoleculeOrientation",
    "EffectiveOrientationSubdomain",
    "EffectiveOrientationSource",
    "ManualOrientationDecision",
    "ManualOrientationIntent",
    "PreparedDomainCorrection",
]
