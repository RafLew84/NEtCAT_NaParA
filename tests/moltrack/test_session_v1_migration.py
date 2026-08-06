from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularM6OrientationAnalysisSettings,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeSessionState,
    analyze_molecular_frame_range,
)
from moltrack.analysis.domain_analysis import (
    DomainAnalysisM6CacheRecord,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    M6AnalyzedMolecule,
    M6ComponentMembership,
    M6FrameComputation,
)
from moltrack.analysis.domain_analysis.cache import M6FrameCacheKey
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    MolTrackPositionAnalysisRange,
    MolTrackPositionAnalysisState,
    build_molecular_centroids,
)
from moltrack.persistence import (
    MolTrackSessionLoadError,
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata


def _annotated_series(source_path: Path) -> tuple[MolTrackImageSeries, np.ndarray]:
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:5, 3:7] = True
    detections = MolecularDetectionSet(frame_count=3)
    detections.set_detections(
        1,
        [MolecularDetection(
            frame_index=1,
            bbox_xyxy=(3.0, 2.0, 7.0, 5.0),
            confidence=0.93,
            detection_id="detection-v1",
            origin="manual",
        )],
        source_view="raw",
        frame_shape=(8, 8),
    )
    segmentations = MolecularSegmentationSet(frame_count=3)
    segmentations.add_segmentation(MolecularSegmentation(
        frame_index=1,
        bbox_xyxy=(3.0, 2.0, 7.0, 5.0),
        mask=mask,
        original_mask=mask,
        prompt_detection_ids=("detection-v1",),
        segmentation_id="segmentation-v1",
    ))
    return MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        molecular_detections=detections,
        molecular_segmentations=segmentations,
    ), mask


def _write_real_v1_session(
    session_path: Path,
    series: MolTrackImageSeries,
) -> bytes:
    legacy_position = MolTrackPositionAnalysisState(
        source_view="raw",
        first_range=MolTrackPositionAnalysisRange("Primary", 1, 2),
        second_range=MolTrackPositionAnalysisRange("Comparison", 0, 0),
        comparison_completed=True,
        use_segmentation_centroids=True,
    )
    save_moltrack_session(
        session_path,
        series,
        ui_state={"position_analysis": legacy_position},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    payload.pop("domain_analysis")
    session_path.write_text(json.dumps(payload), encoding="utf-8")
    return session_path.read_bytes()


def _empty_series_loader(source_path: Path) -> Callable[..., MolTrackImageSeries]:
    def load(*_args: Any, **_kwargs: Any) -> MolTrackImageSeries:
        return MolTrackImageSeries(
            source_path=source_path,
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )

    return load


def test_open_migrates_real_v1_annotations_and_first_range_in_memory(
    tmp_path,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"historical v1 source")
    session_path = tmp_path / "historical-v1.moltrack.json"
    series, mask = _annotated_series(source_path)
    v1_bytes = _write_real_v1_session(session_path, series)

    loaded = load_moltrack_session(session_path)

    assert session_path.read_bytes() == v1_bytes
    assert loaded.schema_version == 2
    assert loaded.position_analysis is None
    assert loaded.molecular_detections is not None
    assert loaded.molecular_detections.get_detection("detection-v1") is not None
    assert loaded.molecular_segmentations is not None
    restored_mask = loaded.molecular_segmentations.get_segmentation(
        "segmentation-v1"
    )
    assert restored_mask is not None
    np.testing.assert_array_equal(restored_mask.mask, mask)
    restored = restore_moltrack_image_series_from_session(
        loaded,
        series_loader=_empty_series_loader(source_path),
    )
    centroids = build_molecular_centroids(
        restored,
        frame_index=1,
        use_segmentation_centroids=True,
    )
    assert [(value.x_px, value.y_px) for value in centroids] == [(5.0, 3.5)]
    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.draft is not None
    assert loaded.domain_analysis_state.draft.frame_indices == (1, 2)
    assert loaded.domain_analysis_state.draft.geometry_mode == (
        "segmentation_preferred"
    )
    assert loaded.domain_analysis_state.classifier_status == "not_run"
    assert loaded.domain_analysis_state.published_result is None
    assert any(
        diagnostic.component == "position_analysis.second_range"
        and "omitted" in diagnostic.reason
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def _saved_v2_payload(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    source_path = tmp_path / "diagnostic-source.mpp"
    source_path.write_bytes(b"diagnostic source")
    session_path = tmp_path / "diagnostic.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((2, 2, 2), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=2, pixels_y=2),
    )
    save_moltrack_session(session_path, series)
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def _m6_cache_record() -> DomainAnalysisM6CacheRecord:
    molecule = M6AnalyzedMolecule(
        source_id="molecule-1",
        raw_centroid_xy=(0.5, 0.5),
        centroid_xy_nm=(0.5, 0.5),
        footprint_pixels_xy=((0, 0),),
    )
    return DomainAnalysisM6CacheRecord(
        key=M6FrameCacheKey(
            physical_frame_id="source-frame-0",
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


def _legacy_m6_series(source_path: Path) -> MolTrackImageSeries:
    detections = MolecularDetectionSet(frame_count=1)
    detections.set_detections(
        0,
        [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(x - 0.2, y - 0.2, x + 0.2, y + 0.2),
                confidence=0.9,
                detection_id=f"molecule-{row}-{column}",
            )
            for row in range(5)
            for column in range(5)
            for x, y in ((4.0 + 2.0 * column, 4.0 + 2.0 * row),)
        ],
        source_view="raw",
        frame_shape=(20, 20),
    )
    return MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 20, 20), dtype=np.float32),
        metadata=STMSequenceMetadata(
            raw_header={"General Info": {"Angle": "0.0"}},
            pixels_x=20,
            pixels_y=20,
            size_nm_x=20.0,
            size_nm_y=20.0,
            scan_angle_deg=0.0,
        ),
        molecular_detections=detections,
    )


def _assert_load_error(
    session_path: Path,
    *,
    kind: str,
    component: str,
) -> MolTrackSessionLoadError:
    before = session_path.read_bytes()
    with pytest.raises(MolTrackSessionLoadError) as raised:
        load_moltrack_session(session_path)
    error = raised.value
    assert error.kind == kind
    assert error.component == component
    assert error.reason
    assert "No session data was activated" in str(error)
    assert "kept in memory" not in str(error)
    assert session_path.read_bytes() == before
    return error


def test_open_distinguishes_unsupported_session_and_required_element(
    tmp_path,
) -> None:
    session_path, payload = _saved_v2_payload(tmp_path)
    payload["schema_version"] = 999
    session_path.write_text(json.dumps(payload), encoding="utf-8")
    schema_error = _assert_load_error(
        session_path,
        kind="unsupported",
        component="schema_version",
    )
    assert "999" in schema_error.reason

    payload["schema_version"] = 2
    payload["ui"]["registration_view_mode"] = "Future registered view"
    session_path.write_text(json.dumps(payload), encoding="utf-8")
    view_error = _assert_load_error(
        session_path,
        kind="unsupported",
        component="ui.registration_view_mode",
    )
    assert "Future registered view" in view_error.reason


def test_open_reports_corrupt_structure_without_activation_or_write(
    tmp_path,
) -> None:
    session_path, payload = _saved_v2_payload(tmp_path)
    payload["working_series"]["source_frame_indices"] = "broken"
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    error = _assert_load_error(
        session_path,
        kind="corrupt",
        component="working_series.source_frame_indices",
    )

    assert "list" in error.reason


def test_v1_rejects_a_non_boolean_centroid_mode_as_corrupt(tmp_path) -> None:
    session_path, payload = _saved_v2_payload(tmp_path)
    payload["schema_version"] = 1
    payload.pop("domain_analysis")
    payload["position_analysis"] = {
        "first_range": {"name": "All", "start_frame": 0, "end_frame": 1},
        "second_range": {"name": "Old", "start_frame": 0, "end_frame": 0},
        "use_segmentation_centroids": "false",
    }
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    error = _assert_load_error(
        session_path,
        kind="corrupt",
        component="position_analysis",
    )

    assert "use_segmentation_centroids must be boolean" in error.reason


def test_v1_routes_compatible_m6_entries_through_v2_cache_validation(
    tmp_path,
) -> None:
    session_path, payload = _saved_v2_payload(tmp_path)
    record = _m6_cache_record()
    series = MolTrackImageSeries(
        source_path=Path(payload["source"]["path"]),
        raw_frames=np.zeros((2, 2, 2), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=2, pixels_y=2),
    )
    state = DomainAnalysisSessionState(
        draft=DomainAnalysisRequest(frame_range=range(2)),
        draft_physical_frame_ids=("source-frame-0", "source-frame-1"),
        m6_cache_records=(record,),
    )
    save_moltrack_session(
        session_path, series, ui_state={"domain_analysis": state}
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    compatible = payload["domain_analysis"]["cache"]["m6_frames"][0]
    outside_scope = json.loads(json.dumps(compatible))
    outside_scope["key"]["physical_frame_id"] = "source-frame-999"
    payload["schema_version"] = 1
    payload.pop("domain_analysis")
    payload["molecular_m6_analysis"] = {
        "reproducible_cache": [
            {"status": "partial"}, compatible, outside_scope,
        ],
    }
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.m6_cache_records == (record,)
    assert any(
        diagnostic.identifier
        == "molecular_m6_analysis.reproducible_cache[0]"
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )
    assert any(
        diagnostic.identifier
        == "molecular_m6_analysis.reproducible_cache[2]"
        for diagnostic in loaded.domain_analysis_state.diagnostics
    )


def test_real_v1_m6_input_is_diagnosed_without_recomputation(tmp_path) -> None:
    source_path = tmp_path / "legacy-m6-source.mpp"
    source_path.write_bytes(b"legacy m6 cache source")
    session_path = tmp_path / "legacy-m6.moltrack.json"
    series = _legacy_m6_series(source_path)
    analyze_molecular_frame_range(
        series,
        MolecularFrameRange("All", 0, 0),
        source_view="raw",
        m6_orientation_settings=MolecularM6OrientationAnalysisSettings(),
    )
    save_moltrack_session(session_path, series)
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    legacy_records = payload["molecular_m6_analysis"]["reproducible_cache"]
    assert legacy_records[0]["cache_record_schema_version"] == 2
    assert "sample_coordinates" in legacy_records[0]
    payload["schema_version"] = 1
    payload.pop("domain_analysis")
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.m6_cache_records == ()
    diagnostic = loaded.domain_analysis_state.diagnostics[0]
    assert diagnostic.identifier == (
        "molecular_m6_analysis.reproducible_cache[0]"
    )
    assert "does not contain a completed M6 computation" in diagnostic.reason
    assert loaded.structural_analysis_cache_records == ()


def test_v1_preserves_independent_molecular_order_configuration(tmp_path) -> None:
    session_path, payload = _saved_v2_payload(tmp_path)
    scope = MolecularFrameRangeAnalysisScope(
        analysis_mode="single_range",
        frame_count=2,
        source_view="raw",
        ranges=(MolecularFrameRange("All", 0, 1),),
    )
    order_state = MolecularOrderTypeSessionState(
        analysis_scope=scope,
        classification_settings=MolecularOrderTypeClassificationSettings(),
    )
    payload["schema_version"] = 1
    payload.pop("domain_analysis")
    payload["molecular_order_type_analysis"] = order_state.to_dict()
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.molecular_order_type_analysis_state == order_state


def test_v1_without_position_state_defaults_to_whole_series_and_saves_v2(
    tmp_path,
) -> None:
    session_path, payload = _saved_v2_payload(tmp_path)
    payload["schema_version"] = 1
    payload.pop("domain_analysis")
    payload["position_analysis"] = None
    payload["molecular_m6_analysis"] = {"legacy": "must not activate"}
    payload["texture_domain_analysis"] = {"legacy": "must not activate"}
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert loaded.domain_analysis_state is not None
    assert loaded.domain_analysis_state.draft is not None
    assert loaded.domain_analysis_state.draft.frame_indices == (0, 1)
    assert loaded.domain_analysis_state.classifier_status == "not_run"
    assert loaded.m6_analysis_state is not None
    assert loaded.m6_analysis_state.enabled is False
    assert loaded.structural_analysis_cache_records == ()
    assert loaded.texture_domain_analysis_state is None
    migrated_path = tmp_path / "explicit-save-v2.moltrack.json"
    series = MolTrackImageSeries(
        source_path=Path(loaded.source_path),
        raw_frames=np.zeros((2, 2, 2), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=2, pixels_y=2),
    )
    save_moltrack_session(
        migrated_path,
        series,
        ui_state={"domain_analysis": loaded.domain_analysis_state},
    )
    migrated = json.loads(migrated_path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 2
    assert migrated["position_analysis"] is None
    assert "molecular_m6_analysis" not in migrated
    assert "texture_domain_analysis" not in migrated
