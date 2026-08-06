from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace

import pytest

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ClassifierConfiguration,
    ClassifierFrameResultProvenance,
    ClassifierIdentity,
    ClassifierOutcome,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    DomainComponentKey,
    DomainLabelSummary,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6PublishedComponent,
    M6PublishedMolecule,
    MoleculeClassification,
)
from moltrack.analysis.domain_analysis.classifier_models import (
    classifier_frame_result_fingerprint,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.persistence import (
    CanonicalJsonObject,
    DomainAnalysisExportSettings,
    export_analysis_package,
)


_M6_SETTINGS = {
    "preset_id": "sixfold-default-v1",
    "minimum_core_neighbors": 3,
}
_M6_SETTINGS_FINGERPRINT = canonical_sha256(_M6_SETTINGS)
_SOURCE_IDENTITY = {
    "file_name": "representative-source.mpp",
    "integrity": {"algorithm": "sha256", "value": "a" * 64},
}


def _component(
    frame_index: int,
    *,
    component_type: str,
    source_id: str,
    pixel_x: int,
    source_kind: str,
    qc_flags: tuple[str, ...] = (),
) -> M6PublishedComponent:
    point = (float(pixel_x), float(frame_index))
    return M6PublishedComponent(
        lattice_domain_id=f"{component_type}-{frame_index}",
        component_type=component_type,
        members=(M6PublishedMolecule(
            source_id=source_id,
            source_kind=source_kind,
            point_xy_nm=point,
        ),),
        core_source_ids=(source_id,),
        halo_source_ids=(),
        footprint_pixels_xy=((pixel_x, 0),),
        footprint_area_nm2=0.5,
        centroid_xy_nm=point,
        bounds_xyxy_nm=(*point, *point),
        qc_flags=qc_flags,
    )


def _frame_gate(frame_index: int) -> M6FrameGate:
    full_source_id = f"molecule-full-{frame_index}"
    island_source_id = f"molecule-island-{frame_index}"
    outside_source_id = f"molecule-outside-{frame_index}"
    return M6FrameGate(
        frame_index=frame_index,
        physical_frame_id=f"physical-frame-{frame_index}",
        coordinate_frame="series_physical_nm",
        coordinate_transform_fingerprint=f"transform-{frame_index}",
        presentation_provenance=M6PresentationProvenance(
            raw_shape=(1, 3),
            expanded_shape=(3, 5),
            source_view="expanded_aligned",
            frame_origin_xy=(float(frame_index), 0.25),
            canvas_offset_xy=(1.5, 2.5),
            registration_fingerprint=f"registration-{frame_index}",
        ),
        source_geometry_fingerprint=f"geometry-{frame_index}",
        m6_settings_fingerprint=_M6_SETTINGS_FINGERPRINT,
        m6_algorithm_version="m6-algorithm-v1",
        pixel_area_nm2=0.5,
        full_domains=(
            _component(
                frame_index,
                component_type="full_domain",
                source_id=full_source_id,
                pixel_x=0,
                source_kind="segmentation",
                qc_flags=("edge_truncated",),
            ),
        ),
        small_ordered_islands=(
            _component(
                frame_index,
                component_type="small_ordered_island",
                source_id=island_source_id,
                pixel_x=1,
                source_kind="bbox_center",
            ),
        ),
        outside_members=(M6PublishedMolecule(
            source_id=outside_source_id,
            source_kind="segmentation",
            point_xy_nm=(2.0, float(frame_index)),
        ),),
        outside_pixels_xy=((2, 0),),
        outside_area_nm2=0.5,
        analyzed_source_ids=(full_source_id, island_source_id, outside_source_id),
        analyzed_pixels_xy=((0, 0), (1, 0), (2, 0)),
        analyzed_area_nm2=1.5,
    )


def _m6_only_state() -> DomainAnalysisSessionState:
    publication = DomainAnalysisPublication(
        request=DomainAnalysisRequest(frame_range=range(2)),
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=M6Gate(frames=(_frame_gate(0), _frame_gate(1))),
            classifier_status="not_requested",
        ),
    )
    return DomainAnalysisSessionState(published_result=publication)


def _csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _package_contents(path):
    return {
        item.name: item.read_bytes()
        for item in path.iterdir()
        if item.is_file()
    }


def _export_settings(
    destination,
    source_frame_indices=(17, 23),
    *,
    physical_frame_ids=None,
):
    return DomainAnalysisExportSettings(
        destination=destination,
        source_frame_indices=source_frame_indices,
        physical_frame_ids=(
            tuple(physical_frame_ids)
            if physical_frame_ids is not None
            else tuple(
                f"physical-frame-{index}"
                for index in range(len(source_frame_indices))
            )
        ),
        source_identity=CanonicalJsonObject(_SOURCE_IDENTITY),
        m6_settings=CanonicalJsonObject(_M6_SETTINGS),
    )


def test_export_analysis_package_writes_m6_only_schema_v9(tmp_path) -> None:
    destination = tmp_path / "domain-analysis"

    result = export_analysis_package(
        _m6_only_state(),
        _export_settings(destination),
    )

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    frames = _csv_rows(destination / "domain_analysis_frames.csv")
    domains = _csv_rows(destination / "domain_analysis_domains.csv")
    memberships = _csv_rows(destination / "domain_analysis_memberships.csv")
    domain_analysis = manifest["analysis"]["domain_analysis"]

    assert manifest["export_schema_version"] == 9
    assert manifest["package_kind"] == "moltrack_analysis"
    assert manifest["source"]["identity"] == _SOURCE_IDENTITY
    assert manifest["working_series"]["physical_frame_ids"] == [
        "physical-frame-0",
        "physical-frame-1",
    ]
    assert domain_analysis["published_result_schema_version"] == 1
    assert domain_analysis["m6_settings"] == _M6_SETTINGS
    assert domain_analysis["request"] == {
        "classifier_ids": [],
        "frame_start": 0,
        "frame_stop": 2,
        "geometry_mode": "segmentation_preferred",
        "request_fingerprint": domain_analysis["request"]["request_fingerprint"],
    }
    assert domain_analysis["result"] == {
        "classifier_status": "not_requested",
        "run_status": "completed",
    }
    assert result.relative_files == (
        "domain_analysis_classifier_outcomes.csv",
        "domain_analysis_domain_classifications.csv",
        "domain_analysis_domains.csv",
        "domain_analysis_frames.csv",
        "domain_analysis_memberships.csv",
        "domain_analysis_molecule_classifications.csv",
        "manifest.json",
    )
    assert result.record_counts == (
        ("domain_analysis_classifier_outcomes.csv", 0),
        ("domain_analysis_domain_classifications.csv", 0),
        ("domain_analysis_domains.csv", 4),
        ("domain_analysis_frames.csv", 2),
        ("domain_analysis_memberships.csv", 6),
        ("domain_analysis_molecule_classifications.csv", 0),
    )
    assert [(row["physical_frame_id"], row["source_frame_index"]) for row in frames] == [
        ("physical-frame-0", "17"),
        ("physical-frame-1", "23"),
    ]
    assert frames[0]["source_view"] == "expanded_aligned"
    assert frames[0]["registration_fingerprint"] == "registration-0"
    assert json.loads(frames[0]["analyzed_pixels_xy"]) == [[0, 0], [1, 0], [2, 0]]
    assert json.loads(frames[0]["outside_pixels_xy"]) == [[2, 0]]
    assert {
        (row["physical_frame_id"], row["lattice_domain_id"], row["component_type"])
        for row in domains
    } == {
        ("physical-frame-0", "full_domain-0", "full_domain"),
        ("physical-frame-0", "small_ordered_island-0", "small_ordered_island"),
        ("physical-frame-1", "full_domain-1", "full_domain"),
        ("physical-frame-1", "small_ordered_island-1", "small_ordered_island"),
    }
    assert {
        (row["component_type"], tuple(json.loads(row["m6_qc_flags"])))
        for row in domains
    } == {
        ("full_domain", ("edge_truncated",)),
        ("small_ordered_island", ()),
    }
    assert {
        (row["physical_frame_id"], row["source_id"], row["partition"])
        for row in memberships
    } == {
        ("physical-frame-0", "molecule-full-0", "full_domain"),
        ("physical-frame-0", "molecule-island-0", "small_ordered_island"),
        ("physical-frame-0", "molecule-outside-0", "outside"),
        ("physical-frame-1", "molecule-full-1", "full_domain"),
        ("physical-frame-1", "molecule-island-1", "small_ordered_island"),
        ("physical-frame-1", "molecule-outside-1", "outside"),
    }
    assert {row["source_kind"] for row in memberships} == {
        "bbox_center",
        "segmentation",
    }
    assert _csv_rows(destination / "domain_analysis_classifier_outcomes.csv") == []
    assert _csv_rows(destination / "domain_analysis_domain_classifications.csv") == []
    assert _csv_rows(destination / "domain_analysis_molecule_classifications.csv") == []
    for file_entry in manifest["files"]:
        assert file_entry["sha256"] == hashlib.sha256(
            (destination / file_entry["path"]).read_bytes()
        ).hexdigest()
        assert manifest["table_schemas"][file_entry["path"]]["columns"]


def test_export_uses_published_request_and_is_deterministic(tmp_path) -> None:
    state = replace(
        _m6_only_state(),
        draft=DomainAnalysisRequest(
            frame_range=range(1),
            geometry_mode="bbox_centers",
        ),
        draft_physical_frame_ids=("physical-frame-0",),
        selected_component=DomainComponentKey(
            physical_frame_id="physical-frame-1",
            lattice_domain_id="full_domain-1",
        ),
    )
    destinations = (tmp_path / "first", tmp_path / "second")
    states = (
        state,
        replace(
            state,
            selected_component=DomainComponentKey(
                physical_frame_id="physical-frame-0",
                lattice_domain_id="full_domain-0",
            ),
        ),
    )

    for destination, snapshot in zip(destinations, states):
        export_analysis_package(
            snapshot,
            _export_settings(destination),
        )

    manifest = json.loads(
        (destinations[0] / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["working_series"]["exported_frames"] == [
        {
            "physical_frame_id": "physical-frame-0",
            "source_frame_index": 17,
            "working_frame_index": 0,
        },
        {
            "physical_frame_id": "physical-frame-1",
            "source_frame_index": 23,
            "working_frame_index": 1,
        },
    ]
    assert manifest["analysis"]["domain_analysis"]["request"]["geometry_mode"] == (
        "segmentation_preferred"
    )
    assert _package_contents(destinations[0]) == _package_contents(destinations[1])


def test_export_keeps_unsorted_membership_provenance_bound_to_source_id(
    tmp_path,
) -> None:
    base_frame = _frame_gate(0)
    component = M6PublishedComponent(
        lattice_domain_id="full-domain-unsorted",
        component_type="full_domain",
        members=(
            M6PublishedMolecule(
                source_id="molecule-z",
                source_kind="segmentation",
                point_xy_nm=(9.0, 0.0),
            ),
            M6PublishedMolecule(
                source_id="molecule-a",
                source_kind="bbox_center",
                point_xy_nm=(1.0, 0.0),
            ),
        ),
        core_source_ids=("molecule-a", "molecule-z"),
        halo_source_ids=(),
        footprint_pixels_xy=((0, 0),),
        footprint_area_nm2=0.5,
        centroid_xy_nm=(5.0, 0.0),
        bounds_xyxy_nm=(1.0, 0.0, 9.0, 0.0),
    )
    frame = replace(
        base_frame,
        full_domains=(component,),
        analyzed_source_ids=(
            "molecule-a",
            "molecule-z",
            "molecule-island-0",
            "molecule-outside-0",
        ),
    )
    publication = DomainAnalysisPublication(
        request=DomainAnalysisRequest(frame_range=range(1)),
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=M6Gate(frames=(frame,)),
            classifier_status="not_requested",
        ),
    )
    destination = tmp_path / "atomic-memberships"

    export_analysis_package(
        DomainAnalysisSessionState(published_result=publication),
        _export_settings(destination, (17,)),
    )

    rows = [
        row
        for row in _csv_rows(destination / "domain_analysis_memberships.csv")
        if row["lattice_domain_id"] == component.lattice_domain_id
    ]
    assert [
        (row["source_id"], row["source_kind"], row["point_x_nm"])
        for row in rows
    ] == [
        ("molecule-a", "bbox_center", "1.0"),
        ("molecule-z", "segmentation", "9.0"),
    ]


def test_export_completed_with_errors_keeps_results_and_atomic_failure(
    tmp_path,
) -> None:
    completed_configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id="classifier-completed",
            schema_version="classifier-schema-v1",
            settings_fingerprint="completed-settings-v1",
            algorithm_version="classifier-algorithm-v1",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )
    failed_configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id="classifier-failed",
            schema_version="classifier-schema-v2",
            settings_fingerprint="failed-settings-v2",
            algorithm_version="classifier-algorithm-v2",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )
    frame = _frame_gate(0)
    classifications = (
        MoleculeClassification(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id="full_domain-0",
            source_id="molecule-full-0",
            m6_partition="full_domain",
            classification_status="classified",
            orientation_label="A",
            evidence_strength=0.75,
            component_id="component-a",
            identity=completed_configuration.identity,
        ),
        MoleculeClassification(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id="small_ordered_island-0",
            source_id="molecule-island-0",
            m6_partition="small_ordered_island",
            classification_status="not_gated",
            orientation_label=None,
            evidence_strength=0.0,
            component_id=None,
            identity=completed_configuration.identity,
        ),
        MoleculeClassification(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id=None,
            source_id="molecule-outside-0",
            m6_partition="outside",
            classification_status="not_gated",
            orientation_label=None,
            evidence_strength=0.0,
            component_id=None,
            identity=completed_configuration.identity,
        ),
    )
    completed_outcome = ClassifierOutcome(
        status="completed",
        configuration=completed_configuration,
        molecule_classifications=classifications,
        frame_result_provenance=(ClassifierFrameResultProvenance(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            cache_key_fingerprint="classifier-frame-cache-key-v1",
            frame_result_fingerprint=classifier_frame_result_fingerprint(
                classifications
            ),
        ),),
        domain_summaries=(DomainLabelSummary(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id="full_domain-0",
            label="A",
            molecule_count=1,
            counts=(("A", 1), ("B", 0), ("C", 0), ("Unknown orientation", 0)),
            evidence_fraction_of_domain=(("A", 0.75), ("B", 0.0), ("C", 0.0)),
            coherent_evidence_fraction_of_domain=(
                ("A", 0.75), ("B", 0.0), ("C", 0.0)
            ),
            resolved_fraction=1.0,
            resolved_evidence_fraction_of_domain=0.75,
            dominant_class="A",
            dominance_margin=0.75,
            reason="dominant_class_passed",
            configuration=completed_configuration,
        ),),
    )
    failed_outcome = ClassifierOutcome(
        status="failed",
        configuration=failed_configuration,
        molecule_classifications=(),
        error_message="classifier unavailable",
        failure_frame_index=0,
    )
    publication = DomainAnalysisPublication(
        request=DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=("classifier-completed", "classifier-failed"),
        ),
        result=DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=M6Gate(frames=(frame,)),
            classifier_status="completed_with_errors",
            classifier_outcomes=(completed_outcome, failed_outcome),
        ),
    )
    destination = tmp_path / "classified-domain-analysis"

    result = export_analysis_package(
        DomainAnalysisSessionState(published_result=publication),
        _export_settings(destination, (17,)),
    )

    molecule_rows = _csv_rows(
        destination / "domain_analysis_molecule_classifications.csv"
    )
    domain_rows = _csv_rows(
        destination / "domain_analysis_domain_classifications.csv"
    )
    outcome_rows = _csv_rows(
        destination / "domain_analysis_classifier_outcomes.csv"
    )
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert result.record_counts[-1] == (
        "domain_analysis_molecule_classifications.csv",
        1,
    )
    assert molecule_rows == [{
        "physical_frame_id": "physical-frame-0",
        "working_frame_index": "0",
        "source_frame_index": "17",
        "classifier_id": "classifier-completed",
        "lattice_domain_id": "full_domain-0",
        "source_id": "molecule-full-0",
        "classification_status": "classified",
        "orientation_label": "A",
        "evidence_strength": "0.75",
        "component_id": "component-a",
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
        "classifier_schema_version": "classifier-schema-v1",
        "classifier_algorithm_version": "classifier-algorithm-v1",
        "classifier_settings_fingerprint": "completed-settings-v1",
    }]
    assert len(domain_rows) == 1
    assert domain_rows[0]["label"] == "A"
    assert domain_rows[0]["molecule_count"] == "1"
    assert json.loads(domain_rows[0]["counts"]) == [
        ["A", 1], ["B", 0], ["C", 0], ["Unknown orientation", 0]
    ]
    assert json.loads(domain_rows[0]["evidence_fraction_of_domain"]) == [
        ["A", 0.75], ["B", 0.0], ["C", 0.0]
    ]
    assert domain_rows[0]["aggregation_policy_version"] == (
        ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1.preset_id
    )
    assert [row["classifier_id"] for row in outcome_rows] == [
        "classifier-completed",
        "classifier-failed",
    ]
    assert [row["status"] for row in outcome_rows] == ["completed", "failed"]
    assert outcome_rows[0]["result_fingerprint"] == (
        completed_outcome.classifier_result_fingerprint
    )
    assert outcome_rows[1]["failure_frame_index"] == "0"
    assert outcome_rows[1]["error_message"] == "classifier unavailable"
    classifier_manifests = manifest["analysis"]["domain_analysis"][
        "classifier_outcomes"
    ]
    assert classifier_manifests[0]["configuration"]["identity"] == {
        "algorithm_version": "classifier-algorithm-v1",
        "classifier_id": "classifier-completed",
        "schema_version": "classifier-schema-v1",
        "settings_fingerprint": "completed-settings-v1",
    }
    assert classifier_manifests[0]["configuration"]["aggregation_preset"] == {
        **ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1.as_dict(),
        "fingerprint": ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1.fingerprint,
    }
    assert classifier_manifests[0]["frame_outcomes"] == [{
        "cache_key_fingerprint": "classifier-frame-cache-key-v1",
        "frame_result_fingerprint": (
            completed_outcome.frame_result_provenance[0].frame_result_fingerprint
        ),
        "physical_frame_id": "physical-frame-0",
        "source_frame_index": 17,
        "status": "completed",
        "working_frame_index": 0,
    }]
    assert classifier_manifests[0]["failure"] is None
    assert classifier_manifests[1]["status"] == "failed"
    assert classifier_manifests[1]["frame_outcomes"] == [{
        "error_message": "classifier unavailable",
        "physical_frame_id": "physical-frame-0",
        "source_frame_index": 17,
        "status": "failed",
        "working_frame_index": 0,
    }]
    assert classifier_manifests[1]["failure"] == {
        "error_message": "classifier unavailable",
        "physical_frame_id": "physical-frame-0",
        "source_frame_index": 17,
        "working_frame_index": 0,
    }


def test_export_marks_frames_after_classifier_failure_as_not_run(tmp_path) -> None:
    configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id="classifier-failed",
            schema_version="classifier-schema-v1",
            settings_fingerprint="classifier-settings-v1",
            algorithm_version="classifier-algorithm-v1",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )
    frames = (
        replace(_frame_gate(0), physical_frame_id="physical-frame-b"),
        replace(_frame_gate(1), physical_frame_id="physical-frame-a"),
    )
    publication = DomainAnalysisPublication(
        request=DomainAnalysisRequest(
            frame_range=range(2),
            classifier_ids=("classifier-failed",),
        ),
        result=DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=M6Gate(frames=frames),
            classifier_status="completed_with_errors",
            classifier_outcomes=(ClassifierOutcome(
                status="failed",
                configuration=configuration,
                molecule_classifications=(),
                error_message="classifier unavailable",
                failure_frame_index=1,
            ),),
        ),
    )
    destination = tmp_path / "failed-frame-outcomes"

    export_analysis_package(
        DomainAnalysisSessionState(published_result=publication),
        _export_settings(
            destination,
            physical_frame_ids=("physical-frame-b", "physical-frame-a"),
        ),
    )

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    outcome = manifest["analysis"]["domain_analysis"]["classifier_outcomes"][0]
    csv_outcome = _csv_rows(
        destination / "domain_analysis_classifier_outcomes.csv"
    )[0]
    assert csv_outcome["failure_physical_frame_id"] == "physical-frame-a"
    assert csv_outcome["failure_frame_index"] == "1"
    assert csv_outcome["failure_source_frame_index"] == "23"
    assert outcome["frame_outcomes"] == [
        {
            "error_message": "classifier unavailable",
            "physical_frame_id": "physical-frame-a",
            "source_frame_index": 23,
            "status": "failed",
            "working_frame_index": 1,
        },
        {
            "physical_frame_id": "physical-frame-b",
            "source_frame_index": 17,
            "status": "not_run",
            "working_frame_index": 0,
        },
    ]


def test_export_rejects_classifier_failure_outside_published_gate(tmp_path) -> None:
    configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id="classifier-failed",
            schema_version="classifier-schema-v1",
            settings_fingerprint="classifier-settings-v1",
            algorithm_version="classifier-algorithm-v1",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )
    publication = DomainAnalysisPublication(
        request=DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=("classifier-failed",),
        ),
        result=DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=M6Gate(frames=(_frame_gate(0),)),
            classifier_status="completed_with_errors",
            classifier_outcomes=(ClassifierOutcome(
                status="failed",
                configuration=configuration,
                molecule_classifications=(),
                error_message="classifier unavailable",
                failure_frame_index=1,
            ),),
        ),
    )
    destination = tmp_path / "invalid-failure-frame"

    with pytest.raises(ValueError, match="failure frame"):
        export_analysis_package(
            DomainAnalysisSessionState(published_result=publication),
            _export_settings(destination, (17,)),
        )

    assert not destination.exists()
