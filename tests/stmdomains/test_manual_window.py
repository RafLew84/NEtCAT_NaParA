"""Manual panel, real centre selection and session isolation through public UI."""

import pytest
from PyQt6.QtCore import QPointF, Qt

from test_analysis_window import Prompts
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from stmdomains.ui.project_prompts import QtProjectPrompts


@pytest.fixture
def opened(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.resize(1024, 768)
    window.show()
    window.controller.open_session(create_analysis_demo(tmp_path)['series'])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    yield window
    window.close()
    window._finish_background_work()


def select_sample(window):
    manual = window.controller.manual
    manual.set_editing(True)
    active = manual.ensure_variant()
    sample = tuple(sorted(active.eligible_ids)[:5])
    manual.select_molecules(sample)
    return sample


def test_panel_hides_outside_editing_and_corrected_image_remains(qtbot, opened):
    panel, controller = opened.manual_panel, opened.controller
    assert not panel.isVisible()
    width = opened.image_view.width()
    panel.edit.click()
    qtbot.waitUntil(panel.isVisible)
    qtbot.waitUntil(lambda: opened.image_view.width() < width)
    selected = select_sample(opened)
    panel.review.click()
    assert controller.result is None
    assert controller.displayed_result.assigned_count == len(selected)
    assert not controller.manual.has_changes
    assert not opened.export_action.isEnabled()
    panel.apply.click()
    expected = controller.displayed_result
    assert controller.manual.has_changes
    panel.edit.click()
    qtbot.waitUntil(lambda: not panel.isVisible() and opened.image_view.width() == width)
    assert controller.displayed_result is expected
    assert opened.result_controls.summary.text().startswith('Ręcznie')
    assert not opened.export_action.isEnabled()
    assert all(action.isEnabled() for action in opened.project_actions.save_actions)
    panel.edit.click()
    panel.undo.click()
    assert controller.displayed_result is None
    panel.redo.click()
    assert controller.displayed_result is expected


def test_click_and_lasso_selection_survive_zoom_and_fractional_alignment(qtbot, opened):
    panel, controller, view = opened.manual_panel, opened.controller, opened.image_view
    panel.edit.click()
    panel.tool.setCurrentIndex(panel.tool.findData('click'))
    eligible = controller.manual.ensure_variant().eligible_ids
    sample = next(d for d in controller.presenter.present(0, controller.view_mode).annotations.detections
                  if d.detection_id in eligible)
    location = view.mapFromScene(QPointF(*sample.center_xy))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=location)
    assert controller.manual.selection == (sample.detection_id,)
    view.zoom_by(1.4)
    controller.set_view_mode('expanded_aligned')
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.manual.selection == (sample.detection_id,)
    panel.tool.setCurrentIndex(panel.tool.findData('lasso'))
    displayed = next(d for d in controller.presenter.present(0, controller.view_mode).annotations.detections
                     if d.detection_id == sample.detection_id)
    x, y = displayed.center_xy
    corners = [view.mapFromScene(QPointF(x+dx, y+dy)) for dx, dy in
               [(-3, -3), (3, -3), (3, 3), (-3, 3), (-3, -3)]]
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=corners[0])
    for corner in corners[1:]:
        qtbot.mouseMove(view.viewport(), pos=corner)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=corners[-1])
    assert controller.manual.selection == (sample.detection_id,)
    panel.mode.setCurrentIndex(panel.mode.findData('subtract'))
    panel.tool.setCurrentIndex(panel.tool.findData('click'))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                    pos=view.mapFromScene(QPointF(x, y)))
    assert not controller.manual.selection


def test_new_analysis_does_not_overwrite_manual_variant_or_transfer_it_to_next_frame(qtbot, opened):
    controller = opened.controller
    select_sample(opened)
    controller.manual.preview('new')
    controller.manual.apply()
    corrected = controller.displayed_result
    key = controller.manual.active.identifier
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    automatic = controller.result
    assert automatic is not None and controller.displayed_result is corrected
    controller.manual.select_variant('')
    assert controller.displayed_result is automatic
    select_sample(opened)
    assert controller.manual.active.identifier != key
    controller.manual.select_variant(key)
    controller.manual.set_comparison(True)
    assert controller.displayed_result is None  # original of this variant had no analysis
    controller.manual.set_comparison(False)
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.displayed_result is None and not controller.manual.selection
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.displayed_result is corrected
    assert controller.project_analysis() is None


def test_cancel_leaving_keeps_manual_changes_and_source(qtbot, opened, tmp_path, monkeypatch):
    controller = opened.controller
    select_sample(opened)
    controller.manual.preview('new')
    controller.manual.apply()
    corrected = controller.displayed_result
    source = controller.series
    monkeypatch.setattr(QtProjectPrompts, 'confirm_unsaved', lambda self: 'cancel')
    opened.close()
    assert opened.isVisible() and controller.displayed_result is corrected
    opened.project_actions.open(tmp_path/'different.moltrack.json')
    assert controller.series is source and not controller.is_busy
    controller.save_project(tmp_path/'corrected.stmdomains')
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert (tmp_path/'corrected.stmdomains').exists()
    monkeypatch.setattr(QtProjectPrompts, 'confirm_unsaved', lambda self: 'discard')


def test_playback_ends_editing_and_preserves_the_variant(qtbot, opened):
    controller = opened.controller
    select_sample(opened)
    controller.manual.preview('new')
    controller.manual.apply()
    variant = controller.manual.active
    controller.set_playback_rate(1)
    controller.play()
    assert controller.is_playing and not controller.manual.editing
    assert not opened.manual_panel.isVisible()
    controller.pause()
    assert controller.manual.active is variant and variant.changed


def test_zero_automatic_result_stays_available_after_manual_domain(qtbot, opened):
    controller = opened.controller
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    zero = controller.result
    assert zero.assigned_count == 0
    select_sample(opened)
    controller.manual.preview('new')
    controller.manual.apply()
    assert controller.displayed_result.assigned_count == 5 and controller.result is zero
    key = controller.manual.active.identifier
    opened.method_controls.baseline.click()
    assert controller.displayed_result is zero
    controller.manual.select_variant(key)
    assert controller.displayed_result.assigned_count == 5


def test_undo_redo_follows_operation_order_across_frames(qtbot, opened):
    controller = opened.controller
    select_sample(opened)
    controller.manual.preview('new')
    controller.manual.apply()
    first = controller.manual.active
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    select_sample(opened)
    controller.manual.preview('new')
    controller.manual.apply()
    second = controller.manual.active
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert '2' in opened.manual_panel.undo.text()
    opened.manual_panel.undo.click()
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.current_index == 1 and first.changed and not second.changed
    opened.manual_panel.undo.click()
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.current_index == 0 and not first.changed
    opened.manual_panel.redo.click()
    qtbot.waitUntil(lambda: not controller.is_busy)
    opened.manual_panel.redo.click()
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.current_index == 1 and first.changed and second.changed
