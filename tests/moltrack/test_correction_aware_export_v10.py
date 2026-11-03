from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ApplyPreparedCorrectionRebase,
    ApplyPreparedDomainCorrection,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    CorrectionWorkspaceQuarantine,
    PendingAutomaticCandidate,
    PreparedCorrectionRebase,
    PrepareCorrectionRebase,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    ReferenceReviewDecision,
    SelectDomainMolecules,
    SetReferenceReviewDecision,
    SignOffReferenceReview,
    ReferenceReviewWorkspace,
    RestoreDomainAnalysisWorkspace,
)
from moltrack.analysis.domain_analysis.correction_rebase_models import (
    automatic_candidate_fingerprint,
)
from moltrack.persistence import (
    CanonicalJsonObject,
    CorrectionAwareExportSettings,
    export_analysis_package,
)
from test_domain_correction_orientation import _automatic_result
from test_domain_analysis_export import _export_settings, _m6_only_state

from moltrack.persistence.domain_analysis_session import (
    domain_analysis_state_to_payload,
)


def test_reference_export_v10_preserves_corrections_and_complete_scope(
    tmp_path,
) -> None:
    state = _ready_corrected_state()
    destination = tmp_path / "correction-aware-v10"

    result = export_analysis_package(
        state,
        CorrectionAwareExportSettings(
            destination=destination,
            source_identity=CanonicalJsonObject({"source": "fixture.mpp"}),
            export_mode="reference",
        ),
    )

    manifest = _json(destination / "manifest.json")
    automatic = _json(destination / "automatic_snapshot.json")
    catalog = _json(destination / "orientation_class_catalog.json")
    projection = _json(destination / "domain_effective_projection.json")
    reviews = _json(destination / "domain_reference_reviews.json")
    rows = _csv_rows(destination / "domain_effective_molecules.csv")

    assert result.package_path == destination
    assert result.package_format == "directory"
    assert manifest["export_schema_version"] == 10
    assert manifest["package_kind"] == "moltrack_correction_aware_analysis"
    assert manifest["export_mode"] == "reference"
    assert manifest["activation_status"] == "active"
    assert manifest["readiness"] == {"ready": True, "blockers": []}
    assert manifest["anchors"]["backend_identity_fingerprint"]
    assert manifest["anchors"]["backend_identities"][0]["backend_id"] == (
        "m6_orientation_components"
    )
    assert manifest["anchors"]["automatic_snapshot_fingerprint"]
    assert manifest["anchors"]["orientation_class_catalog_fingerprint"]
    assert manifest["anchors"]["correction_revision"] == 1
    assert manifest["anchors"]["correction_revision_fingerprint"]
    assert manifest["anchors"]["effective_projection_fingerprint"] == (
        projection["fingerprint"]
    )
    assert catalog["labels"] == ["A", "B", "C", "Z"]
    assert automatic["m6_gate"]["frames"][0]["backend_identity"]["backend_id"] == (
        "m6_orientation_components"
    )
    assert {review["scope"]["target"] for review in reviews} == {
        "m6",
        "orientation",
    }
    assert {row["source_id"] for row in rows} == {"full", "island", "outside"}
    assert len(rows) == 3
    full = next(row for row in rows if row["source_id"] == "full")
    island = next(row for row in rows if row["source_id"] == "island")
    assert full["automatic_orientation_raw"] == "A"
    assert full["effective_orientation"] == "Z"
    assert json.loads(full["raw_automatic_evidence"])
    assert full["m6_review_disposition"] == "accepted_automatic"
    assert full["orientation_review_disposition"] == "corrected"
    assert island["orientation_review_eligibility"] == "not_eligible"
    assert island["orientation_review_reason_code"] == "automatic_gate_excluded"
    correction_state = _json(destination / "domain_correction_state.json")
    revisions = _json_lines(destination / "domain_correction_revisions.jsonl")
    assert correction_state["revision"] == 1
    assert revisions[0]["revision"] == 1
    assert revisions[0]["action"] == "apply"
    assert _json_lines(destination / "domain_correction_operations.jsonl")
    assert _json(destination / "domain_diagnostic_funnels.json")
    assert _json(destination / "domain_rebase_diagnostics.json") == {
        "pending_rebase": None,
        "prepared_rebase": None,
        "records": [],
    }

    exported_paths = {entry["path"] for entry in manifest["files"]}
    assert exported_paths == set(result.relative_files) - {"manifest.json"}
    for entry in manifest["files"]:
        assert entry["sha256"] == hashlib.sha256(
            (destination / entry["path"]).read_bytes()
        ).hexdigest()


@pytest.mark.parametrize(
    "expected_status",
    ("draft", "stale", "conflicted"),
)
def test_non_current_v10_is_audit_only_with_false_readiness(
    tmp_path,
    expected_status,
) -> None:
    state = _non_current_state(expected_status)
    reference_destination = tmp_path / f"{expected_status}-reference"

    with pytest.raises(ValueError, match="requires reference-ready state"):
        export_analysis_package(
            state,
            _v10_settings(reference_destination, "reference"),
        )

    assert not reference_destination.exists()
    audit_destination = tmp_path / f"{expected_status}-audit"
    export_analysis_package(
        state,
        _v10_settings(audit_destination, "audit"),
    )
    manifest = _json(audit_destination / "manifest.json")
    assert manifest["export_mode"] == "audit"
    assert manifest["correction_status"] == expected_status
    assert manifest["readiness"]["ready"] is False
    assert manifest["readiness"]["blockers"]
    rebase = _json(audit_destination / "domain_rebase_diagnostics.json")
    if expected_status in {"stale", "conflicted"}:
        assert rebase["pending_rebase"] is not None
    if expected_status == "conflicted":
        assert rebase["prepared_rebase"]["blocking_reasons"]


def test_backendless_draft_is_rejected_at_request_boundary() -> None:
    with pytest.raises(ValueError, match="backend_id"):
        DomainAnalysisRequest(frame_range=range(1), backend_id=None)


def test_quarantined_v10_exports_raw_audit_without_effective_projection(
    tmp_path,
) -> None:
    active = _ready_corrected_state()
    section = domain_analysis_state_to_payload(active)
    correction_payload = deepcopy(section["correction_workspace"])
    correction_payload["effective_projection_checkpoint"]["fingerprint"] = (
        "tampered"
    )
    quarantine = CorrectionWorkspaceQuarantine.from_payload(
        automatic_snapshot=active.published_result,
        automatic_snapshot_payload=section["published_result"],
        reason_code="effective_projection_checkpoint_mismatch",
        reason="checkpoint does not reproduce",
        correction_workspace_payload=correction_payload,
    )
    state = DomainAnalysisSessionState(
        correction_workspace_quarantine=quarantine,
    )
    reference_destination = tmp_path / "quarantined-reference"

    with pytest.raises(ValueError, match="requires reference-ready state"):
        export_analysis_package(
            state,
            _v10_settings(reference_destination, "reference"),
        )

    audit_destination = tmp_path / "quarantined-audit"
    result = export_analysis_package(
        state,
        _v10_settings(audit_destination, "audit"),
    )
    manifest = _json(audit_destination / "manifest.json")
    quarantine_audit = _json(
        audit_destination / "correction_workspace_quarantine.json"
    )
    assert manifest["activation_status"] == "quarantined"
    assert manifest["correction_status"] == "conflicted"
    assert manifest["readiness"]["ready"] is False
    assert manifest["anchors"]["effective_projection_fingerprint"] is None
    assert quarantine_audit["correction_workspace"] == (
        quarantine.correction_workspace_payload
    )
    assert "domain_effective_projection.json" not in result.relative_files
    assert "domain_effective_molecules.csv" not in result.relative_files


def test_v9_remains_a_distinct_automatic_only_package(tmp_path) -> None:
    destination = tmp_path / "automatic-v9"

    result = export_analysis_package(
        _m6_only_state(),
        _export_settings(destination),
    )

    manifest = _json(destination / "manifest.json")
    assert manifest["export_schema_version"] == 9
    assert manifest["package_kind"] == "moltrack_analysis"
    assert "automatic_snapshot.json" not in result.relative_files
    assert "domain_effective_projection.json" not in result.relative_files


def test_audit_v10_preserves_complete_rebase_record(tmp_path) -> None:
    state = _state_with_promoted_rebase()
    destination = tmp_path / "rebase-audit"

    export_analysis_package(state, _v10_settings(destination, "audit"))

    diagnostics = _json(destination / "domain_rebase_diagnostics.json")
    record = diagnostics["records"][0]
    assert record["record_id"]
    assert record["previous_automatic_snapshot"]["classifier_status"] == "completed"
    assert record["previous_correction_set"]["revision"] == 1
    assert record["promoted_automatic_fingerprint"]


def _ready_corrected_state() -> DomainAnalysisSessionState:
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id="m6_orientation_components",
        classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
    )
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))
    controller.dispatch(SelectDomainMolecules(("full",)))
    controller.dispatch(PreviewManualOrientation("Z", "manual-review"))
    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    controller.dispatch(ApplyPreparedDomainCorrection(prepared))
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
        ReferenceReviewDecision.eligible("full", disposition="corrected"),
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
    snapshot = controller.snapshot
    return DomainAnalysisSessionState(
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
    )


def _non_current_state(status: str) -> DomainAnalysisSessionState:
    state = _ready_corrected_state()
    if status == "draft":
        reviews = ReferenceReviewWorkspace(tuple(
            replace(frame, sign_off=None)
            for frame in state.reference_reviews.frames
        ))
        return replace(state, reference_reviews=reviews)
    publication = state.published_result
    assert publication is not None
    pending = PendingAutomaticCandidate(
        request=publication.request,
        result=publication.result,
        automatic_fingerprint=automatic_candidate_fingerprint(
            publication.request,
            publication.result,
        ),
    )
    corrections = replace(
        state.domain_corrections,
        pending_automatic_candidate=pending,
    )
    if status == "conflicted":
        correction_set = corrections.correction_set
        assert correction_set is not None
        corrections = replace(
            corrections,
            prepared_rebase=PreparedCorrectionRebase(
                expected_correction_revision=correction_set.revision,
                active_automatic_fingerprint=correction_set.automatic_fingerprint,
                candidate_automatic_fingerprint=pending.automatic_fingerprint,
                portable_source_keys=(),
                issues=(),
                resolutions=(),
                source_mapping=(),
                blocking_reasons=("manual resolution required",),
            ),
        )
    return replace(state, domain_corrections=corrections)


def _state_with_promoted_rebase() -> DomainAnalysisSessionState:
    state = _ready_corrected_state()
    publication = state.published_result
    assert publication is not None
    controller = DomainAnalysisWorkspaceController(
        publication.request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(RestoreDomainAnalysisWorkspace(
        draft=publication.request,
        published=publication,
        active_frame_index=0,
        selected_component=None,
        run_status="idle",
        run_diagnosis=None,
        orientation_class_catalog=state.orientation_class_catalog,
        domain_corrections=state.domain_corrections,
        reference_reviews=state.reference_reviews,
    ))
    outcome = publication.result.classifier_outcomes[0]
    candidate = replace(
        publication.result,
        run_status="completed_with_errors",
        classifier_status="completed_with_errors",
        classifier_outcomes=(replace(
            outcome,
            status="failed",
            molecule_classifications=(),
            frame_result_provenance=(),
            domain_summaries=(),
            error_message="controlled rerun failure",
            failure_frame_index=0,
        ),),
        molecule_diagnostic_funnels=(),
    )
    controller.dispatch(PublishDomainAnalysisResult(publication.request, candidate))
    compared = controller.dispatch(PrepareCorrectionRebase())
    prepared = compared.domain_corrections.prepared_rebase
    assert prepared is not None and prepared.is_ready
    controller.dispatch(ApplyPreparedCorrectionRebase(prepared))
    snapshot = controller.snapshot
    return DomainAnalysisSessionState(
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
    )


def _v10_settings(destination, export_mode):
    return CorrectionAwareExportSettings(
        destination=destination,
        source_identity=CanonicalJsonObject({"source": "fixture.mpp"}),
        export_mode=export_mode,
    )


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _json_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
