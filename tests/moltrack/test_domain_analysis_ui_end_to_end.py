from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABC_ORIENTATION_CLASSIFIER_ID,
    ClassifierConfiguration,
    ClassifierAnalysisError,
    ClassifierIdentity,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSessionCacheRecords,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    DomainComponentKey,
    SelectDomainComponent,
    SetDomainAnalysisFrame,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    CanonicalJsonObject,
    DomainAnalysisExportSettings,
    load_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata
from test_domain_analysis_module import (
    _DeterministicM6Adapter,
    _classifier_series,
)
from test_domain_analysis_workspace_lifecycle import _ManualExecutor

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog
    from moltrack.ui.dialogs.position_analysis_dialog import PositionAnalysisDialog
    from moltrack.ui.dialogs.position_analysis_workspace_dialog import (
        PositionAnalysisWorkspaceDialog,
    )
    from moltrack.ui.domain_analysis_composition import (
        DomainAnalysisMainWindowComposition,
    )
    from moltrack.ui.domain_analysis_overlay import DomainAnalysisOverlayPresenter


class _MixedAndUnknownABCClassifier:
    classifier_id = ABC_ORIENTATION_CLASSIFIER_ID
    classifier_schema_version = "ui-abc-schema-v1"
    classifier_settings_fingerprint = "ui-abc-settings-v1"
    classifier_algorithm_version = "ui-abc-algorithm-v1"
    domain_aggregation_preset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1

    def classify_domain(
        self,
        raw_frame,
        *,
        frame_index: int,
        physical_frame_id: str,
        lattice_domain_id: str,
        molecules: tuple[ClassifierMoleculeInput, ...],
    ) -> tuple[ClassifierMoleculePrediction, ...]:
        del raw_frame, physical_frame_id, lattice_domain_id
        if frame_index == 2:
            raise ClassifierAnalysisError("controlled A/B/C failure")
        if frame_index == 1:
            return tuple(
                ClassifierMoleculePrediction(
                    source_id=value.source_id,
                    orientation_label=None,
                    evidence_strength=0.0,
                )
                for value in molecules
            )
        labels = {"m-a": "A", "m-b": "B"}
        return tuple(
            ClassifierMoleculePrediction(
                source_id=value.source_id,
                orientation_label=labels[value.source_id],
                evidence_strength=0.8,
                component_id=f"component-{labels[value.source_id]}",
            )
            for value in molecules
        )


@pytest.fixture(scope="module")
def qt_app():
    if QApplication is None:
        pytest.skip("PyQt6 is required for MolTrack GUI tests")
    return QApplication.instance() or QApplication([])


@pytest.fixture
def domain_ui(qt_app):
    series = _classifier_series(range(3))
    executor = _ManualExecutor()
    controller = DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
        physical_frame_ids=tuple(
            frame.geometry.physical_frame_id for frame in series.frames
        ),
        execution=DomainAnalysisWorkspaceExecution(
            DomainAnalysisModule(
                _DeterministicM6Adapter(reorder_adapter_output=False),
                classifier_adapters={
                    ABC_ORIENTATION_CLASSIFIER_ID: _MixedAndUnknownABCClassifier(),
                },
            ),
            series,
            executor,
        ),
    )
    window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP M6 approved",
        classifier_preset_name="TTMAPP A/B/C approved",
        export_published=lambda publication: None,
    )
    presenter = DomainAnalysisOverlayPresenter(controller, window.viewer)
    yield controller, executor, dialog, window, presenter
    dialog.cancel_button.click()
    presenter.deleteLater()
    dialog.close()
    dialog.deleteLater()
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def _abc_column(table) -> int:
    return next(
        index
        for index in range(table.columnCount())
        if table.horizontalHeaderItem(index).text() == "M6-Gated A/B/C"
    )


def _component_key(frame, component) -> DomainComponentKey:
    return DomainComponentKey(
        frame.physical_frame_id,
        component.lattice_domain_id,
    )


def _assert_mixed_abc(table, viewer, abc_column: int) -> None:
    assert table.item(0, abc_column).text() == "Mixed"
    assert viewer.visible_m6_overlay_source_ids() == ("m-a", "m-b")
    assert viewer.visible_m6_overlay_colors() == (
        (45, 125, 255, 230),
        (245, 155, 45, 230),
    )


def _assert_unknown_abc(table, viewer, abc_column: int) -> None:
    assert table.item(0, abc_column).text() == "Unknown orientation"
    assert viewer.visible_m6_overlay_colors() == (
        (135, 140, 150, 230),
        (135, 140, 150, 230),
    )


def test_domain_analysis_ui_shares_published_overlay_and_selection(
    qt_app,
    domain_ui,
) -> None:
    controller, executor, dialog, window, presenter = domain_ui
    viewer = window.viewer
    assert viewer.visible_m6_overlay_count() == 0
    dialog.range_end_spin.setValue(2)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    publication = controller.snapshot.published
    assert publication is not None
    gate = publication.result.m6_gate
    assert gate is not None

    table = dialog.current_frame_results_panel.domain_table
    abc_column = _abc_column(table)
    _assert_mixed_abc(table, viewer, abc_column)

    table.setCurrentCell(0, 0)
    qt_app.processEvents()
    full_domain = gate.frames[0].full_domains[0]
    full_key = _component_key(gate.frames[0], full_domain)
    assert controller.snapshot.selected_component == full_key
    assert viewer.highlighted_m6_overlay_source_ids() == ("m-a", "m-b")

    controller.dispatch(SetDomainAnalysisFrame(1))
    qt_app.processEvents()
    _assert_unknown_abc(table, viewer, abc_column)

    controller.dispatch(SetDomainAnalysisFrame(0))
    island = gate.frames[0].small_ordered_islands[0]
    island_key = _component_key(gate.frames[0], island)
    raw_x, raw_y = island.footprint_pixels_xy[0]
    viewer.image_pixel_clicked.emit((float(raw_x), float(raw_y)))
    qt_app.processEvents()
    assert controller.snapshot.selected_component == island_key
    assert table.currentRow() == 1
    assert "m-c" not in viewer.visible_m6_overlay_source_ids()

    controller.dispatch(SelectDomainComponent(None))
    presenter.set_target_view("expanded_aligned")
    origin_x, origin_y = gate.frames[0].presentation_provenance.frame_origin_xy
    viewer.image_pixel_clicked.emit((raw_x + origin_x, raw_y + origin_y))
    qt_app.processEvents()
    assert controller.snapshot.selected_component == island_key

    published_colors = viewer.visible_m6_overlay_colors()
    dialog.range_end_spin.setValue(3)
    dialog.analyze_button.click()
    qt_app.processEvents()
    assert controller.snapshot.run.status == "running"
    assert controller.snapshot.published is publication
    assert viewer.visible_m6_overlay_colors() == published_colors


def test_position_analysis_adapter_reads_the_shared_workspace(
    qt_app,
    domain_ui,
) -> None:
    controller, executor, simple, window, _presenter = domain_ui
    advanced = PositionAnalysisWorkspaceDialog(
        controller,
        export_published=lambda publication: None,
    )
    simple.range_end_spin.setValue(2)
    simple.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    assert (
        advanced.current_frame_results_panel.current_results()
        == simple.current_frame_results_panel.current_results()
    )
    first_publication = controller.snapshot.published
    assert first_publication is not None
    first_gate = first_publication.result.m6_gate
    assert first_gate is not None
    assert "Frame 2" in advanced.range_trends_view.toPlainText()
    assert (
        first_gate.frames[0].m6_gate_fingerprint
        in advanced.sixfold_bond_order_view.toPlainText()
    )
    assert "Full Domain" in advanced.domain_types_view.toPlainText()
    assert "Mixed" in advanced.classifier_view.toPlainText()
    assert "m-a" in advanced.order_hierarchy_view.toPlainText()
    advanced.current_frame_results_panel.domain_table.setCurrentCell(0, 0)
    qt_app.processEvents()
    selection = controller.snapshot.selected_component
    assert selection is not None
    assert simple.current_frame_results_panel.domain_table.currentRow() == 0
    assert window.viewer.highlighted_m6_overlay_source_ids() == ("m-a", "m-b")

    simple.range_end_spin.setValue(3)
    simple.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    assert controller.snapshot.run.status == "completed_with_errors", (
        controller.snapshot.run.diagnosis
    )
    assert advanced.frame_range() == (1, 3)
    assert advanced.analysis_tab_labels() == (
        "Current frame",
        "Range trends",
        "Sixfold Bond Order",
        "Domain Types",
        "M6-Gated A/B/C",
        "Order Hierarchy",
    )
    assert "Spatial comparison" not in advanced.analysis_tab_labels()
    assert advanced.overall_status_label.text() == simple.overall_status_label.text()
    assert advanced.m6_status_label.text() == simple.m6_status_label.text()
    assert (
        advanced.classifier_status_label.text() == simple.classifier_status_label.text()
    )
    assert advanced.diagnosis_label.text() == simple.diagnosis_label.text()
    assert (
        advanced.current_frame_results_panel.current_results()
        == simple.current_frame_results_panel.current_results()
    )

    controller.dispatch(SetDomainAnalysisFrame(2))
    qt_app.processEvents()
    assert (
        advanced.current_frame_results_panel.current_results()
        == simple.current_frame_results_panel.current_results()
    )
    abc_column = _abc_column(advanced.current_frame_results_panel.domain_table)
    assert "Unavailable" in (
        advanced.current_frame_results_panel.domain_table.item(0, abc_column).text()
    )
    assert "controlled A/B/C failure" in advanced.classifier_view.toPlainText()
    assert "Frame 3" in advanced.range_trends_view.toPlainText()

    advanced.current_frame_results_panel.domain_table.setCurrentCell(0, 0)
    qt_app.processEvents()
    publication = controller.snapshot.published
    selection = controller.snapshot.selected_component
    assert selection is not None
    advanced.close()
    advanced.deleteLater()
    qt_app.processEvents()
    reopened = PositionAnalysisWorkspaceDialog(
        controller,
        export_published=lambda publication: None,
    )
    qt_app.processEvents()
    assert controller.snapshot.published is publication
    assert controller.snapshot.selected_component == selection
    assert reopened.current_frame_results_panel.domain_table.currentRow() == 0
    assert reopened.frame_range() == (1, 3)
    assert (
        reopened.current_frame_results_panel.current_results()
        == simple.current_frame_results_panel.current_results()
    )
    reopened.close()
    reopened.deleteLater()


def test_position_analysis_actions_share_workspace_lifecycle(
    qt_app,
    domain_ui,
) -> None:
    controller, executor, simple, _window, _presenter = domain_ui
    exported = []
    advanced = PositionAnalysisWorkspaceDialog(
        controller,
        export_published=exported.append,
    )

    advanced.range_end_spin.setValue(2)
    advanced.analyze_button.click()
    qt_app.processEvents()
    assert controller.snapshot.draft.frame_range == range(0, 2)
    assert controller.snapshot.run.status == "running"
    assert simple.range_end_spin.value() == 2
    assert simple.cancel_button.isEnabled()

    advanced.close()
    advanced.deleteLater()
    qt_app.processEvents()
    assert controller.snapshot.run.status == "running"
    executor.run_next()
    qt_app.processEvents()
    publication = controller.snapshot.published
    assert publication is not None
    assert simple.current_frame_results_panel.current_results() is not None

    reopened = PositionAnalysisWorkspaceDialog(
        controller,
        export_published=exported.append,
    )
    qt_app.processEvents()
    assert reopened.frame_range() == (1, 2)
    assert (
        reopened.current_frame_results_panel.current_results()
        == simple.current_frame_results_panel.current_results()
    )
    assert not hasattr(reopened, "second_range_start_spin")

    reopened.range_end_spin.setValue(3)
    reopened.analyze_button.click()
    qt_app.processEvents()
    assert controller.snapshot.run.status == "running"
    assert controller.snapshot.published is publication
    reopened.export_button.click()
    assert exported == [publication]

    reopened.cancel_button.click()
    qt_app.processEvents()
    assert controller.snapshot.run.status == "canceled"
    assert controller.snapshot.published is publication
    assert not simple.cancel_button.isEnabled()
    assert simple.range_end_spin.isEnabled()
    reopened.export_button.click()
    assert exported == [publication, publication]
    executor.run_next()
    assert controller.snapshot.published is publication

    reopened.close()
    reopened.deleteLater()


def test_main_window_cutover_preflight_runs_complete_new_path(
    qt_app,
    tmp_path,
) -> None:
    source_path = tmp_path / "preflight.mpp"
    source_path.write_bytes(b"domain analysis cutover preflight")
    analysis_series = _classifier_series(range(2))
    image_series = MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros((2, 4, 4), dtype=np.uint16),
        metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
    )
    executor = _ManualExecutor()
    classifier = _MixedAndUnknownABCClassifier()
    module = DomainAnalysisModule(
        _DeterministicM6Adapter(
            reorder_adapter_output=False,
            m6_settings_fingerprint=(
                "2056dfb4496987f99bdd695b7f5064b6"
                "00154c8fe5b43d002a5aaffceefd0b67"
            ),
        ),
        classifier_adapters={
            ABC_ORIENTATION_CLASSIFIER_ID: classifier,
        },
    )
    controller = DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
        physical_frame_ids=tuple(
            frame.geometry.physical_frame_id for frame in analysis_series.frames
        ),
        execution=DomainAnalysisWorkspaceExecution(
            module,
            analysis_series,
            executor,
        ),
    )
    classifier_configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=classifier.classifier_id,
            schema_version=classifier.classifier_schema_version,
            settings_fingerprint=(classifier.classifier_settings_fingerprint),
            algorithm_version=classifier.classifier_algorithm_version,
        ),
        aggregation_preset=classifier.domain_aggregation_preset,
    )
    export_destination = tmp_path / "preflight-export"
    export_settings = DomainAnalysisExportSettings(
        destination=export_destination,
        source_frame_indices=image_series.source_frame_indices,
        physical_frame_ids=controller.snapshot.physical_frame_ids,
        source_identity=CanonicalJsonObject({"source": source_path.name}),
        m6_settings=CanonicalJsonObject({"preset": "preflight-m6"}),
    )
    window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
    window.set_image_series(image_series)
    try:
        assert window.btn_position_analysis.text() == "Position Analysis..."
        assert "Analysis" not in (
            action.text().replace("&", "") for action in window.menuBar().actions()
        )
        window.btn_position_analysis.click()
        legacy_dialog = window.position_analysis_dialog()
        assert isinstance(legacy_dialog, PositionAnalysisDialog)
        legacy_dialog.close()
        legacy_dialog.deleteLater()
        qt_app.processEvents()

        composition = DomainAnalysisMainWindowComposition(
            window,
            controller,
            session_series=image_series,
            classifier_configurations=(classifier_configuration,),
            m6_preset_name="TTMAPP M6 approved",
            classifier_preset_name="TTMAPP A/B/C approved",
            export_settings_for=lambda _publication: export_settings,
        )
        simple = composition.open_domain_analysis()
        advanced = composition.open_position_analysis()
        simple.range_end_spin.setValue(2)
        simple.analyze_button.click()
        executor.run_next()
        qt_app.processEvents()

        publication = controller.snapshot.published
        assert publication is not None
        cache_records = module.session_cache_records()
        assert len(cache_records.m6_records) == 2
        assert len(cache_records.classifier_records) == 2
        simple.range_end_spin.setValue(1)
        simple.analyze_button.click()
        executor.run_next()
        qt_app.processEvents()
        publication = controller.snapshot.published
        assert publication is not None
        assert publication.request.frame_indices == (0,)
        cache_records = module.session_cache_records()
        assert len(cache_records.m6_records) == 2
        assert len(cache_records.classifier_records) == 2
        advanced.current_frame_results_panel.domain_table.setCurrentCell(0, 0)
        qt_app.processEvents()
        selection = controller.snapshot.selected_component
        assert selection is not None
        assert window.viewer.highlighted_m6_overlay_source_ids() == (
            "m-a",
            "m-b",
        )

        session_path = tmp_path / "preflight.moltrack.json"
        saved_state = composition.save_session(session_path)
        loaded = load_moltrack_session(session_path)
        session_payload = json.loads(session_path.read_text(encoding="utf-8"))
        assert loaded.domain_analysis_state == saved_state.domain_analysis_state
        assert loaded.domain_analysis_state is not None
        assert loaded.domain_analysis_state.published_result == publication
        assert loaded.domain_analysis_state.selected_component == selection
        assert len(loaded.domain_analysis_state.m6_cache_records) == 1
        assert len(loaded.domain_analysis_state.classifier_cache_records) == 1
        assert session_payload["schema_version"] == 2
        assert "molecular_m6_analysis" not in session_payload
        assert "texture_domain_analysis" not in session_payload

        controller.dispatch(SetDomainAnalysisFrame(1))
        module.restore_session_cache_records(DomainAnalysisSessionCacheRecords())
        assert controller.snapshot.selected_component is None
        assert module.session_cache_records() == DomainAnalysisSessionCacheRecords()
        composition.restore_session(loaded.domain_analysis_state)
        assert composition.session_state() == loaded.domain_analysis_state
        assert controller.snapshot.published == publication
        assert controller.snapshot.selected_component == selection
        assert controller.snapshot.run.status == "completed"
        assert window.viewer.highlighted_m6_overlay_source_ids() == (
            "m-a",
            "m-b",
        )

        simple.export_button.click()
        assert (export_destination / "manifest.json").is_file(), (
            simple.diagnosis_label.text()
        )
        export_manifest = json.loads(
            (export_destination / "manifest.json").read_text(encoding="utf-8")
        )
        assert export_manifest["export_schema_version"] == 9
        assert export_manifest["analysis"]["analysis_mode"] == (
            "domain_analysis_published_snapshot"
        )
        assert "domain_analysis" in export_manifest["analysis"]
        assert "m6_orientation" not in export_manifest["analysis"]
        assert "m6_domain_types" not in export_manifest["analysis"]
        assert all(
            path.name == "manifest.json" or path.name.startswith("domain_analysis_")
            for path in export_destination.iterdir()
        )
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()
