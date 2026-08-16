from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields, replace
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from moltrack.analysis import (
    LatticeDomainCalibrationReferenceDataset,
    MolecularM6OrientationAnalysisSettings,
    MolecularOrientationReferenceDataset,
    build_molecular_sample_coordinates,
)
from moltrack.analysis.domain_analysis import (
    DomainAnalysisFrame,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    M6FrameGeometry,
    M6SourceAnnotation,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from moltrack.persistence import load_moltrack_session
from moltrack.persistence.m6_reference_identity import m6_reference_state_identity
from moltrack.ui.domain_backend_adapters import (
    MolTrackLatticeNetworkAdapter,
    MolTrackOrientationComponentsAdapter,
)
from nanotrack.io import load_stm_sequence
from scripts.check_domain_analysis_cutover_manifest import validate_cutover_manifest
from ttmapp_cutover_ui_support import (
    analyze_in_main_window,
    publish_release_in_main_window,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_REPOSITORY_ROOT = Path(__file__).parents[2]
_REFERENCE_FIXTURE = _FIXTURE_ROOT / "molecular_orientation_reference_ttmapp_v1.json"
_DOMAIN_FIXTURE = _FIXTURE_ROOT / "ttmapp_domain_analysis_v1.json"
_TTMAPP_SOURCE_ROOT = _FIXTURE_ROOT / "ttmapp_domain_analysis_sources"
_RELEASE_REPORT = (
    _REPOSITORY_ROOT / "docs" / "domain_analysis_ttmapp_release_validation.json"
)


@dataclass(frozen=True)
class _TTMAPPGroup:
    group_id: str
    split: str
    source_path: Path
    source_ids: tuple[str, ...]
    series: MolTrackImageSeries
    analysis_series: DomainAnalysisSeries
    acquisition_fingerprint: str
    lineage_fingerprint: str
    reviewed_first_shell_edge: tuple[str, str]


def test_ttmapp_variant_c_cutover_preserves_identity_through_campaign(
    tmp_path,
    monkeypatch,
) -> None:
    reference_payload = json.loads(_REFERENCE_FIXTURE.read_text(encoding="utf-8"))
    assert {"reviewed", "reviewed_by"}.isdisjoint(reference_payload)
    assert {value.name for value in fields(MolecularOrientationReferenceDataset)}.isdisjoint(
        {"reviewed", "reviewed_by"}
    )
    assert "reviewed" not in {
        value.name for value in fields(LatticeDomainCalibrationReferenceDataset)
    }
    with pytest.raises(TypeError, match="backend_id"):
        DomainAnalysisRequest(frame_range=range(1))
    with pytest.raises(ValueError, match="backend_id"):
        DomainAnalysisRequest(frame_range=range(1), backend_id=None)
    assert validate_cutover_manifest(
        _REPOSITORY_ROOT,
        _REPOSITORY_ROOT / "docs" / "domain_analysis_cutover_manifest.json",
    ) >= 13

    groups = _ttmapp_groups()
    assert {group.source_path.parent.name for group in groups} == {"movie2", "movie3"}
    assert all(group.source_path.suffix == ".STP" for group in groups)
    assert all(float(np.ptp(group.series.raw_frames[0])) > 0.0 for group in groups)
    assert all(
        np.count_nonzero(segmentation.mask) > 1
        for group in groups
        for segmentation in group.series.molecular_segmentations.get_segmentations(
            0, source_view="raw"
        )
    )
    settings = _acceptance_settings()
    identities = {
        adapter.backend_identity.backend_id: adapter.backend_identity
        for adapter in _production_adapters(groups[0].analysis_series, settings)
    }
    assert set(identities) == {
        M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        M3_M6_LATTICE_NETWORK_BACKEND_ID,
    }

    qt_app = QApplication.instance() or QApplication([])
    artifacts = {}
    automatic_fingerprints: set[str] = set()
    for group in groups:
        results = {}
        for backend_id in identities:
            artifact = analyze_in_main_window(
                group,
                backend_id,
                settings,
                qt_app,
                tmp_path,
                monkeypatch,
            )
            artifacts[group.split, backend_id] = artifact
            state = artifact.state
            assert load_moltrack_session(
                artifact.session_path
            ).domain_analysis_state == state
            publication = state.published_result
            assert publication is not None
            assert publication.request.backend_id == backend_id
            result = publication.result
            results[backend_id] = result
            automatic_fingerprints.add(_automatic_fingerprint(state))
            assert publication.request.geometry_mode == "segmentation_preferred"
            expected_points = _expected_production_points(group)
            published_points = _published_points(result)
            assert published_points.keys() == expected_points.keys()
            for source_id, point in expected_points.items():
                assert published_points[source_id] == pytest.approx(point)

            manifest = _json(artifact.export_path / "manifest.json")
            assert manifest["export_schema_version"] == 10
            assert manifest["export_mode"] == "reference"
            assert manifest["package_kind"] == "moltrack_correction_aware_analysis"
            assert manifest["readiness"] == {"ready": True, "blockers": []}
            assert manifest["anchors"]["correction_revision"] == 3
            assert manifest["source"]["identity"] == {
                "source_name": group.source_path.name,
                "source_path": str(group.source_path),
            }
            automatic = _json(artifact.export_path / "automatic_snapshot.json")
            assert automatic["request"]["backend_id"] == backend_id
            assert {
                frame["backend_identity"]["backend_id"]
                for frame in automatic["m6_gate"]["frames"]
            } == {backend_id}
            assert not tuple(artifact.export_path.parent.glob("*-legacy-v9*"))

        classic = results[M6_ORIENTATION_COMPONENTS_BACKEND_ID]
        network = results[M3_M6_LATTICE_NETWORK_BACKEND_ID]
        assert classic.m6_gate is not None and network.m6_gate is not None
        assert (
            classic.m6_gate.frames[0].m6_gate_fingerprint
            != network.m6_gate.frames[0].m6_gate_fingerprint
        )

    reference_sessions = {
        group.split: artifacts[
            group.split, M3_M6_LATTICE_NETWORK_BACKEND_ID
        ].session_path
        for group in groups
    }
    reference_fingerprints = {
        _automatic_fingerprint(
            artifacts[group.split, M3_M6_LATTICE_NETWORK_BACKEND_ID].state
        )
        for group in groups
    }
    monkeypatch.setenv(
        "MOLTRACK_M6_VALIDATION_ACCESS_REGISTRY",
        str(tmp_path / "validation-access"),
    )
    root = publish_release_in_main_window(
        groups,
        reference_sessions,
        qt_app,
        tmp_path,
        monkeypatch,
        ancestry="new dataset root",
        run_campaign=True,
    )
    child = publish_release_in_main_window(
        groups,
        reference_sessions,
        qt_app,
        tmp_path,
        monkeypatch,
        ancestry="immutable child",
        parent_packages={
            "m6": root.m6_package,
            "orientation": root.orientation_package,
        },
    )

    root_manifests = {
        "m6": _json(root.m6_package / "manifest.json"),
        "orientation": _json(root.orientation_package / "manifest.json"),
    }
    child_manifests = {
        "m6": _json(child.m6_package / "manifest.json"),
        "orientation": _json(child.orientation_package / "manifest.json"),
    }
    for target in ("m6", "orientation"):
        root_manifest = root_manifests[target]
        child_manifest = child_manifests[target]
        assert root_manifest["schema_version"] == 2
        assert root_manifest["target"] == target
        assert root_manifest["dataset_version"] == 1
        assert root_manifest["parent_version_id"] is None
        assert root_manifest["readiness"] == {"ready": True, "blockers": []}
        assert child_manifest["schema_version"] == 2
        assert child_manifest["target"] == target
        assert child_manifest["dataset_version"] == 2
        assert child_manifest["parent_version_id"] == root_manifest["version_id"]
        assert (
            child_manifest["validation_epoch"]["epoch_id"]
            == root_manifest["validation_epoch"]["epoch_id"]
        )

    measurement_rows = _json_lines(root.m6_package / "measurements.jsonl")
    assert {row["automatic_snapshot_fingerprint"] for row in measurement_rows} == (
        reference_fingerprints
    )
    assert {
        row["measurement_group_id"]: (
            row["acquisition_fingerprint"],
            row["lineage_fingerprint"],
        )
        for row in measurement_rows
    } == {
        "ttmapp-calibration": (
            "ttmapp-34855-acquisition-v1",
            "ttmapp-movie2-lineage-v1",
        ),
        "ttmapp-validation": (
            "ttmapp-34172-acquisition-v1",
            "ttmapp-movie3-lineage-v1",
        ),
    }

    assert root.campaign_report is not None
    campaign = _json(root.campaign_report)
    assert campaign["schema_version"] == "m6-campaign-report-v2"
    assert campaign["status"] == "validated"
    assert campaign["preset_modified"] is False
    assert campaign["dataset_version_id"] == root_manifests["m6"]["version_id"]
    assert {
        value["backend_identity"]["backend_id"]
        for value in campaign["validation_results"]
    } == set(identities)
    assert {
        metric["measurement_group_id"]
        for result in campaign["validation_results"]
        for metric in result["group_metrics"]
    } == {"ttmapp-validation"}
    network_validation = next(
        value
        for value in campaign["validation_results"]
        if value["backend_identity"]["backend_id"]
        == M3_M6_LATTICE_NETWORK_BACKEND_ID
    )
    assert network_validation["metrics"]["boundary_precision"]["status"] == (
        "available"
    )
    assert root.geometry_prompt is not None
    assert "fixed" in root.geometry_prompt and "adaptive" in root.geometry_prompt
    assert "resolution=" in root.geometry_prompt and "reason=" in root.geometry_prompt
    assert all(f"g(r) {backend_id}" in root.geometry_prompt for backend_id in identities)
    preset_library = _json(tmp_path / "operator-home" / ".moltrack" / "m6-presets.json")
    assert preset_library["active_preset_name"] == (
        "TTMAPP adaptive Calibration geometry"
    )
    active = next(
        value
        for value in preset_library["user_presets"]
        if value["name"] == preset_library["active_preset_name"]
    )
    geometry = active["configuration"]["first_shell_geometry"]
    assert geometry["mode"] == "adaptive"
    assert geometry["fixed_fallback"] == {"r_min_nm": 2.4, "r_max_nm": 3.5}
    selection = active["configuration"]["first_shell_geometry_selection"]
    assert selection["dataset_version_id"] == root_manifests["m6"]["version_id"]
    assert selection["geometry_fingerprint"] == campaign["geometry_fingerprint"]

    release = _json(_RELEASE_REPORT)
    assert release["validation_schema_version"] == 3
    assert release["validated_at"] == "2026-08-16"
    assert release["automatic_snapshot_count"] == len(automatic_fingerprints)
    assert release["export"] == {
        "backend_ids": sorted(identities),
        "correction_revision": 3,
        "export_mode": "reference",
        "export_schema_version": 10,
        "package_kind": "moltrack_correction_aware_analysis",
    }
    assert release["reference_packages"] == {
        "m6": {
            "child_dataset_version": 2,
            "parent_link_verified": True,
            "root_dataset_version": 1,
            "schema_version": 2,
        },
        "orientation": {
            "child_dataset_version": 2,
            "parent_link_verified": True,
            "root_dataset_version": 1,
            "schema_version": 2,
        },
    }
    assert release["campaign"] == {
        "backend_ids": sorted(identities),
        "compared_geometry_modes": ["fixed", "adaptive"],
        "geometry_mode": "adaptive",
        "pair_correlation_evidence_for_both_backends": True,
        "schema_version": "m6-campaign-report-v2",
        "status": "validated",
    }


def _acceptance_settings() -> MolecularM6OrientationAnalysisSettings:
    return replace(
        MolecularM6OrientationAnalysisSettings(),
        first_shell_r_min_nm=2.4,
        first_shell_r_max_nm=3.5,
        duplicate_max_distance_nm=0.5,
        geometry_absolute_tolerance_nm=0.1,
        min_neighbors_for_seed=3,
        min_seed_size=3,
        min_domain_size=5,
        q_seed=0.4,
        q_grow=0.2,
        seed_angle_tolerance_deg=15.0,
        grow_angle_tolerance_deg=20.0,
        local_symmetry_trifold_minimum_model_score=0.3,
        local_symmetry_sixfold_minimum_model_score=0.3,
        local_symmetry_mixed_minimum_model_score=0.3,
        local_symmetry_minimum_second_best_margin=0.02,
        local_symmetry_minimum_expected_direction_coverage=0.2,
        lattice_edge_trifold_orientation_tolerance_deg=15.0,
        lattice_edge_sixfold_orientation_tolerance_deg=15.0,
        lattice_edge_conditional_channel_minimum_score=0.3,
        lattice_edge_minimum_classification_confidence=0.3,
        lattice_edge_minimum_orientation_confidence=0.3,
        lattice_seed_min_model_score=0.4,
        lattice_halo_min_model_score=0.2,
    )


def _ttmapp_groups() -> tuple[_TTMAPPGroup, ...]:
    fixture = json.loads(_DOMAIN_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["fixture_schema_version"] == 1
    values = []
    for source in fixture["sources"]:
        split = str(source["split"])
        source_path = _TTMAPP_SOURCE_ROOT / str(source["source_file"])
        loaded = load_stm_sequence(source_path)
        raw = np.asarray(loaded.raw_frames[0], dtype=np.float32)
        pixel_size = loaded.metadata.get_pixel_size_nm()
        assert all(value is not None for value in pixel_size)
        pixel_size = (float(pixel_size[0]), float(pixel_size[1]))
        frozen_detections = source["detections"]
        assert isinstance(frozen_detections, list) and len(frozen_detections) >= 3
        segmentations = MolecularSegmentationSet(frame_count=1)
        detections = MolecularDetectionSet(frame_count=1)
        detection_values = []
        annotations = []
        source_ids = []
        for frozen in frozen_detections:
            bbox = tuple(float(value) for value in frozen["bbox_xyxy"])
            source_id = str(frozen["source_id"])
            detection_id = f"detection-{source_id}"
            detection_values.append(MolecularDetection(
                frame_index=0,
                bbox_xyxy=bbox,
                confidence=float(frozen["confidence"]),
                detection_id=detection_id,
                origin="yolo",
                model_name="yolo11s_v4.0_pro.pt",
                checkpoint_path=f"sha256:{fixture['detector_checkpoint_sha256']}",
                source_view="raw",
            ))
            source_ids.append(source_id)
            full_mask = np.zeros(raw.shape, dtype=bool)
            x1, y1, x2, y2 = (int(round(value)) for value in bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(raw.shape[1], max(x1 + 1, x2))
            y2 = min(raw.shape[0], max(y1 + 1, y2))
            crop = raw[y1:y2, x1:x2]
            full_mask[y1:y2, x1:x2] = crop >= np.quantile(crop, 0.6)
            segmentations.add_segmentation(MolecularSegmentation(
                frame_index=0,
                bbox_xyxy=bbox,
                mask=full_mask,
                prompt_detection_ids=(detection_id,),
                segmentation_id=source_id,
                origin="manual",
                metadata={
                    "source_stp": source_path.name,
                    "mask_method": "bbox-topography-60th-percentile",
                },
            ))
            annotations.append(M6SourceAnnotation(
                source_id=source_id,
                source_view="raw",
                bbox_xyxy=bbox,
            ))
        detections.set_detections(
            0,
            detection_values,
            source_view="raw",
            frame_shape=raw.shape,
        )
        series = MolTrackImageSeries(
            source_path=str(source_path),
            raw_frames=raw[np.newaxis, ...],
            metadata=loaded.metadata,
            molecular_detections=detections,
            molecular_segmentations=segmentations,
            source_frame_indices=(0,),
        )
        physical_frame_id = f"{source_path.parent.name}:{source_path.name}:0"
        analysis_series = DomainAnalysisSeries((DomainAnalysisFrame(
            frame_index=0,
            source_view="raw",
            geometry=M6FrameGeometry(
                physical_frame_id=physical_frame_id,
                raw_shape=raw.shape,
                expanded_shape=raw.shape,
                frame_origin_xy=(0.0, 0.0),
                canvas_offset_xy=(0.0, 0.0),
                pixel_size_nm=pixel_size,
                scan_angle_deg=0.0,
                registration_fingerprint=f"ttmapp-registration-{source_path.stem}-v1",
            ),
            annotations=tuple(annotations),
            raw_frame=raw,
        ),))
        values.append(_TTMAPPGroup(
            group_id=f"ttmapp-{split}",
            split=split,
            source_path=source_path,
            source_ids=tuple(source_ids),
            series=series,
            analysis_series=analysis_series,
            acquisition_fingerprint=str(source["acquisition_fingerprint"]),
            lineage_fingerprint=str(source["lineage_fingerprint"]),
            reviewed_first_shell_edge=(
                str(source["reviewed_first_shell_edge"]["source_id_a"]),
                str(source["reviewed_first_shell_edge"]["source_id_b"]),
            ),
        ))
    return tuple(values)


def _production_adapters(analysis_series, settings):
    return (
        MolTrackOrientationComponentsAdapter(analysis_series, settings=settings),
        MolTrackLatticeNetworkAdapter(analysis_series, settings=settings),
    )


def _expected_production_points(
    group: _TTMAPPGroup,
) -> dict[str, tuple[float, float]]:
    centroids = build_molecular_centroids(
        group.series,
        frame_index=0,
        source_view="raw",
        use_segmentation_centroids=True,
    )
    coordinates = build_molecular_sample_coordinates(
        group.series,
        centroids,
        frame_index=0,
        source_view="raw",
    )
    return dict(zip(coordinates.point_source_ids, coordinates.points_xy_nm))


def _published_points(result) -> dict[str, tuple[float, float]]:
    gate = result.m6_gate
    assert gate is not None
    return {
        molecule.source_id: molecule.point_xy_nm
        for frame in gate.frames
        for molecule in (
            tuple(
                member
                for component in (*frame.full_domains, *frame.small_ordered_islands)
                for member in component.members
            )
            + frame.outside_members
        )
    }


def _automatic_fingerprint(state) -> str:
    publication = state.published_result
    correction_set = state.domain_corrections.correction_set
    projection = state.domain_corrections.effective_projection
    assert publication is not None and correction_set is not None and projection is not None
    return m6_reference_state_identity(
        publication,
        correction_set,
        projection,
    ).automatic_snapshot_fingerprint


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_lines(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
