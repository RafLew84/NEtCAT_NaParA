from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .domain_correction import DomainCorrectionModule
from .domain_correction_actions import (
    ApplyPreparedDomainCorrection,
    RedoDomainCorrection,
    UndoDomainCorrection,
)
from .reference_review import ReferenceReviewPolicy
from .workspace_correction import (
    ClearDomainMoleculeSelection,
    DiscardPreparedDomainCorrection,
    DomainCorrectionWorkspaceAction,
    PreviewCreateManualDomain,
    PreviewDeleteManualDomain,
    PreviewManualOrientation,
    PreviewManualOrientationReset,
    PreviewMoveToManualDomain,
    PreviewRestoreManualDomain,
    SelectDomainMolecules,
    SelectDomainMoleculesByPolygons,
    ToggleDomainMoleculeSelection,
    reduce_domain_corrections,
)
from .workspace_lifecycle_actions import DomainAnalysisWorkspaceIntentError
from .workspace_navigation import hierarchy_reference_diagnosis
from .workspace_review import (
    ReferenceReviewWorkspaceAction,
    reduce_reference_reviews,
)

if TYPE_CHECKING:
    from .workspace_controller import DomainAnalysisWorkspaceSnapshot


def is_correction_workspace_action(action: object) -> bool:
    return isinstance(action, (
        SelectDomainMolecules,
        SelectDomainMoleculesByPolygons,
        ToggleDomainMoleculeSelection,
        ClearDomainMoleculeSelection,
        DiscardPreparedDomainCorrection,
        PreviewManualOrientation,
        PreviewManualOrientationReset,
        PreviewCreateManualDomain,
        PreviewMoveToManualDomain,
        PreviewDeleteManualDomain,
        PreviewRestoreManualDomain,
        ApplyPreparedDomainCorrection,
        RedoDomainCorrection,
        UndoDomainCorrection,
    ))


def reduce_workspace_correction_action(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: DomainCorrectionWorkspaceAction,
    correction_module: DomainCorrectionModule,
    review_policy: ReferenceReviewPolicy,
) -> DomainAnalysisWorkspaceSnapshot:
    if snapshot.run.status == "running" and isinstance(action, (
        ApplyPreparedDomainCorrection,
        RedoDomainCorrection,
        UndoDomainCorrection,
    )):
        raise DomainAnalysisWorkspaceIntentError(
            "Correction history is read-only while a rerun is active."
        )
    automatic = None if snapshot.published is None else snapshot.published.result
    corrected = reduce_domain_corrections(
        snapshot.domain_corrections,
        automatic,
        snapshot.active_physical_frame_id,
        action,
        correction_module,
    )
    if corrected is snapshot.domain_corrections:
        return snapshot
    reviews = snapshot.reference_reviews
    if automatic is not None:
        reviews = review_policy.synchronize(reviews, automatic, corrected)
    highlight = snapshot.hierarchy_highlight
    if highlight is not None:
        diagnosis = hierarchy_reference_diagnosis(
            snapshot.active_physical_frame_id,
            automatic,
            highlight,
            corrected.effective_projection,
        )
        if diagnosis is not None:
            highlight = None
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        domain_corrections=corrected,
        reference_reviews=reviews,
        hierarchy_highlight=highlight,
    )


def reduce_workspace_reference_review_action(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: ReferenceReviewWorkspaceAction,
    review_policy: ReferenceReviewPolicy,
) -> DomainAnalysisWorkspaceSnapshot:
    if snapshot.published is None:
        raise DomainAnalysisWorkspaceIntentError(
            "Reference Review requires a published automatic result."
        )
    try:
        reviews = reduce_reference_reviews(
            snapshot.reference_reviews,
            snapshot.domain_corrections,
            action,
            review_policy,
        )
    except ValueError as error:
        raise DomainAnalysisWorkspaceIntentError(str(error)) from error
    if reviews == snapshot.reference_reviews:
        return snapshot
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        reference_reviews=reviews,
    )


__all__ = [
    "is_correction_workspace_action",
    "reduce_workspace_correction_action",
    "reduce_workspace_reference_review_action",
]
