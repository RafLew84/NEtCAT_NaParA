"""The shared draft reaches one frame and the whole selected range unchanged."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def test_all_tabs_apply_to_single_and_series_without_changing_the_draft(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    action = window.findChild(QAction, "analysisAction")
    assert action is not None and not action.isEnabled()
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    dialog = window.analysis_dialog
    assert dialog.isVisible() and not dialog.isModal() and controller.result is None
    assert [dialog.tabs.tabText(i) for i in range(4)] == ["Zakres", "Klasy", "Porządek", "Domeny"]
    classes = dialog.class_fields
    classes.k.setValue(4)
    classes.fit_source.setCurrentIndex(classes.fit_source.findData("selected_range"))
    classes.fit_start.setValue(1)
    classes.fit_end.setValue(2)
    dialog.acceptance_fields.margin.setValue(.06)
    dialog.acceptance_fields.radius.setValue(.8)
    dialog.order_fields.quantile.setValue(.925)
    dialog.domain_fields.minimum.setValue(6)
    dialog.domain_fields.link_distance.setValue(1.8)
    draft = dialog.plan()
    dialog.close()
    action.trigger()
    assert dialog.plan() == draft
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    single = controller.result
    catalogue = single.catalogue
    assert catalogue.frame_indices == (0, 1) and single.parameters["class_margin"] == .06
    assert dialog.statuses.rowCount() == 1
    classes.mode.setCurrentIndex(classes.mode.findData("existing"))
    assert classes.selected_catalogue is catalogue
    dialog.scope_fields.scope.setCurrentIndex(1)
    dialog.scope_fields.end.setValue(3)
    planned = dialog.plan()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    controller.show_frame(2)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=20000)
    assert controller.series_run.plan == planned
    assert dialog.plan() == planned and dialog.statuses.rowCount() == 3
    for index in range(3):
        controller.show_frame(index)
        qtbot.waitUntil(lambda: not controller.is_busy)
        result = controller.result
        assert result.catalogue is catalogue and result.parameters["class_radius_multiplier"] == .8
        assert result.parameters["order_quantile"] == .925
        assert result.parameters["minimum_domain_size"] == 6
        if index == 0:
            assert result.assignments == single.assignments
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)


def test_single_frame_target_stays_frozen_while_browsing(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    window.analysis_action.trigger()
    dialog = window.analysis_dialog
    dialog.class_fields.k.setValue(4)
    dialog.calculate.click()
    assert not dialog.tabs.isEnabled() and dialog.cancel.isEnabled()
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.current_index == 1 and controller.result is None
    assert controller.series_run.indices == (0,)
    assert controller.series_run.frames[0].status == "complete"
    assert dialog.plan().start == 1 and dialog.plan().k == 4
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result.catalogue.scope == "current_frame"
    assert controller.result.catalogue.frame_indices == (0,)
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)


def test_comparison_never_changes_draft_or_catalogue_until_explicit_copy(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    controller = window.controller
    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    window.analysis_action.trigger()
    dialog, classes = window.analysis_dialog, window.analysis_dialog.class_fields
    classes.k.setValue(4)
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    local = controller.result
    classes.k.setValue(5)
    classes.fit_source.setCurrentIndex(1)
    classes.fit_end.setValue(2)
    dialog.acceptance_fields.margin.setValue(.06)
    dialog.order_fields.radius.setValue(2.)
    dialog.order_fields.sigma.setValue(1.)
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    shared = controller.result
    classes.mode.setCurrentIndex(1)
    draft = dialog.plan()
    dialog.comparison.setCurrentIndex(1)
    assert controller.result is local and dialog.plan() == draft
    assert classes.selected_catalogue is shared.catalogue
    dialog.copy_result.click()
    assert classes.selected_catalogue is local.catalogue
    assert classes.k.value() == 4  # The disabled K display must describe the chosen catalogue.
    assert dialog.acceptance_fields.margin.value() == .075
    assert dialog.order_fields.settings().order_sigma_factor == 4 / 3
    dialog.scope_fields.scope.setCurrentIndex(1)
    dialog.scope_fields.end.setValue(2)
    assert not dialog.calculate.isEnabled() and "wspólny katalog" in dialog.validation.text()
    dialog.baseline.click()
    assert classes.mode.currentData() == "existing" and dialog.scope_fields.end.value() == 2
    assert not dialog.calculate.isEnabled()
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    assert dialog.scope_fields.scope.currentData() == "current_frame" and dialog.calculate.isEnabled()
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert not dialog.calculate.isEnabled() and "innej klatki" in dialog.validation.text()
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert classes.mode.currentData() == "new" and classes.k.value() == 5
    assert classes.selected_catalogue is None and dialog.statuses.rowCount() == 0
    assert dialog.calculate.isEnabled() and "Nowa seria" in dialog.progress.text()
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)
