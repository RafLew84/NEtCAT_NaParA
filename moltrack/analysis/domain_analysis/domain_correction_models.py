from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from .classifier_models import MoleculeClassification
from .fingerprints import canonical_sha256
from .domain_correction_history import (
    DomainCorrectionHistoryAvailability,
    DomainCorrectionHistoryRecord,
    history_availability,
    validate_history,
)
from .models import DomainAnalysisResult
from .manual_domain_models import EffectiveM6Domain, ManualDomainIntent, ManualDomainRecord


EffectiveOrientationSource = Literal["automatic", "manual", "none"]
ManualOrientationOperation = Literal["assign", "reset"]
DomainCorrectionAxis = Literal["m6", "orientation"]
DomainCorrectionConflictSeverity = Literal[
    "blocked",
    "confirmation_required",
    "informational",
]
DomainCorrectionReviewTarget = Literal["m6", "orientation"]


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
    cleared_boundary_source_keys: tuple[tuple[str, str], ...] = ()
    atoms: tuple[DomainCorrectionAtom, ...] = ()
    history_records: tuple[DomainCorrectionHistoryRecord, ...] = ()
    baseline_orientation_decisions: tuple[ManualOrientationDecision, ...] = ()
    baseline_manual_domains: tuple[ManualDomainRecord, ...] = ()
    legacy_boundary_source_keys: tuple[tuple[str, str], ...] | None = None
    review_revisions: tuple[tuple[DomainCorrectionReviewTarget, int], ...] = (
        ("m6", 0),
        ("orientation", 0),
    )

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
        boundary_keys = tuple(sorted({
            (
                _text(physical_frame_id, "boundary physical_frame_id"),
                _text(source_id, "boundary source_id"),
            )
            for physical_frame_id, source_id in self.cleared_boundary_source_keys
        }))
        object.__setattr__(self, "cleared_boundary_source_keys", boundary_keys)
        atoms = tuple(self.atoms)
        if any(not isinstance(value, DomainCorrectionAtom) for value in atoms):
            raise TypeError("atoms must contain DomainCorrectionAtom values.")
        operation_ids = tuple(value.operation_id for value in atoms)
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("Correction atom operation IDs must be unique.")
        object.__setattr__(self, "atoms", atoms)
        records = tuple(self.history_records)
        if any(
            not isinstance(value, DomainCorrectionHistoryRecord)
            for value in records
        ):
            raise TypeError(
                "history_records must contain DomainCorrectionHistoryRecord values."
            )
        validate_history(atoms, records)
        object.__setattr__(self, "history_records", records)
        baseline_values = (
            _baseline_orientation_decisions(self.baseline_orientation_decisions),
            _baseline_manual_domains(self.baseline_manual_domains),
        )
        object.__setattr__(self, "baseline_orientation_decisions", baseline_values[0])
        object.__setattr__(self, "baseline_manual_domains", baseline_values[1])
        raw_legacy_boundary_keys = self.legacy_boundary_source_keys
        legacy_boundary_keys = None if raw_legacy_boundary_keys is None else tuple(sorted({
            (
                _text(physical_frame_id, "legacy boundary physical_frame_id"),
                _text(source_id, "legacy boundary source_id"),
            )
            for physical_frame_id, source_id in raw_legacy_boundary_keys
        }))
        object.__setattr__(
            self,
            "legacy_boundary_source_keys",
            legacy_boundary_keys,
        )
        revisions = dict(self.review_revisions)
        if set(revisions) != {"m6", "orientation"}:
            raise ValueError("review_revisions must contain both review targets.")
        normalized_revisions = tuple(
            (target, _non_negative_integer(revisions[target], f"{target}_review_revision"))
            for target in ("m6", "orientation")
        )
        object.__setattr__(self, "review_revisions", normalized_revisions)

    def review_revision(self, target: DomainCorrectionReviewTarget) -> int:
        try:
            return dict(self.review_revisions)[target]
        except KeyError as error:
            raise ValueError(f"Unsupported review target: {target!r}.") from error

    def history_for(
        self,
        physical_frame_id: str,
    ) -> DomainCorrectionHistoryAvailability:
        return history_availability(
            self.atoms,
            self.history_records,
            physical_frame_id,
        )


@dataclass(frozen=True)
class DomainCorrectionEffect:
    source_id: str
    source_group: str
    before_value: str | None
    after_value: str | None
    before_boundary: bool | None = None
    after_boundary: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "source_group",
            _text(self.source_group, "source_group"),
        )
        for field_name in ("before_boundary", "after_boundary"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a bool or None.")


@dataclass(frozen=True)
class DomainCorrectionConflict:
    severity: DomainCorrectionConflictSeverity
    code: str
    message: str
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in {
            "blocked",
            "confirmation_required",
            "informational",
        }:
            raise ValueError(f"Unsupported conflict severity: {self.severity!r}.")
        object.__setattr__(self, "code", _text(self.code, "conflict code"))
        object.__setattr__(self, "message", _text(self.message, "conflict message"))
        object.__setattr__(self, "source_ids", _source_ids(self.source_ids))


@dataclass(frozen=True)
class DomainCorrectionAtom:
    operation_id: str
    prepared_fingerprint: str
    axis: DomainCorrectionAxis
    physical_frame_id: str
    source_ids: tuple[str, ...]
    intent: ManualOrientationIntent | ManualDomainIntent
    invalidates_review_targets: tuple[DomainCorrectionReviewTarget, ...]
    effects: tuple[DomainCorrectionEffect, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "operation_id",
            "prepared_fingerprint",
            "physical_frame_id",
        ):
            object.__setattr__(self, field_name, _text(
                getattr(self, field_name),
                field_name,
            ))
        if self.axis not in {"m6", "orientation"}:
            raise ValueError(f"Unsupported correction axis: {self.axis!r}.")
        if not isinstance(self.intent, (ManualOrientationIntent, ManualDomainIntent)):
            raise TypeError("Correction atom intent must be supported.")
        expected_axis = (
            "orientation" if isinstance(self.intent, ManualOrientationIntent) else "m6"
        )
        if self.axis != expected_axis:
            raise ValueError("Correction atom axis must match its intent.")
        object.__setattr__(self, "source_ids", _source_ids(self.source_ids))
        targets = tuple(sorted(set(self.invalidates_review_targets)))
        if not targets or any(value not in {"m6", "orientation"} for value in targets):
            raise ValueError("Correction atom must invalidate a supported review target.")
        object.__setattr__(self, "invalidates_review_targets", targets)
        effects = tuple(self.effects)
        if any(not isinstance(value, DomainCorrectionEffect) for value in effects):
            raise TypeError("Atom effects must contain DomainCorrectionEffect values.")
        effects = tuple(sorted(effects, key=lambda value: value.source_id))
        if effects and tuple(value.source_id for value in effects) != self.source_ids:
            raise ValueError("Atom effects must cover its frozen batch exactly.")
        object.__setattr__(self, "effects", effects)


@dataclass(frozen=True)
class PreparedDomainCorrection:
    expected_revision: int
    automatic_fingerprint: str
    intent: ManualOrientationIntent | ManualDomainIntent
    changed_source_ids: tuple[str, ...]
    source_ids: tuple[str, ...] = ()
    effects: tuple[DomainCorrectionEffect, ...] = ()
    conflicts: tuple[DomainCorrectionConflict, ...] = ()
    prepared_fingerprint: str = field(init=False)

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
        source_ids = _source_ids(self.source_ids or self.intent.source_ids or changed)
        object.__setattr__(self, "source_ids", source_ids)
        effects = tuple(sorted(self.effects, key=lambda value: value.source_id))
        conflicts = tuple(self.conflicts)
        if any(not isinstance(value, DomainCorrectionEffect) for value in effects):
            raise TypeError("effects must contain DomainCorrectionEffect values.")
        if any(not isinstance(value, DomainCorrectionConflict) for value in conflicts):
            raise TypeError("conflicts must contain DomainCorrectionConflict values.")
        if any(value.source_id not in source_ids for value in effects):
            raise ValueError("Correction effects must belong to the frozen batch.")
        object.__setattr__(self, "effects", effects)
        object.__setattr__(self, "conflicts", conflicts)
        object.__setattr__(self, "prepared_fingerprint", canonical_sha256({
            "schema_version": "prepared-domain-correction-v1",
            "expected_revision": self.expected_revision,
            "automatic_fingerprint": self.automatic_fingerprint,
            "intent": asdict(self.intent),
            "source_ids": source_ids,
            "changed_source_ids": changed,
            "effects": [asdict(value) for value in effects],
            "conflicts": [asdict(value) for value in conflicts],
        }))

    @property
    def axis(self) -> DomainCorrectionAxis:
        return "orientation" if isinstance(self.intent, ManualOrientationIntent) else "m6"

    @property
    def source_groups(self) -> tuple[str, ...]:
        return tuple(sorted({value.source_group for value in self.effects}))

    @property
    def is_blocked(self) -> bool:
        return any(value.severity == "blocked" for value in self.conflicts)

    @property
    def requires_confirmation(self) -> bool:
        return any(
            value.severity == "confirmation_required"
            for value in self.conflicts
        )

    @property
    def required_restore_member_resolutions(self) -> tuple[str, ...]:
        return tuple(sorted({
            source_id
            for conflict in self.conflicts
            if conflict.code == "restore_membership_conflict"
            for source_id in conflict.source_ids
        }))


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


def _baseline_orientation_decisions(
    values: tuple[ManualOrientationDecision, ...],
) -> tuple[ManualOrientationDecision, ...]:
    decisions = tuple(sorted(
        values,
        key=lambda value: (value.physical_frame_id, value.source_id),
    ))
    if any(not isinstance(value, ManualOrientationDecision) for value in decisions):
        raise TypeError(
            "baseline_orientation_decisions must contain manual decisions."
        )
    keys = tuple((value.physical_frame_id, value.source_id) for value in decisions)
    if len(keys) != len(set(keys)):
        raise ValueError(
            "baseline_orientation_decisions must have unique molecule keys."
        )
    return decisions


def _baseline_manual_domains(
    values: tuple[ManualDomainRecord, ...],
) -> tuple[ManualDomainRecord, ...]:
    domains = tuple(sorted(
        values,
        key=lambda value: (value.physical_frame_id, value.manual_domain_id),
    ))
    if any(not isinstance(value, ManualDomainRecord) for value in domains):
        raise TypeError(
            "baseline_manual_domains must contain ManualDomainRecord values."
        )
    domain_ids = tuple(value.manual_domain_id for value in domains)
    if len(domain_ids) != len(set(domain_ids)):
        raise ValueError("Baseline manual-domain UUIDs must be unique.")
    return domains


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value, "reason_code")


def _source_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, "source_id") for value in values}))


def _non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "DomainCorrectionAtom",
    "DomainCorrectionAxis",
    "DomainCorrectionConflict",
    "DomainCorrectionConflictSeverity",
    "DomainCorrectionEffect",
    "DomainCorrectionHistoryAvailability",
    "DomainCorrectionHistoryRecord",
    "DomainCorrectionReviewTarget",
    "DomainCorrectionWorkspace",
    "EffectiveDomainProjection",
    "EffectiveMoleculeOrientation",
    "EffectiveOrientationSubdomain",
    "EffectiveOrientationSource",
    "ManualOrientationDecision",
    "ManualOrientationIntent",
    "PreparedDomainCorrection",
]
