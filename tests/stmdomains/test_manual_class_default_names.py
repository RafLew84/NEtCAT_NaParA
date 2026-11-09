"""Creating an unnamed class must select a real class before assigning molecules."""

import pytest
from PyQt6.QtCore import Qt

from test_class_operation_controls import control
from stmdomains.core.result_names import domain_names


def test_empty_class_then_assignment_without_typing_name_does_not_clear_class(qtbot, control):
    c, m = control.controller, control.controller.manual
    control.manual_panel.classes.click()
    d = control.manual_panel.class_dialog
    assert not d.name.text()
    d.create_button.click()
    d.apply.click()
    key = 'frame-1-molecule-1'
    m.select_molecules((key,))
    d.assign.click()
    assert m.preview_result is not None, m.message
    assignment = c.displayed_result.assignments[key]
    assert domain_names(c.displayed_result)[assignment.domain_local_id] == 'C1'
    assert assignment.class_id == d.target.currentData()
    d.apply.click()
    assert m.class_list.classes[-1].name == 'C'


@pytest.mark.parametrize('button', ('create_button', 'create_assign'))
def test_whitespace_name_uses_next_letter_and_undo_restores_class_list(qtbot, control, button):
    c, m = control.controller, control.controller.manual
    control.manual_panel.classes.click()
    d = control.manual_panel.class_dialog
    before = c.displayed_result
    m.select_molecules(('frame-1-molecule-1',))
    for expected in ('C', 'D'):
        d.name.setText('   ')
        getattr(d, button).click()
        assert m.preview_result is not None, m.message
        assert m.preview_result.class_list.classes[-1].name == expected
        d.apply.click()
    d.undo.click()
    d.undo.click()
    assert c.displayed_result is before
    d.redo.click()
    assert m.class_list.classes[-1].name == 'C'


def test_unnamed_split_uses_same_default_as_new_empty_class(qtbot, control):
    c, m = control.controller, control.controller.manual
    control.manual_panel.classes.click()
    control.manual_panel.class_dialog.split_class.click()
    d = control.manual_panel.class_dialog.operations_dialog
    d.capture.click()
    qtbot.waitUntil(lambda: not m.class_operations.running)
    d.sources.item(0).setCheckState(Qt.CheckState.Checked)
    m.select_molecules(('frame-1-molecule-1',))
    d.remember.click()
    d.name.clear()
    d.preview.click()
    qtbot.waitUntil(lambda: not m.class_operations.running)
    assert m.class_operations.transaction is not None, m.class_operations.message
    assert c.displayed_result.class_list.classes[-1].name == 'C'
