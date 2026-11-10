"""Reject corrupt histories atomically, even when archive checksums are valid."""

import copy
import json
import zipfile

import pytest

from test_class_operation_controls import control, capture, preview
from test_project_storage import rewrite_part
from stmdomains.io.project import open_project, save_project, ProjectError
from stmdomains.core.project import ProjectSnapshot


def test_bad_manual_references_history_and_membership_leave_open_workspace_intact(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    capture(qtbot, m.class_operations, 'whole_series')
    preview(qtbot, m.class_operations, 'merge', ('A', 'B'), name='C', color='#123456')
    m.class_operations.apply()
    path = tmp_path / 'manual.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert path.exists()
    before = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        state = json.loads(archive.read('manual/state.json'))
        result_path = f"manual/results/{state['variants'][0]['frames'][-1]}.json"
        result = json.loads(archive.read(result_path))
    members = tuple(result['assignments'])
    cases = []
    for mutation in (
        lambda x: x['assignments'].pop(members[0]),
        lambda x: x.update(working_index=99),
        lambda x: x['assignments'][members[0]].update(class_id='unknown-class'),
        lambda x: x['assignments'][members[0]].update(class_id='B'),
        lambda x: x['metadata']['manual_edit'].update(transaction_id='other-transaction'),
        lambda x: x['metadata']['manual_edit'].update(class_list_before='unknown-version'),
        lambda x: x['metadata']['manual_edit'].update(class_sources=['unknown-class']),
        lambda x: x['metadata']['manual_edit'].update(transaction_frames=[99]),
        lambda x: x['metadata']['manual_edit'].update(source_analysis_id='other-source'),
    ):
        changed = copy.deepcopy(result)
        mutation(changed)
        cases.append((result_path, changed))
    for mutation in (
        lambda x: x['variants'][0].update(cursor=0),
        lambda x: x['undo'][-1].update(variant_ids=[x['variants'][0]['identifier']]),
        lambda x: x['revisions'][0]['classes'][0].update(class_id='changed-automatic-id'),
        lambda x: x.update(selected=[[99, x['variants'][0]['identifier']]]),
    ):
        changed = copy.deepcopy(state)
        mutation(changed)
        cases.append(('manual/state.json', changed))
    for part, changed in cases:
        path.write_bytes(before)
        rewrite_part(path, part, json.dumps(changed).encode(), refresh_hash=True)
        with pytest.raises(ProjectError):
            open_project(path)
    errors = []
    c.prompts.show_error = errors.append
    previous, displayed = c.series, c.displayed_result
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert errors and c.series is previous and c.displayed_result is displayed
    assert m.class_list.classes[-1].name == 'C'


def test_legacy_format_has_no_history_and_manual_save_cancellation_is_atomic(qtbot, control, tmp_path):
    from stmdomains.io.project_archive import ProjectCancelled
    c = control.controller
    path = tmp_path / 'legacy.stmdomains'
    c.save_project(path, selection='automatic')
    qtbot.waitUntil(lambda: not c.is_busy)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        project = json.loads(archive.read('project.json'))
    manifest['version'] = 1
    project.pop('manual')
    rewrite_part(path, 'manifest.json', json.dumps(manifest).encode())
    rewrite_part(path, 'project.json', json.dumps(project).encode(), refresh_hash=True)
    legacy = open_project(path)
    assert legacy.manual is None and legacy.analysis is not None
    previous = path.read_bytes()
    manual = c.manual.persistence.snapshot(c.project_analysis(), c.manual.active)
    snapshot = ProjectSnapshot(c.series, analysis=c.project_analysis(), manual=manual)
    cancelled = False
    def cancel_at_manual(message):
        nonlocal cancelled
        if 'historii' in message:
            cancelled = True
    with pytest.raises(ProjectCancelled):
        save_project(path, snapshot, cancelled=lambda: cancelled, progress=cancel_at_manual)
    assert path.read_bytes() == previous
    assert c.manual.persistence.dirty
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert not c.manual.variants and not c.manual.persistence.dirty


def test_pending_preview_cannot_be_silently_omitted_from_save(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    m.preview_classes('update', target='A', name='Pending', color='#abcdef')
    with pytest.raises(ValueError, match='Zatwierdź lub anuluj'):
        c.save_project(tmp_path / 'pending.stmdomains')
    assert m.preview_result is not None and control.project_actions.dirty


def test_multiframe_transaction_cannot_be_split_into_independent_undo_steps(qtbot, control, tmp_path):
    c, m = control.controller, control.controller.manual
    capture(qtbot, m.class_operations, 'whole_series')
    preview(qtbot, m.class_operations, 'merge', ('A', 'B'), target='A')
    m.class_operations.apply()
    path = tmp_path / 'compound.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    with zipfile.ZipFile(path) as archive:
        state = json.loads(archive.read('manual/state.json'))
    step = state['undo'].pop()
    for key in step['variant_ids']:
        state['undo'].append({**step, 'variant_id': key, 'variant_ids': [key]})
    rewrite_part(path, 'manual/state.json', json.dumps(state).encode(), refresh_hash=True)
    with pytest.raises(ProjectError):
        open_project(path)


def test_partial_automatic_run_keeps_uncomputed_frame_with_manual_history(qtbot, control, tmp_path):
    from dataclasses import replace
    c, m = control.controller, control.controller.manual
    base = c.project_analysis()
    partial = replace(base, frames={i: f for i, f in base.frames.items() if i != 2},
                      statuses={**base.statuses, 2: {'status': 'not_run', 'message': 'Przerwano'}},
                      execution={'phase': 'cancelled'})
    manual = m.persistence.snapshot(partial, m.active)
    path = tmp_path / 'partial-manual.stmdomains'
    save_project(path, ProjectSnapshot(c.series, analysis=partial, manual=manual))
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.displayed_result.class_counts == {'A': 6, 'B': 3}
    assert c.series_run.frames[2].status == 'not_run'
    assert 2 not in c.loaded_project.analysis.frames
    c.show_frame(2)
    qtbot.waitUntil(lambda: not c.is_busy)
    assert c.result is None and c.displayed_result is None
