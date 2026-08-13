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
    dialog.manual_domain_move_button.click()
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    assert projection.domain("physical-frame-0", domain_id).source_ids == (
        "m-a",
        "m-d",
    )

    dialog.manual_domain_delete_button.click()
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
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    restored = projection.domain("physical-frame-0", domain_id)
    assert not restored.is_tombstone
    assert restored.source_ids == ("m-a", "m-d")
    _dispose(dialog, qt_app)
