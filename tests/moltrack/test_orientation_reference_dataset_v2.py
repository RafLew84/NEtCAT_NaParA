from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from moltrack.analysis import build_molecular_sample_coordinates
from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ApplyPreparedDomainCorrection,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    ReferenceReviewDecision,
    ReferenceReviewWorkspace,
    SelectDomainMolecules,
    SetReferenceReviewDecision,
    SignOffReferenceReview,
)
from moltrack.core import (
    MolecularCentroid,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from moltrack.persistence import (
    OrientationReferenceDatasetSettings,
    OrientationReferenceMeasurementGroup,
    OrientationReferenceSourceRevision,
    publish_orientation_reference_dataset,
)
from nanotrack.core import STMSequenceMetadata
from test_domain_correction_orientation import _automatic_result


def test_publish_orientation_reference_v2_writes_training_complete_package(
    tmp_path,
) -> None:
    state = _orientation_reviewed_state()
    measurements = (
        _measurement(tmp_path, "measurement-calibration", "calibration", state, b"a"),
        _measurement(tmp_path, "measurement-validation", "validation", state, b"b"),
    )
    first_destination = tmp_path / "orientation-reference-first"
    second_destination = tmp_path / "orientation-reference-second"

    first = publish_orientation_reference_dataset(
        measurements,
        _settings(first_destination),
    )
    second = publish_orientation_reference_dataset(
        measurements,
        _settings(second_destination),
    )

    manifest = _json(first_destination / "manifest.json")
    file_manifest = _json(first_destination / "file_manifest.json")
    frames = _json_lines(first_destination / "frames.jsonl")
    molecules = _json_lines(first_destination / "molecules.jsonl")
    assignments = _json_lines(first_destination / "orientation_assignments.jsonl")

    assert manifest["schema_version"] == 2
    assert manifest["target"] == "orientation"
    assert manifest["dataset_id"] == "ttmapp-orientation-reference"
    assert manifest["dataset_version"] == 1
    assert manifest["readiness"] == {"ready": True, "blockers": []}
    assert first.version_id == second.version_id == manifest["version_id"]
    assert first.version_fingerprint == second.version_fingerprint
    assert "m6_assignments.jsonl" not in first.relative_files

    frame = next(row for row in frames if row["split"] == "calibration")
    assert frame["raw_shape"] == [1, 3]
    assert frame["raw_dtype"] == "float32"
    assert frame["pixel_size_nm"] == [1.0, 1.0]
    assert frame["coordinate_frame"] == "sample_nm"
    assert frame["scan_angle_deg"] == 0.0
    assert frame["scan_angle_missing_qc"] is True
    assert frame["orientation_reference"] == "scan_x_axis_assumed_sample_x"
    raw_object = first_destination / frame["raw_frame_object_path"]
    assert raw_object.exists()
    assert hashlib.sha256(raw_object.read_bytes()).hexdigest() == frame[
        "raw_frame_sha256"
    ]
    np.testing.assert_array_equal(
        np.load(raw_object, allow_pickle=False),
        np.asarray([[1.0, 2.0, 3.0]], dtype=np.float32),
    )

    calibration_molecules = {
        row["source_id"]: row
        for row in molecules
        if row["split"] == "calibration"
    }
    assert set(calibration_molecules) == {"full", "island", "outside"}
    outside = calibration_molecules["outside"]
    assert outside["point_xy_nm"] == [2.5, 0.5]
    assert outside["segmentation_origin"] == "manual"
    assert outside["segmentation_metadata"] == {"operator": "expert"}
    assert outside["parent_detection_id"] == "detection-outside"
    assert outside["segmentation_frame_shape"] == [1, 3]
    assert outside["segmentation_footprint_xyxy"] == [2, 0, 3, 1]
    assert outside["segmentation_shape"] == [1, 1]
    segmentation_object = first_destination / outside["segmentation_object_path"]
    assert segmentation_object.exists()
    assert hashlib.sha256(segmentation_object.read_bytes()).hexdigest() == outside[
        "segmentation_sha256"
    ]
    np.testing.assert_array_equal(
        np.load(segmentation_object, allow_pickle=False),
        np.asarray([[True]], dtype=bool),
    )

    calibration_assignments = {
        row["source_id"]: row
        for row in assignments
        if row["split"] == "calibration"
    }
    assert calibration_assignments["full"]["effective_orientation"] == "A"
    assert calibration_assignments["full"]["effective_orientation_source"] == (
        "automatic"
    )
    assert calibration_assignments["full"]["automatic_classification"][
        "identity"
    ]["classifier_id"] == ABC_ORIENTATION_CLASSIFIER_ID
    assert calibration_assignments["island"]["effective_orientation"] == (
        "Unresolvable"
    )
    assert calibration_assignments["island"]["review_abstention"] == "unresolvable"
    assert calibration_assignments["outside"]["effective_orientation"] == "Z"
    assert calibration_assignments["outside"]["effective_orientation_source"] == (
        "manual"
    )
    assert "effective_m6_partition" not in calibration_assignments["outside"]
    assert all(
        item["path"] in first.relative_files
        for item in file_manifest["files"]
    )


def test_orientation_reference_child_preserves_validation_epoch(tmp_path) -> None:
    state = _orientation_reviewed_state()
    parent_measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, b"a"),
        _measurement(tmp_path, "validation", "validation", state, b"b"),
    )
    parent_path = tmp_path / "orientation-parent"
    parent = publish_orientation_reference_dataset(
        parent_measurements,
        _settings(parent_path),
    )
    child_measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, b"c"),
        _measurement(tmp_path, "validation", "validation", state, b"b"),
    )
    child_path = tmp_path / "orientation-child"

    child = publish_orientation_reference_dataset(
        child_measurements,
        _settings(child_path, parent_package=parent_path),
    )

    manifest = _json(child_path / "manifest.json")
    assert manifest["dataset_version"] == 2
    assert manifest["parent_version_id"] == parent.version_id
    assert child.validation_epoch_id == parent.validation_epoch_id
    assert child.version_id != parent.version_id


def test_orientation_publisher_rejects_incomplete_review_geometry_and_masks(
    tmp_path,
) -> None:
    state = _orientation_reviewed_state()
    unsigned_state = replace(
        state,
        reference_reviews=ReferenceReviewWorkspace(tuple(
            replace(frame, sign_off=None)
            if frame.scope.target == "orientation"
            else frame
            for frame in state.reference_reviews.frames
        )),
    )
    cases = []
    cases.append((
        "signed Orientation review",
        (
            _measurement(tmp_path, "unsigned-cal", "calibration", unsigned_state, b"d"),
            _measurement(tmp_path, "unsigned-val", "validation", unsigned_state, b"e"),
        ),
    ))
    no_pixel = (
        _measurement(tmp_path, "pixel-cal", "calibration", state, b"f"),
        _measurement(tmp_path, "pixel-val", "validation", state, b"g"),
    )
    no_pixel[0].series.metadata = replace(
        no_pixel[0].series.metadata,
        size_nm_x=0.0,
    )
    cases.append(("positive pixel size", no_pixel))
    no_mask = (
        _measurement(tmp_path, "mask-cal", "calibration", state, b"h"),
        _measurement(tmp_path, "mask-val", "validation", state, b"i"),
    )
    no_mask[0].series.molecular_segmentations.remove_segmentation("outside")
    cases.append(("one raw mask", no_mask))
    no_parent_detection = (
        _measurement(tmp_path, "parent-cal", "calibration", state, b"j"),
        _measurement(tmp_path, "parent-val", "validation", state, b"k"),
    )
    no_parent_detection[0].series.molecular_detections.remove_detection(
        "detection-outside"
    )
    cases.append(("parent Detection Identity", no_parent_detection))

    for index, (message, measurements) in enumerate(cases):
        destination = tmp_path / f"rejected-{index}"
        with pytest.raises(ValueError, match=message):
            publish_orientation_reference_dataset(
                measurements,
                _settings(destination),
            )
        assert not destination.exists()


def _orientation_reviewed_state() -> DomainAnalysisSessionState:
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
    for source_id, label, reason in (
        ("outside", "Z", "expert-label"),
        ("island", "Unresolvable", "ambiguous-shape"),
    ):
        controller.dispatch(SelectDomainMolecules((source_id,)))
        controller.dispatch(PreviewManualOrientation(label, reason))
        prepared = controller.snapshot.domain_corrections.prepared
        assert prepared is not None
        controller.dispatch(ApplyPreparedDomainCorrection.confirmed(prepared))
    for decision in (
        ReferenceReviewDecision.eligible("full", disposition="accepted_automatic"),
        ReferenceReviewDecision.abstain(
            "island",
            "unresolvable",
            reason_code="ambiguous-shape",
        ),
        ReferenceReviewDecision.eligible("outside", disposition="created"),
    ):
        controller.dispatch(SetReferenceReviewDecision(
            "orientation",
            "frame-0",
            decision,
        ))
    controller.dispatch(SignOffReferenceReview("orientation", "frame-0"))
    snapshot = controller.snapshot
    return DomainAnalysisSessionState(
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
    )


def _measurement(tmp_path, group_id, split, state, source_content):
    source_path = tmp_path / f"{group_id}.mpp"
    source_path.write_bytes(source_content)
    masks = MolecularSegmentationSet(frame_count=1)
    detections = MolecularDetectionSet(frame_count=1)
    for x, source_id in enumerate(("full", "island", "outside")):
        detection_id = f"detection-{source_id}"
        detections.set_detections(
            0,
            [
                *detections.get_detections(0, source_view="raw"),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(float(x), 0.0, float(x + 1), 1.0),
                    confidence=1.0,
                    source_view="raw",
                    detection_id=detection_id,
                    origin="manual",
                ),
            ],
            source_view="raw",
            frame_shape=(1, 3),
        )
        mask = np.zeros((1, 3), dtype=bool)
        mask[0, x] = True
        masks.add_segmentation(MolecularSegmentation(
            frame_index=0,
            source_view="raw",
            bbox_xyxy=(float(x), 0.0, float(x + 1), 1.0),
            mask=mask,
            origin="manual",
            prompt_detection_ids=(detection_id,),
            metadata={"operator": "expert"},
            segmentation_id=source_id,
        ))
    first_value = float(source_content[0] - ord("a") + 1)
    series = MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.asarray(
            [[[first_value, first_value + 1.0, first_value + 2.0]]],
            dtype=np.float32,
        ),
        metadata=STMSequenceMetadata(
            pixels_x=3,
            pixels_y=1,
            size_nm_x=3.0,
            size_nm_y=1.0,
        ),
        molecular_segmentations=masks,
        molecular_detections=detections,
    )
    centroids = tuple(
        MolecularCentroid.from_segmentation(
            segmentation,
            frame_shape=series.frame_shape,
        )
        for segmentation in masks.get_segmentations(0, source_view="raw")
    )
    return OrientationReferenceMeasurementGroup(
        measurement_group_id=group_id,
        split=split,
        source_revision=OrientationReferenceSourceRevision.from_path(
            source_path,
            source_file_name=source_path.name,
            acquisition_fingerprint=f"acquisition-{group_id}",
            lineage_fingerprint=f"lineage-{group_id}",
        ),
        snapshot=state,
        series=series,
        sample_coordinates=(build_molecular_sample_coordinates(
            series,
            centroids,
            frame_index=0,
            source_view="raw",
        ),),
    )


def _settings(destination, *, parent_package=None):
    return OrientationReferenceDatasetSettings(
        destination=destination,
        dataset_id="ttmapp-orientation-reference",
        publication_reason="initial reviewed Orientation reference",
        parent_package=parent_package,
    )


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _json_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
