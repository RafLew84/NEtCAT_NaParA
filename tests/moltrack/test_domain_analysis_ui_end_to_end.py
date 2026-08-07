from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABC_ORIENTATION_CLASSIFIER_ID,
    ClassifierAnalysisError,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    DomainComponentKey,
    SelectDomainComponent,
    SetDomainAnalysisFrame,
)
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
    from moltrack.ui.dialogs.position_analysis_workspace_dialog import (
        PositionAnalysisWorkspaceDialog,
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
    advanced = PositionAnalysisWorkspaceDialog(controller)
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
    reopened = PositionAnalysisWorkspaceDialog(controller)
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
