from __future__ import annotations

from dataclasses import dataclass

from .reference_review import (
    ReferenceReviewDecision,
    ReferenceReviewPolicy,
    ReferenceReviewTarget,
    ReferenceReviewWorkspace,
)
from .workspace_correction import DomainCorrectionWorkspaceState


@dataclass(frozen=True)
class SetReferenceReviewDecision:
    target: ReferenceReviewTarget
    physical_frame_id: str
    decision: ReferenceReviewDecision

    def __post_init__(self) -> None:
        target, physical_frame_id = _review_key(self.target, self.physical_frame_id)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "physical_frame_id", physical_frame_id)
        if not isinstance(self.decision, ReferenceReviewDecision):
            raise TypeError("decision must be a ReferenceReviewDecision.")


@dataclass(frozen=True)
class SignOffReferenceReview:
    target: ReferenceReviewTarget
    physical_frame_id: str

    def __post_init__(self) -> None:
        target, physical_frame_id = _review_key(self.target, self.physical_frame_id)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "physical_frame_id", physical_frame_id)


ReferenceReviewWorkspaceAction = (
    SetReferenceReviewDecision | SignOffReferenceReview
)


def reduce_reference_reviews(
    workspace: ReferenceReviewWorkspace,
    corrections: DomainCorrectionWorkspaceState,
    action: ReferenceReviewWorkspaceAction,
    policy: ReferenceReviewPolicy,
) -> ReferenceReviewWorkspace:
    if isinstance(action, SetReferenceReviewDecision):
        projection = corrections.effective_projection
        if projection is None:
            raise ValueError("Reference Review requires an effective projection.")
        return policy.record(
            workspace,
            projection,
            action.target,
            action.physical_frame_id,
            action.decision,
        )
    if isinstance(action, SignOffReferenceReview):
        return policy.sign_off(
            workspace,
            action.target,
            action.physical_frame_id,
        )
    raise TypeError("Unsupported Reference Review Workspace action.")


def _review_key(
    target: object,
    physical_frame_id: object,
) -> tuple[ReferenceReviewTarget, str]:
    if target not in {"m6", "orientation"}:
        raise ValueError(f"Unsupported Reference Review target: {target!r}.")
    if not isinstance(physical_frame_id, str) or not physical_frame_id.strip():
        raise ValueError("physical_frame_id must be non-empty text.")
    return target, physical_frame_id.strip()


__all__ = [
    "ReferenceReviewWorkspaceAction",
    "SetReferenceReviewDecision",
    "SignOffReferenceReview",
]
