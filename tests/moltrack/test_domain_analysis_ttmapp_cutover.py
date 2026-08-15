from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QWidget

from moltrack.analysis import (
    LatticeDomainCalibrationReferenceDataset,
    MolecularM6OrientationAnalysisSettings,
    MolecularOrientationReferenceDataset,
)
from moltrack.analysis.domain_analysis import (
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisSessionState,
    FirstShellGeometryPolicy,
    M6FrameGeometry,
    M6Preset,
    M6PresetLibrary,
    M6PresetWorkspace,
    M6RunConfiguration,
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
)
from moltrack.persistence import (
    load_moltrack_session,
)
from moltrack.persistence.m6_reference_identity import m6_reference_state_identity
from moltrack.ui.domain_analysis_release_workflow import (
    DomainAnalysisReleaseWorkflow,
)
from moltrack.ui.domain_backend_adapters import (
    MolTrackLatticeNetworkAdapter,
    MolTrackOrientationComponentsAdapter,
)
from nanotrack.io import load_stm_sequence
from scripts.check_domain_analysis_cutover_manifest import validate_cutover_manifest
from ttmapp_cutover_ui_support import (
    correct_and_review as _correct_and_review,
    run_release_actions_in_ui as _run_release_actions_in_ui,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_REPOSITORY_ROOT = Path(__file__).parents[2]
_REFERENCE_FIXTURE = _FIXTURE_ROOT / "molecular_orientation_reference_ttmapp_v1.json"
_DOMAIN_FIXTURE = _FIXTURE_ROOT / "ttmapp_domain_analysis_v1.json"
_TTMAPP_SOURCE_ROOT = _FIXTURE_ROOT / "ttmapp_domain_analysis_sources"
_NOW = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
_RELEASE_REPORT = _REPOSITORY_ROOT / "docs" / "domain_analysis_ttmapp_release_validation.json"


@dataclass(frozen=True)
class _TTMAPPGroup:
    group_id: str
    split: str
    physical_frame_id: str
    source_path: Path
    source_ids: tuple[str, ...]
    series: MolTrackImageSeries
    analysis_series: DomainAnalysisSeries
    points_by_source_id: tuple[tuple[str, tuple[float, float]], ...]
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
    settings = replace(
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
    probe_adapters = _production_adapters(groups[0].analysis_series, settings)
    identities = {
        adapter.backend_identity.backend_id: adapter.backend_identity
        for adapter in probe_adapters
    }
    configurations = {
        backend_id: M6RunConfiguration(
            backend_identity=identity,
            settings=settings,
            first_shell_geometry=FirstShellGeometryPolicy.fixed(
                r_min_nm=settings.first_shell_r_min_nm,
                r_max_nm=settings.first_shell_r_max_nm,
            ),
        )
        for backend_id, identity in identities.items()
    }
    library = _operator_preset_library(
        tmp_path,
        configurations,
        groups[0].analysis_series,
    )
    frozen_configuration = library.active_run_configuration()
    assert frozen_configuration.settings.first_shell_r_max_nm == 3.5
    assert frozen_configuration.backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
    assert library.preset(
        f"Built-in {M6_ORIENTATION_COMPONENTS_BACKEND_ID}"
    ).configuration.configuration_fingerprint != (
        frozen_configuration.configuration_fingerprint
    )

    qt_app = QApplication.instance() or QApplication([])
    states: dict[tuple[str, str], DomainAnalysisSessionState] = {}
    automatic_fingerprints: set[str] = set()
    for group in groups:
        adapters = _production_adapters(group.analysis_series, settings)
        assert {
            value.backend_identity.backend_id: value.backend_identity
            for value in adapters
        } == identities
        module = DomainAnalysisModule({
            value.backend_identity.backend_id: value for value in adapters
        }, {})
        results = {}
        for backend_id, configuration in configurations.items():
            request = DomainAnalysisRequest(
                frame_range=range(1),
                backend_id=backend_id,
                m6_configuration=configuration,
            )
            state, result = _correct_and_review(
                group,
                request,
                module,
                library,
                qt_app,
                tmp_path,
            )
            results[backend_id] = request, result
            states[group.split, backend_id] = state
            automatic_fingerprints.add(_automatic_fingerprint(state))
            published_points = _published_points(result)
            expected_points = dict(group.points_by_source_id)
            assert published_points.keys() == expected_points.keys()
            for source_id, point in expected_points.items():
                assert published_points[source_id] == pytest.approx(point)
        classic_request, classic_result = results[M6_ORIENTATION_COMPONENTS_BACKEND_ID]
        network_request, network_result = results[M3_M6_LATTICE_NETWORK_BACKEND_ID]
        assert classic_result.m6_gate is not None
        assert network_result.m6_gate is not None
        assert classic_request.backend_id != network_request.backend_id
        assert (
            classic_result.m6_gate.frames[0].m6_gate_fingerprint
            != network_result.m6_gate.frames[0].m6_gate_fingerprint
        )

    for (split, backend_id), state in states.items():
        group = next(value for value in groups if value.split == split)
        session_path = tmp_path / f"ttmapp-{split}-{backend_id}.moltrack.json"
        restored = load_moltrack_session(session_path).domain_analysis_state
        assert restored == state
        export_path = tmp_path / f"ttmapp-v10-{split}-{backend_id}"
        export_manifest = _json(export_path / "manifest.json")
        assert export_manifest["export_schema_version"] == 10
        assert export_manifest["source"]["identity"] == {
            "source_file_name": group.source_path.name,
            "acquisition_fingerprint": group.acquisition_fingerprint,
            "lineage_fingerprint": group.lineage_fingerprint,
        }
        assert export_manifest["anchors"]["automatic_snapshot_fingerprint"] in (
            automatic_fingerprints
        )
        automatic_snapshot = _json(export_path / "automatic_snapshot.json")
        assert automatic_snapshot["request"]["backend_id"] == backend_id
        assert {
            frame["backend_identity"]["backend_id"]
            for frame in automatic_snapshot["m6_gate"]["frames"]
        } == {backend_id}

    reference_states = {
        group.split: states[group.split, M3_M6_LATTICE_NETWORK_BACKEND_ID]
        for group in groups
    }
    reference_automatic_fingerprints = {
        _automatic_fingerprint(value) for value in reference_states.values()
    }

    monkeypatch.setenv(
        "MOLTRACK_M6_VALIDATION_ACCESS_REGISTRY",
        str(tmp_path / "validation-access"),
    )
    _configure_release_prompts(monkeypatch, groups, tmp_path)
    workspaces = iter((*groups, *groups, groups[0]))
    release_owner = QWidget()
    release_workflow = DomainAnalysisReleaseWorkflow(release_owner)

    def current_workspace():
        group = next(workspaces)
        return (
            reference_states[group.split],
            group.series,
            group.analysis_series,
            library,
        )

    workflow_actions = release_workflow.actions(
        current_workspace,
        save_session=lambda: None,
        open_session=lambda: None,
    )
    try:
        _run_release_actions_in_ui(
            next(group for group in groups if group.split == "calibration"),
            reference_states["calibration"],
            library,
            workflow_actions,
            qt_app,
        )
    finally:
        release_owner.close()
        release_owner.deleteLater()
        qt_app.processEvents()
    m6_package = release_workflow.m6_publication
    orientation_package = release_workflow.orientation_publication
    release_campaign = release_workflow.last_campaign
    geometry = release_campaign.geometry
    geometry_comparison = release_campaign.geometry_comparison
    campaign_configuration = release_campaign.configuration
    campaign = release_campaign.campaign
    shortlist = release_campaign.shortlist
    report = release_campaign.publication.report
    observed = dict(release_campaign.evaluation_trace)
    assert workflow_actions.publish_m6_reference is not None
    with pytest.raises(RuntimeError, match="published M6 reference is immutable"):
        workflow_actions.publish_m6_reference()
    assert release_workflow.m6_publication == m6_package
    assert _json(m6_package.package_path / "manifest.json")["target"] == "m6"
    assert _json(orientation_package.package_path / "manifest.json")["target"] == (
        "orientation"
    )
    measurement_rows = _json_lines(m6_package.package_path / "measurements.jsonl")
    assert {row["automatic_snapshot_fingerprint"] for row in measurement_rows} == (
        reference_automatic_fingerprints
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

    assert geometry.policy.mode == "adaptive"
    assert geometry.policy.fixed_r_max_nm == 3.5
    assert {
        value.policy.mode for value in geometry_comparison.report.policy_results
    } == {"fixed", "adaptive"}
    assert geometry_comparison.evidence_backend_ids == tuple(sorted(identities))
    assert all(
        evidence.pair_correlation is not None
        and evidence.unavailable_reason is None
        for backend in geometry_comparison.backend_evidence
        for evidence in backend.pair_correlations
    )
    assert all(
        metric.status == "available"
        and metric.precision is not None
        and metric.recall is not None
        and metric.f1_score is not None
        for result in geometry_comparison.report.policy_results
        for metric in result.metrics
    )
    adaptive_result = geometry_comparison.report.result("adaptive")
    assert all(
        decision.resolution == "adaptive_g_r"
        or (
            decision.resolution == "fixed_fallback"
            and decision.fallback_reason
        )
        for decision in adaptive_result.decisions
    )
    operator_summary = geometry_comparison.operator_summary()
    assert "resolution=" in operator_summary
    assert "reason=" in operator_summary
    assert all(
        decision.evidence_fingerprint in operator_summary
        for decision in adaptive_result.decisions
    )
    assert all(
        f"g(r) {backend_id}" in operator_summary
        for backend_id in identities
    )
    assert geometry.dataset_version_id == m6_package.version_id
    assert geometry.geometry_fingerprint == campaign.geometry_fingerprint
    assert all(metric.reference_edge_count == 1 for metric in geometry.policy_result.metrics)
    assert all(metric.true_positive_edge_count == 1 for metric in geometry.policy_result.metrics)
    assert all(metric.f1_score is not None and metric.f1_score > 0.0 for metric in geometry.policy_result.metrics)
    assert campaign.dataset_version_id == m6_package.version_id
    assert campaign.dataset_version_fingerprint == m6_package.version_fingerprint
    assert all(
        value.selected_candidate is not None
        for value in campaign.backend_results_for(geometry)
    ), [
        (
            value.backend_identity.backend_id,
            [
                (
                    candidate.eligible,
                    candidate.eligibility_failures,
                    candidate.metrics.macro_membership_precision,
                    candidate.metrics.macro_membership_recall,
                    candidate.local_stability_ari,
                )
                for candidate in value.ranked_candidates
            ],
        )
        for value in campaign.backend_results_for(geometry)
    ]
    assert report.schema_version == "m6-campaign-report-v2"
    assert {value.backend_identity.backend_id for value in report.validation_results} == (
        set(identities)
    )
    network_validation = next(
        value
        for value in report.validation_results
        if value.backend_identity.backend_id == M3_M6_LATTICE_NETWORK_BACKEND_ID
    )
    assert network_validation.metrics.boundary_precision.status == "available"
    assert {
        value.measurement_group_id
        for result in report.validation_results
        for value in result.group_metrics
    } == {next(value.group_id for value in groups if value.split == "validation")}
    assert all(
        {version_id for version_id, _group_id in values} == {m6_package.version_id}
        for values in observed.values()
    )
    assert {
        group_id
        for _version_id, group_id in observed[M6_ORIENTATION_COMPONENTS_BACKEND_ID]
    } == {
        group_id
        for _version_id, group_id in observed[M3_M6_LATTICE_NETWORK_BACKEND_ID]
    }
    assert report.preset_modified is False
    active_configuration = library.active_run_configuration()
    assert active_configuration == campaign_configuration
    assert active_configuration != frozen_configuration
    assert campaign_configuration != frozen_configuration
    assert campaign_configuration.first_shell_geometry == geometry.policy
    assert campaign_configuration.first_shell_geometry.mode == "adaptive"
    selection_record = campaign_configuration.first_shell_geometry_selection
    assert selection_record is not None
    assert selection_record.dataset_version_id == m6_package.version_id
    assert selection_record.geometry_fingerprint == geometry.geometry_fingerprint
    assert selection_record.policy_fingerprint == geometry.policy.policy_fingerprint
    assert selection_record.evidence_fingerprints == tuple(
        (
            decision.measurement_group_id,
            decision.symmetry_class,
            decision.evidence_fingerprint,
        )
        for decision in geometry.policy_result.decisions
    )
    release = _json(_RELEASE_REPORT)
    assert release["validation_schema_version"] == 2
    assert release["automatic_snapshot_fingerprints"] == sorted(
        automatic_fingerprints
    )
    assert release["export"] == {
        "backend_ids": sorted(identities),
        "export_schema_version": 10,
        "correction_revision": 3,
    }
    assert release["reference_packages"] == {
        "m6": {
            "version_id": m6_package.version_id,
            "version_fingerprint": m6_package.version_fingerprint,
        },
        "orientation": {
            "version_id": orientation_package.version_id,
            "version_fingerprint": orientation_package.version_fingerprint,
        },
    }
    assert release["campaign"] == {
        "backend_ids": sorted(identities),
        "dataset_version_id": report.dataset_version_id,
        "dataset_version_fingerprint": report.dataset_version_fingerprint,
        "geometry_fingerprint": report.geometry_fingerprint,
        "recommended_backend_id": report.recommended_backend_id,
        "results": [
            _campaign_result_summary(result, shortlist)
            for result in report.validation_results
        ],
        "schema_version": report.schema_version,
        "status": report.status,
        "validation_epoch_id": report.validation_epoch_id,
    }


def _configure_release_prompts(monkeypatch, groups, tmp_path: Path) -> None:
    split_choices = iter(value.split for value in (*groups, *groups))
    group_ids = iter(value.group_id for value in (*groups, *groups))
    objective_values = iter((0.9, 0.8, 0.2, 0.2))
    group_by_id = {value.group_id: value for value in groups}
    active_group = [None]

    def get_item(_owner, title, label, *_args, **_kwargs):
        if label == "Whole measurement group split":
            return next(split_choices), True
        if label.startswith("Select first-shell geometry policy"):
            return "adaptive", True
        group = next(value for key, value in group_by_id.items() if key in title)
        symmetry = "trifold" if group.split == "calibration" else "sixfold"
        return symmetry, True

    def get_text(_owner, title, label, *_args, **_kwargs):
        if label == "Stable measurement_group_id":
            group_id = next(group_ids)
            active_group[0] = group_by_id[group_id]
            return group_id, True
        if label == "Stable acquisition fingerprint":
            return active_group[0].acquisition_fingerprint, True
        if label == "Stable sample/condition lineage fingerprint":
            return active_group[0].lineage_fingerprint, True
        if label == "Active preset name":
            return "TTMAPP adaptive Calibration geometry", True
        dataset_id = (
            "ttmapp-m6-cutover"
            if "m6" in title.lower()
            else "ttmapp-orientation-cutover"
        )
        return dataset_id, True

    def get_edges(_owner, title, _label, *_args, **_kwargs):
        group = next(value for key, value in group_by_id.items() if key in title)
        left, right = _first_shell_pair(group)
        return f"{left},{right}", True

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(get_item))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(get_text))
    monkeypatch.setattr(QInputDialog, "getMultiLineText", staticmethod(get_edges))
    monkeypatch.setattr(
        QInputDialog,
        "getDouble",
        staticmethod(
            lambda _owner, _title, _label, *_args, **_kwargs: (
                next(objective_values),
                True,
            )
        ),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        staticmethod(
            lambda _owner, _title, *_args, **_kwargs: str(tmp_path)
        ),
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
        points_xy_nm = []
        source_ids = []
        for frozen in frozen_detections:
            bbox = tuple(float(value) for value in frozen["bbox_xyxy"])
            source_id = str(frozen["source_id"])
            detection_id = f"detection-{source_id}"
            detection_values.append(MolecularDetection(
                frame_index=0, bbox_xyxy=bbox,
                confidence=float(frozen["confidence"]), detection_id=detection_id,
                origin="yolo", model_name="yolo11s_v4.0_pro.pt",
                checkpoint_path=f"sha256:{fixture['detector_checkpoint_sha256']}",
                source_view="raw",
            ))
            center_x = (bbox[0] + bbox[2]) / 2.0
            center_y = (bbox[1] + bbox[3]) / 2.0
            points_xy_nm.append((center_x * pixel_size[0], (raw.shape[0] - center_y) * pixel_size[1]))
            source_ids.append(source_id)
            full_mask = np.zeros(raw.shape, dtype=bool)
            x1, y1, x2, y2 = (int(round(value)) for value in bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(raw.shape[1], max(x1 + 1, x2)), min(raw.shape[0], max(y1 + 1, y2))
            crop = raw[y1:y2, x1:x2]
            local_mask = crop >= np.quantile(crop, 0.6)
            full_mask[y1:y2, x1:x2] = local_mask
            segmentation = MolecularSegmentation(
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
            )
            segmentations.add_segmentation(segmentation)
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
            physical_frame_id=physical_frame_id,
            source_path=source_path,
            source_ids=source_ids,
            series=series,
            analysis_series=analysis_series,
            points_by_source_id=tuple(zip(source_ids, points_xy_nm)),
            acquisition_fingerprint=str(source["acquisition_fingerprint"]),
            lineage_fingerprint=str(source["lineage_fingerprint"]),
            reviewed_first_shell_edge=(
                str(source["reviewed_first_shell_edge"]["source_id_a"]),
                str(source["reviewed_first_shell_edge"]["source_id_b"]),
            ),
        ))
    return tuple(values)


def _first_shell_pair(group: _TTMAPPGroup) -> tuple[str, str]:
    points = dict(group.points_by_source_id)
    left, right = group.reviewed_first_shell_edge
    distance = float(np.linalg.norm(np.subtract(points[left], points[right])))
    assert distance == pytest.approx(
        next(
            float(source["reviewed_first_shell_edge"]["distance_nm"])
            for source in json.loads(_DOMAIN_FIXTURE.read_text(encoding="utf-8"))["sources"]
            if source["split"] == group.split
        )
    )
    return left, right


def _operator_preset_library(
    tmp_path,
    configurations,
    analysis_series,
) -> M6PresetLibrary:
    default_settings = MolecularM6OrientationAnalysisSettings()
    built_ins = tuple(
        M6Preset(
            name=f"Built-in {adapter.backend_identity.backend_id}",
            configuration=M6RunConfiguration(
                backend_identity=adapter.backend_identity,
                settings=default_settings,
                first_shell_geometry=FirstShellGeometryPolicy.fixed(
                    r_min_nm=default_settings.first_shell_r_min_nm,
                    r_max_nm=default_settings.first_shell_r_max_nm,
                ),
            ),
            created_at=_NOW,
            updated_at=_NOW,
            built_in=True,
        )
        for adapter in _production_adapters(analysis_series, default_settings)
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=built_ins,
        clock=lambda: _NOW,
    )
    for backend_id, configuration in configurations.items():
        name = f"TTMAPP explicit cutover preset [{backend_id}]"
        workspace = M6PresetWorkspace(library)
        workspace.update(
            name=name,
            description="Operator-frozen campaign settings",
            configuration=configuration,
        )
        workspace.save_as(name)
    library.set_active(
        "TTMAPP explicit cutover preset "
        f"[{M6_ORIENTATION_COMPONENTS_BACKEND_ID}]"
    )
    return library


def _production_adapters(analysis_series, settings):
    return (
        MolTrackOrientationComponentsAdapter(
            analysis_series,
            settings=settings,
        ),
        MolTrackLatticeNetworkAdapter(
            analysis_series,
            settings=settings,
        ),
    )


def _campaign_result_summary(result, shortlist) -> dict[str, object]:
    calibration = next(
        entry.candidate
        for entry in shortlist.entries
        if entry.backend_identity.backend_id == result.backend_identity.backend_id
    )
    return {
        "backend_id": result.backend_identity.backend_id,
        "calibration_group_ids": [
            value.measurement_group_id for value in calibration.group_metrics
        ],
        "calibration_macro_ari": calibration.metrics.macro_adjusted_rand_index,
        "calibration_objective_loss": calibration.objective_loss,
        "passed_validation_constraints": result.passed_constraints,
        "validation_group_ids": [
            value.measurement_group_id for value in result.group_metrics
        ],
        "validation_macro_ari": result.metrics.macro_adjusted_rand_index,
        "validation_objective_loss": result.objective_loss,
    }


def _published_points(result) -> dict[str, tuple[float, float]]:
    gate = result.m6_gate
    assert gate is not None
    return {
        molecule.source_id: molecule.point_xy_nm
        for frame in gate.frames
        for molecule in (
            tuple(
                member
                for component in (
                    *frame.full_domains,
                    *frame.small_ordered_islands,
                )
                for member in component.members
            )
            + frame.outside_members
        )
    }


def _automatic_fingerprint(state: DomainAnalysisSessionState) -> str:
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
