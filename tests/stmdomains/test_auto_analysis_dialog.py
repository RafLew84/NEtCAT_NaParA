"""Auto selection remains explicit in the common draft and in completed results."""

from PyQt6.QtWidgets import QDialog

from stmdomains.tools.auto_classes_demo import create_auto_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def open_demo(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(create_auto_demo(tmp_path))
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.analysis_action.trigger()
    return window, window.controller, window.analysis_dialog


def calculate(qtbot, controller, dialog):
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=25000)


def test_auto_manual_comparison_draft_and_ranking(qtbot, tmp_path):
    window, controller, dialog = open_demo(qtbot, tmp_path)
    classes = dialog.class_fields
    classes.k.setValue(5)
    classes.count_mode.setCurrentIndex(classes.count_mode.findData("auto"))
    classes.auto_max_k.setValue(4)
    assert dialog.plan().class_count_mode == "auto" and not classes.k.isEnabled()
    assert dialog.acceptance_fields.margin.isEnabled()
    dialog.acceptance_fields.margin.setValue(.06)
    dialog.domain_fields.minimum.setValue(6)
    calculate(qtbot, controller, dialog)
    auto = controller.result
    assert auto.catalogue.k == 1 and auto.parameters["class_count_mode"] == "auto"
    assert "Auto" in dialog.displayed.text() and "K1" in dialog.auto_summary.text()
    dialog.auto_details.click()
    ranking = dialog.findChild(QDialog, "autoRankingDialog")
    assert ranking.isVisible() and ranking.table.rowCount() == 4
    ranking.close()
    classes.count_mode.setCurrentIndex(0)
    calculate(qtbot, controller, dialog)
    assert controller.result.catalogue.k == 5
    assert controller.previous_result is auto
    draft = dialog.plan()
    dialog.comparison.setCurrentIndex(1)
    assert controller.result is auto and dialog.plan() == draft
    assert "wyświetlanego wyniku" in dialog.auto_summary.text() and dialog.auto_details.isEnabled()
    dialog.copy_result.click()
    assert classes.mode.currentData() == "existing" and classes.chosen_k == 1
    assert dialog.plan().class_count_mode == "auto"
    assert not dialog.acceptance_fields.margin.isEnabled()
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)


def test_undetermined_local_and_shared_leave_completed_result_and_ranking_available(qtbot, tmp_path):
    window, controller, dialog = open_demo(qtbot, tmp_path)
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    classes = dialog.class_fields
    classes.count_mode.setCurrentIndex(1)
    calculate(qtbot, controller, dialog)
    good = controller.result
    assert good.catalogue.k == 2
    classes.auto_max_k.setValue(1)
    calculate(qtbot, controller, dialog)
    assert controller.result is good
    assert controller.series_run.selection["selected_k"] is None
    assert "nierozstrzygnięte" in dialog.auto_summary.text()
    assert dialog.auto_details.isEnabled()
    classes.fit_source.setCurrentIndex(classes.fit_source.findData("selected_range"))
    classes.fit_start.setValue(3)
    classes.fit_end.setValue(5)
    calculate(qtbot, controller, dialog)
    assert controller.series_run.phase == "undetermined"
    assert controller.series_run.processed_count == 0
    assert controller.result is good and controller.series_run.selection["selected_k"] is None
    assert "Niewykonana" == dialog.statuses.item(0, 1).text()
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)
