from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest

from moltrack.analysis.domain_analysis import (
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6PublishedComponent,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.domain_analysis.models import M6ComponentType
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from nanotrack.core import STMSequenceMetadata


def _component(
    frame_index: int,
    *,
    component_type: M6ComponentType,
    source_id: str,
    pixel_x: int,
) -> M6PublishedComponent:
    point = (float(pixel_x), float(frame_index))
    return M6PublishedComponent(
        lattice_domain_id=f"{component_type}-{frame_index}",
        component_type=component_type,
        source_ids=(source_id,),
        core_source_ids=(source_id,),
        halo_source_ids=(),
        points_xy_nm=(point,),
        footprint_pixels_xy=((pixel_x, 0),),
        footprint_area_nm2=1.0,
        centroid_xy_nm=point,
        bounds_xyxy_nm=(*point, *point),
    )


def _frame_gate(frame_index: int) -> M6FrameGate:
    full_source_id = f"molecule-a-{frame_index}"
    island_source_id = f"molecule-b-{frame_index}"
    outside_source_id = f"molecule-c-{frame_index}"
    return M6FrameGate(
        frame_index=frame_index,
        physical_frame_id=f"physical-frame-{frame_index}",
        coordinate_frame="series_physical_nm",
        coordinate_transform_fingerprint=f"transform-{frame_index}",
        presentation_provenance=M6PresentationProvenance(
            raw_shape=(1, 3),
            expanded_shape=(2, 4),
            source_view="expanded_aligned",
            frame_origin_xy=(float(frame_index), 0.5),
            canvas_offset_xy=(2.0, 3.0),
            registration_fingerprint=f"registration-{frame_index}",
        ),
        source_geometry_fingerprint=f"geometry-{frame_index}",
        m6_settings_fingerprint="m6-settings-v1",
        m6_algorithm_version="m6-algorithm-v1",
        pixel_area_nm2=1.0,
        full_domains=(_component(
            frame_index,
            component_type="full_domain",
            source_id=full_source_id,
            pixel_x=0,
        ),),
        small_ordered_islands=(_component(
            frame_index,
            component_type="small_ordered_island",
            source_id=island_source_id,
            pixel_x=1,
        ),),
        outside_source_ids=(outside_source_id,),
        outside_points_xy_nm=((2.0, float(frame_index)),),
        outside_pixels_xy=((2, 0),),
        outside_area_nm2=1.0,
        analyzed_source_ids=(
            full_source_id,
            island_source_id,
            outside_source_id,
        ),
        analyzed_pixels_xy=((0, 0), (1, 0), (2, 0)),
        analyzed_area_nm2=3.0,
    )


def test_m6_only_published_result_round_trips_through_public_session_seams(
    tmp_path,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"domain analysis source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((2, 1, 3), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=3, pixels_y=1),
    )
    request = DomainAnalysisRequest(frame_range=range(2))
    publication = DomainAnalysisPublication(
        request=request,
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=M6Gate(frames=(_frame_gate(0), _frame_gate(1))),
            classifier_status="not_requested",
        ),
    )
    state = DomainAnalysisSessionState(published_result=publication)

    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": state},
    )
    loaded = load_moltrack_session(session_path)
    payload = json.loads(session_path.read_text(encoding="utf-8"))

    assert loaded.domain_analysis_state == state
    assert payload["schema_version"] == 2
    assert payload["domain_analysis"]["schema_version"] == 1
    assert payload["domain_analysis"]["classifier_status"] == "not_requested"
    assert payload["domain_analysis"]["cache"] == {
        "schema_version": 1,
        "m6_frames": [],
        "classifier_frames": [],
    }
    assert "molecular_m6_analysis" not in payload
    assert "texture_domain_analysis" not in payload
    assert "raw_frame" not in session_path.read_text(encoding="utf-8")


def test_load_rejects_duplicate_physical_frame_identity_before_activation(
    tmp_path,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"domain analysis source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((2, 1, 3), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=3, pixels_y=1),
    )
    request = DomainAnalysisRequest(frame_range=range(2))
    state = DomainAnalysisSessionState(published_result=DomainAnalysisPublication(
        request=request,
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=M6Gate(frames=(_frame_gate(0), _frame_gate(1))),
            classifier_status="not_requested",
        ),
    ))
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": state},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    frames = payload["domain_analysis"]["published_result"]["m6_gate"]["frames"]
    frames[1]["physical_frame_id"] = frames[0]["physical_frame_id"]
    duplicate_identity_frame = replace(
        _frame_gate(1),
        physical_frame_id=frames[0]["physical_frame_id"],
    )
    frames[1]["m6_gate_fingerprint"] = (
        duplicate_identity_frame.m6_gate_fingerprint
    )
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="physical_frame_id values must be unique"):
        load_moltrack_session(session_path)


def test_load_rejects_invalid_core_halo_membership_before_activation(
    tmp_path,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"domain analysis source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 3), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=3, pixels_y=1),
    )
    state = DomainAnalysisSessionState(published_result=DomainAnalysisPublication(
        request=DomainAnalysisRequest(frame_range=range(1)),
        result=DomainAnalysisResult(
            run_status="completed",
            m6_gate=M6Gate(frames=(_frame_gate(0),)),
            classifier_status="not_requested",
        ),
    ))
    save_moltrack_session(
        session_path,
        series,
        ui_state={"domain_analysis": state},
    )
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    frame = payload["domain_analysis"]["published_result"]["m6_gate"][
        "frames"
    ][0]
    component = frame["full_domains"][0]
    component["halo_source_ids"] = list(component["core_source_ids"])
    fingerprint_payload = dict(frame)
    fingerprint_payload.pop("presentation_provenance")
    fingerprint_payload.pop("m6_gate_fingerprint")
    fingerprint_payload["schema_version"] = "domain-analysis-m6-gate-v1"
    frame["m6_gate_fingerprint"] = canonical_sha256(fingerprint_payload)
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Core and halo memberships"):
        load_moltrack_session(session_path)


@pytest.mark.parametrize("invalid_schema_version", [2.5, "2", True])
def test_load_rejects_non_integer_top_level_schema_version(
    tmp_path,
    invalid_schema_version,
) -> None:
    source_path = tmp_path / "series.mpp"
    source_path.write_bytes(b"domain analysis source")
    session_path = tmp_path / "state.moltrack.json"
    series = MolTrackImageSeries(
        source_path=source_path,
        raw_frames=np.zeros((1, 1, 3), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=3, pixels_y=1),
    )
    save_moltrack_session(session_path, series)
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["schema_version"] = invalid_schema_version
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version must be an integer"):
        load_moltrack_session(session_path)
