from __future__ import annotations

import json

import numpy as np
import pytest

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    ReferenceReviewPolicy,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    MolTrackSessionLoadError,
    load_moltrack_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata
from domain_analysis_test_support import as_legacy_session_v2
from test_domain_analysis_full_session_persistence import (
    _completed_outcome,
    _configuration,
    _published_gate,
)


def test_open_migrates_session_v2_to_a_correction_aware_v3_draft(tmp_path) -> None:
    source_path = tmp_path / "legacy-v2-source.mpp"
    source_path.write_bytes(b"legacy session v2 source")
    legacy_path = tmp_path / "legacy-v2.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    configuration = _configuration(ABC_ORIENTATION_CLASSIFIER_ID)
    gate = _published_gate()
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
    )
    publication = DomainAnalysisPublication(
        request=request,
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=gate,
            classifier_status="completed",
            classifier_outcomes=(_completed_outcome(gate, configuration),),
        ),
    )
    state = DomainAnalysisSessionState(
        draft=request,
        draft_classifier_configurations=(configuration,),
        draft_physical_frame_ids=("physical-frame-0",),
        published_result=publication,
        opaque_components=((
            "legacy_audit",
            {"component_id": "legacy-audit", "schema_version": 7},
        ),),
    )
    save_moltrack_session(
        legacy_path,
        series,
        {"domain_analysis": state},
    )
    payload = as_legacy_session_v2(
        json.loads(legacy_path.read_text(encoding="utf-8"))
    )
    legacy_path.write_text(json.dumps(payload), encoding="utf-8")
    legacy_bytes = legacy_path.read_bytes()

    loaded = load_moltrack_session(legacy_path)

    assert legacy_path.read_bytes() == legacy_bytes
    assert loaded.schema_version == 3
    assert loaded.source_path == str(source_path.resolve())
    assert loaded.source_frame_indices == (0,)
    migrated = loaded.domain_analysis_state
    assert migrated is not None
    assert migrated.draft == request
    assert migrated.draft_classifier_configurations == (configuration,)
    assert migrated.draft_physical_frame_ids == ("physical-frame-0",)
    assert migrated.published_result is not None
    assert migrated.published_result.request == request
    assert migrated.published_result.result.m6_gate == gate
    assert migrated.published_result.result.classifier_outcomes == (
        publication.result.classifier_outcomes
    )
    assert {
        frame.backend_identity.backend_id
        for frame in migrated.published_result.result.m6_gate.frames
    } == {M6_ORIENTATION_COMPONENTS_BACKEND_ID}
    assert migrated.orientation_class_catalog.labels == ("A", "B", "C")
    assert migrated.orientation_class_catalog.revision == 0
    corrections = migrated.domain_corrections
    assert corrections.correction_set is not None
    assert corrections.correction_set.revision == 0
    assert corrections.correction_set.atoms == ()
    assert corrections.correction_set.history_records == ()
    assert corrections.rebase_records == ()
    assert corrections.effective_projection is not None
    assert corrections.effective_projection.molecules[0].effective_orientation == "A"
    assert {
        frame.scope.target for frame in migrated.reference_reviews.frames
    } == {"m6", "orientation"}
    assert all(
        not frame.decisions and frame.sign_off is None
        for frame in migrated.reference_reviews.frames
    )
    review_policy = ReferenceReviewPolicy()
    assert not review_policy.readiness(migrated.reference_reviews, "m6").ready
    assert not review_policy.readiness(
        migrated.reference_reviews,
        "orientation",
    ).ready
    assert {value.identifier for value in migrated.diagnostics}.issuperset({
        "legacy-audit",
        "historical-backend:m6_orientation_components",
        "migrated-session-v2-without-corrections",
        "review-not-inferred-from-legacy",
    })

    migrated_path = tmp_path / "migrated-v3.moltrack.json"
    save_moltrack_session(
        migrated_path,
        series,
        {"domain_analysis": migrated},
    )
    migrated_payload = json.loads(migrated_path.read_text(encoding="utf-8"))
    assert migrated_payload["schema_version"] == 3
    assert migrated_payload["domain_analysis"]["schema_version"] == 2
    assert migrated_payload["domain_analysis"]["correction_workspace"][
        "schema_version"
    ] == 1
    assert migrated_payload["domain_analysis"]["correction_workspace"][
        "readiness"
    ]["ready"] is False


def test_session_v2_migration_does_not_guess_a_conflicting_backend(tmp_path) -> None:
    source_path = tmp_path / "conflicting-backend-source.mpp"
    source_path.write_bytes(b"conflicting legacy backend")
    session_path = tmp_path / "conflicting-backend-v2.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    gate = _published_gate()
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    )
    state = DomainAnalysisSessionState(
        draft=request,
        published_result=DomainAnalysisPublication(
            request=request,
            result=DomainAnalysisResult(
                run_status="completed",
                m6_gate=gate,
                classifier_status="not_requested",
            ),
        ),
    )
    save_moltrack_session(session_path, series, {"domain_analysis": state})
    payload = as_legacy_session_v2(
        json.loads(session_path.read_text(encoding="utf-8"))
    )
    publication = payload["domain_analysis"]["published_result"]
    publication["request"]["backend_id"] = "m3_m6_lattice_network"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        MolTrackSessionLoadError,
        match="does not prove one historical domain backend",
    ):
        load_moltrack_session(session_path)
