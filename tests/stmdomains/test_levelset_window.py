"""Level-set results remain independent through navigation, drafts and persistence."""

import numpy as np

from test_geometry_domain_window import opened
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.ui.project_view import capture_draft, capture_view


def test_levelset_comparison_draft_navigation_and_cancellation(qtbot, opened):
    controller, dialog = opened.controller, opened.analysis_dialog
    assert dialog.method.findData('levelset') >= 0
    controller.analyze_geometry_domains(GeometryDomainSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    geometric = controller.result
    opened.image_view.zoom_by(1.2)
    viewport = opened.image_view.view_state()
    dialog.method.setCurrentIndex(dialog.method.findData('levelset'))
    assert not dialog.geometry_fields.distance.isEnabled()
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    result = controller.result
    assert result.parameters['domain_method'] == 'gibou_fedkiw_features_v1'
    assert result.domain_count > 0
    assert opened.image_view.view_state() == viewport
    opened.method_controls.geometric.click()
    assert controller.result is geometric
    opened.method_controls.levelset.click()
    assert controller.result is result and opened.image_view.view_state() == viewport
    dialog.levelset_fields.regularization.setValue(1.)
    assert controller.result is result
    dialog.calculate.click()
    controller.cancel()
    qtbot.waitUntil(lambda: controller.pending_task_count == 0, timeout=20000)
    assert controller.result is result
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is None
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is result


def test_levelset_save_open_and_export_keep_actual_result(qtbot, opened, tmp_path):
    controller, dialog = opened.controller, opened.analysis_dialog
    dialog.method.setCurrentIndex(dialog.method.findData('levelset'))
    assert dialog.method.currentData() == 'levelset'
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    expected = controller.result
    dialog.levelset_fields.regularization.setValue(.7)
    path = tmp_path/'levelset.stmdomains'
    errors = []
    controller.prompts.show_error = errors.append
    controller.save_project(path, view=capture_view(opened), draft=capture_draft(dialog))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not errors
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not errors
    assert controller.domain_method == 'levelset' and controller.baseline_result is None
    assert controller.result.assignments == expected.assignments
    assert np.array_equal(controller.result.domain_labels, expected.domain_labels)
    assert controller.result.parameters == expected.parameters
    assert dialog.method.currentData() == 'levelset'
    assert dialog.levelset_fields.regularization.value() == .7
    from stmdomains.io.export_tables import table_rows
    from stmdomains.core.project import ProjectSnapshot
    snapshot = ProjectSnapshot(controller.series, analysis=controller.project_analysis())
    rows = table_rows(snapshot, 0, controller.result, controller.presenter.analysis_input(0).annotations)
    assert rows['domains'] and not rows['classes']
    assert all(row['class_id'] == '' for row in rows['domains'])
    assert rows['frames'][0]['assigned_count'] == expected.assigned_count


def test_levelset_manual_revision_survives_reanalysis_save_and_export(qtbot, opened, tmp_path):
    from stmdomains.analysis.levelset_settings import LevelSetSettings
    from test_export_manual import export, rows
    c, m = opened.controller, opened.controller.manual
    c.analyze_levelset_domains(LevelSetSettings())
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    original = c.result
    m.set_editing(True)
    key = next(k for k, a in original.assignments.items() if a.domain_local_id)
    m.select_molecules((key,))
    m.preview_classes('create_assign', name='Ręczna', color='#123456')
    assert m.preview_result is not None, m.message
    m.apply()
    expected, identifier = c.displayed_result, m.active.identifier
    m.set_editing(False)
    c.analyze_levelset_domains(LevelSetSettings(1.))
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert c.result is not original
    assert m.variants[identifier].original is original
    m.select_variant(identifier)
    assert c.displayed_result.assignments == expected.assignments
    path = tmp_path/'corrected.stmdomains'
    c.save_project(path)
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert path.exists()
    c.open_session(path)
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert c.displayed_result.assignments == expected.assignments
    assert np.array_equal(c.displayed_result.domain_labels, expected.domain_labels)
    target = tmp_path/'csv-png'
    export(qtbot, c, target, mode='domains')
    molecule = next(r for r in rows(target, 'molecules') if r['detection_id'] == key)
    assert molecule['class_name'] == 'Ręczna'
    assert molecule['base_class_id'] == '' and molecule['assignment_origin'] == 'manual'
    m.set_editing(True)
    m.undo()
    assert c.displayed_result.assignments == original.assignments
    m.redo()
    assert c.displayed_result.assignments == expected.assignments
