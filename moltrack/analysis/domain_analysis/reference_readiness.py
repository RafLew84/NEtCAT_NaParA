from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeAlias, cast

from .fingerprints import canonical_sha256
from .reference_review import (
    ReferenceReviewPolicy,
    ReferenceReviewTarget,
    ReferenceReviewWorkspace,
)
from .session_state import DomainAnalysisSessionState
from .workspace_correction import DomainCorrectionWorkspaceState
from .workspace_controller import DomainAnalysisWorkspaceSnapshot


ReferenceReadinessBlockerCode = Literal[
    "no_active_publication",
    "correction_workspace_quarantined",
    "pending_automatic_candidate",
    "prepared_correction",
    "stale_rebase",
    "conflicted_rebase",
    "effective_projection_missing",
    "review_scope_missing",
    "review_decisions_incomplete",
    "review_sign_off_missing",
    "review_reason_missing",
    "source_revision_drifted",
    "calibration_split_missing",
    "validation_split_missing",
]
ReferenceSplit = Literal["calibration", "validation"]
ReferenceReadinessSnapshot: TypeAlias = (
    DomainAnalysisSessionState | DomainAnalysisWorkspaceSnapshot
)
_BLOCKER_CODES = frozenset({
    "no_active_publication",
    "correction_workspace_quarantined",
    "pending_automatic_candidate",
    "prepared_correction",
    "stale_rebase",
    "conflicted_rebase",
    "effective_projection_missing",
    "review_scope_missing",
    "review_decisions_incomplete",
    "review_sign_off_missing",
    "review_reason_missing",
    "source_revision_drifted",
    "calibration_split_missing",
    "validation_split_missing",
})


@dataclass(frozen=True)
class ReferenceReadinessBlocker:
    code: ReferenceReadinessBlockerCode
    message: str

    def __post_init__(self) -> None:
        if self.code not in _BLOCKER_CODES:
            raise ValueError(f"Unsupported Reference Readiness blocker: {self.code!r}.")
        if not self.message.strip():
            raise ValueError("Reference Readiness blocker message must be non-empty.")


@dataclass(frozen=True)
class ReferenceReadiness:
    target: ReferenceReviewTarget
    blockers: tuple[ReferenceReadinessBlocker, ...] = ()
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_target(self.target)
        if any(not isinstance(value, ReferenceReadinessBlocker) for value in self.blockers):
            raise TypeError("blockers must contain ReferenceReadinessBlocker values.")
        blockers = tuple(sorted(
            set(self.blockers),
            key=lambda value: (value.code, value.message),
        ))
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "fingerprint", canonical_sha256({
            "schema_version": "reference-readiness-v1",
            "target": self.target,
            "blockers": [
                {"code": value.code, "message": value.message}
                for value in blockers
            ],
        }))

    @property
    def ready(self) -> bool:
        return not self.blockers

    def require_ready(self) -> None:
        if not self.ready:
            raise ReferenceReadinessError(self)


class ReferenceReadinessError(ValueError):
    def __init__(self, result: ReferenceReadiness) -> None:
        self.result = result
        label = "M6" if result.target == "m6" else "Orientation"
        detail = "; ".join(
            f"{value.code}: {value.message}" for value in result.blockers
        )
        super().__init__(f"{label} Reference Dataset is not ready; {detail}")


class ReferenceReadinessSourceRevision(Protocol):
    def verify_current_bytes(self) -> None: ...


class ReferenceReadinessMeasurement(Protocol):
    @property
    def measurement_group_id(self) -> str: ...

    @property
    def split(self) -> ReferenceSplit: ...

    @property
    def snapshot(self) -> ReferenceReadinessSnapshot: ...

    @property
    def source_revision(self) -> ReferenceReadinessSourceRevision: ...


class ReferenceReadinessPolicy:
    """Own the target-specific gate shared by UI and reference publishers."""

    def evaluate_snapshot(
        self,
        snapshot: ReferenceReadinessSnapshot,
        target: ReferenceReviewTarget,
    ) -> ReferenceReadiness:
        target = _validate_target(target)
        publication, quarantine, corrections, reviews = _state(snapshot)
        label = "M6" if target == "m6" else "Orientation"
        blockers: list[ReferenceReadinessBlocker] = []
        result = None if publication is None else getattr(publication, "result", None)
        if publication is None or getattr(result, "m6_gate", None) is None:
            blockers.append(ReferenceReadinessBlocker(
                "no_active_publication",
                f"{label} Reference Dataset publication rejects draft state.",
            ))
        if publication is None and quarantine is not None:
            blockers.append(ReferenceReadinessBlocker(
                "correction_workspace_quarantined",
                f"Quarantined corrections cannot publish a {label} reference.",
            ))
        if corrections.pending_automatic_candidate is not None:
            blockers.append(ReferenceReadinessBlocker(
                "pending_automatic_candidate",
                f"Stale corrections cannot publish a {label} reference.",
            ))
        if corrections.prepared is not None:
            blockers.append(ReferenceReadinessBlocker(
                "prepared_correction",
                f"Prepared correction draft cannot publish a {label} reference.",
            ))
        rebase = corrections.prepared_rebase
        if rebase is not None:
            if rebase.is_ready:
                blockers.append(ReferenceReadinessBlocker(
                    "stale_rebase",
                    f"Stale correction rebase must be promoted before {label} publication.",
                ))
            else:
                blockers.append(ReferenceReadinessBlocker(
                    "conflicted_rebase",
                    f"Conflicted corrections cannot publish a {label} reference.",
                ))
        if (
            corrections.correction_set is None
            or corrections.effective_projection is None
        ):
            blockers.append(ReferenceReadinessBlocker(
                "effective_projection_missing",
                f"{label} Reference Dataset requires an effective projection.",
            ))
        review_readiness = ReferenceReviewPolicy().readiness(reviews, target)
        blockers.extend(
            ReferenceReadinessBlocker(value.code, value.message)
            for value in review_readiness.blockers
        )
        blockers.extend(_reason_blockers(reviews, target, label))
        return ReferenceReadiness(target, tuple(blockers))

    def evaluate_dataset(
        self,
        measurements: tuple[ReferenceReadinessMeasurement, ...],
        target: ReferenceReviewTarget,
        *,
        candidate_snapshot: ReferenceReadinessSnapshot | None = None,
    ) -> ReferenceReadiness:
        target = _validate_target(target)
        values = tuple(measurements)
        blockers = [
            blocker
            for measurement in values
            for blocker in self.evaluate_snapshot(measurement.snapshot, target).blockers
        ]
        blockers.extend(_source_revision_blockers(values))
        splits = {value.split for value in values}
        if candidate_snapshot is not None and splits != {"calibration", "validation"}:
            blockers.extend(
                self.evaluate_snapshot(candidate_snapshot, target).blockers
            )
        if "calibration" not in splits:
            blockers.append(_split_blocker("calibration"))
        if "validation" not in splits:
            blockers.append(_split_blocker("validation"))
        return ReferenceReadiness(target, tuple(blockers))


def _state(
    value: ReferenceReadinessSnapshot,
) -> tuple[
    object | None,
    object | None,
    DomainCorrectionWorkspaceState,
    ReferenceReviewWorkspace,
]:
    if isinstance(value, DomainAnalysisSessionState):
        return (
            value.published_result,
            value.correction_workspace_quarantine,
            value.domain_corrections,
            value.reference_reviews,
        )
    if isinstance(value, DomainAnalysisWorkspaceSnapshot):
        return (
            value.published,
            value.correction_workspace_quarantine,
            value.domain_corrections,
            value.reference_reviews,
        )
    raise TypeError("snapshot must be Domain Analysis reference state.")


def _reason_blockers(
    reviews: ReferenceReviewWorkspace,
    target: ReferenceReviewTarget,
    label: str,
) -> tuple[ReferenceReadinessBlocker, ...]:
    blockers = []
    for frame in reviews.frames:
        if frame.scope.target != target:
            continue
        for decision in frame.decisions:
            requires_reason = (
                decision.eligibility == "not_eligible"
                or decision.disposition == "rejected"
                or decision.abstention is not None
            )
            if requires_reason and decision.reason_code is None:
                blockers.append(ReferenceReadinessBlocker(
                    "review_reason_missing",
                    f"{label} review decision for {decision.source_id} requires a reason.",
                ))
    return tuple(blockers)


def _source_revision_blockers(
    measurements: tuple[ReferenceReadinessMeasurement, ...],
) -> tuple[ReferenceReadinessBlocker, ...]:
    blockers = []
    for measurement in measurements:
        try:
            measurement.source_revision.verify_current_bytes()
        except ValueError:
            blockers.append(ReferenceReadinessBlocker(
                "source_revision_drifted",
                "Reference source drift: current bytes differ for measurement "
                f"group {measurement.measurement_group_id}.",
            ))
    return tuple(blockers)


def _split_blocker(split: ReferenceSplit) -> ReferenceReadinessBlocker:
    label = "Calibration" if split == "calibration" else "Validation"
    code: ReferenceReadinessBlockerCode = (
        "calibration_split_missing"
        if split == "calibration"
        else "validation_split_missing"
    )
    return ReferenceReadinessBlocker(
        code,
        "Reference Dataset requires non-empty Calibration and Validation; "
        f"{label} is missing.",
    )


def _validate_target(target: object) -> ReferenceReviewTarget:
    if target not in {"m6", "orientation"}:
        raise ValueError(f"Unsupported Reference Readiness target: {target!r}.")
    return cast(ReferenceReviewTarget, target)


__all__ = [
    "ReferenceReadiness",
    "ReferenceReadinessBlocker",
    "ReferenceReadinessBlockerCode",
    "ReferenceReadinessError",
    "ReferenceReadinessMeasurement",
    "ReferenceReadinessPolicy",
    "ReferenceReadinessSnapshot",
    "ReferenceReadinessSourceRevision",
]
