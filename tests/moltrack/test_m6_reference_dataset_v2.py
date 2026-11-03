from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ApplyPreparedDomainCorrection,
    CorrectionWorkspaceQuarantine,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    DomainCorrectionModule,
    ManualOrientationIntent,
    PreviewCreateManualDomain,
    PendingAutomaticCandidate,
    PreparedCorrectionRebase,
    PublishDomainAnalysisResult,
    ReferenceReadinessError,
    ReferenceReadinessPolicy,
    ReferenceReviewDecision,
    ReferenceReviewPolicy,
    SelectDomainMolecules,
    SetReferenceReviewDecision,
    SignOffReferenceReview,
    ReferenceReviewWorkspace,
)
from moltrack.analysis.domain_analysis.correction_rebase_models import (
    automatic_candidate_fingerprint,
)
from moltrack.persistence import (
    M6ReferenceDatasetSettings,
    M6ReferenceFirstShellEdge,
    M6ReferenceFirstShellFrame,
    M6ReferenceMeasurementGroup,
    M6ReferenceSourceRevision,
    publish_m6_reference_dataset,
)
from moltrack.persistence.domain_analysis_session import (
    domain_analysis_state_to_payload,
)
from moltrack.persistence.reference_dataset_reader import (
    load_reference_dataset_package,
)
from test_domain_correction_orientation import _automatic_result


def test_publish_m6_reference_v2_writes_complete_target_specific_dataset(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    measurements = (
        _measurement(tmp_path, "measurement-calibration", "calibration", state, "a"),
        _measurement(tmp_path, "measurement-validation", "validation", state, "b"),
    )
    first_destination = tmp_path / "m6-reference-first"
    second_destination = tmp_path / "m6-reference-second"

    first = publish_m6_reference_dataset(
        measurements,
        _settings(first_destination),
    )
    second = publish_m6_reference_dataset(
        measurements,
        _settings(second_destination),
    )

    manifest = _json(first_destination / "manifest.json")
    file_manifest = _json(first_destination / "file_manifest.json")
    measurement_rows = _json_lines(first_destination / "measurements.jsonl")
    assignment_rows = _json_lines(first_destination / "m6_assignments.jsonl")
    signoff_rows = _json_lines(first_destination / "review_signoffs.jsonl")
    edge_rows = _json_lines(first_destination / "m6_first_shell_edges.jsonl")
    round_trip = load_reference_dataset_package(
        first_destination,
        expected_target="m6",
    )

    assert manifest["schema_version"] == 2
    assert manifest["target"] == "m6"
    assert manifest["dataset_id"] == "ttmapp-m6-reference"
    assert manifest["dataset_version"] == 1
    assert manifest["parent_version_id"] is None
    assert manifest["readiness"] == {"ready": True, "blockers": []}
    assert manifest["publication_reason"] == "initial reviewed M6 reference"
    assert manifest["version_id"] == first.version_id == second.version_id
    assert (
        manifest["version_fingerprint"]
        == first.version_fingerprint
        == second.version_fingerprint
    )
    assert (
        manifest["validation_epoch"]["epoch_id"]
        == first.validation_epoch_id
        == second.validation_epoch_id
    )
    assert manifest["partitions"]["calibration"]["measurement_group_count"] == 1
    assert manifest["partitions"]["validation"]["measurement_group_count"] == 1
    assert {row["split"] for row in measurement_rows} == {
        "calibration",
        "validation",
    }
    assert {row["measurement_group_id"] for row in measurement_rows} == {
        "measurement-calibration",
        "measurement-validation",
    }
    frame_rows = _json_lines(first_destination / "frames.jsonl")
    assert len(frame_rows) == 2
    assert {row["first_shell_symmetry_class"] for row in frame_rows} == {"sixfold"}
    assert len(_json_lines(first_destination / "molecules.jsonl")) == 6
    assert len(_json_lines(first_destination / "source_geometry.jsonl")) == 6
    assert len(assignment_rows) == 6
    assert round_trip.manifest == manifest
    assert round_trip.json_lines("m6_assignments.jsonl") == assignment_rows
    assert len(edge_rows) == 4
    assert {row["target"] for row in signoff_rows} == {"m6"}
    assert len(signoff_rows) == 2
    outside = [
        row for row in assignment_rows if row["source_id"] == "outside"
    ]
    assert len(outside) == 2
    assert {row["effective_m6_partition"] for row in outside} == {
        "full_domain"
    }
    assert {row["review_disposition"] for row in outside} == {"created"}
    assert all(row["effective_domain_id"] for row in outside)
    assert all("orientation" not in row for row in assignment_rows)
    assert "orientation_assignments.jsonl" not in first.relative_files
    assert _json_lines(first_destination / "diagnostic_stages.jsonl")

    payload_paths = {entry["path"] for entry in file_manifest["files"]}
    assert payload_paths == set(first.relative_files) - {
        "manifest.json",
        "file_manifest.json",
    }
    for entry in file_manifest["files"]:
        assert entry["sha256"] == hashlib.sha256(
            (first_destination / entry["path"]).read_bytes()
        ).hexdigest()


def test_publisher_rejects_non_ready_m6_states_without_creating_a_package(
    tmp_path,
) -> None:
    ready = _m6_reviewed_state()
    cases = (
        ("draft", DomainAnalysisSessionState()),
        ("signed M6 review", _without_m6_signoff(ready)),
        ("Stale corrections", _stale_state(ready)),
        ("Conflicted corrections", _conflicted_state(ready)),
        ("Quarantined corrections", _quarantined_state(ready)),
    )

    for index, (message, state) in enumerate(cases):
        destination = tmp_path / f"rejected-{index}"
        measurements = (
            _measurement(tmp_path, "calibration", "calibration", state, "a"),
            _measurement(tmp_path, "validation", "validation", state, "b"),
        )
        with pytest.raises(ValueError, match=message):
            publish_m6_reference_dataset(
                measurements,
                _settings(destination),
            )
        assert not destination.exists()


def test_publisher_requires_reason_both_splits_and_whole_measurement_groups(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    calibration = _measurement(tmp_path, "same-group", "calibration", state, "a")
    validation = _measurement(tmp_path, "same-group", "validation", state, "b")

    with pytest.raises(ValueError, match="publication_reason"):
        M6ReferenceDatasetSettings(
            destination=tmp_path / "missing-reason",
            dataset_id="ttmapp-m6-reference",
            publication_reason="",
        )
    with pytest.raises(ValueError, match="Calibration and Validation"):
        publish_m6_reference_dataset(
            (calibration,),
            _settings(tmp_path / "empty-validation"),
        )
    with pytest.raises(ValueError, match="exactly one dataset split"):
        publish_m6_reference_dataset(
            (calibration, validation),
            _settings(tmp_path / "split-group"),
        )


@pytest.mark.parametrize(
    ("state_kind", "expected_codes"),
    (
        ("stale", {"pending_automatic_candidate"}),
        (
            "conflicted",
            {"pending_automatic_candidate", "conflicted_rebase"},
        ),
        (
            "quarantined",
            {
                "no_active_publication",
                "correction_workspace_quarantined",
                "effective_projection_missing",
                "review_scope_missing",
            },
        ),
    ),
)
def test_reference_readiness_types_previously_divergent_blockers(
    state_kind,
    expected_codes,
) -> None:
    state_factory = {
        "stale": _stale_state,
        "conflicted": _conflicted_state,
        "quarantined": _quarantined_state,
    }[state_kind]
    readiness = ReferenceReadinessPolicy().evaluate_snapshot(
        state_factory(_m6_reviewed_state()),
        "m6",
    )

    assert {value.code for value in readiness.blockers} == expected_codes


def test_split_completeness_is_owned_by_reference_readiness_policy(tmp_path) -> None:
    state = _m6_reviewed_state()
    measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, "a"),
    )
    expected = ReferenceReadinessPolicy().evaluate_dataset(measurements, "m6")

    assert tuple(value.code for value in expected.blockers) == (
        "validation_split_missing",
    )
    with pytest.raises(ReferenceReadinessError) as raised:
        publish_m6_reference_dataset(
            measurements,
            _settings(tmp_path / "missing-validation"),
        )
    assert raised.value.result == expected


def test_published_version_is_immutable(tmp_path) -> None:
    state = _m6_reviewed_state()
    measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, "a"),
        _measurement(tmp_path, "validation", "validation", state, "b"),
    )
    destination = tmp_path / "immutable-version"
    publish_m6_reference_dataset(measurements, _settings(destination))
    before = {
        path.name: path.read_bytes()
        for path in destination.iterdir()
        if path.is_file()
    }

    with pytest.raises(FileExistsError, match="already exists"):
        publish_m6_reference_dataset(measurements, _settings(destination))

    after = {
        path.name: path.read_bytes()
        for path in destination.iterdir()
        if path.is_file()
    }
    assert after == before


def test_m6_version_identity_ignores_orientation_only_corrections(tmp_path) -> None:
    m6_state = _m6_reviewed_state()
    orientation_changed = _with_manual_orientation(m6_state, "B")
    baseline = publish_m6_reference_dataset(
        (
            _measurement(tmp_path, "calibration", "calibration", m6_state, "a"),
            _measurement(tmp_path, "validation", "validation", m6_state, "b"),
        ),
        _settings(tmp_path / "m6-baseline"),
    )
    changed = publish_m6_reference_dataset(
        (
            _measurement(
                tmp_path,
                "calibration",
                "calibration",
                orientation_changed,
                "a",
            ),
            _measurement(
                tmp_path,
                "validation",
                "validation",
                orientation_changed,
                "b",
            ),
        ),
        _settings(tmp_path / "m6-orientation-changed"),
    )

    assert changed.version_id == baseline.version_id
    assert changed.version_fingerprint == baseline.version_fingerprint
    assert changed.validation_epoch_id == baseline.validation_epoch_id


def _m6_reviewed_state() -> DomainAnalysisSessionState:
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
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewCreateManualDomain())
    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    controller.dispatch(ApplyPreparedDomainCorrection.confirmed(prepared))
    for source_id, disposition in (
        ("full", "accepted_automatic"),
        ("island", "accepted_automatic"),
        ("outside", "created"),
    ):
        controller.dispatch(SetReferenceReviewDecision(
            "m6",
            "frame-0",
            ReferenceReviewDecision.eligible(
                source_id,
                disposition=disposition,
            ),
        ))
    controller.dispatch(SignOffReferenceReview("m6", "frame-0"))
    snapshot = controller.snapshot
    return DomainAnalysisSessionState(
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
    )


def _measurement(source_root, group_id, split, state, source_character):
    source_path = source_root / f"{group_id}-{split}.mpp"
    source_path.write_bytes(source_character.encode("ascii"))
    return M6ReferenceMeasurementGroup(
        measurement_group_id=group_id,
        split=split,
        source_revision=M6ReferenceSourceRevision.from_path(
            source_path,
            source_file_name=f"{group_id}.mpp",
            acquisition_fingerprint=f"acquisition-{group_id}",
            lineage_fingerprint=f"lineage-{group_id}",
        ),
        snapshot=state,
        first_shell_frames=(M6ReferenceFirstShellFrame("frame-0", "sixfold"),),
        first_shell_edges=(
            M6ReferenceFirstShellEdge("frame-0", "full", "island"),
            M6ReferenceFirstShellEdge("frame-0", "island", "outside"),
        ),
    )


def _without_m6_signoff(state):
    reviews = ReferenceReviewWorkspace(tuple(
        replace(frame, sign_off=None)
        if frame.scope.target == "m6"
        else frame
        for frame in state.reference_reviews.frames
    ))
    return replace(state, reference_reviews=reviews)


def _pending(state):
    publication = state.published_result
    assert publication is not None
    return PendingAutomaticCandidate(
        request=publication.request,
        result=publication.result,
        automatic_fingerprint=automatic_candidate_fingerprint(
            publication.request,
            publication.result,
        ),
    )


def _with_manual_orientation(state, orientation_label):
    publication = state.published_result
    correction_set = state.domain_corrections.correction_set
    assert publication is not None and correction_set is not None
    module = DomainCorrectionModule()
    prepared = module.prepare(
        correction_set,
        publication.result,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full",),
            orientation_label=orientation_label,
        ),
    )
    corrected = module.dispatch(
        correction_set,
        publication.result,
        ApplyPreparedDomainCorrection.confirmed(prepared),
    )
    domain_corrections = replace(
        state.domain_corrections,
        correction_set=corrected,
        effective_projection=module.project(publication.result, corrected),
    )
    return replace(
        state,
        domain_corrections=domain_corrections,
        reference_reviews=ReferenceReviewPolicy().synchronize(
            state.reference_reviews,
            publication.result,
            domain_corrections,
        ),
    )


def _stale_state(state):
    return replace(
        state,
        domain_corrections=replace(
            state.domain_corrections,
            pending_automatic_candidate=_pending(state),
        ),
    )


def _conflicted_state(state):
    pending = _pending(state)
    correction_set = state.domain_corrections.correction_set
    assert correction_set is not None
    prepared = PreparedCorrectionRebase(
        expected_correction_revision=correction_set.revision,
        active_automatic_fingerprint=correction_set.automatic_fingerprint,
        candidate_automatic_fingerprint=pending.automatic_fingerprint,
        portable_source_keys=(),
        issues=(),
        resolutions=(),
        source_mapping=(),
        blocking_reasons=("manual resolution required",),
    )
    return replace(
        state,
        domain_corrections=replace(
            state.domain_corrections,
            pending_automatic_candidate=pending,
            prepared_rebase=prepared,
        ),
    )


def _quarantined_state(state):
    section = domain_analysis_state_to_payload(state)
    correction_payload = deepcopy(section["correction_workspace"])
    correction_payload["effective_projection_checkpoint"]["fingerprint"] = (
        "tampered"
    )
    quarantine = CorrectionWorkspaceQuarantine.from_payload(
        automatic_snapshot=state.published_result,
        automatic_snapshot_payload=section["published_result"],
        reason_code="effective_projection_checkpoint_mismatch",
        reason="checkpoint does not reproduce",
        correction_workspace_payload=correction_payload,
    )
    return DomainAnalysisSessionState(correction_workspace_quarantine=quarantine)


def _settings(destination):
    return M6ReferenceDatasetSettings(
        destination=destination,
        dataset_id="ttmapp-m6-reference",
        publication_reason="initial reviewed M6 reference",
    )


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _json_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
