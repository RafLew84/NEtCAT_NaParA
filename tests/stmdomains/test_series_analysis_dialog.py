"""One menu dialog applies class and domain choices to the selected series range."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def test_series_dialog_applies_all_settings_and_exposes_frame_statuses(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    action = window.findChild(QAction, "seriesAnalysisAction")
    assert action is not None and not action.isEnabled()
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    action.trigger()
    dialog = window.series_analysis_dialog
    assert dialog.isVisible() and not dialog.isModal()
    dialog.k.setValue(4)
    dialog.start.setValue(3)
    dialog.end.setValue(2)
    assert not dialog.calculate.isEnabled()
    dialog.start.setValue(1)
    dialog.end.setValue(3)
    assert dialog.fit_start.value() == 1 and dialog.fit_end.value() == 3
    dialog.domain_fields.minimum.setValue(6)
    dialog.domain_fields.link_distance.setValue(1.8)
    assert controller.result is None
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    assert controller.series_run.phase == "complete"
    assert controller.active_catalogue.k == 4 and controller.active_catalogue.frame_indices == (0, 1, 2)
    assert dialog.statuses.rowCount() == 3 and "3/3" in dialog.progress.text()
    for index in range(3):
        controller.show_frame(index)
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result.working_index == index
        assert controller.result.parameters["minimum_domain_size"] == 6
        assert controller.result.parameters["edge_distance_factor"] == 1.8
        assert controller.result.catalogue is controller.active_catalogue
    dialog.fit_source.setCurrentIndex(3)
    assert not dialog.k.isEnabled() and dialog.calculate.isEnabled()
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)


def test_individual_tuning_is_distinguished_from_the_original_series_run(qtbot, tmp_path):
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.tools.class_discovery_demo import create_class_discovery_demo

    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    controller = window.controller
    controller.open_session(create_class_discovery_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.start_series_analysis(SeriesAnalysisPlan(k=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    run, saved = controller.series_run, controller.result
    assert "spoza tego przebiegu" not in window.details_label.text()
    window.domain_settings_action.trigger()
    domain = window.domain_settings_dialog
    domain.minimum.setValue(6)
    qtbot.mouseClick(domain.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.parameters["minimum_domain_size"] == 6
    assert "spoza tego przebiegu" in window.details_label.text()
    assert controller.series_run is run and run.plan.domain_settings.minimum_domain_size == 8
    assert controller.previous_result is saved
    domain.comparison.setCurrentIndex(1)
    assert "spoza tego przebiegu" not in window.details_label.text()
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)
