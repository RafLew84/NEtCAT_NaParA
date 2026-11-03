"""Opening/saving publishes work only after a complete successful operation."""

from stmdomains.tools.auto_classes_demo import create_auto_demo
from stmdomains.ui.session_controller import SessionController
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from test_analysis_window import Prompts


def test_controller_restores_selected_run_and_keeps_old_work_on_bad_open(qtbot, tmp_path):
    prompts = Prompts()
    errors = []
    prompts.show_error = errors.append
    controller = SessionController(prompts)
    controller.open_session(create_auto_demo(tmp_path / 'source'))
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.start_series_analysis(SeriesAnalysisPlan(end=1, class_count_mode='auto'))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    expected = controller.result
    path = tmp_path / 'work.stmdomains'
    controller.save_project(path, view={'current_index': 0, 'mode': 'raw', 'gamma': 1.3}, draft={'k': 7})
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert path.exists() and controller.project_path == path
    controller.series.source_path.unlink()
    controller.series.session_path.unlink()
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.assignments == expected.assignments
    assert controller.result.catalogue.identifier == expected.catalogue.identifier
    assert controller.series_run.processed_count == 2 and controller.gamma == 1.3
    assert controller.loaded_project.draft['k'] == 7
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is not None
    old = controller.series
    bad = tmp_path / 'bad.stmdomains'
    bad.write_bytes(b'not a zip')
    controller.open_session(bad)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.series is old and controller.result is not None
    assert len(errors) == 1
    controller.shutdown()
    controller.wait_for_workers()


def test_displayed_previous_and_latest_refusal_are_separate_saved_runs(qtbot, tmp_path):
    from stmdomains.io.project import open_project
    from test_analysis_session import Prompts as CollectingPrompts
    controller = SessionController(CollectingPrompts())
    controller.open_session(create_auto_demo(tmp_path / 'source'))
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.start_series_analysis(SeriesAnalysisPlan(start=1, current_frame=True, class_count_mode='auto'))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    good = controller.result
    good_id = controller.series_run.identifier
    controller.start_series_analysis(SeriesAnalysisPlan(start=1, current_frame=True, class_count_mode='auto', auto_max_k=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    assert controller.result is good and controller.series_run.selection['selected_k'] is None
    refused_id = controller.series_run.identifier
    for selection, identifier in (('displayed', good_id), ('latest', refused_id)):
        path = tmp_path / f'{selection}.stmdomains'
        controller.save_project(path, selection=selection)
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
        assert not controller.prompts.errors
        snapshot = open_project(path)
        assert snapshot.analysis.identifier == identifier
        if selection == 'displayed':
            result = snapshot.analysis.frames[1]
            assert result.assignments == good.assignments
            assert snapshot.analysis.statuses[1]['assigned'] == good.assigned_count
        else:
            assert snapshot.analysis.execution['selection']['selected_k'] is None
            assert snapshot.analysis.frames[1].status == 'insufficient_data'
    controller.shutdown()
    controller.wait_for_workers()


def test_cancelled_run_restores_done_and_not_run_frames_without_fabricated_zeros(qtbot, tmp_path):
    from stmdomains.tools.analysis_demo import create_analysis_demo
    from test_analysis_session import Prompts as CollectingPrompts
    controller = SessionController(CollectingPrompts())
    controller.open_session(create_analysis_demo(tmp_path / 'source')['series'])
    qtbot.waitUntil(lambda: not controller.is_busy)
    def stop_after_first():
        run = controller.series_run
        if controller.series_running and run.frames[0].status == 'complete':
            controller.cancel()
    controller.series_analysis_changed.connect(stop_after_first)
    controller.start_series_analysis(SeriesAnalysisPlan(end=4, k=4, fit_source='selected_range', fit_end=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    assert controller.series_run.phase == 'cancelled'
    path = tmp_path / 'partial.stmdomains'
    controller.save_project(path, selection='latest')
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not controller.prompts.errors
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert not controller.prompts.errors
    assert controller.series_run.processed_count == 1
    assert controller.series_run.frames[4].status == 'not_run'
    assert controller.result is not None and controller.result.status == 'complete'
    controller.show_frame(4)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is None
    controller.shutdown()
    controller.wait_for_workers()
