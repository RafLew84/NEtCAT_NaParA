from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_domain_analysis_dialog import _dialog, _dispose, _workspace
from test_domain_analysis_workspace_lifecycle import _ManualExecutor

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None


@pytest.fixture(scope="module")
def qt_app():
    if QApplication is None:
        pytest.skip("PyQt6 is required for MolTrack GUI tests")
    return QApplication.instance() or QApplication([])


def test_correct_sheet_creates_moves_deletes_and_restores_manual_domain(
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

    dialog.manual_domain_create_button.click()
    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    domain_id = prepared.intent.manual_domain_id
    assert domain_id is not None
    assert not dialog.correction_confirm_impact_checkbox.isHidden()
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    assert projection.domain("physical-frame-0", domain_id).source_ids == ("m-d",)
    assert "0 unassigned" in dialog.domain_hierarchy_sheet.ledger_summary_label.text()
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    assert any(
        component.key.lattice_domain_id == domain_id
        for component in overlay.components
    )
    assert overlay.unassigned_pixels_xy == ()
    hierarchy_labels = tuple(
        dialog.domain_hierarchy_sheet.tree.topLevelItem(index).text(0)
        for index in range(dialog.domain_hierarchy_sheet.tree.topLevelItemCount())
    )
    assert f"Domain {domain_id}" in hierarchy_labels

    dialog.command_center.canvas.select_molecule("m-a")
    dialog.manual_domain_combo.setCurrentIndex(
        dialog.manual_domain_combo.findData(domain_id)
    )
    boundary_combo = (
        dialog.domain_correction_sheet.manual_domain_controls
        .boundary_resolution_combo
    )
    boundary_combo.setCurrentIndex(boundary_combo.findData("clear"))
    dialog.manual_domain_move_button.click()
    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    assert prepared.intent.boundary_resolution == "clear"
    assert not dialog.correction_confirm_impact_checkbox.isHidden()
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    assert projection.domain("physical-frame-0", domain_id).source_ids == (
        "m-a",
        "m-d",
    )

    dialog.manual_domain_delete_button.click()
    assert not dialog.correction_confirm_impact_checkbox.isHidden()
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    assert projection.domain("physical-frame-0", domain_id).is_tombstone
    assert "2 unassigned" in dialog.domain_hierarchy_sheet.ledger_summary_label.text()
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    assert all(
        component.key.lattice_domain_id != domain_id
        for component in overlay.components
    )
    assert (0, 0) in overlay.unassigned_pixels_xy
    hierarchy_labels = tuple(
        dialog.domain_hierarchy_sheet.tree.topLevelItem(index).text(0)
        for index in range(dialog.domain_hierarchy_sheet.tree.topLevelItemCount())
    )
    assert f"Domain {domain_id} (tombstone)" in hierarchy_labels
    assert dialog.manual_domain_restore_button.isEnabled()

    dialog.manual_domain_restore_button.click()
    assert dialog.correction_confirm_impact_checkbox.isHidden()
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    restored = projection.domain("physical-frame-0", domain_id)
    assert not restored.is_tombstone
    assert restored.source_ids == ("m-a", "m-d")
    _dispose(dialog, qt_app)


def test_restore_conflicts_are_resolved_per_member_in_the_production_sheet(
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
    dialog.command_center.canvas.select_molecule("m-a")
    dialog.command_center.canvas.select_molecule("m-b")

    dialog.manual_domain_create_button.click()
    first = controller.snapshot.domain_corrections.prepared
    assert first is not None
    first_id = first.intent.manual_domain_id
    assert first_id is not None
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    dialog.manual_domain_delete_button.click()
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()

    dialog.manual_domain_create_button.click()
    second = controller.snapshot.domain_corrections.prepared
    assert second is not None
    second_id = second.intent.manual_domain_id
    assert second_id is not None
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    qt_app.processEvents()

    dialog.manual_domain_combo.setCurrentIndex(
        dialog.manual_domain_combo.findData(first_id)
    )
    dialog.manual_domain_restore_button.click()
    blocked = controller.snapshot.domain_corrections.prepared
    assert blocked is not None and blocked.is_blocked
    assert blocked.required_restore_member_resolutions == ("m-a", "m-b")

    resolution_combos = (
        dialog.domain_correction_sheet.manual_domain_controls
        .restore_resolution_combos
    )
    move_back_combo = resolution_combos["m-a"]
    keep_current_combo = resolution_combos["m-b"]
    move_back_combo.setCurrentIndex(move_back_combo.findData("move_back"))
    keep_current_combo.setCurrentIndex(
        keep_current_combo.findData("keep_current")
    )
    dialog.manual_domain_restore_button.click()
    resolved = controller.snapshot.domain_corrections.prepared
    assert resolved is not None and not resolved.is_blocked
    assert resolved.intent.member_resolutions == (
        ("m-a", "move_back"),
        ("m-b", "keep_current"),
    )
    keep_current_combo.setCurrentIndex(
        keep_current_combo.findData("move_back")
    )
    assert controller.snapshot.domain_corrections.prepared is None
    keep_current_combo.setCurrentIndex(
        keep_current_combo.findData("keep_current")
    )
    dialog.manual_domain_restore_button.click()
    resolved = controller.snapshot.domain_corrections.prepared
    assert resolved is not None and not resolved.is_blocked
    dialog.orientation_apply_button.click()
    qt_app.processEvents()

    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    assert projection.domain("physical-frame-0", first_id).source_ids == ("m-a",)
    assert projection.domain("physical-frame-0", second_id).source_ids == ("m-b",)
    _dispose(dialog, qt_app)


def test_polygon_crossing_groups_requires_confirmation_and_commits_once(
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
    dialog.correction_polygon_selection_button.click()
    dialog.command_center.canvas.select_polygons((
        ((-0.5, -0.5), (1.5, -0.5), (1.5, 1.5), (-0.5, 1.5)),
        ((-0.25, -0.25), (0.75, -0.25), (0.75, 1.25), (-0.25, 1.25)),
    ))
    qt_app.processEvents()

    state = controller.snapshot.domain_corrections
    assert state.selected_source_ids == ("m-a", "m-b", "m-d")
    assert len(state.selection_polygons) == 2
    overlay = dialog.command_center.canvas.current_overlay
    assert overlay is not None
    assert len(overlay.selection_polygons_xy) == 2

    dialog.orientation_target_combo.setCurrentText("Z")
    dialog.orientation_preview_button.click()
    qt_app.processEvents()
    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    assert prepared.requires_confirmation
    assert "outside" in prepared.source_groups
    assert len(prepared.source_groups) == 2
    assert not dialog.correction_confirm_impact_checkbox.isHidden()
    assert not dialog.orientation_apply_button.isEnabled()
    dialog.correction_confirm_impact_checkbox.setChecked(True)
    assert dialog.orientation_apply_button.isEnabled()

    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    correction = controller.snapshot.domain_corrections
    assert correction.selected_source_ids == ("m-a", "m-b", "m-d")
    assert correction.selection_polygons == ()
    assert correction.prepared is None
    assert correction.correction_set is not None
    assert len(correction.correction_set.atoms) == 1
    assert correction.correction_set.atoms[0].source_ids == (
        "m-a",
        "m-b",
        "m-d",
    )
    _dispose(dialog, qt_app)
