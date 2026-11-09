"""Panel A split/merge through real project loading and existing session history."""

import numpy as np
import pytest
from PyQt6.QtCore import QPointF, Qt

from test_analysis_window import Prompts
from stmdomains.tools.manual_partition_demo import create_partition_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


@pytest.fixture
def opened(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.resize(1024, 768)
    window.show()
    window.controller.open_session(create_partition_demo(tmp_path))
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.manual_panel.edit.click()
    yield window
    window.close()
    window._finish_background_work()


def choose(window, operation, *ids):
    panel = window.manual_panel
    panel.operation.setCurrentIndex(panel.operation.findData(operation))
    window.controller.manual.select_molecules(ids)
    panel.review.click()


def test_split_merge_preview_cancel_history_and_original_in_panel(qtbot, opened):
    controller, panel = opened.controller, opened.manual_panel
    original = controller.result
    chosen = tuple(f'frame-1-molecule-{i}' for i in (1, 2, 9, 10, 17, 18))
    choose(opened, 'split', *chosen)
    preview = controller.manual.preview_result
    assert preview.domain_count == 3 and preview.assigned_count == 57
    assert 'A1 (48)' in panel.message.text() and 'A2 (6)' in panel.message.text()
    panel.cancel.click()
    assert controller.displayed_result is original and not controller.manual.has_changes
    panel.review.click()
    panel.apply.click()
    split = controller.displayed_result
    panel.compare.click()
    assert controller.displayed_result is original
    panel.compare.click()
    choose(opened, 'merge', chosen[0], 'frame-1-molecule-3')
    panel.target.setCurrentIndex(panel.target.findData(7))
    panel.review.click()
    assert 'A1: 42' in panel.members.toPlainText() and 'A2: 6' in panel.members.toPlainText()
    assert 'frame-1-molecule-48' in panel.members.toPlainText()
    assert [panel.target.itemData(i) for i in range(panel.target.count())] == [7, 12]
    assert [panel.target.itemText(i) for i in range(panel.target.count())] == ['A1 (ID 7)', 'A2 (ID 12)']
    assert 'Podgląd: 48 molekuł' in panel.message.text()
    panel.cancel.click()
    assert controller.displayed_result is split
    panel.review.click()
    panel.apply.click()
    merged = controller.displayed_result
    assert np.array_equal(merged.domain_labels, original.domain_labels)
    assert merged.assigned_count == 57 and merged.domain_count == 2
    panel.undo.click()
    assert controller.displayed_result is split
    panel.redo.click()
    assert controller.displayed_result is merged
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.displayed_result.assigned_count == 57 and controller.displayed_result.domain_count == 3
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.displayed_result is merged


def test_reanalysis_preserves_split_and_its_own_original(qtbot, opened):
    controller, panel = opened.controller, opened.manual_panel
    original = controller.result
    choose(opened, 'split', 'frame-1-molecule-1')
    panel.apply.click()
    corrected = controller.displayed_result
    key = controller.manual.active.identifier
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    assert controller.result is not original and controller.displayed_result is corrected
    panel.compare.click()
    assert controller.displayed_result is original
    panel.compare.click()
    controller.manual.select_variant('')
    assert controller.displayed_result is controller.result
    controller.manual.select_variant(key)
    assert controller.displayed_result is corrected


def test_merge_conflict_is_explicit_and_gap_is_refused_without_losing_edits(qtbot, opened):
    controller, panel = opened.controller, opened.manual_panel
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    original = controller.result
    choose(opened, 'merge', 'frame-2-molecule-1', 'frame-2-molecule-5')
    assert 'Różne klasy' in panel.message.text() and 'nieustaloną' in panel.message.text()
    panel.target.setCurrentIndex(panel.target.findData(9))
    assert controller.manual.preview_result is None  # A target change requires a fresh preview.
    panel.review.click()
    assert '?1 (48)' in panel.message.text()
    panel.apply.click()
    assert controller.displayed_result.assignments['frame-2-molecule-1'].class_id == ''
    assert controller.displayed_result.assignments['frame-2-molecule-1'].domain_local_id == 9
    panel.undo.click()
    assert controller.displayed_result is original
    controller.show_frame(2)
    qtbot.waitUntil(lambda: not controller.is_busy)
    original = controller.result
    choose(opened, 'merge', 'frame-3-molecule-1', 'frame-3-molecule-5')
    assert 'przerwa' in panel.message.text()
    assert not panel.apply.isEnabled() and controller.displayed_result is original


def test_real_lasso_in_aligned_view_splits_current_members_and_preserves_other_domains(qtbot, opened):
    controller, panel, view = opened.controller, opened.manual_panel, opened.image_view
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.set_view_mode('expanded_aligned')
    qtbot.waitUntil(lambda: not controller.is_busy)
    original = controller.result
    panel.operation.setCurrentIndex(panel.operation.findData('split'))
    view.zoom_by(1.3)
    frame = controller.presenter.present(1, controller.view_mode)
    center = frame.annotations.detections[0].center_xy
    x, y = center
    corners = [view.mapFromScene(QPointF(x+dx, y+dy)) for dx, dy in
               [(-5, -5), (17, -5), (17, 17), (-5, 17), (-5, -5)]]
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=corners[0])
    for corner in corners[1:]:
        qtbot.mouseMove(view.viewport(), pos=corner)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=corners[-1])
    assert set(controller.manual.selection) == {f'frame-2-molecule-{i}' for i in (1, 2, 9, 10)}
    panel.review.click()
    panel.apply.click()
    split = controller.displayed_result
    assert split.domain_count == 4 and split.assigned_count == original.assigned_count
    assert np.array_equal(split.domain_labels == 11, original.domain_labels == 11)
    controller.set_view_mode('raw')
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.displayed_result is split
