"""Shared manual lists and per-frame assignments through the application window."""

import pytest
from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.tools.class_discovery_demo import create_class_discovery_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts
from stmdomains.ui.result_style import assignment_color


@pytest.fixture
def opened(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.resize(1024, 768)
    window.show()
    c = window.controller
    c.open_session(create_class_discovery_demo(tmp_path)['pair_a'])
    qtbot.waitUntil(lambda: not c.is_busy)
    c.fit_current_classes(ClassFitSettings(k=2, scope='selected_range', start=0, end=1))
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    window.manual_panel.edit.click()
    yield window
    window.close()
    window._finish_background_work()


def test_shared_names_colors_and_global_history_preserve_model_and_frame_assignments(qtbot, opened):
    c, m = opened.controller, opened.controller.manual
    original = c.result
    model = original.catalogue
    m.preview_classes('create', name='Moja klasa', color='#123456')
    created = m.preview_result.class_list
    target = created.classes[-1].class_id
    assert c.displayed_result.class_list is created and not m.has_changes
    m.apply()
    m.select_molecules((next(iter(m.active.eligible_ids)),))
    m.preview_classes('assign', target=target)
    m.apply()
    first = c.displayed_result
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    c.analyze_current_frame()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    m.select_variant('')
    m.set_editing(True)
    second_original = c.result
    assert m.class_list.identifier == created.identifier
    assert not any(a.class_id == target for a in c.displayed_result.assignments.values())
    m.preview_classes('update', target=target, name='Wspólna nazwa', color='#abcdef')
    m.apply()
    renamed = m.class_list
    c.show_frame(0)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_list is renamed
    assert c.displayed_result.assignments == first.assignments
    m.undo()  # Metadata operation on frame 2; shared list restored everywhere.
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.current_index == 1 and m.class_list is created
    m.redo()
    assert m.class_list is renamed
    assert model.k == 2 and len(model.state['centers']) == 2
    assert second_original.catalogue is model and original.class_list is None
    assert original.assignments != first.assignments


def test_class_window_creates_assigns_unassigned_points_and_keeps_model_legend(qtbot, opened):
    c, m = opened.controller, opened.controller.manual
    opened.manual_panel.classes.click()
    dialog = opened.manual_panel.class_dialog
    assert dialog.isVisible() and not dialog.isModal()
    original = c.result
    key = next(k for k, a in original.assignments.items() if not a.domain_local_id
               and k in m.active.eligible_ids)
    m.select_molecules((key,))
    dialog.name.setText('Pojedyncze wskazania')
    dialog.color.setText('#123456')
    dialog.create_assign.click()
    assert m.preview_result is not None
    assert c.displayed_result.assignments[key].domain_local_id == 0
    assert assignment_color(c.displayed_result, key, 'classes') == '#123456'
    dialog.apply.click()
    target = c.displayed_result.assignments[key].class_id
    assert dialog.target.currentData() == target
    opened.result_controls.mode.setCurrentIndex(opened.result_controls.mode.findData('classes'))
    assert 'bez domeny: 1' in opened.result_controls.summary.text()
    assert 'Pojedyncze wskazania' in opened.result_controls.legend.text()
    assert 'K modelu: 2' in dialog.scope.text()
    assert 'ręczne: 1' in dialog.scope.text()
    assert c.displayed_result.assigned_count == original.assigned_count
    dialog.compare.click()
    assert c.displayed_result is original
    assert 'Pojedyncze wskazania' not in opened.result_controls.legend.text()
    dialog.compare.click()
    dialog.undo.click()
    assert c.displayed_result is original


def test_lists_do_not_cross_catalogues_or_unanalysed_frames_and_reanalysis_keeps_edits(qtbot, opened):
    c, m = opened.controller, opened.controller.manual
    m.preview_classes('create_assign', name='Własna', color='#123456')
    assert m.preview_result is None  # Missing selection is not an empty assignment.
    m.select_molecules((next(iter(m.active.eligible_ids)),))
    m.preview_classes('create_assign', name='Własna', color='#123456')
    m.apply()
    first_key, first = m.active.identifier, c.displayed_result
    target = first.class_list.classes[-1].class_id
    original = c.result
    c.fit_current_classes(ClassFitSettings(k=1))
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert c.displayed_result is first
    m.select_variant('')
    m.set_editing(True)
    assert m.class_list.identifier != first.class_list.identifier
    assert target not in {label.class_id for label in m.class_list.classes}
    m.select_molecules((next(iter(m.active.eligible_ids)),))
    m.preview_classes('assign', target=target)
    assert m.preview_result is None
    m.select_variant(first_key)
    m.set_comparison(True)
    assert c.displayed_result is original
    m.set_comparison(False)
    assert c.displayed_result is first
    c.show_frame(2)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.result is None and m.class_list.catalogue_id == ''
    assert not m.class_list.classes
    m.select_molecules((next(iter(m.active.eligible_ids)),))
    m.preview_classes('create_assign', name='Bez modelu', color='#abcdef')
    m.apply()
    assert c.displayed_result.assigned_count == 0
    assert c.displayed_result.catalogue is None
    assert original.class_list is None


def test_shared_class_used_on_another_frame_cannot_be_deleted(qtbot, opened):
    c, m = opened.controller, opened.controller.manual
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    c.analyze_current_frame()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    m.select_variant('')
    m.set_editing(True)
    m.select_molecules((next(iter(m.active.eligible_ids)),))
    m.preview_classes('create_assign', name='Tylko na drugiej', color='#123456')
    m.apply()
    labels = m.class_list
    target = labels.classes[-1].class_id
    c.show_frame(0)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert m.class_list is labels
    assert not any(a.class_id == target for a in c.displayed_result.assignments.values())
    m.preview_classes('delete', target=target)
    assert m.preview_result is None and 'członków' in m.message
    opened.manual_panel.classes.click()
    dialog = opened.manual_panel.class_dialog
    dialog.target.setCurrentIndex(dialog.target.findData(target))
    assert not dialog.delete.isEnabled()


def test_navigation_renders_shared_names_even_after_editing_panel_is_closed(qtbot, opened):
    c, m = opened.controller, opened.controller.manual
    m.set_editing(False)
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    c.analyze_current_frame()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    second = c.result
    c.show_frame(0)
    qtbot.waitUntil(lambda: not c.is_busy)
    m.set_editing(True)
    target = m.class_list.classes[0].class_id
    m.preview_classes('update', target=target, name='Wspólna nazwa na obu klatkach', color='#123456')
    m.apply()
    m.set_editing(False)
    opened.result_controls.mode.setCurrentIndex(opened.result_controls.mode.findData('classes'))
    c.show_frame(1)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert 'Wspólna nazwa na obu klatkach' in opened.result_controls.legend.text()
    assert c.displayed_result.assignments == second.assignments
    assert not opened.manual_panel.isVisible()
    m.set_editing(True)
    domain = next(a.domain_local_id for a in second.assignments.values()
                  if a.domain_local_id and a.class_id == target)
    combo = opened.manual_panel.target
    assert combo.itemText(combo.findData(domain)).startswith('Wspólna nazwa na obu klatkach · ')
