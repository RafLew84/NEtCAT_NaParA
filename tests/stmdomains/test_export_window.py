"""Use the real menu and dialog; exported files must describe the chosen result."""

import csv
import json

from stmdomains.ui.main_window import STMDomainsMainWindow
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from test_analysis_session import Prompts


def test_menu_exports_partial_range_and_preserves_display_and_draft(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path / 'source')['series'])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.start_series_analysis(SeriesAnalysisPlan(k=4, current_frame=True))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    result = controller.result
    window.analysis_dialog.class_fields.k.setValue(7)
    window.export_action.trigger()
    dialog = window.export_dialog
    assert dialog.isVisible()
    dialog.folder.setText(str(tmp_path))
    dialog.name.setText('results')
    dialog.scope.setCurrentIndex(1)
    dialog.first.setValue(1)
    dialog.last.setValue(2)
    dialog.export_button.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    assert not controller.prompts.errors
    target = tmp_path / 'results'
    assert (target / 'frame-000001.png').exists() and (target / 'frame-000002.png').exists()
    with (target / 'frames.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert int(rows[0]['assigned_count']) == result.assigned_count
    assert rows[1]['assigned_count'] == ''
    from PyQt6.QtGui import QImage
    png_metadata = json.loads(QImage(str(target / 'frame-000002.png')).text('STM Domains'))
    assert png_metadata['analysis_status'] == rows[1]['analysis_status']
    assert png_metadata['analysis_id'] == rows[1]['analysis_id']
    assert controller.result is result and controller.current_index == 0
    assert window.analysis_dialog.class_fields.k.value() == 7
    assert json.loads((target / 'frame-000001.json').read_text())['parameters']['k'] == 4
    assert 'Zapisano' in dialog.status.text()
    window.close()


def test_default_export_scope_follows_single_result_after_navigation(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path / 'source')['series'])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.start_series_analysis(SeriesAnalysisPlan(k=4, current_frame=True))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    result = controller.result
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is None
    window.export_action.trigger()
    dialog = window.export_dialog
    assert dialog.selection.currentData() == 'latest'
    assert dialog.scope.currentData() == 'range'
    assert dialog.first.value() == dialog.last.value() == 1
    dialog.folder.setText(str(tmp_path))
    dialog.name.setText('single-result')
    dialog.png.setChecked(False)
    dialog.export_button.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    with (tmp_path / 'single-result' / 'frames.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]['working_number'] == '1'
    assert int(rows[0]['assigned_count']) == result.assigned_count
    assert controller.current_index == 1 and controller.result is None
    window.close()


def test_cancel_and_error_leave_open_work_and_shutdown_does_not_wait_for_gui(qtbot, tmp_path, monkeypatch):
    from threading import Event, Timer
    from pathlib import Path
    from stmdomains.core.export import ExportOptions
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path / 'source')['series'])
    qtbot.waitUntil(lambda: not controller.is_busy)
    series = controller.series
    entered, release = Event(), Event()
    write = Path.write_bytes
    def delayed_write(path, data):
        if path.name == 'frame-000001.json':
            entered.set()
            assert release.wait(5)
        return write(path, data)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'write_bytes', delayed_write)
        controller.start_export(tmp_path / 'cancelled', (0, 1), ExportOptions(), view={}, selection='none')
        qtbot.waitUntil(entered.is_set)
        controller.cancel()
        release.set()
        qtbot.waitUntil(lambda: controller.pending_task_count == 0)
    assert controller.series is series and not (tmp_path / 'cancelled').exists()
    controller.start_export(tmp_path / 'missing' / 'output', (0,), ExportOptions(), view={}, selection='none')
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.prompts.errors and controller.series is series
    entered.clear()
    release.clear()
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'write_bytes', delayed_write)
        controller.start_export(tmp_path / 'closed', (0,), ExportOptions(), view={}, selection='none')
        qtbot.waitUntil(entered.is_set)
        window.close()
        Timer(.1, release.set).start()
        window._finish_background_work()
    assert not (tmp_path / 'closed').exists() and not window.isVisible()
