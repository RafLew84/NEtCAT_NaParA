from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from .correction_rebase import (
    ApplyPreparedCorrectionRebase,
    CorrectionRebasePolicy,
    PrepareCorrectionRebase,
)
from .domain_correction import DomainCorrectionModule
from .models import DomainAnalysisRequest, DomainAnalysisResult
from .reference_review import ReferenceReviewPolicy
from .workspace_correction import DomainCorrectionWorkspaceState
from .workspace_lifecycle_actions import DomainAnalysisWorkspaceIntentError

if TYPE_CHECKING:
    from .workspace_controller import (
        DomainAnalysisPublication,
        DomainAnalysisWorkspaceSnapshot,
    )


CorrectionRebaseWorkspaceAction = (
    PrepareCorrectionRebase | ApplyPreparedCorrectionRebase
)


def queue_pending_automatic_candidate(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    request: DomainAnalysisRequest,
    result: DomainAnalysisResult,
    rebase_policy: CorrectionRebasePolicy,
) -> DomainAnalysisWorkspaceSnapshot:
    publication = snapshot.published
    if publication is None:
        raise ValueError("An active publication is required before queuing a rerun.")
    candidate = rebase_policy.pending_candidate(
        publication.request,
        publication.result,
        request,
        result,
    )
    state = snapshot.domain_corrections
    if candidate is None or candidate == state.pending_automatic_candidate:
        return snapshot
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        domain_corrections=replace(
            state,
            prepared=None,
            pending_automatic_candidate=candidate,
            prepared_rebase=None,
        ),
    )


PublicationFactory = Callable[
    [DomainAnalysisRequest, DomainAnalysisResult],
    "DomainAnalysisPublication",
]


def reduce_workspace_rebase_action(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: CorrectionRebaseWorkspaceAction,
    correction_module: DomainCorrectionModule,
    rebase_policy: CorrectionRebasePolicy,
    review_policy: ReferenceReviewPolicy,
    publication_factory: PublicationFactory,
) -> DomainAnalysisWorkspaceSnapshot:
    if snapshot.run.status == "running":
        raise DomainAnalysisWorkspaceIntentError(
            "Correction Rebase is read-only while a rerun is active."
        )
    publication = snapshot.published
    state = snapshot.domain_corrections
    candidate = state.pending_automatic_candidate
    correction_set = state.correction_set
    if publication is None or candidate is None or correction_set is None:
        raise DomainAnalysisWorkspaceIntentError(
            "Correction Rebase requires an active result and pending candidate."
        )
    try:
        if isinstance(action, PrepareCorrectionRebase):
            prepared = rebase_policy.prepare(
                publication.request,
                publication.result,
                correction_set,
                candidate,
                action.resolutions,
            )
            if prepared == state.prepared_rebase:
                return snapshot
            return replace(
                snapshot,
                revision=snapshot.revision + 1,
                domain_corrections=replace(
                    state,
                    prepared=None,
                    prepared_rebase=prepared,
                ),
            )
        if action.preview != state.prepared_rebase:
            raise ValueError("Apply requires the current prepared Correction Rebase.")
        promotion = rebase_policy.promote(
            action.preview,
            publication.request,
            publication.result,
            correction_set,
            candidate,
        )
    except ValueError as error:
        raise DomainAnalysisWorkspaceIntentError(str(error)) from error
    promoted_publication = publication_factory(candidate.request, candidate.result)
    promoted_state = DomainCorrectionWorkspaceState(
        correction_set=promotion.correction_set,
        effective_projection=correction_module.project(
            candidate.result,
            promotion.correction_set,
        ),
        rebase_records=state.rebase_records + (promotion.record,),
    )
    reviews = review_policy.synchronize(
        snapshot.reference_reviews,
        candidate.result,
        promoted_state,
    )
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        published_revision=snapshot.published_revision + 1,
        published=promoted_publication,
        selected_component=None,
        hierarchy_highlight=None,
        domain_corrections=promoted_state,
        reference_reviews=reviews,
    )


__all__ = [
    "CorrectionRebaseWorkspaceAction",
    "queue_pending_automatic_candidate",
    "reduce_workspace_rebase_action",
]
