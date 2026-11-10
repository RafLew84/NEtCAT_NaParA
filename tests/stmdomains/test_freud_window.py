"""Panel A uses native calculations and retains the other method's exact result."""

from test_geometry_domain_window import opened  # shared real-data Qt fixture


def test_panel_a_calculates_without_k_and_switches_preserved_results(qtbot, opened):
    controller, dialog = opened.controller, opened.analysis_dialog
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    baseline = controller.result
    index = dialog.method.findData('freud')
    assert index >= 0
    dialog.method.setCurrentIndex(index)
    assert not dialog.tabs.isTabVisible(1)
    dialog.freud_fields.tolerance.setValue(.12)
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    result = controller.result
    assert result.parameters['freud_settings']['tolerance'] == .12
    assert result.domain_count > 0 and result.catalogue is None
    assert controller.domain_method == 'freud'
    assert controller.baseline_result is baseline
    controller.select_domain_method('baseline')
    assert controller.result is baseline
    controller.select_domain_method('freud')
    assert controller.result is result


def test_freud_project_restores_applied_result_and_distinct_draft(qtbot, opened, tmp_path):
    from stmdomains.analysis.freud_settings import FreudSettings
    from stmdomains.ui.project_view import capture_draft, capture_view
    from stmdomains.io.export_tables import table_rows
    from stmdomains.core.project import ProjectSnapshot
    controller, dialog = opened.controller, opened.analysis_dialog
    errors = []
    controller.prompts.show_error = errors.append
    controller.analyze_freud_domains(FreudSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    expected = controller.result
    dialog.method.setCurrentIndex(dialog.method.findData('freud'))
    dialog.freud_fields.tolerance.setValue(.3)
    path = tmp_path/'freud.stmdomains'
    controller.save_project(path, view=capture_view(opened), draft=capture_draft(dialog))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not errors
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not errors
    assert controller.domain_method == 'freud' and controller.baseline_result is None
    assert controller.result.assignments == expected.assignments
    assert dialog.method.currentData() == 'freud' and dialog.freud_fields.tolerance.value() == .3
    assert controller.result.parameters['freud_settings']['tolerance'] == .2
    snapshot = ProjectSnapshot(controller.series, analysis=controller.project_analysis())
    rows = table_rows(snapshot, 0, controller.result, controller.presenter.analysis_input(0).annotations)
    assert rows['domains'] and rows['classes']
    restored = controller.result
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    controller.select_domain_method('freud')
    assert controller.result is restored


def test_cancel_error_and_frame_change_keep_completed_results(qtbot, opened, monkeypatch):
    from stmdomains.analysis.freud_settings import FreudSettings
    from stmdomains.analysis import freud_adapter
    controller = opened.controller
    controller.analyze_freud_domains(FreudSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    expected = controller.result
    controller.analyze_freud_domains(FreudSettings(registration=True))
    qtbot.wait(150)
    controller.cancel()
    qtbot.waitUntil(lambda: controller.pending_task_count == 0, timeout=10000)
    assert controller.result is expected
    errors = []
    controller.prompts.show_error = errors.append
    with monkeypatch.context() as patch:
        patch.setattr(freud_adapter.importlib.util, 'find_spec', lambda name: None)
        controller.analyze_freud_domains(FreudSettings())
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=10000)
    assert errors and controller.result is expected
    controller.analyze_freud_domains(FreudSettings(registration=True))
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=10000)
    assert controller.result is None
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=10000)
    assert controller.result is expected


def test_neighbour_overlay_follows_aligned_image_and_clears_on_frame_change(qtbot, opened):
    from PyQt6.QtCore import QPointF, Qt
    from stmdomains.analysis.freud_settings import FreudSettings
    controller, image = opened.controller, opened.image_view
    controller.analyze_freud_domains(FreudSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    result = controller.result
    identity = next(k for k, m in result.assignments.items() if m.domain_local_id)
    for mode in ('raw', 'expanded_aligned'):
        controller.set_view_mode(mode)
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=10000)
        detection = next(d for d in opened._presented.annotations.detections if d.detection_id == identity)
        if mode == 'expanded_aligned':
            assert len(image.freud_overlay.segments()) == 4
            assert image.freud_overlay.segments()[0].p1() == QPointF(*detection.center_xy)
        point = image.mapFromScene(QPointF(*detection.center_xy))
        qtbot.mouseClick(image.viewport(), Qt.MouseButton.LeftButton, pos=point)
        lines = image.freud_overlay.segments()
        assert len(lines) == 4
        assert lines[0].p1() == QPointF(*detection.center_xy)
        assert opened._selected.detection_id == identity
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=10000)
    assert not image.freud_overlay.segments()
