"""Class operations use a frozen set of frame variants and one global history step."""

from test_manual_class_window import opened
from PyQt6.QtCore import Qt


def test_multi_frame_merge_survives_navigation_and_undo_restores_both(qtbot, opened):
    c, m = opened.controller, opened.controller.manual
    first = c.result
    m.set_editing(False)
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    c.analyze_current_frame()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    second = c.result
    c.show_frame(0)
    qtbot.waitUntil(lambda: not c.is_busy)
    m.set_editing(True)
    op = m.class_operations
    op.capture('selected_range', 0, 1)
    qtbot.waitUntil(lambda: not op.running)
    assert tuple(op.frames) == (0, 1)
    op.preview('merge', sources=tuple(x.class_id for x in m.class_list.classes), name='C', color='#123456')
    qtbot.waitUntil(lambda: not op.running)
    assert op.transaction is not None, op.message
    target = op.transaction.after.classes[-1].class_id
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_counts[target] == second.assigned_count
    assert c.result is second
    op.apply()
    assert m.has_changes
    m.undo()
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result is first
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result is second
    m.redo()
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_counts[target] == first.assigned_count


def test_class_window_offers_merge_and_preview_cancel_without_mutation(qtbot, opened):
    p, m = opened.manual_panel, opened.controller.manual
    p.classes.click()
    p.class_dialog.merge_classes.click()
    dialog = p.class_dialog.operations_dialog
    assert dialog.isVisible()
    dialog.capture.click()
    qtbot.waitUntil(lambda: not m.class_operations.running)
    for i in range(dialog.sources.count()):
        dialog.sources.item(i).setCheckState(Qt.CheckState.Checked)
    dialog.name.setText('C')
    original = opened.controller.result
    dialog.preview.click()
    qtbot.waitUntil(lambda: not m.class_operations.running)
    assert m.class_operations.transaction is not None, dialog.message.text()
    assert dialog.apply.isEnabled()
    assert dialog.frames.rowCount() == 1
    dialog.cancel.click()
    assert not m.has_changes and opened.controller.displayed_result is original
    assert len(m.class_list.classes) == 2
