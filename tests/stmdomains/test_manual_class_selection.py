"""Collect several gestures before assigning classes, with controls in the dialog."""

from PyQt6.QtCore import QPointF, Qt
from test_class_operation_controls import control


def click_member(qtbot, window, key):
    c = window.controller
    point = next(d for d in c.presenter.present(c.current_index, c.view_mode).annotations.detections
                 if d.detection_id == key)
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton,
                    pos=window.image_view.mapFromScene(QPointF(*point.center_xy)))


def test_class_dialog_collects_clicks_into_one_assignment(qtbot, control):
    c, m = control.controller, control.controller.manual
    control.manual_panel.classes.click()
    dialog = control.manual_panel.class_dialog
    controls = dialog.selection_controls
    controls.tool.setCurrentIndex(controls.tool.findData('click'))
    controls.mode.setCurrentIndex(controls.mode.findData('add'))
    before = c.displayed_result
    for key in ('frame-1-molecule-1', 'frame-1-molecule-2'):
        click_member(qtbot, control, key)
    assert set(m.selection) == {'frame-1-molecule-1', 'frame-1-molecule-2'}
    assert c.displayed_result is before
    dialog.target.setCurrentIndex(dialog.target.findData('B'))
    dialog.assign.click()
    dialog.apply.click()
    result = c.displayed_result
    assert result.assignments['frame-1-molecule-1'].domain_local_id == result.assignments['frame-1-molecule-2'].domain_local_id
    assert result.domain_count == before.domain_count + 1
    dialog.undo.click()
    assert c.displayed_result.assignments == before.assignments


def test_selection_controls_sync_and_add_lasso_to_clicks(qtbot, control):
    c, m = control.controller, control.controller.manual
    control.manual_panel.classes.click()
    dialog = control.manual_panel.class_dialog
    controls = dialog.selection_controls
    controls.tool.setCurrentIndex(controls.tool.findData('click'))
    assert control.manual_panel.tool.currentData() == 'click'
    assert controls.mode.currentData() == 'add'
    click_member(qtbot, control, 'frame-1-molecule-1')
    controls.tool.setCurrentIndex(controls.tool.findData('lasso'))
    d = next(d for d in c.presenter.present(0, c.view_mode).annotations.detections if d.detection_id == 'frame-1-molecule-2')
    x, y = d.center_xy
    corners = [control.image_view.mapFromScene(QPointF(x+dx,y+dy)) for dx,dy in ((-4,-4),(4,-4),(4,4),(-4,4),(-4,-4))]
    qtbot.mousePress(control.image_view.viewport(), Qt.MouseButton.LeftButton, pos=corners[0])
    for point in corners[1:]:
        qtbot.mouseMove(control.image_view.viewport(), pos=point)
    qtbot.mouseRelease(control.image_view.viewport(), Qt.MouseButton.LeftButton, pos=corners[-1])
    assert set(m.selection) == {'frame-1-molecule-1','frame-1-molecule-2'}
    controls.mode.setCurrentIndex(controls.mode.findData('subtract'))
    click_member(qtbot, control, 'frame-1-molecule-1')
    assert m.selection == ('frame-1-molecule-2',)
    controls.clear.click()
    assert not m.selection
    dialog.split_class.click()
    ops = dialog.operations_dialog
    ops.selection_controls.tool.setCurrentIndex(ops.selection_controls.tool.findData('click'))
    ops.selection_controls.mode.setCurrentIndex(ops.selection_controls.mode.findData('add'))
    click_member(qtbot, control, 'frame-1-molecule-1')
    click_member(qtbot, control, 'frame-1-molecule-2')
    assert len(m.selection) == 2


def test_repair_fragments_in_class_dialog_roundtrips_and_undo_is_atomic(qtbot, control, tmp_path):
    import numpy as np
    c, m = control.controller, control.controller.manual
    control.manual_panel.classes.click()
    d = control.manual_panel.class_dialog
    d.target.setCurrentIndex(d.target.findData('B'))
    for key in ('frame-1-molecule-1', 'frame-1-molecule-2'):
        m.select_molecules((key,))
        d.assign.click()
        d.apply.click()
    before = c.displayed_result
    assert before.domain_count == 4
    m.select_molecules(('frame-1-molecule-1',))
    d.join_touching.setChecked(True)
    d.assign.click()
    assert m.preview_result is not None, m.message
    assert c.displayed_result.domain_count == 3
    assert 'Domeny: 4 → 3' in d.message.text()
    d.apply.click()
    corrected = c.displayed_result
    assert corrected.assignments['frame-1-molecule-1'].domain_local_id == corrected.assignments['frame-1-molecule-2'].domain_local_id
    np.testing.assert_array_equal(corrected.domain_labels > 0, before.domain_labels > 0)
    path = tmp_path / 'joined.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert path.exists()
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.assignments == corrected.assignments
    m.undo()
    assert c.displayed_result.assignments == before.assignments
    np.testing.assert_array_equal(c.displayed_result.domain_labels, before.domain_labels)
    m.redo()
    assert c.displayed_result.assignments == corrected.assignments
    m.set_comparison(True)
    assert not d.join_touching.isEnabled() and not d.selection_controls.isEnabled()
