"""Batch results arrive on their own frames and remain browsable after cancellation."""

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.tools.class_discovery_demo import create_class_discovery_demo
from stmdomains.analysis.class_settings import ClassFitSettings
import pytest
from test_analysis_session import controller  # noqa: F401


def test_series_navigation_and_partial_cancel_keep_finished_frames(qtbot, controller, tmp_path):
    controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    views = []
    controller.frame_changed.connect(views.append)
    plan = SeriesAnalysisPlan(start=0, end=4, k=4, fit_source="selected_range", fit_end=1,
                              domain_settings=DomainSettings(minimum_domain_size=6))
    controller.start_series_analysis(plan)
    assert controller.series_running and controller.series_run.phase == "fitting"
    controller.show_frame(4)
    qtbot.waitUntil(lambda: controller.current_index == 4)
    assert controller.series_running
    qtbot.waitUntil(lambda: controller.series_run.frames[0].status == "complete", timeout=15000)
    controller.cancel()
    qtbot.waitUntil(lambda: not controller.pending_task_count, timeout=15000)
    assert controller.series_run.phase == "cancelled" and not controller.series_running
    assert controller.series_run.frames[4].status == "not_run"
    assert controller.result is None
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    result = controller.result
    assert result is not None and result.catalogue is controller.active_catalogue
    assert result.parameters["minimum_domain_size"] == 6
    assert all(v.result is None or v.frame.working_index == v.result.working_index for v in views)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.assignments == result.assignments
    assert not controller.prompts.errors


@pytest.mark.parametrize("action", ["cancel", "reopen", "shutdown"])
def test_fit_cancel_reopen_and_shutdown_never_publish_late_catalogue(qtbot, controller, tmp_path, action):
    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.fit_current_classes(ClassFitSettings(k=4))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    saved, active = controller.result, controller.active_catalogue
    observed = []

    def act():
        run = controller.series_run
        if run and run.phase == "fitting" and "Kalibracja" in run.message and not observed:
            observed.append(True)
            if action == "reopen":
                controller.open_session(path)
            elif action == "shutdown":
                controller.shutdown()
            else:
                controller.cancel()

    controller.series_analysis_changed.connect(act)
    controller.start_series_analysis(SeriesAnalysisPlan(whole_series=True))
    qtbot.waitUntil(lambda: bool(observed) and not controller.pending_task_count, timeout=15000)
    if action == "reopen":
        assert controller.result is controller.active_catalogue is controller.series_run is None
    else:
        assert controller.result is saved and controller.active_catalogue is active
        assert controller.series_run.phase == "cancelled"
        assert all(row.status == "not_run" for row in controller.series_run.frames.values())
    assert not controller.prompts.errors


def test_failed_fit_preserves_good_result_then_same_series_can_run_again(qtbot, controller, tmp_path):
    controller.open_session(create_class_discovery_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.fit_current_classes(ClassFitSettings(k=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    saved, active = controller.result, controller.active_catalogue
    controller.start_series_analysis(SeriesAnalysisPlan(k=8))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.series_run.phase == "failed"
    assert controller.result is saved and controller.active_catalogue is active
    assert "K8" in controller.prompts.errors[-1]
    controller.start_series_analysis(SeriesAnalysisPlan(k=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.series_run.phase == "complete"
    assert controller.result.catalogue.scope == "selected_range"
    assert controller.previous_result is saved
    assert controller.result.metadata["series_analysis"]["run_id"] == controller.series_run.identifier


def test_repeated_batches_and_browsing_keep_only_two_versions_per_frame(qtbot, controller, tmp_path):
    controller.open_session(create_class_discovery_demo(tmp_path)["pair_b"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.start_series_analysis(SeriesAnalysisPlan(whole_series=True))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    run = controller.series_run
    assert run.frames[2].status == "no_annotations"
    catalogue = controller.active_catalogue
    first = controller.result
    for minimum in (6, 7):
        controller.start_series_analysis(SeriesAnalysisPlan(whole_series=True, fit_source="existing",
                                            domain_settings=DomainSettings(minimum_domain_size=minimum)))
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
        assert controller.result.catalogue is catalogue and controller.previous_result is first
        first = controller.result
    for index in (2, 1, 0, 2, 1, 0):
        controller.show_frame(index)
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result.working_index == index
        assert controller.presenter.image_cache_bytes <= 32 * 1024**2
    assert controller.result is first
    assert controller.previous_result.parameters["minimum_domain_size"] == 6
    assert not controller.prompts.errors
