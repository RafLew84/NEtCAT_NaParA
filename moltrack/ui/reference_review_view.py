from __future__ import annotations

from moltrack.analysis.domain_analysis import (
    DomainAnalysisWorkspaceController,
    ReferenceReviewDecision,
    ReferenceReviewTarget,
    SetReferenceReviewDecision,
    SignOffReferenceReview,
)


class ReferenceReviewActionBinding:
    """Translate Review sheet signals into typed workspace actions."""

    def __init__(self, controller: DomainAnalysisWorkspaceController) -> None:
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        self._controller = controller

    def record_decision(
        self,
        target: ReferenceReviewTarget,
        physical_frame_id: str,
        decision: ReferenceReviewDecision,
    ) -> None:
        self._controller.dispatch(SetReferenceReviewDecision(
            target,
            physical_frame_id,
            decision,
        ))

    def sign_off(
        self,
        target: ReferenceReviewTarget,
        physical_frame_id: str,
    ) -> None:
        self._controller.dispatch(SignOffReferenceReview(
            target,
            physical_frame_id,
        ))


__all__ = ["ReferenceReviewActionBinding"]
