"""Export the applied editing state through the running application's public API."""

import csv
import json

from PyQt6.QtGui import QImage

from stmdomains.core.export import ExportOptions
from test_class_operation_controls import control
from test_class_operation_controls import capture, preview, visit
from test_manual_window import opened


def rows(path, table):
    with (path / f'{table}.csv').open(encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def export(qtbot, c, path, indices=(0,), selection='displayed', mode='classes'):
    c.start_export(path, indices, ExportOptions(image_width=640),
                   view={'assignment_mode': mode}, selection=selection)
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert path.exists(), c.export_message
    return rows(path, 'frames')


def test_export_applied_class_only_edit_and_original_have_separate_counts(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    before, dirty = c.displayed_result, m.persistence.dirty
    target = tmp_path / 'corrected'
    frame = export(qtbot, c, target)[0]
    assert frame['result_variant'] == 'after_corrections'
    assert frame['frame_state'] == 'corrected'
    assert frame['assigned_count'] == '7'
    assert frame['class_assigned_count'] == '9'
    assert frame['manual_class_assigned_count'] == '2'
    assert frame['automatic_class_assigned_count'] == '7'
    classes = {r['class_id']: r for r in rows(target, 'classes')}
    assert classes['A']['assigned_count'] == '6'
    assert classes['A']['class_only_count'] == '2'
    molecules = {r['detection_id']: r for r in rows(target, 'molecules')}
    assert sum(r['assignment_origin'] == 'manual' for r in molecules.values()) == 2
    changed = next(r for r in molecules.values() if r['assignment_origin'] == 'manual')
    assert changed['base_class_id'] == '' and changed['class_id'] == 'A'
    assert changed['domain_local_id'] == '0' and changed['correction_revision'] != ''
    png = json.loads(QImage(str(target / 'frame-000001.png')).text('STM Domains'))
    assert 'Po korektach' in png['caption']
    assert next(e['count'] for e in png['legend'] if e['label'] == 'Klasa A') == 6
    original = tmp_path / 'original'
    base = export(qtbot, c, original, selection='base')[0]
    assert base['result_variant'] == 'automatic'
    assert base['class_assigned_count'] == '7' and base['manual_class_assigned_count'] == '0'
    assert c.displayed_result is before and m.persistence.dirty == dirty


def test_export_menu_defaults_to_corrections_and_names_original_explicitly(qtbot, control, tmp_path):
    assert control.export_action.isEnabled()
    control.export_action.trigger()
    dialog = control.export_dialog
    assert dialog.selection.currentData() == 'displayed'
    assert 'Po korektach' in dialog.selection.currentText()
    assert dialog.selection.findData('base') >= 0
    dialog.folder.setText(str(tmp_path))
    dialog.name.setText('from-menu')
    dialog.scope.setCurrentIndex(dialog.scope.findData('current'))
    dialog.export_button.click()
    qtbot.waitUntil(lambda: not control.controller.is_busy)
    assert rows(tmp_path / 'from-menu', 'frames')[0]['class_only_count'] == '2'


def test_manual_without_model_and_unsupported_area_do_not_invent_automatic_zero(qtbot, opened, tmp_path):
    import pytest
    c, m = opened.controller, opened.controller.manual
    m.set_editing(True)
    key = next(d.detection_id for d in c.presenter.analysis_input(0).annotations.detections)
    m.select_molecules((key,))
    m.preview('new')
    m.apply()
    m.select_molecules((key,))
    m.preview_classes('create_assign', name='Własna', color='#123456')
    assert m.preview_result is not None, m.message
    m.apply()
    assert c.result is None
    target = tmp_path / 'manual-only'
    first, absent = export(qtbot, c, target, (0, 1))
    assert first['frame_state'] == 'manual_only' and first['automatic_available'] == '0'
    assert first['base_analysis_id'] == first['catalogue_id'] == ''
    assert first['assigned_count'] == first['manual_assigned_count'] == '1'
    assert first['approx_area_px2'] == '' and first['approx_area_status'] == 'unavailable'
    assert absent['frame_state'] == 'unanalysed' and absent['assigned_count'] == ''
    member = next(r for r in rows(target, 'molecules') if r['detection_id'] == key and r['working_index'] == '0')
    assert member['base_domain_local_id'] == '' and member['base_class_id'] == ''
    assert member['class_name'] == 'Własna' and member['class_color'] == '#123456'
    assert member['class_origin'] == 'manual'
    assert rows(target, 'classes')[0]['touches_field_edge'] == ''
    with pytest.raises(ValueError, match='Brak bazowego'):
        c.start_export(tmp_path / 'missing-base', (0,), ExportOptions(), view={}, selection='base')
    opened.export_action.trigger()
    assert opened.export_dialog.selection.findData('base') == -1
    assert 'Brak bazowego' in opened.export_dialog.status.text()


def test_export_multiframe_class_merge_split_and_undo_keep_domains_separate(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    op = m.class_operations
    capture(qtbot, op, 'whole_series')
    tx = preview(qtbot, op, 'merge', ('A', 'B'), name='Połączona', color='#123456')
    target_class = tx.after.classes[-1].class_id
    op.apply()
    target = tmp_path / 'merged'
    frames = export(qtbot, c, target, (0, 1, 2))
    assert [r['class_assigned_count'] for r in frames] == ['9', '7', '7']
    assert [r['domain_count'] for r in frames] == ['2', '2', '2']
    assert frames[2]['frame_state'] == 'automatic'
    assert {r['class_id'] for r in rows(target, 'domains') if r['working_index'] == '2'} == {'A', 'B'}
    for index in (0, 1):
        meta = json.loads((target / f'frame-{index+1:06d}.json').read_text())
        merge = meta['applied_operations'][-1]
        assert merge['class_operation'] == 'merge' and merge['transaction_frames'] == [0, 1]
        assert merge['class_sources'] == ['A', 'B']
        groups = [r for r in rows(target, 'domains') if r['working_index'] == str(index)]
        assert len(groups) == 2 and {r['class_id'] for r in groups} == {target_class}
    capture(qtbot, op, 'selected_range', 0, 1)
    for index in (0, 1):
        visit(qtbot, c, index)
        m.select_molecules((f'frame-{index+1}-molecule-1',))
        op.remember_selection()
    preview(qtbot, op, 'split', (target_class,), name='Wydzielona', color='#abcdef')
    op.apply()
    split = export(qtbot, c, tmp_path / 'split', (0, 1))
    assert [r['domain_count'] for r in split] == ['3', '3']
    m.undo()
    qtbot.waitUntil(lambda: not c.is_busy)
    undone = export(qtbot, c, tmp_path / 'undo', (0, 1))
    assert [r['correction_revision'] for r in undone] == [r['correction_revision'] for r in frames[:2]]
    m.redo()
    qtbot.waitUntil(lambda: not c.is_busy)
    redone = export(qtbot, c, tmp_path / 'redo', (0, 1))
    assert redone == split


def test_domain_edits_and_frozen_export_preserve_the_exact_selected_state(qtbot, control, tmp_path):
    from stmdomains.ui.export_selection import capture_export
    from stmdomains.io.export_results import export_results
    c, m = control.controller, control.controller.manual
    keys = ('frame-1-molecule-1', 'frame-1-molecule-2')
    original = c.result
    for operation, target in (('split', 0), ('merge', 1), ('remove', 0), ('new', 0), ('remove', 0), ('add', 1)):
        selected = (keys[0], 'frame-1-molecule-3') if operation == 'merge' else keys
        m.select_molecules(selected)
        m.preview(operation, target)
        assert m.preview_result is not None, m.message
        m.apply()
        expected = c.displayed_result
        name = f'{operation}-{expected.metadata["manual_edit"]["revision"]}'
        output = tmp_path / name
        export(qtbot, c, output, mode='domains')
        actual = {r['detection_id']: r for r in rows(output, 'molecules')}
        assert {k: (r['class_id'], int(r['domain_local_id'])) for k, r in actual.items()} == {
            k: (r.class_id, r.domain_local_id) for k, r in expected.assignments.items()}
        assert rows(output, 'frames')[0]['domain_count'] == str(expected.domain_count)
        png = json.loads(QImage(str(output / 'frame-000001.png')).text('STM Domains'))
        assert sum(e['count'] for e in png['legend'] if e['label'].startswith('Domena ')) == expected.assigned_count
    frozen = capture_export(c, 'displayed', {})
    exported_state = c.displayed_result
    m.undo()
    export_results(tmp_path / 'frozen', frozen, (0,), ExportOptions(png=False))
    frozen_rows = rows(tmp_path / 'frozen', 'molecules')
    assert next(r for r in frozen_rows if r['detection_id'] == keys[0])['domain_local_id'] == '1'
    assert c.displayed_result is not exported_state
    assert c.result is original


def test_export_cancel_error_and_preview_leave_dirty_work_and_history(qtbot, control, tmp_path, monkeypatch):
    from pathlib import Path
    from threading import Event
    import pytest
    c, m = control.controller, control.controller.manual
    from test_analysis_session import Prompts
    c.prompts = Prompts()
    before = c.displayed_result
    entered, release = Event(), Event()
    write = Path.write_bytes
    def delayed_write(path, data):
        if path.name == 'frame-000001.json':
            entered.set()
            assert release.wait(5)
        return write(path, data)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'write_bytes', delayed_write)
        c.start_export(tmp_path / 'cancelled', (0, 1), ExportOptions(), view={})
        qtbot.waitUntil(entered.is_set)
        c.cancel()
        release.set()
        qtbot.waitUntil(lambda: c.pending_task_count == 0)
    assert not (tmp_path / 'cancelled').exists()
    c.start_export(tmp_path / 'missing-parent' / 'error', (0,), ExportOptions(), view={})
    qtbot.waitUntil(lambda: not c.is_busy)
    assert 'Błąd eksportu' in c.export_message
    assert c.displayed_result is before and m.persistence.dirty
    m.select_molecules(('frame-1-molecule-1',))
    m.preview_classes('assign', target='B')
    with pytest.raises(ValueError, match='podgląd'):
        c.start_export(tmp_path / 'preview', (0,), ExportOptions(), view={})
    m.cancel_preview()
    m.undo()
    assert c.displayed_result.class_counts == {'A': 4, 'B': 3}
    m.redo()
    assert c.displayed_result is before


def test_shared_class_rename_exports_unvisited_frames_with_same_frozen_revision(qtbot, control, tmp_path):
    from stmdomains.ui.export_selection import capture_export
    from stmdomains.io.export_results import export_results
    c, m = control.controller, control.controller.manual
    m.preview_classes('update', target='A', name='Wspólna nazwa', color='#123456')
    m.apply()
    revision = m.class_list.version
    frozen = capture_export(c, 'displayed', {})
    variants = tuple(m.variants)
    path = tmp_path / 'shared'
    frames = export(qtbot, c, path, (0, 1, 2))
    assert frames[1]['frame_state'] == 'corrected'
    assert frames[1]['class_list_revision'] == frames[0]['class_list_revision'] == revision
    assert frames[2]['frame_state'] == 'automatic'
    assert tuple(m.variants) == variants
    classes = {r['class_name'] for r in rows(path, 'classes') if r['working_index'] == '1'}
    assert classes == {'Wspólna nazwa', 'B'}
    m.undo()
    export_results(tmp_path / 'shared-frozen', frozen, (1,), ExportOptions(png=False))
    assert rows(tmp_path / 'shared-frozen', 'frames')[0]['class_list_revision'] == revision
    original = export(qtbot, c, tmp_path / 'shared-base', (1,), selection='base')[0]
    assert original['class_list_revision'] == ''
