from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pytest

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ApplyPreparedCorrectionRebase,
    ApplyPreparedDomainCorrection,
    CorrectionRebasePolicy,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    PrepareCorrectionRebase,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    ReferenceReviewDecision,
    ReferenceReviewPolicy,
    RestoreDomainAnalysisWorkspace,
    SelectDomainMolecules,
    SetReferenceReviewDecision,
    SignOffReferenceReview,
)
from moltrack.analysis.domain_analysis.diagnostic_funnel import (
    build_molecule_diagnostic_funnels,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from nanotrack.core import STMSequenceMetadata
from test_domain_correction_orientation import _automatic_result


def test_session_v3_round_trip_recomputes_the_effective_projection(tmp_path) -> None:
    source_path = tmp_path / "source.mpp"
    source_path.write_bytes(b"correction-aware-session-v3")
    series = MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros((1, 4, 4), dtype=np.uint16),
        metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
    )
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id="m6_orientation_components",
        classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
    )
    automatic = _with_funnels(_automatic_result())
    record_ids = iter(("rebase-record-1",))
    fixed_time = datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc)
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
        rebase_policy=CorrectionRebasePolicy(
            record_id_factory=lambda: next(record_ids),
            clock=lambda: fixed_time,
        ),
        review_policy=ReferenceReviewPolicy(clock=lambda: fixed_time),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("Z", "manual-review"))
    correction = controller.snapshot.domain_corrections.prepared
    assert correction is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction))

    failed_outcome = replace(
        automatic.classifier_outcomes[0],
        status="failed",
        molecule_classifications=(),
        frame_result_provenance=(),
        domain_summaries=(),
        error_message="controlled rerun failure",
        failure_frame_index=0,
    )
    promoted_result = _with_funnels(replace(
        automatic,
        run_status="completed_with_errors",
        classifier_status="completed_with_errors",
        classifier_outcomes=(failed_outcome,),
        molecule_diagnostic_funnels=(),
    ))
    controller.dispatch(PublishDomainAnalysisResult(request, promoted_result))
    compared = controller.dispatch(PrepareCorrectionRebase())
    rebase = compared.domain_corrections.prepared_rebase
    assert rebase is not None and rebase.is_ready
    controller.dispatch(ApplyPreparedCorrectionRebase(rebase))
    _complete_both_reviews(controller)

    pending_result = automatic
    controller.dispatch(PublishDomainAnalysisResult(request, pending_result))
    controller.dispatch(PrepareCorrectionRebase())
    snapshot = controller.snapshot
    saved_draft = replace(request, classifier_ids=())
    state = DomainAnalysisSessionState(
        draft=saved_draft,
        draft_classifier_configurations=(),
        draft_physical_frame_ids=("frame-0",),
        published_result=snapshot.published,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
        orientation_class_catalog=snapshot.orientation_class_catalog,
    )
    session_path = tmp_path / "session.moltrack.json"

    save_moltrack_session(
        session_path,
        series,
        {
            "domain_analysis": state,
            "runtime_capability_catalog": ("abc_orientation",),
        },
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    loaded = load_moltrack_session(session_path)

    assert payload["schema_version"] == 3
    assert payload["domain_analysis"]["schema_version"] == 2
    correction_payload = payload["domain_analysis"]["correction_workspace"]
    assert correction_payload["schema_version"] == 1
    assert correction_payload["readiness"]["ready"] is False
    assert "pending_rebase" in correction_payload["readiness"]["blockers"]
    assert "runtime_capability_catalog" not in payload
    assert loaded.schema_version == 3
    assert loaded.domain_analysis_state is not None
    restored = loaded.domain_analysis_state
    assert restored.draft == saved_draft
    assert restored.published_result == snapshot.published
    assert restored.orientation_class_catalog.labels == ("A", "B", "C", "Z")
    assert restored.domain_corrections.correction_set == (
        snapshot.domain_corrections.correction_set
    )
    assert restored.domain_corrections.rebase_records == (
        snapshot.domain_corrections.rebase_records
    )
    assert restored.domain_corrections.pending_automatic_candidate == (
        snapshot.domain_corrections.pending_automatic_candidate
    )
    assert restored.domain_corrections.prepared_rebase == (
        snapshot.domain_corrections.prepared_rebase
    )
    assert restored.reference_reviews == snapshot.reference_reviews
    assert restored.domain_corrections.effective_projection == (
        snapshot.domain_corrections.effective_projection
    )
    assert restored.domain_corrections.effective_projection is not (
        snapshot.domain_corrections.effective_projection
    )
    assert correction_payload["effective_projection_checkpoint"]["fingerprint"]
    assert correction_payload["diagnostic_funnels"]

    restored_controller = DomainAnalysisWorkspaceController(
        restored.draft,
        physical_frame_ids=("frame-0",),
    )
    opened = restored_controller.dispatch(RestoreDomainAnalysisWorkspace(
        draft=restored.draft,
        published=restored.published_result,
        active_frame_index=0,
        selected_component=None,
        run_status=restored.run_status,
        run_diagnosis=restored.run_diagnosis,
        orientation_class_catalog=restored.orientation_class_catalog,
        domain_corrections=restored.domain_corrections,
        reference_reviews=restored.reference_reviews,
    ))
    assert opened.orientation_class_catalog == restored.orientation_class_catalog
    assert opened.domain_corrections == restored.domain_corrections
    assert opened.reference_reviews == restored.reference_reviews

    session_path.write_text(
        json.dumps({**payload, "schema_version": 2}),
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError,
        match="Unsupported domain_analysis schema_version: 2",
    ):
        load_moltrack_session(session_path)

def test_unknown_outer_version_is_rejected_before_source_open(tmp_path) -> None:
    session_path = tmp_path / "future-session.moltrack.json"
    session_path.write_text(
        json.dumps({
            "schema_version": 999,
            "source": {"path": str(tmp_path / "missing-source.mpp")},
        }),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported MolTrack session schema_version: 999",
    ):
        load_moltrack_session(session_path)


def _with_funnels(result):
    return replace(
        result,
        molecule_diagnostic_funnels=build_molecule_diagnostic_funnels(result),
    )


def _complete_both_reviews(controller) -> None:
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
        ReferenceReviewDecision.not_eligible(
            "full",
            reason_code="classifier_failed",
        ),
    ))
    controller.dispatch(SetReferenceReviewDecision(
        "orientation",
        "frame-0",
        ReferenceReviewDecision.not_eligible(
            "island",
            reason_code="automatic_gate_excluded",
        ),
    ))
    controller.dispatch(SetReferenceReviewDecision(
        "orientation",
        "frame-0",
        ReferenceReviewDecision.eligible(
            "outside",
            disposition="created",
        ),
    ))
    controller.dispatch(SignOffReferenceReview("m6", "frame-0"))
    controller.dispatch(SignOffReferenceReview("orientation", "frame-0"))
