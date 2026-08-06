from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS,
    ClassifierConfiguration,
    ClassifierFrameResultProvenance,
    ClassifierIdentity,
    ClassifierOutcome,
    DomainAnalysisClassifierCacheRecord,
    DomainAnalysisM6CacheRecord,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    DomainAnalysisViewSettings,
    DomainComponentKey,
    DomainLabelSummary,
    M6AnalyzedMolecule,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6PublishedComponent,
    MoleculeClassification,
)
from moltrack.analysis.domain_analysis.cache import (
    ClassifierFrameCacheKey,
    M6FrameCacheKey,
    classifier_frame_cache_record,
)
from moltrack.analysis.domain_analysis.classifier_models import (
    classifier_frame_result_fingerprint,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from nanotrack.core import STMSequenceMetadata


def _configuration(classifier_id: str) -> ClassifierConfiguration:
    return ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=classifier_id,
            schema_version=f"{classifier_id}-schema-v1",
            settings_fingerprint=f"{classifier_id}-settings-v1",
            algorithm_version=f"{classifier_id}-algorithm-v1",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )


def _published_gate() -> M6Gate:
    component = M6PublishedComponent(
        lattice_domain_id="domain-1",
        component_type="full_domain",
        source_ids=("molecule-1",),
        core_source_ids=("molecule-1",),
        halo_source_ids=(),
        points_xy_nm=((0.5, 0.5),),
        footprint_pixels_xy=((0, 0),),
        footprint_area_nm2=1.0,
        centroid_xy_nm=(0.5, 0.5),
        bounds_xyxy_nm=(0.5, 0.5, 0.5, 0.5),
    )
    return M6Gate(frames=(M6FrameGate(
        frame_index=0,
        physical_frame_id="physical-frame-0",
        coordinate_frame="series_physical_nm",
        coordinate_transform_fingerprint="transform-v1",
        presentation_provenance=M6PresentationProvenance(
            raw_shape=(1, 1),
            expanded_shape=(1, 1),
            source_view="raw",
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            registration_fingerprint="registration-v1",
        ),
        source_geometry_fingerprint="geometry-v1",
        m6_settings_fingerprint="m6-settings-v1",
        m6_algorithm_version="m6-algorithm-v1",
        pixel_area_nm2=1.0,
        full_domains=(component,),
        small_ordered_islands=(),
        outside_source_ids=(),
        outside_points_xy_nm=(),
        outside_pixels_xy=(),
        outside_area_nm2=0.0,
        analyzed_source_ids=("molecule-1",),
        analyzed_pixels_xy=((0, 0),),
        analyzed_area_nm2=1.0,
    ),))


def _completed_outcome(
    gate: M6Gate,
    configuration: ClassifierConfiguration,
) -> ClassifierOutcome:
    frame = gate.frames[0]
    classification = MoleculeClassification(
        frame_index=0,
        physical_frame_id=frame.physical_frame_id,
        m6_gate_fingerprint=frame.m6_gate_fingerprint,
        lattice_domain_id="domain-1",
        source_id="molecule-1",
        m6_partition="full_domain",
        classification_status="classified",
        orientation_label="A",
        evidence_strength=0.8,
        component_id="component-a",
        identity=configuration.identity,
    )
    result_fingerprint = classifier_frame_result_fingerprint((classification,))
    return ClassifierOutcome(
        status="completed",
        configuration=configuration,
        molecule_classifications=(classification,),
        frame_result_provenance=(ClassifierFrameResultProvenance(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            cache_key_fingerprint="classifier-cache-key-v1",
            frame_result_fingerprint=result_fingerprint,
        ),),
        domain_summaries=(DomainLabelSummary(
            frame_index=0,
            physical_frame_id=frame.physical_frame_id,
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id="domain-1",
            label="A",
            molecule_count=1,
            counts=(("A", 1), ("B", 0), ("C", 0), ("Unknown orientation", 0)),
            evidence_fraction_of_domain=(("A", 0.8), ("B", 0.0), ("C", 0.0)),
            coherent_evidence_fraction_of_domain=(
                ("A", 0.8), ("B", 0.0), ("C", 0.0)
            ),
            resolved_fraction=1.0,
            resolved_evidence_fraction_of_domain=0.8,
            dominant_class="A",
            dominance_margin=0.8,
            reason="dominant_class_passed",
            configuration=configuration,
        ),),
    )


def _m6_cache_record() -> DomainAnalysisM6CacheRecord:
    molecule = M6AnalyzedMolecule(
        source_id="molecule-1",
        raw_centroid_xy=(0.5, 0.5),
        centroid_xy_nm=(0.5, 0.5),
        footprint_pixels_xy=((0, 0),),
    )
    return DomainAnalysisM6CacheRecord(
        key=M6FrameCacheKey(
            physical_frame_id="physical-frame-0",
            geometry_mode="segmentation_preferred",
            coordinate_transform_fingerprint="transform-v1",
            m6_settings_fingerprint="m6-settings-v1",
            m6_algorithm_version="m6-algorithm-v1",
        ),
        computation=M6FrameComputation(
            frame_index=0,
            molecules=(molecule,),
            analyzed_pixels_xy=((0, 0),),
            pixel_area_nm2=1.0,
            full_domains=(M6ComponentMembership(
                lattice_domain_id="domain-1",
                source_ids=("molecule-1",),
                core_source_ids=("molecule-1",),
            ),),
            small_ordered_islands=(),
            coordinate_frame="series_physical_nm",
            coordinate_transform_fingerprint="transform-v1",
            m6_settings_fingerprint="m6-settings-v1",
        ),
    )


def test_full_workspace_round_trips_through_public_session_seams(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"full domain workspace source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    first = _configuration("classifier-a")
    second = _configuration("classifier-b")
    gate = _published_gate()
    completed = _completed_outcome(gate, first)
    failed = ClassifierOutcome(
        status="failed",
        configuration=second,
        molecule_classifications=(),
        error_message="classifier unavailable",
        failure_frame_index=0,
    )
    published_request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=("classifier-a", "classifier-b"),
    )
    publication = DomainAnalysisPublication(
        request=published_request,
        result=DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=gate,
            classifier_status="completed_with_errors",
            classifier_outcomes=(completed, failed),
        ),
    )
    classification = completed.molecule_classifications[0]
    classifier_cache = DomainAnalysisClassifierCacheRecord(
        key=ClassifierFrameCacheKey(
            physical_frame_id="physical-frame-0",
            configuration=first,
            m6_gate_fingerprint=gate.frames[0].m6_gate_fingerprint,
            raw_frame_fingerprint="a" * 64,
            raw_sampling_geometry_fingerprint="sampling-geometry-v1",
        ),
        record=classifier_frame_cache_record((classification,)),
    )
    state = DomainAnalysisSessionState(
        draft=DomainAnalysisRequest(
            frame_range=range(1),
            geometry_mode="bbox_centers",
            classifier_ids=("classifier-a", "classifier-b"),
        ),
        draft_classifier_configurations=(first, second),
        draft_physical_frame_ids=("physical-frame-0",),
        published_result=publication,
        view_settings=DomainAnalysisViewSettings(
            overlay_visible=False,
            overlay_opacity_percent=37,
        ),
        selected_component=DomainComponentKey(
            physical_frame_id="physical-frame-0",
            lattice_domain_id="domain-1",
        ),
        run_status="completed_with_errors",
        run_diagnosis="classifier-b failed",
        m6_cache_records=(_m6_cache_record(),),
        classifier_cache_records=(classifier_cache,),
    )

    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": state},
    )
    loaded = load_moltrack_session(session_path)
    payload = json.loads(session_path.read_text(encoding="utf-8"))

    assert loaded.domain_analysis_state == state
    assert payload["domain_analysis"]["draft"]["geometry_mode"] == "bbox_centers"
    assert len(payload["domain_analysis"]["draft"][
        "classifier_configurations"
    ]) == 2
    assert payload["domain_analysis"]["draft"]["physical_frame_ids"] == [
        "physical-frame-0"
    ]
    assert payload["domain_analysis"]["view_settings"] == {
        "overlay_visible": False,
        "overlay_opacity_percent": 37,
    }
    assert payload["domain_analysis"]["run"]["status"] == "completed_with_errors"
    assert len(payload["domain_analysis"]["published_result"]["classifier_outcomes"]) == 2
    assert payload["domain_analysis"]["cache"]["classifier_frames"][0][
        "key"
    ]["raw_frame_fingerprint"] == "a" * 64
    assert len(payload["domain_analysis"]["cache"]["m6_frames"]) == 1
    assert '"raw_frame":' not in session_path.read_text(encoding="utf-8")


def test_open_running_workspace_requires_an_explicit_retry(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"running workspace source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={
            "domain_analysis": DomainAnalysisSessionState(
                draft=DomainAnalysisRequest(frame_range=range(1))
            )
        },
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["run"] = {
        "status": "running",
        "diagnosis": "transient progress must not be restored",
    }
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.run_status == "retry_required"
    assert loaded.domain_analysis_state.run_diagnosis == (
        DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS
    )


def test_open_rejects_failed_classifier_cache_as_a_valid_hit(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"failed cache source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    configuration = _configuration("classifier-a")
    gate = _published_gate()
    classification = _completed_outcome(
        gate,
        configuration,
    ).molecule_classifications[0]
    cache_record = DomainAnalysisClassifierCacheRecord(
        key=ClassifierFrameCacheKey(
            physical_frame_id="physical-frame-0",
            configuration=configuration,
            m6_gate_fingerprint=gate.frames[0].m6_gate_fingerprint,
            raw_frame_fingerprint="b" * 64,
            raw_sampling_geometry_fingerprint="sampling-geometry-v1",
        ),
        record=classifier_frame_cache_record((classification,)),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(
            draft=DomainAnalysisRequest(
                frame_range=range(1),
                classifier_ids=("classifier-a",),
            ),
            draft_classifier_configurations=(configuration,),
            draft_physical_frame_ids=("physical-frame-0",),
            m6_cache_records=(_m6_cache_record(),),
            classifier_cache_records=(cache_record,),
        )},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["classifier_frames"][0][
        "status"
    ] = "failed"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.classifier_cache_records == ()
    assert any(
        diagnostic.component == "classifier_cache"
        and "incomplete classifier cache" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_rejects_canceled_m6_cache_as_a_valid_hit(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"canceled cache source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(
            draft=DomainAnalysisRequest(frame_range=range(1)),
            draft_physical_frame_ids=("physical-frame-0",),
            m6_cache_records=(_m6_cache_record(),),
        )},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["m6_frames"][0][
        "status"
    ] = "canceled"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.m6_cache_records == ()
    assert any(
        diagnostic.component == "m6_cache"
        and "incomplete M6 cache" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_corrupt_cache_component_but_preserves_draft(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"corrupt cache component source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    draft = DomainAnalysisRequest(frame_range=range(1))
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(draft=draft)},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["m6_frames"] = "not-a-list"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.draft == draft
    assert any(
        diagnostic.component == "cache"
        and "must be a list" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_ignores_unknown_v2_fields_but_rejects_bad_required_types(
    tmp_path,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"compatible v2 source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    state = DomainAnalysisSessionState(
        draft=DomainAnalysisRequest(frame_range=range(1))
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": state},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["future_component"] = {
        "component_id": "future-component-v1",
        "schema_version": 1,
        "opaque": True,
    }
    payload["domain_analysis"]["view_settings"]["future_overlay"] = "hint"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)
    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.draft == state.draft
    assert loaded.domain_analysis_state.view_settings == state.view_settings
    assert loaded.domain_analysis_state.opaque_components == ((
        "future_component",
        {
            "component_id": "future-component-v1",
            "schema_version": 1,
            "opaque": True,
        },
    ),)
    assert loaded.domain_analysis_state.diagnostics[0].component == (
        "future_component"
    )
    assert loaded.domain_analysis_state.diagnostics[0].identifier == (
        "future-component-v1"
    )
    assert loaded.domain_analysis_state.diagnostics[0].schema_version == "1"
    assert "unsupported" in loaded.domain_analysis_state.diagnostics[0].reason
    round_trip_path = tmp_path / "round-trip.moltrack.json"
    save_moltrack_session(
        round_trip_path,
        series,
        ui_state={"domain_analysis": loaded.domain_analysis_state},
    )
    round_trip = json.loads(round_trip_path.read_text(encoding="utf-8"))
    assert round_trip["domain_analysis"]["future_component"] == {
        "component_id": "future-component-v1",
        "schema_version": 1,
        "opaque": True,
    }

    payload["domain_analysis"]["view_settings"][
        "overlay_opacity_percent"
    ] = "37"
    session_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        ValueError,
        match="domain_analysis.view_settings.overlay_opacity_percent must be an integer",
    ):
        load_moltrack_session(session_path)


def test_save_rejects_a_draft_outside_the_working_series(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"draft range source")
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )

    with pytest.raises(
        ValueError,
        match="Domain Analysis draft range exceeds source_frame_indices length",
    ):
        save_moltrack_session(
            tmp_path / "state.moltrack.json",
            series,
            ui_state={"domain_analysis": DomainAnalysisSessionState(
                draft=DomainAnalysisRequest(frame_range=range(2))
            )},
        )


def test_open_rejects_only_classifier_result_for_a_foreign_m6_gate(
    tmp_path,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"foreign gate source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    configuration = _configuration("classifier-a")
    gate = _published_gate()
    outcome = _completed_outcome(gate, configuration)
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=("classifier-a",),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(
            published_result=DomainAnalysisPublication(
                request=request,
                result=DomainAnalysisResult(
                    run_status="completed",
                    m6_gate=gate,
                    classifier_status="completed",
                    classifier_outcomes=(outcome,),
                ),
            )
        )},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    saved_outcome = payload["domain_analysis"]["published_result"][
        "classifier_outcomes"
    ][0]
    saved_outcome["molecule_classifications"][0][
        "m6_gate_fingerprint"
    ] = "foreign-m6-gate"
    saved_outcome["domain_summaries"][0][
        "m6_gate_fingerprint"
    ] = "foreign-m6-gate"
    classification = replace(
        outcome.molecule_classifications[0],
        m6_gate_fingerprint="foreign-m6-gate",
    )
    frame_fingerprint = classifier_frame_result_fingerprint((classification,))
    saved_outcome["frame_result_provenance"][0][
        "frame_result_fingerprint"
    ] = frame_fingerprint
    modified_outcome = replace(
        outcome,
        molecule_classifications=(classification,),
        frame_result_provenance=(replace(
            outcome.frame_result_provenance[0],
            frame_result_fingerprint=frame_fingerprint,
        ),),
        domain_summaries=(replace(
            outcome.domain_summaries[0],
            m6_gate_fingerprint="foreign-m6-gate",
        ),),
    )
    saved_outcome["classifier_result_fingerprint"] = (
        modified_outcome.classifier_result_fingerprint
    )
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    publication = loaded.domain_analysis_state.published_result
    assert publication is not None
    assert publication.result.m6_gate == gate
    assert publication.result.run_status == "completed_with_errors"
    assert publication.result.classifier_outcomes is not None
    assert publication.result.classifier_outcomes[0].status == "failed"
    assert any(
        diagnostic.component == "classifier_outcome"
        and "does not match the published M6 gate" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_an_unsupported_m6_cache_geometry_mode(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"bad cache geometry source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(
            draft=DomainAnalysisRequest(frame_range=range(1)),
            draft_physical_frame_ids=("physical-frame-0",),
            m6_cache_records=(_m6_cache_record(),),
        )},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["m6_frames"][0]["key"][
        "geometry_mode"
    ] = "unsupported_geometry"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.m6_cache_records == ()
    assert any(
        diagnostic.component == "m6_cache"
        and "Unsupported M6 cache geometry_mode" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_raw_pixels_inside_an_opaque_component(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"opaque raw pixels source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    save_moltrack_session(session_path, series)
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["future_component"] = {
        "component_id": "future-with-pixels",
        "schema_version": 1,
        "raw_frame": [[1.0]],
    }
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.opaque_components == ()
    assert any(
        diagnostic.component == "future_component"
        and "raw pixels" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_rejects_only_incomplete_classifier_outcome(tmp_path) -> None:
    configuration = _configuration("classifier-a")
    gate = _published_gate()
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=("classifier-a",),
    )
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"incomplete classifier source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(
            published_result=DomainAnalysisPublication(
                request=request,
                result=DomainAnalysisResult(
                    run_status="completed",
                    m6_gate=gate,
                    classifier_status="completed",
                    classifier_outcomes=(
                        _completed_outcome(gate, configuration),
                    ),
                ),
            )
        )},
    )
    incomplete = ClassifierOutcome(
        status="completed",
        configuration=configuration,
        molecule_classifications=(),
        frame_result_provenance=(ClassifierFrameResultProvenance(
            frame_index=0,
            physical_frame_id="physical-frame-0",
            cache_key_fingerprint="classifier-cache-key-v1",
            frame_result_fingerprint=classifier_frame_result_fingerprint(()),
        ),),
        domain_summaries=(),
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    saved_outcome = payload["domain_analysis"]["published_result"][
        "classifier_outcomes"
    ][0]
    saved_outcome["molecule_classifications"] = []
    saved_outcome["domain_summaries"] = []
    saved_outcome["frame_result_provenance"][0][
        "frame_result_fingerprint"
    ] = classifier_frame_result_fingerprint(())
    saved_outcome["classifier_result_fingerprint"] = (
        incomplete.classifier_result_fingerprint
    )
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    publication = loaded.domain_analysis_state.published_result
    assert publication is not None
    assert publication.result.classifier_outcomes is not None
    assert publication.result.classifier_outcomes[0].status == "failed"
    assert any(
        "complete published M6 gate" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_cache_outside_the_active_workspace(tmp_path) -> None:
    configuration = _configuration("classifier-a")
    stale_configuration = _configuration("stale-classifier")
    gate = _published_gate()
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"cache scope source")
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    active_path = tmp_path / "active.moltrack.json"
    stale_path = tmp_path / "stale.moltrack.json"
    active_classification = _completed_outcome(
        gate,
        configuration,
    ).molecule_classifications[0]
    stale_classification = _completed_outcome(
        gate,
        stale_configuration,
    ).molecule_classifications[0]
    stale_cache = DomainAnalysisClassifierCacheRecord(
        key=ClassifierFrameCacheKey(
            physical_frame_id="physical-frame-0",
            configuration=stale_configuration,
            m6_gate_fingerprint=gate.frames[0].m6_gate_fingerprint,
            raw_frame_fingerprint=None,
            raw_sampling_geometry_fingerprint="sampling-geometry-v1",
        ),
        record=classifier_frame_cache_record((stale_classification,)),
    )
    active_cache = DomainAnalysisClassifierCacheRecord(
        key=replace(stale_cache.key, configuration=configuration),
        record=classifier_frame_cache_record((active_classification,)),
    )
    for path, classifier_id, saved_configuration, cache_record in (
        (active_path, "classifier-a", configuration, active_cache),
        (stale_path, "stale-classifier", stale_configuration, stale_cache),
    ):
        save_moltrack_session(
            path,
            series,
            ui_state={"domain_analysis": DomainAnalysisSessionState(
                draft=DomainAnalysisRequest(
                    frame_range=range(1),
                    classifier_ids=(classifier_id,),
                ),
                draft_classifier_configurations=(saved_configuration,),
                draft_physical_frame_ids=("physical-frame-0",),
                m6_cache_records=(_m6_cache_record(),),
                classifier_cache_records=(cache_record,),
            )},
        )
    payload = json.loads(active_path.read_text(encoding="utf-8"))
    stale_payload = json.loads(stale_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["classifier_frames"] = (
        stale_payload["domain_analysis"]["cache"]["classifier_frames"]
    )
    active_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(active_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.classifier_cache_records == ()
    assert any(
        "active classifier configuration" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_corrupt_publication_but_preserves_draft(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"corrupt publication source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    draft = DomainAnalysisRequest(
        frame_range=range(1),
        geometry_mode="bbox_centers",
    )
    publication = DomainAnalysisPublication(
        request=DomainAnalysisRequest(frame_range=range(1)),
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=_published_gate(),
            classifier_status="not_requested",
        ),
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": DomainAnalysisSessionState(
            draft=draft,
            draft_physical_frame_ids=("physical-frame-0",),
            published_result=publication,
            selected_component=DomainComponentKey(
                physical_frame_id="physical-frame-0",
                lattice_domain_id="domain-1",
            ),
        )},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["published_result"]["m6_gate"]["frames"][0][
        "m6_gate_fingerprint"
    ] = "corrupt-m6-fingerprint"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.draft == draft
    assert loaded.domain_analysis_state.published_result is None
    assert loaded.domain_analysis_state.selected_component is None
    assert any(
        diagnostic.component == "published_result"
        and "m6_gate_fingerprint" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_all_conflicting_classifier_cache_records(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"classifier cache conflict source")
    first_path = tmp_path / "first.moltrack.json"
    second_path = tmp_path / "second.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    configuration = _configuration("classifier-a")
    gate = _published_gate()
    first_value = _completed_outcome(
        gate,
        configuration,
    ).molecule_classifications[0]
    second_value = replace(
        first_value,
        orientation_label="B",
        evidence_strength=0.7,
        component_id="component-b",
    )
    key = ClassifierFrameCacheKey(
        physical_frame_id="physical-frame-0",
        configuration=configuration,
        m6_gate_fingerprint=gate.frames[0].m6_gate_fingerprint,
        raw_frame_fingerprint=None,
        raw_sampling_geometry_fingerprint="sampling-geometry-v1",
    )
    for path, value in ((first_path, first_value), (second_path, second_value)):
        save_moltrack_session(
            path,
            series,
            ui_state={"domain_analysis": DomainAnalysisSessionState(
                draft=DomainAnalysisRequest(
                    frame_range=range(1),
                    classifier_ids=("classifier-a",),
                ),
                draft_classifier_configurations=(configuration,),
                draft_physical_frame_ids=("physical-frame-0",),
                m6_cache_records=(_m6_cache_record(),),
                classifier_cache_records=(DomainAnalysisClassifierCacheRecord(
                    key=key,
                    record=classifier_frame_cache_record((value,)),
                ),),
            )},
        )
    payload = json.loads(first_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["classifier_frames"].append(
        second_payload["domain_analysis"]["cache"]["classifier_frames"][0]
    )
    first_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(first_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.classifier_cache_records == ()
    assert any(
        diagnostic.component == "classifier_cache"
        and "conflicting records" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_open_skips_all_conflicting_m6_cache_records(tmp_path) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"m6 cache conflict source")
    first_path = tmp_path / "first.moltrack.json"
    second_path = tmp_path / "second.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=1, pixels_y=1),
    )
    first_record = _m6_cache_record()
    first_molecule = first_record.computation.molecules[0]
    second_record = replace(
        first_record,
        computation=replace(
            first_record.computation,
            molecules=(replace(
                first_molecule,
                raw_centroid_xy=(0.25, 0.25),
            ),),
        ),
    )
    for path, record in (
        (first_path, first_record),
        (second_path, second_record),
    ):
        save_moltrack_session(
            path,
            series,
            ui_state={"domain_analysis": DomainAnalysisSessionState(
                draft=DomainAnalysisRequest(frame_range=range(1)),
                draft_physical_frame_ids=("physical-frame-0",),
                m6_cache_records=(record,),
            )},
        )
    payload = json.loads(first_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    payload["domain_analysis"]["cache"]["m6_frames"].append(
        second_payload["domain_analysis"]["cache"]["m6_frames"][0]
    )
    first_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(first_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.m6_cache_records == ()
    assert any(
        diagnostic.component == "m6_cache"
        and "conflicting records" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )
