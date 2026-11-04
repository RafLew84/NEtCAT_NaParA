"""Panel A applies drafts and compares actual results on the same image."""

import pytest
from PyQt6.QtCore import Qt

from test_analysis_window import Prompts
from stmdomains.tools.geometry_demo import create_geometry_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


@pytest.fixture
def opened(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    paths = create_geometry_demo(tmp_path)
    window.controller.open_session(paths['series'])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    yield window
    window.close()
    window._finish_background_work()


def test_panel_a_compares_without_moving_image_and_cancel_keeps_results(qtbot, opened):
    controller, dialog = opened.controller, opened.analysis_dialog
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    baseline = controller.result
    opened.image_view.zoom_by(1.2)
    viewport = opened.image_view.view_state()
    dialog.show()
    dialog.method.setCurrentIndex(1)
    assert dialog.calculate.isEnabled()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    geometric = controller.result
    assert geometric is not baseline and geometric.parameters['domain_method'] == 'geometry_tolerances_v1'
    assert controller.geometry is not None
    assert not dialog.isVisible()
    assert opened.image_view.view_state() == viewport
    opened.method_controls.baseline.click()
    assert controller.result is baseline
    assert opened.image_view.view_state() == viewport
    opened.method_controls.geometric.click()
    assert controller.result is geometric
    dialog.show()
    dialog.geometry_fields.angle.setValue(5.)
    assert controller.result is geometric
    dialog.calculate.click()
    controller.cancel()
    qtbot.waitUntil(lambda: controller.pending_task_count == 0, timeout=15000)
    assert controller.result is geometric
    controller.select_domain_method('baseline')
    assert controller.result is baseline


def test_geometric_result_and_draft_survive_project_save_and_export(qtbot, opened, tmp_path):
    import numpy as np
    from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
    from stmdomains.ui.project_view import capture_draft, capture_view
    from stmdomains.io.export_tables import table_rows
    from stmdomains.core.project import ProjectSnapshot
    controller, dialog = opened.controller, opened.analysis_dialog
    controller.analyze_geometry_domains(GeometryDomainSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    expected = controller.result
    assert expected.domain_count > 0
    dialog.method.setCurrentIndex(1)
    dialog.geometry_fields.angle.setValue(7.)
    path = tmp_path / 'geometry.stmdomains'
    errors = []
    controller.prompts.show_error = errors.append
    controller.save_project(path, view=capture_view(opened), draft=capture_draft(dialog))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not errors
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not errors
    assert controller.domain_method == 'geometry' and controller.baseline_result is None
    assert controller.result.assignments == expected.assignments
    assert np.array_equal(controller.result.domain_labels, expected.domain_labels)
    assert dialog.method.currentData() == 'geometry' and dialog.geometry_fields.angle.value() == 7.
    snapshot = ProjectSnapshot(controller.series, analysis=controller.project_analysis())
    rows = table_rows(snapshot, 0, controller.result, controller.presenter.analysis_input(0).annotations)
    assert rows['domains'] and not rows['classes']
    assert all(row['class_id'] == '' for row in rows['domains'])
    assert rows['frames'][0]['assigned_count'] == expected.assigned_count

    restored = controller.result
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.domain_method == 'baseline'
    controller.select_domain_method('geometry')
    assert controller.result is restored
