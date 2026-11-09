"""Literal acceptance counts through the real importer, window and editing API."""

import numpy as np
import pytest
from dataclasses import replace

from test_analysis_window import Prompts
from stmdomains.tools.class_operations_demo import create_class_operations_demo, initialize_class_operations_demo
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


@pytest.fixture
def control(qtbot, tmp_path):
    w = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(w)
    w.show()
    w.controller.open_session(create_class_operations_demo(tmp_path))
    qtbot.waitUntil(lambda: not w.controller.is_busy)
    initialize_class_operations_demo(w)
    w.controller.manual.set_editing(True)
    yield w
    w.close()
    w._finish_background_work()


def test_scope_preparation_can_be_cancelled_before_touching_assignments(qtbot, control):
    c, m = control.controller, control.controller.manual
    before = c.displayed_result
    op = m.class_operations
    op.capture('whole_series')
    assert op.running
    op.cancel_preview()
    qtbot.waitUntil(lambda: not op.running)
    assert not op.frames and op.labels is None
    assert c.displayed_result is before


def capture(qtbot, op, scope='current_frame', start=0, end=1):
    op.capture(scope, start, end)
    qtbot.waitUntil(lambda: not op.running)
    assert op.labels is not None, op.message


def preview(qtbot, op, operation, sources, **kwargs):
    op.preview(operation, sources=sources, **kwargs)
    qtbot.waitUntil(lambda: not op.running)
    assert op.transaction is not None, op.message
    return op.transaction


def visit(qtbot, c, index):
    c.show_frame(index)
    qtbot.waitUntil(lambda: not c.is_busy)


def test_literal_merge_counts_existing_target_and_cancel(qtbot, control):
    c, m = control.controller, control.controller.manual
    op, before = m.class_operations, c.displayed_result
    assert before.class_counts == {'A': 6, 'B': 3}
    capture(qtbot, op)
    tx = preview(qtbot, op, 'merge', ('A', 'B'), name='C', color='#123456')
    target = tx.after.classes[-1].class_id
    assert c.displayed_result.class_counts == {'A': 0, 'B': 0, target: 9}
    op.cancel_preview()
    assert c.displayed_result is before
    assert m.class_list is tx.before
    tx = preview(qtbot, op, 'merge', ('A', 'B'), target='A')
    assert tx.after is tx.before
    op.apply()
    assert c.displayed_result.class_counts == {'A': 9, 'B': 0}
    assert c.displayed_result.domain_count == 2 and c.displayed_result.unassigned_count == 2
    np.testing.assert_array_equal(c.displayed_result.domain_labels, before.domain_labels)
    visit(qtbot, c, 1)
    assert c.displayed_result.class_counts == {'A': 4, 'B': 3}
    m.undo()
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result is before


def test_literal_multi_frame_merge_and_split_include_class_only_members(qtbot, control):
    c, m = control.controller, control.controller.manual
    op = m.class_operations
    capture(qtbot, op, 'whole_series')
    assert tuple(op.frames) == (0, 1) and 'inny katalog' in op.skipped[2]
    tx = preview(qtbot, op, 'merge', ('A', 'B'), name='C', color='#123456')
    target = tx.after.classes[-1].class_id
    assert [change.after.class_counts[target] for change in tx.changes] == [9, 7]
    visit(qtbot, c, 2)
    assert c.displayed_result.class_counts == {'A': 4, 'B': 3}
    assert op.transaction is tx and tuple(op.frames) == (0, 1)
    op.apply()
    visit(qtbot, c, 0)
    merged = c.displayed_result
    capture(qtbot, op)
    m.select_molecules(('frame-1-molecule-1', 'frame-1-molecule-8'))
    op.remember_selection(whole_domains=True)
    assert len(op.selections[0]) == 5
    split = preview(qtbot, op, 'split', (target,), name='D', color='#abcdef')
    new = split.after.classes[-1].class_id
    assert c.displayed_result.class_counts[target] == 4 and c.displayed_result.class_counts[new] == 5
    assert c.displayed_result.domain_count == 2 and c.displayed_result.unassigned_count == 2
    np.testing.assert_array_equal(c.displayed_result.domain_labels, merged.domain_labels)
    op.apply()
    m.undo()
    assert c.displayed_result is merged
    capture(qtbot, op)
    m.select_molecules(('frame-1-molecule-5',))
    op.remember_selection()
    tx = preview(qtbot, op, 'split', (target,), name='D', color='#abcdef')
    assert c.displayed_result.domain_count == 3
    assert c.displayed_result.class_counts[target] == 8
    assert c.displayed_result.class_counts[tx.after.classes[-1].class_id] == 1
    np.testing.assert_array_equal(c.displayed_result.domain_labels > 0, merged.domain_labels > 0)
    op.apply()
    m.undo()
    assert c.displayed_result is merged
    visit(qtbot, c, 1)
    assert c.displayed_result.class_counts[target] == 7


def test_split_basket_requires_each_frame_and_later_edits_invalidate_preview(qtbot, control):
    c, m = control.controller, control.controller.manual
    op = m.class_operations
    capture(qtbot, op, 'selected_range')
    m.select_molecules(('frame-1-molecule-1',))
    op.remember_selection()
    op.preview('split', sources=('A',), name='D', color='#abcdef')
    qtbot.waitUntil(lambda: not op.running)
    assert op.transaction is None and 'Klatka 2' in op.message
    visit(qtbot, c, 1)
    assert not m.selection and tuple(op.selections) == (0,)
    m.select_molecules(('frame-2-molecule-1',))
    op.remember_selection()
    preview(qtbot, op, 'split', ('A',), name='D', color='#abcdef')
    assert c.displayed_result.domain_count == 3
    m.preview_classes('update', target='A', name='Zmieniona', color='#123456')
    assert op.transaction is None and not op.frames
    m.cancel_preview()
    assert c.displayed_result.domain_count == 2


def test_scope_and_preview_follow_label_revisions_with_chronological_history(qtbot, control):
    c, m = control.controller, control.controller.manual
    op = m.class_operations
    before = c.displayed_result
    capture(qtbot, op, 'whole_series')
    tx = preview(qtbot, op, 'merge', ('A', 'B'), name='C', color='#123456')
    target = tx.after.classes[-1].class_id
    op.apply()
    m.preview_classes('update', target=target, name='Po scaleniu', color='#abcdef')
    m.apply()
    m.undo()
    assert m.class_list.classes[-1].name == 'C'
    m.undo()
    assert c.displayed_result is before and len(m.class_list.classes) == 2
    visit(qtbot, c, 1)
    assert c.displayed_result.class_counts == {'A': 4, 'B': 3}
    m.redo()
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_counts[target] == 9
    m.redo()
    assert m.class_list.classes[-1].name == 'Po scaleniu'


def test_cancel_background_preview_then_close_keeps_current_result(qtbot, control):
    c, m = control.controller, control.controller.manual
    op = m.class_operations
    before = c.displayed_result
    capture(qtbot, op, 'whole_series')
    op.preview('merge', sources=('A', 'B'), name='C', color='#123456')
    op.cancel_preview()
    qtbot.waitUntil(lambda: not op.running)
    assert op.transaction is None and c.displayed_result is before
    assert len(m.class_list.classes) == 2
    op.preview('merge', sources=('A', 'B'), name='C', color='#123456')
    control.close()
    control._finish_background_work()
    qtbot.waitUntil(lambda: c.pending_task_count == 0)
    assert op.transaction is None and c.displayed_result is before


def test_scope_uses_explicit_variant_even_when_another_variant_is_displayed(qtbot, control):
    c, m = control.controller, control.controller.manual
    original = c.result
    foreign = replace(original, catalogue=replace(original.catalogue, parameters={'different': True}))
    chosen = m.variant_for(0, foreign)
    assert m.active is not chosen
    op = m.class_operations
    op.capture('current_frame', variant_id=chosen.identifier)
    qtbot.waitUntil(lambda: not op.running)
    assert op.frames == {0: chosen} and m.active is chosen


def test_invalid_replacement_selection_clears_previous_preview(qtbot, control):
    m = control.controller.manual
    op = m.class_operations
    capture(qtbot, op)
    m.select_molecules(('frame-1-molecule-1',))
    op.remember_selection()
    preview(qtbot, op, 'split', ('A',), name='D', color='#abcdef')
    m.select_molecules(())
    op.remember_selection()
    assert op.transaction is None and 'Zaznacz' in op.message


def test_reused_dialog_updates_range_for_a_longer_series(qtbot, control, tmp_path):
    p, c = control.manual_panel, control.controller
    p.classes.click()
    p.class_dialog.merge_classes.click()
    dialog = p.class_dialog.operations_dialog
    assert dialog.end.maximum() == 3
    dialog.close()
    c.open_session(create_analysis_demo(tmp_path / 'longer')['series'])
    qtbot.waitUntil(lambda: not c.is_busy)
    c.manual.set_editing(True)
    assert dialog.start.maximum() == dialog.end.maximum() == 5
