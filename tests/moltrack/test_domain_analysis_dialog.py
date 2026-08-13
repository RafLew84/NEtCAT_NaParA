from __future__ import annotations

import json
import os
from dataclasses import replace
from functools import partial

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    CancelDomainAnalysis,
    DomainAnalysisEvent,
    DomainAnalysisModule,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    DomainComponentKey,
    DomainHierarchyHighlight,
    M6Gate,
    PublishDomainAnalysisResult,
    ReceiveDomainAnalysisEvent,
    SelectDomainComponent,
    SetDomainAnalysisFrame,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.persistence import (
    CanonicalJsonObject,
    DomainAnalysisExportSettings,
    export_analysis_package,
)
from test_domain_analysis_module import (
    _ControlledClassifier,
    _DeterministicM6Adapter,
    _classifier_series,
)
from domain_analysis_test_support import domain_analysis_module as DomainAnalysisModule

DomainAnalysisRequest = partial(
    DomainAnalysisRequest, backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID
)
from test_domain_analysis_workspace_lifecycle import _ManualExecutor
from test_domain_analysis_export import _frame_gate as _export_frame_gate

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QSpinBox
except ImportError:  # pragma: no cover - optional outside target GUI env
    Qt = None
    QApplication = None
    QSpinBox = None

if QApplication is not None:
    from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog
    from moltrack.ui.domain_analysis_overlay import (
        DOMAIN_ANALYSIS_HIGHLIGHT_COLOR,
        orientation_marker_style,
    )


@pytest.fixture(scope="module")
def qt_app():
    if QApplication is None:
        pytest.skip("PyQt6 is required for MolTrack GUI tests")
    return QApplication.instance() or QApplication([])


def _workspace(
    executor: _ManualExecutor,
    *,
    classifier_failure_frame: int | None = None,
    m6_failure_frame: int | None = None,
    m6_settings_fingerprint: str = "m6-settings-v1",
) -> DomainAnalysisWorkspaceController:
    series = _classifier_series(range(3))
    classifier = _ControlledClassifier(
        ABC_ORIENTATION_CLASSIFIER_ID,
        [],
        {"active": 0, "max_active": 0},
        fail_frame_index=classifier_failure_frame,
    )
    execution = DomainAnalysisWorkspaceExecution(
        DomainAnalysisModule(
            _DeterministicM6Adapter(
                reorder_adapter_output=False,
                fail_frame_index=m6_failure_frame,
                m6_settings_fingerprint=m6_settings_fingerprint,
            ),
            classifier_adapters={ABC_ORIENTATION_CLASSIFIER_ID: classifier},
        ),
        series,
        executor,
    )
    return DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
        physical_frame_ids=tuple(
            frame.geometry.physical_frame_id for frame in series.frames
        ),
        execution=execution,
    )


def test_dialog_opens_spatial_command_center_over_one_workspace(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    snapshot_before_open = controller.snapshot
    canvas_frames = np.arange(48, dtype=np.float32).reshape(3, 4, 4)

    dialog = _dialog(
        controller,
        lambda publication: None,
        canvas_frame_for=lambda frame_index: canvas_frames[frame_index],
    )
    dialog.show()
    qt_app.processEvents()

    command_center = dialog.command_center
    assert controller.snapshot is snapshot_before_open
    assert command_center.rendered_snapshot is snapshot_before_open
    assert command_center.canvas.objectName() == "domainAnalysisCanvas"
    assert command_center.canvas.has_image
    np.testing.assert_array_equal(
        command_center.canvas.viewer.image_item.image,
        canvas_frames[0],
    )
    assert command_center.stage_rail.objectName() == "domainAnalysisStageRail"
    assert command_center.bottom_sheet.objectName() == "domainAnalysisBottomSheet"
    assert command_center.stage_ids == (
        "analyze",
        "correct",
        "review",
        "datasets",
        "presets",
        "calibrate",
    )
    assert command_center.current_stage == "analyze"

    dialog.range_end_spin.setValue(3)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    publication = controller.snapshot.published
    assert publication is not None

    controller.dispatch(SetDomainAnalysisFrame(1))
    qt_app.processEvents()
    frame_snapshot = controller.snapshot
    assert frame_snapshot.published is publication
    assert command_center.canvas.current_frame_index == 1
    np.testing.assert_array_equal(
        command_center.canvas.viewer.image_item.image,
        canvas_frames[1],
    )
    rendered_frame = command_center.canvas.viewer.image_item.image
    results = dialog.current_frame_results_panel.current_results()
    assert results is not None
    assert results.domains[0].component_key is not None
    assert results.domains[0].component_key.physical_frame_id == "physical-frame-1"

    command_center.stage_button("review").click()
    qt_app.processEvents()

    assert command_center.current_stage == "review"
    assert command_center.current_sheet_stage == "review"
    assert controller.snapshot is frame_snapshot
    assert command_center.rendered_snapshot is frame_snapshot
    assert controller.snapshot.published is publication
    assert dialog.current_frame_results_panel.current_results() is results
    assert command_center.canvas.viewer.image_item.image is rendered_frame
    _dispose(dialog, qt_app)


def test_correct_hierarchy_highlights_without_changing_selection(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    canvas_frames = np.arange(48, dtype=np.float32).reshape(3, 4, 4)
    dialog = _dialog(
        controller,
        lambda publication: None,
        canvas_frame_for=lambda frame_index: canvas_frames[frame_index],
    )
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    table = dialog.current_frame_results_panel.domain_table
    table.setCurrentCell(0, 0)
    selection = controller.snapshot.selected_component
    publication = controller.snapshot.published
    assert selection is not None
    assert publication is not None
    gate = publication.result.m6_gate
    assert gate is not None
    domain_id = gate.frames[0].full_domains[0].lattice_domain_id

    dialog.command_center.stage_button("correct").click()
    tree = dialog.domain_hierarchy_sheet.tree
    assert dialog.domain_hierarchy_sheet.ledger_summary_label.text() == (
        "Ledger: 4 molecules · 2 full-domain · 1 small-island · 1 unassigned"
    )
    domain_item = tree.findItems(
        f"Domain {domain_id}",
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
        0,
    )[0]
    orientation_item = tree.findItems(
        "A",
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
        0,
    )[0]
    domain_item.setExpanded(True)
    tree.setCurrentItem(orientation_item)
    qt_app.processEvents()

    highlight = controller.snapshot.hierarchy_highlight
    assert highlight == DomainHierarchyHighlight(
        physical_frame_id="physical-frame-0",
        target_kind="orientation_subdomain",
        lattice_domain_id=domain_id,
        orientation_label="A",
    )
    assert controller.snapshot.selected_component == selection
    assert controller.snapshot.published is publication
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    assert overlay.hierarchy_highlight == highlight
    assert overlay.highlighted_source_ids == ("m-a", "m-b")
    assert overlay.components[0].m6_boundary_color_rgb == (220, 230, 233)
    assert overlay.components[1].m6_boundary_color_rgb == (232, 98, 88)
    assert {
        (point.state, point.color_rgb, point.symbol)
        for point in overlay.orientation_points
    } == {
        ("A", (0, 114, 178), "o"),
    }

    islands_item = tree.findItems(
        "Small ordered islands",
        Qt.MatchFlag.MatchExactly,
        0,
    )[0]
    tree.setCurrentItem(islands_item)
    qt_app.processEvents()
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    assert controller.snapshot.selected_component == selection
    assert controller.snapshot.hierarchy_highlight is not None
    assert controller.snapshot.hierarchy_highlight.target_kind == (
        "small_ordered_islands"
    )
    assert tuple(
        component.key.lattice_domain_id
        for component in overlay.components
        if component.is_highlighted
    ) == (gate.frames[0].small_ordered_islands[0].lattice_domain_id,)

    unassigned_item = tree.findItems(
        "Unassigned molecules",
        Qt.MatchFlag.MatchExactly,
        0,
    )[0]
    tree.setCurrentItem(unassigned_item)
    qt_app.processEvents()
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    assert overlay.unassigned_is_highlighted
    assert controller.snapshot.selected_component == selection

    controller.dispatch(SetDomainAnalysisFrame(1))
    qt_app.processEvents()

    assert controller.snapshot.hierarchy_highlight is None
    assert dialog.domain_hierarchy_sheet.current_highlight is None
    assert dialog.command_center.canvas.current_overlay is None
    _dispose(dialog, qt_app)


def test_correct_sheet_previews_and_applies_manual_orientation_from_canvas(
    qt_app,
) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(
        controller,
        lambda publication: None,
        canvas_frame_for=lambda _frame_index: np.zeros((4, 4), dtype=np.float32),
    )
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    dialog.command_center.stage_button("correct").click()

    dialog.command_center.canvas.select_molecule("m-d")
    dialog.orientation_target_combo.setCurrentText("D")
    dialog.orientation_preview_button.click()
    qt_app.processEvents()

    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    assert prepared.changed_source_ids == ("m-d",)
    assert dialog.orientation_apply_button.isEnabled()

    dialog.orientation_target_combo.setCurrentText("E")
    qt_app.processEvents()
    assert controller.snapshot.domain_corrections.prepared is None
    assert not dialog.orientation_apply_button.isEnabled()
    dialog.orientation_preview_button.click()
    qt_app.processEvents()

    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    corrected = projection.molecule("physical-frame-0", "m-d")
    assert corrected.effective_orientation == "E"
    assert corrected.effective_domain_id is None
    assert corrected.effective_confidence is None
    assert all(
        "m-d" not in subdomain.source_ids
        for subdomain in projection.orientation_subdomains
    )
    assert dialog.orientation_effective_label.text() == "Effective: E (manual)"
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    manual_point = next(
        point
        for point in overlay.orientation_points
        if point.source_id == "m-d"
    )
    assert manual_point.state == "E"
    assert manual_point.component_key is None

    dialog.orientation_reset_button.click()
    assert not dialog.correction_confirm_impact_checkbox.isHidden()
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    reset = controller.snapshot.domain_corrections.effective_projection
    assert reset is not None
    assert reset.molecule("physical-frame-0", "m-d").effective_orientation is None
    _dispose(dialog, qt_app)


def test_correct_hierarchy_uses_effective_orientation_inside_full_domain(
    qt_app,
) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(
        controller,
        lambda publication: None,
        canvas_frame_for=lambda _frame_index: np.zeros((4, 4), dtype=np.float32),
    )
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    dialog.command_center.canvas.select_molecule("m-a")
    dialog.orientation_target_combo.setCurrentText("D")
    dialog.orientation_preview_button.click()
    dialog.orientation_apply_button.click()
    qt_app.processEvents()

    labels = tuple(
        dialog.domain_hierarchy_sheet.tree.topLevelItem(0).child(index).text(0)
        for index in range(
            dialog.domain_hierarchy_sheet.tree.topLevelItem(0).childCount()
        )
    )
    assert "D" in labels
    d_item = dialog.domain_hierarchy_sheet.tree.findItems(
        "D",
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
        0,
    )[0]
    dialog.domain_hierarchy_sheet.tree.setCurrentItem(d_item)
    qt_app.processEvents()
    assert controller.snapshot.hierarchy_highlight is not None
    assert controller.snapshot.hierarchy_highlight.orientation_label == "D"
    _dispose(dialog, qt_app)


def test_orientation_markers_encode_a_to_z_with_color_and_shape(qt_app) -> None:
    styles = tuple(
        orientation_marker_style(chr(ord("A") + index))
        for index in range(26)
    )

    assert tuple(style.symbol for style in styles[:4]) == ("o", "t", "s", "d")
    assert tuple(style.color_rgb for style in styles[:4]) == (
        (0, 114, 178),
        (230, 159, 0),
        (204, 121, 167),
        (0, 158, 115),
    )
    assert DOMAIN_ANALYSIS_HIGHLIGHT_COLOR == (241, 196, 15)
    assert len({(style.color_rgb, style.symbol) for style in styles}) == 26


def test_dialog_runs_one_range_and_exports_exact_publication(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    exported: list[DomainAnalysisPublication] = []
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP M6 approved",
        classifier_preset_name="TTMAPP A/B/C approved",
        export_published=exported.append,
    )
    dialog.show()

    assert len(dialog.findChildren(QSpinBox)) == 2
    assert dialog.m6_preset_edit.isReadOnly()
    assert dialog.classifier_preset_edit.isReadOnly()
    assert dialog.aggregation_policy_edit.isReadOnly()
    assert dialog.classify_abc_checkbox.isChecked()
    assert tuple(
        dialog.domain_backend_combo.itemData(index)
        for index in range(dialog.domain_backend_combo.count())
    ) == ("m6_orientation_components", "m3_m6_lattice_network")
    assert "m6-gated" in dialog.classify_abc_checkbox.text().lower()
    assert "compare" not in dialog.windowTitle().lower()
    dialog.range_start_spin.setValue(2)
    dialog.range_end_spin.setValue(3)

    assert controller.snapshot.draft.frame_range == range(1, 3)
    dialog.analyze_button.click()
    assert controller.snapshot.run.status == "running"
    assert dialog.cancel_button.isEnabled()
    assert not dialog.range_start_spin.isEnabled()

    executor.run_next()
    qt_app.processEvents()

    assert controller.snapshot.run.status == "completed"
    assert "completed" in dialog.overall_status_label.text().lower()
    assert dialog.export_button.isEnabled()
    publication = controller.snapshot.published
    assert publication is not None

    dialog.export_button.click()

    assert exported == [publication]
    assert exported[0] is publication
    dialog.domain_backend_combo.setCurrentIndex(1)
    assert controller.snapshot.draft.backend_id == "m3_m6_lattice_network"
    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()


def test_domain_table_selects_canonical_key_and_tracks_external_selection(
    qt_app,
) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    panel = dialog.current_frame_results_panel
    table = panel.domain_table
    columns = {
        table.horizontalHeaderItem(index).text(): index
        for index in range(table.columnCount())
    }
    publication = controller.snapshot.published
    assert publication is not None
    gate = publication.result.m6_gate
    assert gate is not None
    full_domain_id = gate.frames[0].full_domains[0].lattice_domain_id
    island_id = gate.frames[0].small_ordered_islands[0].lattice_domain_id
    assert table.rowCount() == 2
    assert table.item(0, columns["Stable ID"]).text() == full_domain_id
    assert table.item(0, columns["Type"]).text() == "full_domain"
    assert table.item(0, columns["Area [nm2]"]).text() != "n/a"
    assert table.item(0, columns["Centroid [nm]"]).text() != "n/a"
    assert table.item(1, columns["Type"]).text() == "small_ordered_island"

    table.setCurrentCell(1, 0)

    assert controller.snapshot.selected_component == DomainComponentKey(
        "physical-frame-0",
        island_id,
    )

    controller.dispatch(SelectDomainComponent(DomainComponentKey(
        "physical-frame-0",
        full_domain_id,
    )))
    qt_app.processEvents()

    assert table.currentRow() == 0
    assert controller.snapshot.selected_component == DomainComponentKey(
        "physical-frame-0",
        full_domain_id,
    )
    _dispose(dialog, qt_app)


def test_domain_table_selection_is_frame_local(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.range_end_spin.setValue(3)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    table = dialog.current_frame_results_panel.domain_table
    table.setCurrentCell(0, 0)
    frame_zero_selection = controller.snapshot.selected_component
    assert frame_zero_selection is not None

    controller.dispatch(SetDomainAnalysisFrame(1))
    qt_app.processEvents()

    assert controller.snapshot.selected_component is None
    assert not table.selectedItems()
    frame_one_rows = dialog.current_frame_results_panel.current_results()
    assert frame_one_rows is not None
    frame_one_key = frame_one_rows.domains[0].component_key
    assert frame_one_key is not None
    assert frame_one_key.physical_frame_id == "physical-frame-1"
    controller.dispatch(SelectDomainComponent(frame_one_key))
    qt_app.processEvents()
    assert table.currentRow() == 0

    controller.dispatch(SetDomainAnalysisFrame(0))
    qt_app.processEvents()

    assert controller.snapshot.selected_component is None
    assert not table.selectedItems()
    assert frame_zero_selection.physical_frame_id == "physical-frame-0"
    _dispose(dialog, qt_app)


def test_domain_table_keeps_last_publication_during_draft_and_run(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    publication = controller.snapshot.published
    assert publication is not None
    table = dialog.current_frame_results_panel.domain_table
    published_cells = _table_cells(table)

    dialog.range_end_spin.setValue(2)

    assert controller.snapshot.published is publication
    assert _table_cells(table) == published_cells
    dialog.analyze_button.click()
    assert controller.snapshot.run.status == "running"
    assert controller.snapshot.published is publication
    assert _table_cells(table) == published_cells
    dialog.cancel_button.click()
    _dispose(dialog, qt_app)


def test_domain_table_classifies_full_domains_but_not_islands(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    table = dialog.current_frame_results_panel.domain_table
    classification = _column_index(table, "M6-Gated A/B/C")
    status = _column_index(table, "Status")
    results = dialog.current_frame_results_panel.current_results()
    assert results is not None

    assert results.domains[0].classification_status == "available"
    assert results.domains[0].classification_label == "A"
    assert results.domains[0].classification_error is None
    assert results.domains[1].classification_status == "not_applicable"
    assert table.item(0, classification).text() == "A"
    assert table.item(1, classification).text() == "Not applicable"
    assert table.item(0, status).text() == "OK"
    assert table.item(1, status).text() == "OK"
    _dispose(dialog, qt_app)


def test_domain_table_distinguishes_missing_classifier(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.classify_abc_checkbox.setChecked(False)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    table = dialog.current_frame_results_panel.domain_table
    classification = _column_index(table, "M6-Gated A/B/C")

    assert table.item(0, classification).text() == "Not requested"
    assert table.item(1, classification).text() == "Not applicable"
    _dispose(dialog, qt_app)


def test_domain_table_keeps_rows_when_classifier_partially_fails(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor, classifier_failure_frame=0)
    dialog = _dialog(controller, lambda publication: None)
    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()
    table = dialog.current_frame_results_panel.domain_table
    classification = _column_index(table, "M6-Gated A/B/C")

    assert table.rowCount() == 2
    assert "unavailable" in table.item(0, classification).text().lower()
    assert "controlled classifier failure" in (
        table.item(0, classification).text().lower()
    )
    assert table.item(1, classification).text() == "Not applicable"
    _dispose(dialog, qt_app)


def test_domain_table_distinguishes_no_publication_and_empty_result(qt_app) -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0",),
    )
    dialog = _dialog(controller, lambda publication: None)
    dialog.show()
    qt_app.processEvents()

    assert dialog.current_frame_results_panel.domain_table.rowCount() == 0
    assert dialog.current_frame_results_panel.empty_label.text() == (
        "No published Domain Analysis result."
    )

    original = _export_frame_gate(0)
    components = original.full_domains + original.small_ordered_islands
    empty_frame = replace(
        original,
        full_domains=(),
        small_ordered_islands=(),
        outside_members=(
            tuple(member for component in components for member in component.members)
            + original.outside_members
        ),
        outside_pixels_xy=original.analyzed_pixels_xy,
        outside_area_nm2=original.analyzed_area_nm2,
    )
    controller.dispatch(PublishDomainAnalysisResult(
        request,
        DomainAnalysisResult(
            run_status="completed",
            m6_gate=M6Gate(frames=(empty_frame,)),
            classifier_status="not_requested",
        ),
    ))
    qt_app.processEvents()

    assert dialog.current_frame_results_panel.domain_table.rowCount() == 0
    assert dialog.current_frame_results_panel.empty_label.text() == (
        "No M6 domains or small ordered islands in current frame."
    )
    _dispose(dialog, qt_app)


def test_cancel_preserves_and_exports_previous_publication(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    exported: list[DomainAnalysisPublication] = []
    dialog = _dialog(controller, exported.append)

    dialog.analyze_button.click()
    executor.run_next()
    previous = controller.snapshot.published
    assert previous is not None
    dialog.range_end_spin.setValue(2)
    dialog.analyze_button.click()

    assert controller.snapshot.run.status == "running"
    assert controller.snapshot.published is previous
    assert dialog.export_button.isEnabled()
    dialog.export_button.click()
    assert exported == [previous]
    dialog.cancel_button.click()

    assert controller.snapshot.run.status == "canceled"
    assert controller.snapshot.published is previous
    assert not dialog.cancel_button.isEnabled()
    assert dialog.range_end_spin.isEnabled()
    dialog.export_button.click()
    assert exported == [previous, previous]
    executor.run_next()
    assert controller.snapshot.published is previous
    _dispose(dialog, qt_app)


def test_partial_classifier_error_keeps_m6_result_visible(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor, classifier_failure_frame=0)
    dialog = _dialog(controller, lambda publication: None)

    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    snapshot = controller.snapshot
    assert snapshot.run.status == "completed_with_errors"
    assert snapshot.published is not None
    assert snapshot.published.result.m6_gate is not None
    assert dialog.m6_status_label.text() == "Completed"
    classifier_status = dialog.classifier_status_label.text().lower()
    assert "completed with errors" in classifier_status
    assert "controlled classifier failure" in classifier_status
    assert "frame 1" in classifier_status
    _dispose(dialog, qt_app)


def test_classifier_progress_keeps_completed_m6_stage_visible(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.analyze_button.click()
    identity = controller.snapshot.run.identity
    assert identity is not None

    controller.dispatch(ReceiveDomainAnalysisEvent(
        identity,
        DomainAnalysisEvent(
            stage_id=ABC_ORIENTATION_CLASSIFIER_ID,
            status="started",
            message="M6-Gated A/B/C Classification started.",
        ),
    ))
    qt_app.processEvents()

    assert dialog.m6_status_label.text() == "Completed"
    assert "started" in dialog.classifier_status_label.text().lower()
    controller.dispatch(CancelDomainAnalysis())
    _dispose(dialog, qt_app)


def test_full_failure_shows_diagnosis_without_exportable_result(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor, m6_failure_frame=0)
    dialog = _dialog(controller, lambda publication: None)

    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    assert controller.snapshot.run.status == "failed"
    assert controller.snapshot.published is None
    assert "failed" in dialog.overall_status_label.text().lower()
    assert "synthetic m6 backend failure" in dialog.diagnosis_label.text().lower()
    assert not dialog.export_button.isEnabled()
    _dispose(dialog, qt_app)


def test_export_callback_can_send_exact_publication_to_schema_v9(
    qt_app,
    tmp_path,
) -> None:
    m6_settings = {"preset_id": "dialog-test-m6-v1"}
    executor = _ManualExecutor()
    controller = _workspace(
        executor,
        m6_settings_fingerprint=canonical_sha256(m6_settings),
    )
    destination = tmp_path / "domain-analysis"
    received: list[DomainAnalysisPublication] = []

    def export_published(publication: DomainAnalysisPublication) -> None:
        received.append(publication)
        export_analysis_package(
            DomainAnalysisSessionState(published_result=publication),
            DomainAnalysisExportSettings(
                destination=destination,
                source_frame_indices=(41, 42, 43),
                physical_frame_ids=controller.snapshot.physical_frame_ids,
                source_identity=CanonicalJsonObject({
                    "file_name": "dialog-source.mpp",
                    "integrity": {"algorithm": "sha256", "value": "a" * 64},
                }),
                m6_settings=CanonicalJsonObject(m6_settings),
            ),
        )

    dialog = _dialog(controller, export_published)
    dialog.analyze_button.click()
    executor.run_next()
    publication = controller.snapshot.published
    assert publication is not None

    dialog.export_button.click()

    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert received == [publication]
    assert received[0] is publication
    assert manifest["export_schema_version"] == 9
    assert manifest["analysis"]["domain_analysis"]["request"]["frame_stop"] == 1
    _dispose(dialog, qt_app)


def _dialog(
    controller: DomainAnalysisWorkspaceController,
    export_published,
    *,
    canvas_frame_for=None,
):
    return DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP M6 approved",
        classifier_preset_name="TTMAPP A/B/C approved",
        export_published=export_published,
        canvas_frame_for=canvas_frame_for,
    )


def _dispose(dialog, qt_app) -> None:
    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()


def _table_cells(table) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(
            table.item(row, column).text()
            for column in range(table.columnCount())
        )
        for row in range(table.rowCount())
    )


def _column_index(table, label: str) -> int:
    return next(
        index
        for index in range(table.columnCount())
        if table.horizontalHeaderItem(index).text() == label
    )
