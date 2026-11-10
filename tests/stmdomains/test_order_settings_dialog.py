"""Order settings are drafts until explicitly recalculated on a frozen catalogue."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def test_order_dialog_applies_compares_and_restores_without_moving_the_image(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    action = window.findChild(QAction, "analysisAction")
    assert action is not None and not action.isEnabled()
    window.controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    action.trigger()
    dialog = window.analysis_dialog
    assert dialog.isVisible() and not dialog.isModal() and dialog.calculate.isEnabled()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    base = window.controller.result
    dialog.class_fields.mode.setCurrentIndex(1)
    before = (window.image_view.geometry(), window.image_view.transform())
    dialog.order_fields.radius.setValue(2.)
    dialog.order_fields.sigma.setValue(1.)
    assert window.controller.result is base and "Edycja nie zmienia" in dialog.validation.text()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    tuned = window.controller.result
    assert tuned.catalogue is base.catalogue and tuned.assigned_count < base.assigned_count
    assert "2 × d" in dialog.displayed.toolTip()
    assert tuned.metadata["order_calibration"]["seed"] == 20261102
    dialog.comparison.setCurrentIndex(1)
    assert window.controller.result is base and dialog.order_fields.radius.value() == 2.
    dialog.comparison.setCurrentIndex(0)
    qtbot.mouseClick(dialog.baseline, Qt.MouseButton.LeftButton)
    assert window.controller.result is tuned
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    assert window.controller.result.assignments == base.assignments
    assert (window.image_view.geometry(), window.image_view.transform()) == before
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert not dialog.calculate.isEnabled() and "Klatka 2" in dialog.context.text()
    window.close()
    qtbot.waitUntil(lambda: not window.controller.pending_task_count and not window.filmstrip.pending_task_count)
