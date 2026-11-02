"""The analyze button computes a result from the displayed series without a model dialog."""

from PyQt6.QtCore import Qt

from stmdomains.tools.browsing_demo import create_browsing_demo
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


class Prompts:
    def choose_session(self):
        raise AssertionError("No additional file selection is needed for analysis")

    def choose_source(self, message, suggested):
        raise AssertionError(message)

    def confirm_source(self, path, reasons):
        return True

    def show_error(self, message):
        raise AssertionError(message)


def test_analyze_button_displays_no_annotations_without_loading_a_model(qtbot, tmp_path):
    path = create_browsing_demo(tmp_path)["series"]
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    assert not window.analyze_button.isEnabled()
    window.controller.open_session(path)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    window.controller.show_frame(3)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.analyze_button.isEnabled()
    before = window.image_view.geometry()
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.controller.result.status == "no_annotations"
    assert "Brak oznaczeń" in window.result_controls.summary.text()
    assert window.result_controls.mode.currentData() == "domains"
    assert window.image_view.geometry() == before
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert "Brak analizy" in window.result_controls.summary.text()
    window.close()
    qtbot.waitUntil(lambda: window.controller.pending_task_count == 0
                   and window.filmstrip.pending_task_count == 0)


def test_computed_domains_and_completed_zero_are_visible_in_window(qtbot, tmp_path):
    path = create_analysis_demo(tmp_path)["series"]
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(path)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    result = window.controller.result
    assert result.status == "complete" and result.domain_count > 0
    assert f"Domeny: {result.domain_count}" in window.result_controls.summary.text()
    assert "Duplikaty: 1" in window.result_controls.legend.toolTip()
    window.image_view.zoom_by(1.3)
    scale = window.image_view.transform().m11()
    window.result_controls.mode.setCurrentIndex(1)
    assert "Klasy:" in window.result_controls.summary.text()
    assert window.image_view.transform().m11() == scale
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert "Brak analizy" in window.result_controls.summary.text()
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    assert window.controller.result.status == "complete"
    assert window.controller.result.assigned_count == 0
    assert "0 / 405" in window.result_controls.summary.text()
    window.close()
    qtbot.waitUntil(lambda: window.controller.pending_task_count == 0
                   and window.filmstrip.pending_task_count == 0)
