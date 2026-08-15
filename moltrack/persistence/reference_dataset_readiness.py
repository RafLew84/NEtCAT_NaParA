from __future__ import annotations

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSessionState,
    ReferenceReviewPolicy,
)

from .reference_dataset_identity import ReferenceTarget


def validate_reference_snapshot_readiness(
    state: DomainAnalysisSessionState,
    target: ReferenceTarget,
) -> None:
    """Apply the common publication gate to one target-reviewed snapshot."""

    label = "M6" if target == "m6" else "Orientation"
    if not isinstance(state, DomainAnalysisSessionState):
        raise TypeError("snapshot must be a DomainAnalysisSessionState.")
    if state.correction_workspace_quarantine is not None:
        raise ValueError(f"Quarantined corrections cannot publish a {label} reference.")
    publication = state.published_result
    if publication is None or publication.result.m6_gate is None:
        raise ValueError(f"{label} Reference Dataset publication rejects draft state.")
    corrections = state.domain_corrections
    if corrections.prepared_rebase is not None and not corrections.prepared_rebase.is_ready:
        raise ValueError(f"Conflicted corrections cannot publish a {label} reference.")
    if corrections.pending_automatic_candidate is not None:
        raise ValueError(f"Stale corrections cannot publish a {label} reference.")
    if corrections.prepared is not None:
        raise ValueError(
            f"Prepared correction draft cannot publish a {label} reference."
        )
    if corrections.correction_set is None or corrections.effective_projection is None:
        raise ValueError(f"{label} Reference Dataset requires an effective projection.")
    readiness = ReferenceReviewPolicy().readiness(state.reference_reviews, target)
    if not readiness.ready:
        raise ValueError(
            f"{label} Reference Dataset requires complete signed {label} review scope."
        )
    _validate_review_reasons(state, target, label)


def _validate_review_reasons(
    state: DomainAnalysisSessionState,
    target: ReferenceTarget,
    label: str,
) -> None:
    for frame in state.reference_reviews.frames:
        if frame.scope.target != target:
            continue
        for decision in frame.decisions:
            requires_reason = (
                decision.eligibility == "not_eligible"
                or decision.disposition == "rejected"
                or decision.abstention is not None
            )
            if requires_reason and decision.reason_code is None:
                raise ValueError(
                    f"{label} review decisions requiring a reason are incomplete."
                )


__all__ = ["validate_reference_snapshot_readiness"]
