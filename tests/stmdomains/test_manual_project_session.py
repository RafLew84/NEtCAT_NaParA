"""Portable manual edits resume through the same session API as ordinary projects."""

from test_class_operation_controls import control
from test_manual_window import opened
from stmdomains.core.result_names import domain_names


def test_save_after_undo_reopens_classes_and_redo_without_original_sources(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    original = c.result
    m.select_molecules(('frame-1-molecule-1',))
    m.preview_classes('create_assign', name='Fragment', color='#123456')
    m.apply()
    target = m.class_list.classes[-1].class_id
    m.preview_classes('update', target=target, name='Nowa nazwa', color='#abcdef')
    m.apply()
    m.undo()
    assert m.class_list.classes[-1].name == 'Fragment'
    path = tmp_path / 'edited.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert path.exists()
    c.series.source_path.unlink()
    c.series.session_path.unlink()
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_list.classes[-1].name == 'Fragment'
    assert c.displayed_result.assignments['frame-1-molecule-1'].class_id == target
    assert c.displayed_result.domain_count == 3
    assert c.series_run.frames[0].assigned == original.assigned_count
    assert c.series_run.frames[0].active == original.active_count
    m.set_editing(True)
    m.redo()
    assert m.class_list.classes[-1].name == 'Nowa nazwa'
    m.undo()
    assert m.class_list.classes[-1].name == 'Fragment'
    assert 'Fragment · 1' in domain_names(c.displayed_result).values()
    m.set_comparison(True)
    assert c.displayed_result.assignments == original.assignments


def test_multiframe_merge_and_split_history_survives_save_after_undo(qtbot, control, tmp_path):
    from test_class_operation_controls import capture, preview, visit
    c, m = control.controller, control.controller.manual
    op = m.class_operations
    capture(qtbot, op, 'whole_series')
    tx = preview(qtbot, op, 'merge', ('A', 'B'), name='C', color='#123456')
    merged_class = tx.after.classes[-1].class_id
    op.apply()
    capture(qtbot, op)
    m.select_molecules(('frame-1-molecule-5',))
    op.remember_selection()
    tx = preview(qtbot, op, 'split', (merged_class,), name='D', color='#abcdef')
    split_class = tx.after.classes[-1].class_id
    op.apply()
    m.undo()
    path = tmp_path / 'multi.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert path.exists()
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_counts[merged_class] == 9
    m.redo()
    assert c.displayed_result.class_counts[split_class] == 1
    assert c.displayed_result.domain_count == 3
    m.undo()
    m.undo()
    assert c.displayed_result.class_counts == {'A': 6, 'B': 3}
    visit(qtbot, c, 1)
    assert c.displayed_result.class_counts == {'A': 4, 'B': 3}
    m.redo()
    qtbot.waitUntil(lambda: not c.is_busy)
    visit(qtbot, c, 1)
    assert c.displayed_result.class_counts[merged_class] == 7


def test_manual_save_lifecycle_cancel_failure_and_save_as(qtbot, control, tmp_path):
    from test_project_window import ProjectPrompts
    c, m = control.controller, control.controller.manual
    prompts = ProjectPrompts(tmp_path / 'first.stmdomains')
    prompts.selection = 'manual:' + m.active.identifier
    actions = control.project_actions
    actions.prompts = prompts
    assert all(a.isEnabled() for a in actions.save_actions)
    actions.save(save_as=True)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert prompts.path.exists() and not actions.dirty
    first = prompts.path.read_bytes()
    m.preview_classes('update', target='A', name='Renamed', color='#123456')
    m.apply()
    assert actions.dirty
    assert not actions.allow_close()
    prompts.path = None
    actions.save(save_as=True)
    assert actions.dirty
    errors = []
    c.prompts.show_error = errors.append
    prompts.path = tmp_path / 'missing' / 'broken.stmdomains'
    actions.save(save_as=True)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert errors and actions.dirty and m.class_list.classes[0].name == 'Renamed'
    prompts.path = tmp_path / 'second.stmdomains'
    actions.save(save_as=True)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert prompts.path.exists() and not actions.dirty
    assert (tmp_path / 'first.stmdomains').read_bytes() == first
    m.undo()
    assert actions.dirty
    m.redo()
    assert not actions.dirty


def test_no_analysis_roundtrip_every_local_edit_and_full_history(qtbot, opened, tmp_path, monkeypatch):
    import numpy as np
    from sklearn.cluster import KMeans
    c, m = opened.controller, opened.controller.manual
    m.set_editing(True)
    variant = m.ensure_variant()
    available = tuple(d.detection_id for d in variant.data.annotations.detections if d.detection_id in variant.eligible_ids)
    keys = tuple(available[i] for i in (0, 1, 9, 10, 3, 4, 12, 13))
    states = []
    for operation, chosen, target in (
        ('new', keys[:3], 0), ('add', keys[3:4], 1), ('new', keys[4:8], 0),
        ('move', keys[6:7], 1), ('remove', keys[6:7], 0),
        ('split', keys[:1], 0), ('merge', (keys[0], keys[1]), 0),
    ):
        m.select_molecules(chosen)
        m.preview(operation, target)
        assert m.preview_result is not None, m.message
        m.apply()
        states.append(c.displayed_result)
    m.preview_classes('create', name='Empty', color='#123456')
    m.apply()
    states.append(c.displayed_result)
    empty = m.class_list.classes[-1].class_id
    m.preview_classes('update', target=empty, name='Changed', color='#abcdef')
    m.apply()
    states.append(c.displayed_result)
    m.preview_classes('delete', target=empty)
    m.apply()
    states.append(c.displayed_result)
    m.select_molecules(keys[:1])
    m.preview_classes('create_assign', name='F', color='#123456')
    m.apply()
    states.append(c.displayed_result)
    m.select_molecules(keys[3:4])
    m.preview_classes('assign', target=m.class_list.classes[-1].class_id)
    m.apply()
    states.append(c.displayed_result)
    path = tmp_path / 'without-analysis.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert path.exists()
    def no_fit(*args, **kwargs):
        raise AssertionError('Reopening must not fit classes')
    monkeypatch.setattr(KMeans, 'fit', no_fit)
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.result is None and c.loaded_project.analysis is None
    assert len(c.loaded_project.manual.undo) == len(states)
    for expected in reversed(states):
        actual = c.displayed_result
        assert actual.assignments == expected.assignments
        if expected.class_list is None:
            assert actual.class_list is None
        else:
            assert actual.class_list.classes == expected.class_list.classes
            assert actual.class_list.version == expected.class_list.version
        np.testing.assert_array_equal(actual.domain_labels, expected.domain_labels)
        m.undo()
    assert c.displayed_result is None
    m.redo()
    assert c.displayed_result.assignments == states[0].assignments
    m.set_comparison(True)
    assert c.displayed_result is None


def test_save_one_source_keeps_other_source_dirty_and_idle_editing_clean(qtbot, opened, tmp_path):
    from test_project_window import ProjectPrompts
    c, m = opened.controller, opened.controller.manual
    prompts = ProjectPrompts(tmp_path / 'plain.stmdomains')
    opened.project_actions.prompts = prompts
    opened.project_actions.save()
    qtbot.waitUntil(lambda: not c.is_busy)
    assert not opened.project_actions.dirty
    m.set_editing(True)
    assert not opened.project_actions.dirty
    keys = tuple(sorted(m.ensure_variant().eligible_ids))[:3]
    m.select_molecules(keys)
    m.preview('new')
    m.apply()
    c.analyze_current_frame()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    m.select_variant('')
    m.ensure_variant()
    m.select_molecules(keys)
    m.preview_classes('create_assign', name='New', color='#123456')
    m.apply()
    prompts.selection = 'manual:' + m.active.identifier
    prompts.path = tmp_path / 'only-automatic-source.stmdomains'
    opened.project_actions.save(save_as=True)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert prompts.path.exists()
    assert opened.project_actions.dirty
    assert 'Pozostają niezapisane' in opened.progress_label.text()


def test_overwriting_saved_project_without_manual_edits_marks_them_unsaved(qtbot, control, tmp_path):
    from test_project_window import ProjectPrompts
    c, m = control.controller, control.controller.manual
    p = ProjectPrompts(tmp_path / 'edited.stmdomains')
    p.selection = 'manual:' + m.active.identifier
    control.project_actions.prompts = p
    control.project_actions.save(save_as=True)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert not control.project_actions.dirty
    p.selection = 'automatic'
    control.project_actions.save()
    qtbot.waitUntil(lambda: not c.is_busy)
    assert control.project_actions.dirty
    assert 'Pozostają niezapisane' in control.progress_label.text()
    assert not control.project_actions.allow_close()


def test_editing_same_automatic_base_after_reopen_resumes_saved_variant(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    identifier = m.active.identifier
    path = tmp_path / 'resume.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    m.select_variant('')
    assert c.displayed_result is c.result
    m.set_editing(True)
    assert m.active.identifier == identifier
    assert c.displayed_result.class_counts == {'A': 6, 'B': 3}


def test_local_geometry_class_list_rebinds_and_resumes_after_reopen(qtbot, opened, tmp_path):
    from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
    c, m = opened.controller, opened.controller.manual
    c.analyze_geometry_domains(GeometryDomainSettings())
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert c.result is not None and c.result.catalogue is None
    m.set_editing(True)
    m.preview_classes('create', name='Local', color='#123456')
    m.apply()
    identifier, labels = m.active.identifier, m.class_list
    path = tmp_path / 'local.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert path.exists()
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert m.class_list.identifier == labels.identifier and m.class_list.version == labels.version
    m.select_variant('')
    m.set_editing(True)
    assert m.active.identifier == identifier
    m.undo()
    assert not m.class_list.classes
    m.redo()
    assert m.class_list.classes[0].name == 'Local'
