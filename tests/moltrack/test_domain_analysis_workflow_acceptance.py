from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABC_ORIENTATION_CLASSIFIER_ID,
    ClassifierConfiguration,
    ClassifierIdentity,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    DomainAnalysisRequest as _DomainAnalysisRequest,
    DomainAnalysisSessionState,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
    M6OrientationComponentsEvidence,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata
from moltrack.ui import MolTrackMainWindow
from domain_analysis_test_support import as_legacy_session_v2

from moltrack.ui import domain_analysis_runtime as runtime
from moltrack.ui.domain_analysis_composition import (
    DomainAnalysisMainWindowComposition,
)

DomainAnalysisRequest = partial(
    _DomainAnalysisRequest, backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID
)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@dataclass(frozen=True)
class _MoleculeScenario:
    source_id: str
    bbox_xyxy: tuple[float, float, float, float]
    mask_pixels_xy: tuple[tuple[int, int], ...] = ()
    prompt_detection_id: str | None = None


_MOLECULES = (
    _MoleculeScenario("m-a", (0, 0, 2, 1), ((0, 0), (1, 0)), "det-a"),
    _MoleculeScenario("m-b", (0, 1, 2, 2), ((0, 1), (1, 1)), "det-b"),
    _MoleculeScenario("m-c", (2, 0, 3, 1)),
    _MoleculeScenario("m-d", (3, 0, 4, 3)),
)


@dataclass(frozen=True)
class _BuiltComposition:
    composition: DomainAnalysisMainWindowComposition
    session_series: MolTrackImageSeries


@dataclass(frozen=True)
class _RejectedSessionCase:
    path: Path
    kind: str
    component: str
    reason: str
    original_bytes: bytes


def _stub_m6_analysis(
    adapter,
    frame: M6CanonicalFrame,
    *,
    frame_index: int,
    geometry_mode: str,
) -> M6FrameComputation:
    del geometry_mode
    assert tuple(value.source_id for value in frame.molecules) == tuple(
        value.source_id for value in _MOLECULES
    )
    return M6FrameComputation(
        frame_index=frame_index,
        molecules=frame.molecules,
        analyzed_pixels_xy=frame.analyzed_pixels_xy,
        pixel_area_nm2=frame.pixel_area_nm2,
        full_domains=(M6ComponentMembership(
            lattice_domain_id="domain-full",
            source_ids=("m-a", "m-b"),
            core_source_ids=("m-a",),
            halo_source_ids=("m-b",),
        ),),
        small_ordered_islands=(M6ComponentMembership(
            lattice_domain_id="domain-island",
            source_ids=("m-c",),
            core_source_ids=("m-c",),
        ),),
        coordinate_frame=frame.coordinate_frame,
        coordinate_transform_fingerprint=frame.coordinate_transform_fingerprint,
        backend_identity=adapter.backend_identity,
        native_evidence=M6OrientationComponentsEvidence(
            assignment_status=tuple(
                (value.source_id, "assigned") for value in frame.molecules
            ),
            q6=tuple((value.source_id, None) for value in frame.molecules),
        ),
    )


def _stub_abc_classification(
    _classifier,
    raw_frame,
    *,
    frame_index: int,
    physical_frame_id: str,
    lattice_domain_id: str,
    molecules: tuple[ClassifierMoleculeInput, ...],
) -> tuple[ClassifierMoleculePrediction, ...]:
    del raw_frame, frame_index, physical_frame_id, lattice_domain_id
    predictions = []
    for molecule in molecules:
        label: Literal["A", "B"] = "A" if molecule.source_id == "m-a" else "B"
        predictions.append(ClassifierMoleculePrediction(
            source_id=molecule.source_id,
            orientation_label=label,
            evidence_strength=0.8,
            component_id=f"component-{label}",
        ))
    return tuple(predictions)


def _annotated_series(source_path: Path) -> MolTrackImageSeries:
    detections = MolecularDetectionSet(frame_count=1)
    detections.set_detections(
        0,
        [
            MolecularDetection(
                0,
                value.bbox_xyxy,
                0.9,
                detection_id=value.prompt_detection_id or value.source_id,
            )
            for value in _MOLECULES
        ],
        source_view="raw",
        frame_shape=(4, 4),
    )
    segmentations = MolecularSegmentationSet(frame_count=1)
    for value in _MOLECULES:
        if not value.mask_pixels_xy:
            continue
        mask: np.ndarray = np.zeros((4, 4), dtype=bool)
        for x, y in value.mask_pixels_xy:
            mask[y, x] = True
        segmentations.add_segmentation(MolecularSegmentation(
            frame_index=0,
            bbox_xyxy=value.bbox_xyxy,
            mask=mask,
            original_mask=mask,
            prompt_detection_ids=(value.prompt_detection_id,),
            segmentation_id=value.source_id,
        ))
    return MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros((1, 4, 4), dtype=np.uint16),
        metadata=STMSequenceMetadata(
            pixels_x=4,
            pixels_y=4,
            size_nm_x=4.0,
            size_nm_y=4.0,
        ),
        molecular_detections=detections,
        molecular_segmentations=segmentations,
    )


def _wait_until(
    qt_app,
    predicate: Callable[[], bool],
    failure_message: Callable[[], str] = lambda: "condition was not satisfied",
) -> None:
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert predicate(), failure_message()


def _select_first_domain(dialog) -> None:
    dialog.current_frame_results_panel.domain_table.setCurrentCell(0, 0)


def _review_target_in_ui(sheet, target, decisions, qt_app) -> None:
    sheet.target_combo.setCurrentIndex(sheet.target_combo.findData(target))
    qt_app.processEvents()
    for row in range(sheet.review_table.rowCount()):
        source_id = sheet.review_table.item(row, 0).text()
        decision, reason = decisions[source_id]
        sheet.review_table.selectRow(row)
        sheet.decision_combo.setCurrentIndex(
            sheet.decision_combo.findData(decision)
        )
        sheet.reason_edit.setText(reason or "")
        sheet.record_button.click()
        qt_app.processEvents()
    assert sheet.sign_off_button.isEnabled()
    sheet.sign_off_button.click()
    qt_app.processEvents()


def test_one_public_domain_analysis_workflow_survives_round_trip_and_rejects_bad_input(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "workflow.mpp"
    source_path.write_bytes(b"domain analysis acceptance source")
    initial_series = _annotated_series(source_path)
    initial_session_path = tmp_path / "initial.moltrack.json"
    save_moltrack_session(initial_session_path, initial_series)

    export_destination = tmp_path / "workflow-domain-analysis"
    built_compositions: list[_BuiltComposition] = []
    monkeypatch.setattr(runtime._MolTrackM6Adapter, "analyze_frame", _stub_m6_analysis)
    monkeypatch.setattr(
        runtime.TextureABCClassifierAdapter,
        "classify_domain",
        _stub_abc_classification,
    )
    monkeypatch.setattr(
        runtime.QFileDialog,
        "getExistingDirectory",
        lambda *_args: str(tmp_path),
    )

    def restore_series(session):
        return restore_moltrack_image_series_from_session(
            session,
            series_loader=lambda *_args, **_kwargs: MolTrackImageSeries(
                source_path=source_path,
                raw_frames=initial_series.raw_frames.copy(),
                metadata=initial_series.metadata,
            ),
        )

    def build_composition(owner, session_series):
        composition = runtime.build_domain_analysis_main_window_composition(
            owner,
            session_series,
        )
        built_compositions.append(_BuiltComposition(composition, session_series))
        return composition

    window = MolTrackMainWindow(
        yolo_model_discovery=lambda: [],
        session_restorer=restore_series,
        domain_analysis_composition_factory=build_composition,
    )
    try:
        window.open_state(initial_session_path)
        assert window.viewer.visible_molecular_segmentation_ids() == ["m-a", "m-b"]
        assert window.viewer.visible_molecular_detection_count() == 4
        assert window.btn_position_analysis.text() == "Domain Analysis..."
        assert [action.text() for action in window.analysis_menu.actions()] == [
            "Position Analysis..."
        ]

        window.btn_position_analysis.click()
        dialog = window.domain_analysis_dialog()
        assert dialog is not None
        assert len(built_compositions) == 1
        composition = built_compositions[-1].composition
        restored_series = built_compositions[-1].session_series
        audit_destination = tmp_path / "workflow-domain-analysis-audit-v10"
        assert dialog.audit_export_button.text() == "Export audit v10..."
        assert dialog.audit_export_button.isEnabled()
        dialog.audit_export_button.click()
        audit_manifest_path = audit_destination / "manifest.json"
        _wait_until(qt_app, audit_manifest_path.is_file)
        audit_manifest = json.loads(
            audit_manifest_path.read_text(encoding="utf-8")
        )
        assert audit_manifest["export_schema_version"] == 10
        assert audit_manifest["export_mode"] == "audit"
        assert audit_manifest["readiness"] == {
            "ready": False,
            "blockers": ["no_active_automatic_snapshot"],
        }
        _wait_until(
            qt_app,
            lambda: window.statusBar().currentMessage().startswith(
                "Exported Domain Analysis to"
            ),
        )
        assert [value.source_id for value in build_molecular_centroids(restored_series)] == [
            "m-a",
            "m-b",
            "m-c",
            "m-d",
        ]

        dialog.analyze_button.click()
        _wait_until(
            qt_app,
            dialog.export_button.isEnabled,
            dialog.diagnosis_label.text,
        )
        publication = composition.session_state().published_result
        assert publication is not None
        _select_first_domain(dialog)
        qt_app.processEvents()
        selection = composition.session_state().selected_component
        assert selection is not None
        assert window.viewer.highlighted_m6_overlay_source_ids() == ("m-a", "m-b")

        window.action_position_analysis.trigger()
        qt_app.processEvents()
        assert len(built_compositions) == 1
        advanced = window.position_analysis_dialog()
        assert advanced is not None
        assert not hasattr(advanced, "second_range_start_spin")
        assert "Spatial comparison" not in advanced.analysis_tab_labels()
        outcomes = publication.result.classifier_outcomes
        assert outcomes is not None
        classifications = tuple(
            value
            for outcome in outcomes
            for value in outcome.molecule_classifications
        )
        assert {
            value.source_id
            for value in classifications
            if value.classification_status == "classified"
        } == {"m-a", "m-b"}
        assert all(
            value.m6_partition == "full_domain"
            for value in classifications
            if value.classification_status == "classified"
        )
        assert all(
            value.classification_status == "not_gated"
            and value.orientation_label is None
            and value.evidence_strength == 0.0
            for value in classifications
            if value.m6_partition != "full_domain"
        )

        saved_path = tmp_path / "round-trip.moltrack.json"
        window.save_state(saved_path)
        saved = load_moltrack_session(saved_path)
        saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))
        saved_state = saved.domain_analysis_state
        assert saved_payload["schema_version"] == 3
        assert {
            "position_analysis",
            "molecular_m6_analysis",
            "m6_domain_type_analysis",
            "molecular_order_type_analysis",
            "texture_domain_analysis",
        }.isdisjoint(saved_payload)
        assert saved_state is not None
        assert saved_state.draft == composition.session_state().draft
        assert saved_state.published_result == publication
        assert saved_state.selected_component == selection
        assert len(saved_state.m6_cache_records) == 1
        assert len(saved_state.classifier_cache_records) == 1

        window.open_state(saved_path)
        assert len(built_compositions) == 2
        composition = built_compositions[-1].composition
        assert composition.session_state() == saved_state
        assert composition.session_state().published_result == publication
        assert composition.session_state().selected_component == selection
        assert window.viewer.highlighted_m6_overlay_source_ids() == ("m-a", "m-b")
        assert (
            composition.session_state().m6_cache_records
            == saved_state.m6_cache_records
        )
        assert (
            composition.session_state().classifier_cache_records
            == saved_state.classifier_cache_records
        )

        window.btn_position_analysis.click()
        assert len(built_compositions) == 2
        reopened = window.domain_analysis_dialog()
        assert reopened is not None
        reopened.command_center.stage_button("review").click()
        review_sheet = reopened.reference_review_sheet
        _review_target_in_ui(
            review_sheet,
            "m6",
            {source_id: ("accepted_automatic", None) for source_id in (
                "m-a", "m-b", "m-c", "m-d"
            )},
            qt_app,
        )
        _review_target_in_ui(
            review_sheet,
            "orientation",
            {
                "m-a": ("accepted_automatic", None),
                "m-b": ("accepted_automatic", None),
                "m-c": ("not_eligible", "automatic_gate_excluded"),
                "m-d": ("not_eligible", "automatic_gate_excluded"),
            },
            qt_app,
        )
        reopened.export_button.click()
        manifest_path = export_destination / "manifest.json"
        _wait_until(qt_app, manifest_path.is_file)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        automatic = json.loads(
            (export_destination / "automatic_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["export_schema_version"] == 10
        assert manifest["package_kind"] == "moltrack_correction_aware_analysis"
        assert manifest["export_mode"] == "reference"
        assert manifest["readiness"] == {"ready": True, "blockers": []}
        assert automatic["request_fingerprint"] == (
            publication.request_fingerprint
        )
        assert [
            value["m6_gate_fingerprint"]
            for value in automatic["m6_gate"]["frames"]
        ] == [
            value.m6_gate_fingerprint
            for value in publication.result.m6_gate.frames
        ]
        assert [
            value["classifier_result_fingerprint"]
            for value in automatic["classifier_outcomes"]
        ] == [
            value.classifier_result_fingerprint
            for value in publication.result.classifier_outcomes or ()
        ]
        legacy_destination = tmp_path / "workflow-domain-analysis-legacy-v9"
        assert not legacy_destination.exists()
        _wait_until(
            qt_app,
            lambda: window.statusBar().currentMessage().startswith(
                "Exported Domain Analysis to"
            ),
        )
        assert reopened.legacy_export_button.text() == "Export legacy v9..."
        assert reopened.legacy_export_button.isEnabled()
        reopened.legacy_export_button.click()
        legacy_manifest_path = legacy_destination / "manifest.json"
        _wait_until(qt_app, legacy_manifest_path.is_file)
        legacy_manifest = json.loads(
            legacy_manifest_path.read_text(encoding="utf-8")
        )
        assert legacy_manifest["export_schema_version"] == 9
        assert legacy_manifest["package_kind"] == "moltrack_analysis"
        assert not (legacy_destination / "automatic_snapshot.json").exists()

        active_state = composition.session_state()
        active_overlay = window.viewer.highlighted_m6_overlay_source_ids()
        unsupported_path = tmp_path / "unsupported.moltrack.json"
        unsupported_payload = json.loads(saved_path.read_text(encoding="utf-8"))
        unsupported_payload["schema_version"] = 999
        unsupported_path.write_text(json.dumps(unsupported_payload), encoding="utf-8")
        corrupt_path = tmp_path / "corrupt.moltrack.json"
        corrupt_path.write_text('{"schema_version": 2,', encoding="utf-8")
        invalid_cases = (
            _RejectedSessionCase(
                unsupported_path,
                "unsupported",
                "schema_version",
                "Unsupported MolTrack session schema_version: 999.",
                unsupported_path.read_bytes(),
            ),
            _RejectedSessionCase(
                corrupt_path,
                "corrupt",
                "session_file",
                "invalid JSON at line 1",
                corrupt_path.read_bytes(),
            ),
        )

        with patch.object(
            QMessageBox,
            "critical",
            return_value=QMessageBox.StandardButton.Ok,
        ) as critical:
            for case in invalid_cases:
                window.open_state(case.path)
                assert len(built_compositions) == 2
                assert composition.session_state() == active_state
                assert window.viewer.highlighted_m6_overlay_source_ids() == active_overlay
                assert case.path.read_bytes() == case.original_bytes
                message = critical.call_args.args[2]
                assert f"session {case.kind}" in message
                assert case.component in message
                assert case.reason in message

        safe_path = tmp_path / "saved-after-rejections.moltrack.json"
        window.save_state(safe_path)
        assert load_moltrack_session(safe_path).domain_analysis_state == active_state
        assert all(
            case.path.read_bytes() == case.original_bytes
            for case in invalid_cases
        )
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_open_v2_without_abc_then_enable_save_and_reopen_uses_runtime_capability(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "capability-catalog.mpp"
    source_path.write_bytes(b"domain analysis capability catalog source")
    initial_series = _annotated_series(source_path)
    initial_path = tmp_path / "initial.moltrack.json"
    without_abc_path = tmp_path / "without-abc.moltrack.json"
    enabled_path = tmp_path / "enabled-abc.moltrack.json"
    save_moltrack_session(initial_path, initial_series)
    built_compositions: list[_BuiltComposition] = []

    def restore_series(session):
        return restore_moltrack_image_series_from_session(
            session,
            series_loader=lambda *_args, **_kwargs: MolTrackImageSeries(
                source_path=source_path,
                raw_frames=initial_series.raw_frames.copy(),
                metadata=initial_series.metadata,
            ),
        )

    def build_composition(owner, session_series):
        composition = runtime.build_domain_analysis_main_window_composition(
            owner,
            session_series,
        )
        built_compositions.append(_BuiltComposition(composition, session_series))
        return composition

    monkeypatch.setattr(QMessageBox, "critical", lambda *_args: None)
    window = MolTrackMainWindow(
        yolo_model_discovery=lambda: [],
        session_restorer=restore_series,
        domain_analysis_composition_factory=build_composition,
    )
    try:
        window.open_state(initial_path)
        window.btn_position_analysis.click()
        dialog = window.domain_analysis_dialog()
        assert dialog is not None
        dialog.classify_abc_checkbox.setChecked(False)
        window.save_state(without_abc_path)
        legacy_payload = as_legacy_session_v2(
            json.loads(without_abc_path.read_text(encoding="utf-8"))
        )
        without_abc_path.write_text(
            json.dumps(legacy_payload),
            encoding="utf-8",
        )

        window.open_state(without_abc_path)
        assert len(built_compositions) == 2
        window.btn_position_analysis.click()
        restored = window.domain_analysis_dialog()
        assert restored is not None
        assert not restored.classify_abc_checkbox.isChecked()

        restored.classify_abc_checkbox.setChecked(True)
        window.save_state(enabled_path)
        assert enabled_path.is_file()

        enabled = load_moltrack_session(enabled_path).domain_analysis_state
        assert enabled is not None
        assert enabled.draft is not None
        assert enabled.draft.classifier_ids == (ABC_ORIENTATION_CLASSIFIER_ID,)
        assert tuple(
            value.identity.classifier_id
            for value in enabled.draft_classifier_configurations
        ) == (ABC_ORIENTATION_CLASSIFIER_ID,)

        window.open_state(enabled_path)
        assert len(built_compositions) == 3
        assert (
            built_compositions[-1].composition.session_state().draft
            == enabled.draft
        )
        window.btn_position_analysis.click()
        reopened = window.domain_analysis_dialog()
        assert reopened is not None
        assert reopened.classify_abc_checkbox.isChecked()
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_restore_reports_classifier_missing_from_runtime_capability_catalog(
    qt_app,
    tmp_path,
) -> None:
    source_path = tmp_path / "missing-capability.mpp"
    source_path.write_bytes(b"domain analysis missing capability source")
    window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
    composition = runtime.build_domain_analysis_main_window_composition(
        window,
        _annotated_series(source_path),
    )
    initial_draft = composition.session_state().draft
    missing_id = "missing_classifier_adapter"
    missing_configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=missing_id,
            schema_version="missing-schema-v1",
            settings_fingerprint="missing-settings-v1",
            algorithm_version="missing-algorithm-v1",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )
    state = DomainAnalysisSessionState(
        draft=DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(missing_id,),
        ),
        draft_classifier_configurations=(missing_configuration,),
    )

    try:
        with pytest.raises(ValueError, match="Unavailable classifier IDs") as raised:
            composition.restore_session(state)

        assert missing_id in str(raised.value)
        assert composition.session_state().draft == initial_draft
    finally:
        composition.shutdown()
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_runtime_composition_exposes_the_release_workflow_actions(
    qt_app,
    tmp_path,
) -> None:
    source_path = tmp_path / "release-workflow.mpp"
    source_path.write_bytes(b"domain analysis release workflow source")
    window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
    composition = runtime.build_domain_analysis_main_window_composition(
        window,
        _annotated_series(source_path),
    )

    try:
        dialog = composition.open_domain_analysis()
        dataset_sheet = dialog.reference_dataset_sheet

        assert dataset_sheet.save_session_button.isEnabled()
        assert dataset_sheet.open_session_button.isEnabled()
        assert dataset_sheet.publish_m6_button.isEnabled()
        assert dataset_sheet.publish_orientation_button.isEnabled()
        assert dialog.calibration_sheet.run_campaign_button.isEnabled()
    finally:
        composition.shutdown()
        window.close()
        window.deleteLater()
        qt_app.processEvents()
