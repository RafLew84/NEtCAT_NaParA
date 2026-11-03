from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from functools import partial

import pytest

from moltrack.analysis.domain_analysis import (
    ApplyPreparedCorrectionRebase,
    ApplyPreparedDomainCorrection,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceIntentError,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M6Gate,
    PrepareCorrectionRebase,
    PublishDomainAnalysisResult,
    PreviewCreateManualDomain,
    PreviewManualOrientation,
    ReferenceReviewDecision,
    ReferenceReviewFrame,
    ReferenceReviewPolicy,
    ReferenceReviewScope,
    ReferenceReviewSignOff,
    SetReferenceReviewDecision,
    SelectDomainMolecules,
    SignOffReferenceReview,
)
from test_domain_correction_orientation import _automatic_result
from test_domain_analysis_workspace_controller import _completed_result


DomainAnalysisRequest = partial(
    DomainAnalysisRequest,
    backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)


def test_complete_m6_sign_off_keeps_orientation_review_draft() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
        review_policy=ReferenceReviewPolicy(
            clock=lambda: datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc)
        ),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="complete decision",
    ):
        controller.dispatch(SignOffReferenceReview("m6", "frame-0"))

    for source_id in ("full", "island", "outside"):
        controller.dispatch(SetReferenceReviewDecision(
            "m6",
            "frame-0",
            ReferenceReviewDecision.eligible(
                source_id,
                disposition="accepted_automatic",
            ),
        ))
    reviewed = controller.dispatch(SignOffReferenceReview("m6", "frame-0"))

    m6_review = reviewed.reference_reviews.review_for("frame-0", "m6")
    orientation_review = reviewed.reference_reviews.review_for(
        "frame-0",
        "orientation",
    )
    assert m6_review.status == "reviewed"
    assert m6_review.sign_off is not None
    assert m6_review.sign_off.signed_at_utc == "2026-08-14T12:30:00+00:00"
    assert not hasattr(m6_review.sign_off, "reviewer_id")
    assert orientation_review.status == "draft"
    assert ReferenceReviewPolicy().readiness(
        reviewed.reference_reviews,
        "m6",
    ).ready
    assert not ReferenceReviewPolicy().readiness(
        reviewed.reference_reviews,
        "orientation",
    ).ready


def test_automatic_orientation_abstention_cannot_be_accepted_as_review() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="automatic abstention",
    ):
        controller.dispatch(SetReferenceReviewDecision(
            "orientation",
            "frame-0",
            ReferenceReviewDecision.eligible(
                "island",
                disposition="accepted_automatic",
            ),
        ))

    review = controller.snapshot.reference_reviews.review_for(
        "frame-0",
        "orientation",
    )
    assert review.decisions == ()


@pytest.mark.parametrize(
    ("target", "abstention"),
    (("orientation", "uncertain"), ("m6", "unresolvable")),
)
def test_review_abstentions_are_target_specific(target, abstention) -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="only valid",
    ):
        controller.dispatch(SetReferenceReviewDecision(
            target,
            "frame-0",
            ReferenceReviewDecision.abstain(
                "full",
                abstention,
                reason_code="scientific_abstention",
            ),
        ))


def test_orientation_correction_invalidates_only_orientation_sign_off() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))
    for source_id in ("full", "island", "outside"):
        controller.dispatch(SetReferenceReviewDecision(
            "m6",
            "frame-0",
            ReferenceReviewDecision.eligible(
                source_id,
                disposition="accepted_automatic",
            ),
        ))
    controller.dispatch(SetReferenceReviewDecision(
        "orientation",
        "frame-0",
        ReferenceReviewDecision.eligible(
            "full",
            disposition="accepted_automatic",
        ),
    ))
    for source_id in ("island", "outside"):
        controller.dispatch(SetReferenceReviewDecision(
            "orientation",
            "frame-0",
            ReferenceReviewDecision.not_eligible(
                source_id,
                reason_code="automatic_gate_excluded",
            ),
        ))
    controller.dispatch(SignOffReferenceReview("m6", "frame-0"))
    signed = controller.dispatch(SignOffReferenceReview(
        "orientation",
        "frame-0",
    ))
    signed_orientation = signed.reference_reviews.review_for(
        "frame-0",
        "orientation",
    )

    controller.dispatch(SelectDomainMolecules(("outside",)))
    previewed = controller.dispatch(PreviewManualOrientation("D"))
    preview = previewed.domain_corrections.prepared
    assert preview is not None
    corrected = controller.dispatch(
        ApplyPreparedDomainCorrection.confirmed(preview)
    )

    m6_review = corrected.reference_reviews.review_for("frame-0", "m6")
    orientation_review = corrected.reference_reviews.review_for(
        "frame-0",
        "orientation",
    )
    assert m6_review.status == "reviewed"
    assert orientation_review.status == "draft"
    assert orientation_review.sign_off is None
    assert orientation_review.decisions == ()
    assert (
        orientation_review.scope.annotation_revision
        == signed_orientation.scope.annotation_revision + 1
    )


@pytest.mark.parametrize(
    ("target", "source_id", "disposition"),
    (
        ("m6", "full", "created"),
        ("orientation", "full", "corrected"),
        ("orientation", "outside", "created"),
        ("orientation", "outside", "rejected"),
    ),
)
def test_disposition_must_match_the_effective_scientific_state(
    target,
    source_id,
    disposition,
) -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="does not match",
    ):
        controller.dispatch(SetReferenceReviewDecision(
            target,
            "frame-0",
            ReferenceReviewDecision.eligible(
                source_id,
                disposition=disposition,
                reason_code=(
                    "rejected_automatic"
                    if disposition == "rejected"
                    else None
                ),
            ),
        ))


@pytest.mark.parametrize(
    "decision_factory",
    (
        lambda: ReferenceReviewDecision.eligible(
            "full",
            disposition="rejected",
        ),
        lambda: ReferenceReviewDecision.abstain("full", "uncertain", reason_code=""),
        lambda: ReferenceReviewDecision.abstain(
            "full",
            "unresolvable",
            reason_code="",
        ),
        lambda: ReferenceReviewDecision.not_eligible("full", reason_code=""),
    ),
)
def test_rejection_abstention_and_exclusion_require_a_reason(
    decision_factory,
) -> None:
    with pytest.raises(ValueError, match="reason"):
        decision_factory()


def test_abstention_keeps_an_independent_rejected_disposition() -> None:
    decision = ReferenceReviewDecision.abstain(
        "full",
        "uncertain",
        reason_code="ambiguous_membership",
    )

    assert decision.disposition == "rejected"
    assert decision.abstention == "uncertain"


def test_m6_correction_invalidates_both_target_sign_offs() -> None:
    controller = _signed_controller()
    before = controller.snapshot.reference_reviews

    controller.dispatch(SelectDomainMolecules(("outside",)))
    previewed = controller.dispatch(PreviewCreateManualDomain())
    preview = previewed.domain_corrections.prepared
    assert preview is not None
    corrected = controller.dispatch(
        ApplyPreparedDomainCorrection.confirmed(preview)
    )

    for target in ("m6", "orientation"):
        previous = before.review_for("frame-0", target)
        review = corrected.reference_reviews.review_for("frame-0", target)
        assert review.status == "draft"
        assert review.sign_off is None
        assert review.decisions == ()
        assert review.scope.annotation_revision == previous.scope.annotation_revision + 1


def test_correction_invalidates_only_the_touched_frame_review() -> None:
    request = DomainAnalysisRequest(frame_range=range(2))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0", "physical-frame-1"),
    )
    controller.dispatch(PublishDomainAnalysisResult(
        request,
        _completed_result(range(2)),
    ))
    for frame_index in range(2):
        controller.dispatch(SetReferenceReviewDecision(
            "m6",
            f"physical-frame-{frame_index}",
            ReferenceReviewDecision.eligible(
                f"molecule-{frame_index}",
                disposition="accepted_automatic",
            ),
        ))
        controller.dispatch(SignOffReferenceReview(
            "m6",
            f"physical-frame-{frame_index}",
        ))

    controller.dispatch(SelectDomainMolecules(("molecule-0",)))
    previewed = controller.dispatch(PreviewCreateManualDomain())
    preview = previewed.domain_corrections.prepared
    assert preview is not None
    corrected = controller.dispatch(
        ApplyPreparedDomainCorrection.confirmed(preview)
    )

    assert corrected.reference_reviews.review_for(
        "physical-frame-0",
        "m6",
    ).status == "draft"
    assert corrected.reference_reviews.review_for(
        "physical-frame-1",
        "m6",
    ).status == "reviewed"


def test_new_source_revision_returns_both_target_reviews_to_draft() -> None:
    controller = _signed_controller()
    publication = controller.snapshot.published
    assert publication is not None
    automatic = publication.result
    gate = automatic.m6_gate
    assert gate is not None
    changed_frame = replace(
        gate.frames[0],
        source_geometry_fingerprint="geometry-1",
    )
    changed_automatic = replace(automatic, m6_gate=M6Gate((changed_frame,)))

    republished = _publish_and_promote(controller, PublishDomainAnalysisResult(
        publication.request,
        changed_automatic,
    ))

    for target in ("m6", "orientation"):
        review = republished.reference_reviews.review_for("frame-0", target)
        assert review.status == "draft"
        assert review.decisions == ()
        assert review.scope.source_geometry_fingerprint == "geometry-1"


def test_identical_republication_preserves_valid_target_sign_offs() -> None:
    controller = _signed_controller()
    before = controller.snapshot
    publication = before.published
    assert publication is not None

    republished = controller.dispatch(PublishDomainAnalysisResult(
        publication.request,
        publication.result,
    ))

    assert republished.reference_reviews == before.reference_reviews


def test_orientation_automatic_change_preserves_m6_sign_off() -> None:
    controller = _signed_controller()
    before = controller.snapshot
    publication = before.published
    assert publication is not None
    without_orientation = replace(
        publication.result,
        classifier_status="not_requested",
        classifier_outcomes=None,
    )

    republished = _publish_and_promote(controller, PublishDomainAnalysisResult(
        publication.request,
        without_orientation,
    ))

    assert republished.reference_reviews.review_for(
        "frame-0",
        "m6",
    ).status == "reviewed"
    assert republished.reference_reviews.review_for(
        "frame-0",
        "orientation",
    ).status == "draft"


def test_one_frame_source_change_preserves_other_frame_sign_off() -> None:
    request = DomainAnalysisRequest(frame_range=range(2))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0", "physical-frame-1"),
    )
    automatic = _completed_result(range(2))
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    for frame_index in range(2):
        controller.dispatch(SetReferenceReviewDecision(
            "m6",
            f"physical-frame-{frame_index}",
            ReferenceReviewDecision.eligible(
                f"molecule-{frame_index}",
                disposition="accepted_automatic",
            ),
        ))
        controller.dispatch(SignOffReferenceReview(
            "m6",
            f"physical-frame-{frame_index}",
        ))
    gate = automatic.m6_gate
    assert gate is not None
    changed_frame = replace(
        gate.frames[0],
        source_geometry_fingerprint="changed-geometry-0",
    )
    changed_automatic = replace(
        automatic,
        m6_gate=M6Gate((changed_frame, gate.frames[1])),
    )

    republished = _publish_and_promote(controller, PublishDomainAnalysisResult(
        request,
        changed_automatic,
    ))

    assert republished.reference_reviews.review_for(
        "physical-frame-0",
        "m6",
    ).status == "draft"
    assert republished.reference_reviews.review_for(
        "physical-frame-1",
        "m6",
    ).status == "reviewed"


def test_incomplete_review_cannot_be_reconstructed_with_a_sign_off() -> None:
    review = ReferenceReviewFrame(
        scope=ReferenceReviewScope(
            target="m6",
            physical_frame_id="frame-0",
            automatic_fingerprint="automatic-0",
            source_geometry_fingerprint="geometry-0",
            annotation_revision=0,
            source_ids=("full", "outside"),
        ),
        decisions=(ReferenceReviewDecision.eligible(
            "full",
            disposition="accepted_automatic",
        ),),
    )

    with pytest.raises(ValueError, match="complete"):
        replace(
            review,
            sign_off=ReferenceReviewSignOff(
                target="m6",
                physical_frame_id="frame-0",
                signed_at_utc="2026-08-14T12:30:00+00:00",
                signed_state_fingerprint=review.state_fingerprint,
            ),
        )


def test_empty_frozen_scope_can_be_explicitly_signed_off() -> None:
    automatic = _completed_result(range(1))
    gate = automatic.m6_gate
    assert gate is not None
    empty_frame = replace(
        gate.frames[0],
        full_domains=(),
        analyzed_source_ids=(),
        analyzed_pixels_xy=(),
        analyzed_area_nm2=0.0,
    )
    empty_result = replace(automatic, m6_gate=M6Gate((empty_frame,)))
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, empty_result))

    signed = controller.dispatch(SignOffReferenceReview(
        "m6",
        "physical-frame-0",
    ))

    assert signed.reference_reviews.review_for(
        "physical-frame-0",
        "m6",
    ).status == "reviewed"
    assert ReferenceReviewPolicy().readiness(
        signed.reference_reviews,
        "m6",
    ).ready


def _signed_controller() -> DomainAnalysisWorkspaceController:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))
    for source_id in ("full", "island", "outside"):
        controller.dispatch(SetReferenceReviewDecision(
            "m6",
            "frame-0",
            ReferenceReviewDecision.eligible(
                source_id,
                disposition="accepted_automatic",
            ),
        ))
    controller.dispatch(SetReferenceReviewDecision(
        "orientation",
        "frame-0",
        ReferenceReviewDecision.eligible(
            "full",
            disposition="accepted_automatic",
        ),
    ))
    for source_id in ("island", "outside"):
        controller.dispatch(SetReferenceReviewDecision(
            "orientation",
            "frame-0",
            ReferenceReviewDecision.not_eligible(
                source_id,
                reason_code="automatic_gate_excluded",
            ),
        ))
    controller.dispatch(SignOffReferenceReview("m6", "frame-0"))
    controller.dispatch(SignOffReferenceReview("orientation", "frame-0"))
    return controller


def _publish_and_promote(
    controller: DomainAnalysisWorkspaceController,
    action: PublishDomainAnalysisResult,
):
    controller.dispatch(action)
    compared = controller.dispatch(PrepareCorrectionRebase())
    preview = compared.domain_corrections.prepared_rebase
    assert preview is not None and preview.is_ready
    return controller.dispatch(ApplyPreparedCorrectionRebase(preview))
