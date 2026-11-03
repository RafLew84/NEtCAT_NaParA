from __future__ import annotations

from moltrack.analysis.domain_analysis import (
    DetectionIdentity,
    ReferenceReviewDecision,
    ReferenceReviewTarget,
    ReferenceReviewWorkspace,
)


def reference_review_decisions_by_identity(
    workspace: ReferenceReviewWorkspace,
    target: ReferenceReviewTarget,
) -> dict[DetectionIdentity, ReferenceReviewDecision]:
    """Index one target's review decisions without losing frame identity."""

    if not isinstance(workspace, ReferenceReviewWorkspace):
        raise TypeError("workspace must be a ReferenceReviewWorkspace.")
    if target not in {"m6", "orientation"}:
        raise ValueError(f"Unsupported reference review target: {target!r}.")
    indexed: dict[DetectionIdentity, ReferenceReviewDecision] = {}
    for frame in workspace.frames:
        if frame.scope.target != target:
            continue
        for decision in frame.decisions:
            identity = DetectionIdentity(
                physical_frame_id=frame.scope.physical_frame_id,
                source_id=decision.source_id,
            )
            if identity in indexed:
                raise ValueError("Reference review identities must be unique.")
            indexed[identity] = decision
    return indexed


__all__ = ["reference_review_decisions_by_identity"]
