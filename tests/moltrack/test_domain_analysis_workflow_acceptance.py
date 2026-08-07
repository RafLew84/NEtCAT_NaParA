from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
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
from moltrack.ui import domain_analysis_runtime as runtime
from moltrack.ui.domain_analysis_composition import (
    DomainAnalysisMainWindowComposition,
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
        m6_settings_fingerprint=adapter.m6_settings_fingerprint,
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
        assert saved_payload["schema_version"] == 2
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
        reopened.export_button.click()
        manifest_path = export_destination / "manifest.json"
        _wait_until(qt_app, manifest_path.is_file)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exported = manifest["analysis"]["domain_analysis"]
        assert manifest["export_schema_version"] == 9
        assert exported["session_schema_version"] == saved_state.schema_version
        assert exported["request"]["request_fingerprint"] == (
            publication.request_fingerprint
        )
        assert [
            value["m6_gate_fingerprint"]
            for value in exported["m6_gate"]["frames"]
        ] == [
            value.m6_gate_fingerprint
            for value in publication.result.m6_gate.frames
        ]
        assert [
            value["classifier_result_fingerprint"]
            for value in exported["classifier_outcomes"]
        ] == [
            value.classifier_result_fingerprint
            for value in publication.result.classifier_outcomes or ()
        ]

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
