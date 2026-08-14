from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable, Literal

from .fingerprints import canonical_sha256
from .models import DomainAnalysisResult, M6FrameGate
from .domain_correction_models import (
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
)
from .workspace_correction import DomainCorrectionWorkspaceState


ReferenceReviewTarget = Literal["m6", "orientation"]
ReferenceReviewEligibility = Literal["eligible", "not_eligible"]
ReferenceReviewDisposition = Literal[
    "accepted_automatic",
    "corrected",
    "created",
    "rejected",
]
ReferenceReviewAbstention = Literal["uncertain", "unresolvable"]
ReferenceReviewStatus = Literal["draft", "reviewed"]


@dataclass(frozen=True)
class ReferenceReviewDecision:
    source_id: str
    eligibility: ReferenceReviewEligibility
    disposition: ReferenceReviewDisposition | None = None
    abstention: ReferenceReviewAbstention | None = None
    reason_code: str | None = None

    @classmethod
    def eligible(
        cls,
        source_id: str,
        *,
        disposition: ReferenceReviewDisposition,
        reason_code: str | None = None,
    ) -> ReferenceReviewDecision:
        return cls(
            source_id=source_id,
            eligibility="eligible",
            disposition=disposition,
            reason_code=reason_code,
        )

    @classmethod
    def abstain(
        cls,
        source_id: str,
        abstention: ReferenceReviewAbstention,
        *,
        reason_code: str,
    ) -> ReferenceReviewDecision:
        return cls(
            source_id=source_id,
            eligibility="eligible",
            disposition="rejected",
            abstention=abstention,
            reason_code=reason_code,
        )

    @classmethod
    def not_eligible(
        cls,
        source_id: str,
        *,
        reason_code: str,
    ) -> ReferenceReviewDecision:
        return cls(
            source_id=source_id,
            eligibility="not_eligible",
            reason_code=reason_code,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if self.eligibility not in {"eligible", "not_eligible"}:
            raise ValueError(f"Unsupported review eligibility: {self.eligibility!r}.")
        if self.disposition not in {
            None,
            "accepted_automatic",
            "corrected",
            "created",
            "rejected",
        }:
            raise ValueError(f"Unsupported review disposition: {self.disposition!r}.")
        if self.abstention not in {None, "uncertain", "unresolvable"}:
            raise ValueError(f"Unsupported review abstention: {self.abstention!r}.")
        reason = _optional_text(self.reason_code)
        object.__setattr__(self, "reason_code", reason)
        if self.eligibility == "not_eligible":
            if self.disposition is not None or self.abstention is not None:
                raise ValueError("A not-eligible decision cannot carry a disposition.")
            if reason is None:
                raise ValueError("A not-eligible decision requires a reason_code.")
            return
        if self.disposition is None:
            raise ValueError(
                "An eligible decision requires a review disposition."
            )
        if self.abstention is not None and self.disposition != "rejected":
            raise ValueError("A review abstention must reject the automatic decision.")
        if (
            self.disposition == "rejected" or self.abstention is not None
        ) and reason is None:
            raise ValueError(
                "Rejected, uncertain and unresolvable decisions require a reason_code."
            )


@dataclass(frozen=True)
class ReferenceReviewScope:
    target: ReferenceReviewTarget
    physical_frame_id: str
    automatic_fingerprint: str
    source_geometry_fingerprint: str
    annotation_revision: int
    source_ids: tuple[str, ...]
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_target(self.target)
        for field_name in (
            "physical_frame_id",
            "automatic_fingerprint",
            "source_geometry_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if isinstance(self.annotation_revision, bool) or self.annotation_revision < 0:
            raise ValueError("annotation_revision must be a non-negative integer.")
        source_ids = tuple(sorted(_text(value, "source_id") for value in self.source_ids))
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Reference Review Scope source IDs must be unique.")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "fingerprint", canonical_sha256({
            "schema_version": "reference-review-scope-v1",
            "target": self.target,
            "physical_frame_id": self.physical_frame_id,
            "automatic_fingerprint": self.automatic_fingerprint,
            "source_geometry_fingerprint": self.source_geometry_fingerprint,
            "annotation_revision": self.annotation_revision,
            "source_ids": source_ids,
        }))


@dataclass(frozen=True)
class ReferenceReviewSignOff:
    target: ReferenceReviewTarget
    physical_frame_id: str
    signed_at_utc: str
    signed_state_fingerprint: str

    def __post_init__(self) -> None:
        _validate_target(self.target)
        object.__setattr__(
            self,
            "physical_frame_id",
            _text(self.physical_frame_id, "physical_frame_id"),
        )
        timestamp = _text(self.signed_at_utc, "signed_at_utc")
        parsed = datetime.fromisoformat(timestamp)
        if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("signed_at_utc must be a UTC timestamp.")
        object.__setattr__(self, "signed_at_utc", timestamp)
        object.__setattr__(
            self,
            "signed_state_fingerprint",
            _text(self.signed_state_fingerprint, "signed_state_fingerprint"),
        )


@dataclass(frozen=True)
class ReferenceReviewFrame:
    scope: ReferenceReviewScope
    decisions: tuple[ReferenceReviewDecision, ...] = ()
    sign_off: ReferenceReviewSignOff | None = None
    state_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ReferenceReviewScope):
            raise TypeError("scope must be a ReferenceReviewScope.")
        decisions = tuple(sorted(self.decisions, key=lambda value: value.source_id))
        if any(not isinstance(value, ReferenceReviewDecision) for value in decisions):
            raise TypeError("decisions must contain ReferenceReviewDecision values.")
        source_ids = tuple(value.source_id for value in decisions)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Each scoped source_id can have only one review decision.")
        if any(value not in self.scope.source_ids for value in source_ids):
            raise ValueError("Review decisions must belong to the frozen scope.")
        object.__setattr__(self, "decisions", decisions)
        fingerprint = canonical_sha256({
            "schema_version": "reference-review-state-v1",
            "scope_fingerprint": self.scope.fingerprint,
            "decisions": [
                {
                    "source_id": value.source_id,
                    "eligibility": value.eligibility,
                    "disposition": value.disposition,
                    "abstention": value.abstention,
                    "reason_code": value.reason_code,
                }
                for value in decisions
            ],
        })
        object.__setattr__(self, "state_fingerprint", fingerprint)
        if self.sign_off is not None:
            if not isinstance(self.sign_off, ReferenceReviewSignOff):
                raise TypeError("sign_off must be a ReferenceReviewSignOff.")
            if not self.is_complete:
                raise ValueError(
                    "A Reference Review Sign-Off requires a complete frozen scope."
                )
            if (
                self.sign_off.target != self.scope.target
                or self.sign_off.physical_frame_id != self.scope.physical_frame_id
                or self.sign_off.signed_state_fingerprint != fingerprint
            ):
                raise ValueError("Reference Review Sign-Off does not match its state.")

    @property
    def status(self) -> ReferenceReviewStatus:
        return "reviewed" if self.sign_off is not None else "draft"

    @property
    def missing_source_ids(self) -> tuple[str, ...]:
        decided = {value.source_id for value in self.decisions}
        return tuple(value for value in self.scope.source_ids if value not in decided)

    @property
    def is_complete(self) -> bool:
        return not self.missing_source_ids


@dataclass(frozen=True)
class ReferenceReviewWorkspace:
    frames: tuple[ReferenceReviewFrame, ...] = ()

    def __post_init__(self) -> None:
        frames = tuple(sorted(
            self.frames,
            key=lambda value: (value.scope.physical_frame_id, value.scope.target),
        ))
        if any(not isinstance(value, ReferenceReviewFrame) for value in frames):
            raise TypeError("frames must contain ReferenceReviewFrame values.")
        keys = tuple(
            (value.scope.physical_frame_id, value.scope.target) for value in frames
        )
        if len(keys) != len(set(keys)):
            raise ValueError("Reference Review frame-target keys must be unique.")
        object.__setattr__(self, "frames", frames)

    def review_for(
        self,
        physical_frame_id: str,
        target: ReferenceReviewTarget,
    ) -> ReferenceReviewFrame:
        key = (_text(physical_frame_id, "physical_frame_id"), _validate_target(target))
        try:
            return next(
                value
                for value in self.frames
                if (value.scope.physical_frame_id, value.scope.target) == key
            )
        except StopIteration as error:
            raise ValueError(f"Unknown Reference Review scope: {key!r}.") from error

    def with_review(self, review: ReferenceReviewFrame) -> ReferenceReviewWorkspace:
        key = (review.scope.physical_frame_id, review.scope.target)
        if not any(
            (value.scope.physical_frame_id, value.scope.target) == key
            for value in self.frames
        ):
            raise ValueError(f"Unknown Reference Review scope: {key!r}.")
        return ReferenceReviewWorkspace(tuple(
            review
            if (value.scope.physical_frame_id, value.scope.target) == key
            else value
            for value in self.frames
        ))


@dataclass(frozen=True)
class ReferenceReviewReadiness:
    target: ReferenceReviewTarget
    ready: bool
    blockers: tuple[str, ...]


class ReferenceReviewPolicy:
    """Own completeness, explicit sign-off and derived target readiness."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def initialize(
        self,
        automatic: DomainAnalysisResult,
        corrections: DomainCorrectionWorkspaceState,
    ) -> ReferenceReviewWorkspace:
        return ReferenceReviewWorkspace(tuple(
            ReferenceReviewFrame(scope)
            for scope in _current_scopes(automatic, corrections)
        ))

    def synchronize(
        self,
        workspace: ReferenceReviewWorkspace,
        automatic: DomainAnalysisResult,
        corrections: DomainCorrectionWorkspaceState,
    ) -> ReferenceReviewWorkspace:
        previous = {
            (value.scope.physical_frame_id, value.scope.target): value
            for value in workspace.frames
        }
        synchronized = []
        for scope in _current_scopes(automatic, corrections):
            key = (scope.physical_frame_id, scope.target)
            review = previous.get(key)
            if review is None:
                synchronized.append(ReferenceReviewFrame(scope))
            elif review.scope == scope:
                synchronized.append(review)
            else:
                synchronized.append(ReferenceReviewFrame(scope=scope))
        return ReferenceReviewWorkspace(tuple(synchronized))

    def record(
        self,
        workspace: ReferenceReviewWorkspace,
        projection: EffectiveDomainProjection,
        target: ReferenceReviewTarget,
        physical_frame_id: str,
        decision: ReferenceReviewDecision,
    ) -> ReferenceReviewWorkspace:
        review = workspace.review_for(physical_frame_id, target)
        if decision.source_id not in review.scope.source_ids:
            raise ValueError("Reference Review decision is outside the frozen scope.")
        if decision.abstention == "uncertain" and target != "m6":
            raise ValueError("The uncertain abstention is only valid for M6 review.")
        if decision.abstention == "unresolvable" and target != "orientation":
            raise ValueError(
                "The unresolvable abstention is only valid for Orientation review."
            )
        if (
            target == "orientation"
            and decision.disposition == "accepted_automatic"
        ):
            molecule = projection.molecule(physical_frame_id, decision.source_id)
            classification = molecule.automatic_classification
            if (
                classification is None
                or classification.classification_status != "classified"
                or molecule.effective_orientation_source != "automatic"
            ):
                raise ValueError(
                    "An automatic abstention cannot be accepted as Orientation review."
                )
        if decision.disposition in {
            "accepted_automatic",
            "corrected",
            "created",
        }:
            expected = _scientific_disposition(
                projection,
                target,
                physical_frame_id,
                decision.source_id,
            )
            if decision.disposition != expected:
                raise ValueError(
                    f"Review disposition {decision.disposition!r} does not match "
                    f"the effective {target} scientific state."
                )
        elif decision.disposition == "rejected" and decision.abstention is None:
            expected = _scientific_disposition(
                projection,
                target,
                physical_frame_id,
                decision.source_id,
            )
            if expected != "accepted_automatic":
                raise ValueError(
                    "Review disposition 'rejected' does not match an existing "
                    f"automatic {target} scientific state."
                )
        decisions = {
            value.source_id: value for value in review.decisions
        }
        decisions[decision.source_id] = decision
        return workspace.with_review(replace(
            review,
            decisions=tuple(decisions.values()),
            sign_off=None,
        ))

    def sign_off(
        self,
        workspace: ReferenceReviewWorkspace,
        target: ReferenceReviewTarget,
        physical_frame_id: str,
    ) -> ReferenceReviewWorkspace:
        review = workspace.review_for(physical_frame_id, target)
        if not review.is_complete:
            raise ValueError(
                "Reference Review sign-off requires one complete decision "
                "for every source_id in the frozen scope."
            )
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("Reference Review clock must return an aware datetime.")
        timestamp = now.astimezone(timezone.utc).isoformat()
        return workspace.with_review(replace(
            review,
            sign_off=ReferenceReviewSignOff(
                target=review.scope.target,
                physical_frame_id=review.scope.physical_frame_id,
                signed_at_utc=timestamp,
                signed_state_fingerprint=review.state_fingerprint,
            ),
        ))

    def readiness(
        self,
        workspace: ReferenceReviewWorkspace,
        target: ReferenceReviewTarget,
    ) -> ReferenceReviewReadiness:
        target = _validate_target(target)
        reviews = tuple(
            value for value in workspace.frames if value.scope.target == target
        )
        blockers = []
        if not reviews:
            blockers.append(f"No frozen {target} review scopes exist.")
        for review in reviews:
            if review.missing_source_ids:
                blockers.append(
                    f"{review.scope.physical_frame_id}: missing decisions for "
                    f"{', '.join(review.missing_source_ids)}."
                )
            elif review.status != "reviewed":
                blockers.append(
                    f"{review.scope.physical_frame_id}: explicit sign-off is missing."
                )
        return ReferenceReviewReadiness(target, not blockers, tuple(blockers))


def _current_scopes(
    automatic: DomainAnalysisResult,
    corrections: DomainCorrectionWorkspaceState,
) -> tuple[ReferenceReviewScope, ...]:
        correction_set = corrections.correction_set
        projection = corrections.effective_projection
        if correction_set is None or projection is None or automatic.m6_gate is None:
            raise ValueError("Reference Review requires an effective published result.")
        scopes = []
        for frame in automatic.m6_gate.frames:
            for target in ("m6", "orientation"):
                scopes.append(ReferenceReviewScope(
                    target=target,
                    physical_frame_id=frame.physical_frame_id,
                    automatic_fingerprint=_review_automatic_fingerprint(
                        automatic,
                        frame,
                        target,
                    ),
                    source_geometry_fingerprint=frame.source_geometry_fingerprint,
                    annotation_revision=_frame_annotation_revision(
                        correction_set,
                        frame.physical_frame_id,
                        target,
                    ),
                    source_ids=frame.analyzed_source_ids,
                ))
        return tuple(scopes)


def _frame_annotation_revision(
    correction_set: DomainCorrectionWorkspace,
    physical_frame_id: str,
    target: ReferenceReviewTarget,
) -> int:
    atoms = {value.operation_id: value for value in correction_set.atoms}
    return sum(
        1
        for record in correction_set.history_records
        if record.physical_frame_id == physical_frame_id
        and target in atoms[record.operation_id].invalidates_review_targets
    )


def _review_automatic_fingerprint(
    automatic: DomainAnalysisResult,
    frame: M6FrameGate,
    target: ReferenceReviewTarget,
) -> str:
    payload: dict[str, object] = {
        "schema_version": "reference-review-automatic-anchor-v1",
        "target": target,
        "physical_frame_id": frame.physical_frame_id,
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
    }
    if target == "orientation":
        payload["classifiers"] = [
            {
                "classifier_id": outcome.classifier_id,
                "configuration_fingerprint": (
                    outcome.classifier_configuration_fingerprint
                ),
                "frame_result_fingerprint": next((
                    value.frame_result_fingerprint
                    for value in outcome.frame_result_provenance
                    if value.physical_frame_id == frame.physical_frame_id
                ), None),
                "classifications": [
                    asdict(value)
                    for value in outcome.molecule_classifications
                    if value.physical_frame_id == frame.physical_frame_id
                ],
                "frame_failure": (
                    outcome.error_message
                    if outcome.failure_frame_index == frame.frame_index
                    else None
                ),
            }
            for outcome in automatic.classifier_outcomes or ()
        ]
    return canonical_sha256(payload)


def _scientific_disposition(
    projection: EffectiveDomainProjection,
    target: ReferenceReviewTarget,
    physical_frame_id: str,
    source_id: str,
) -> ReferenceReviewDisposition | None:
    molecule = projection.molecule(physical_frame_id, source_id)
    if target == "orientation":
        if molecule.manual_decision is None:
            return (
                "accepted_automatic"
                if molecule.effective_orientation_source == "automatic"
                else None
            )
        classification = molecule.automatic_classification
        return (
            "corrected"
            if classification is not None
            and classification.classification_status == "classified"
            else "created"
        )
    automatic_partition, automatic_domain_id = _automatic_m6_state(
        projection,
        physical_frame_id,
        source_id,
    )
    effective_state = (molecule.m6_partition, molecule.effective_domain_id)
    if effective_state == (automatic_partition, automatic_domain_id):
        return "accepted_automatic"
    if automatic_partition != "full_domain" and molecule.m6_partition == "full_domain":
        return "created"
    return "corrected"


def _automatic_m6_state(
    projection: EffectiveDomainProjection,
    physical_frame_id: str,
    source_id: str,
) -> tuple[str, str | None]:
    gate = projection.automatic_result.m6_gate
    assert gate is not None
    frame = next(
        value
        for value in gate.frames
        if value.physical_frame_id == physical_frame_id
    )
    for component in frame.full_domains:
        if source_id in component.source_ids:
            return "full_domain", component.lattice_domain_id
    for component in frame.small_ordered_islands:
        if source_id in component.source_ids:
            return "small_ordered_island", None
    if source_id in frame.outside_source_ids:
        return "outside", None
    raise ValueError(f"Unknown automatic source_id: {source_id!r}.")


def _validate_target(value: object) -> ReferenceReviewTarget:
    if value not in {"m6", "orientation"}:
        raise ValueError(f"Unsupported Reference Review target: {value!r}.")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value, "reason_code")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "ReferenceReviewAbstention",
    "ReferenceReviewDecision",
    "ReferenceReviewDisposition",
    "ReferenceReviewEligibility",
    "ReferenceReviewFrame",
    "ReferenceReviewPolicy",
    "ReferenceReviewReadiness",
    "ReferenceReviewScope",
    "ReferenceReviewSignOff",
    "ReferenceReviewStatus",
    "ReferenceReviewTarget",
    "ReferenceReviewWorkspace",
]
