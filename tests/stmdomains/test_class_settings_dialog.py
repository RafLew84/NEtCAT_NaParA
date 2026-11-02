"""Manual class discovery from the menu preserves old results and explicit scope."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def test_class_dialog_selects_k_scope_and_compares_catalogues(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.resize(1000, 760)
    window.show()
    action = window.findChild(QAction, "classSettingsAction")
    assert action is not None and not action.isEnabled()
    window.controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    action.trigger()
    dialog = window.class_settings_dialog
    assert dialog.isVisible() and not dialog.isModal()
    dialog.k.setValue(4)
    assert window.controller.result is None
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    local = window.controller.result
    assert local.catalogue.k == 4 and local.catalogue.scope == "current_frame"
    window.image_view.zoom_by(1.2)
    geometry, transform = window.image_view.geometry(), window.image_view.transform()
    dialog.scope.setCurrentIndex(1)
    dialog.start.setValue(2)
    dialog.end.setValue(1)
    assert not dialog.calculate.isEnabled() and "Początek" in dialog.validation.text()
    dialog.start.setValue(1)
    dialog.end.setValue(2)
    dialog.k.setValue(5)
    assert dialog.calculate.isEnabled() and window.controller.result is local
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    shared = window.controller.result
    assert shared.catalogue.frame_indices == (0, 1) and shared.catalogue.scope == "selected_range"
    assert "wspólny" in window.details_label.text()
    dialog.comparison.setCurrentIndex(1)
    assert window.controller.result is local and window.controller.active_catalogue is local.catalogue
    assert local.catalogue.identifier[:8] in dialog.displayed.text()
    assert window.image_view.geometry() == geometry and window.image_view.transform() == transform
    dialog.comparison.setCurrentIndex(0)
    window.controller.show_frame(4)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert "Nieprzeliczone" in window.details_label.text()
    assert window.controller.result is None and not dialog.comparison.isEnabled()
    dialog.scope.setCurrentIndex(2)
    assert not dialog.start.isEnabled() and not dialog.end.isEnabled()
    dialog.scope.setCurrentIndex(1)
    dialog.start.setValue(4)
    dialog.end.setValue(2)
    assert not dialog.calculate.isEnabled()
    dialog.scope.setCurrentIndex(2)
    assert dialog.calculate.isEnabled()  # Hidden range fields do not constrain the whole series.
    dialog.close()
    window.close()
    qtbot.waitUntil(lambda: not window.controller.pending_task_count and not window.filmstrip.pending_task_count)
