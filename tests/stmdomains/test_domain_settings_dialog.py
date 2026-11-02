"""Menu-driven domain tuning is explicit, validated and keeps the image position."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


def test_menu_dialog_edits_recomputes_compares_and_restores_without_moving_image(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.resize(1000, 760)
    window.show()
    action = window.findChild(QAction, "domainSettingsAction")
    assert action is not None and not action.isEnabled()
    window.controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    action.trigger()
    dialog = window.domain_settings_dialog
    assert dialog.isVisible() and not dialog.isModal()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    base = window.controller.result
    window.image_view.zoom_by(1.4)
    window.image_view.horizontalScrollBar().setValue(30)
    before = (window.image_view.geometry(), window.image_view.transform(),
              window.image_view.horizontalScrollBar().value(), window.image_view.verticalScrollBar().value())
    dialog.minimum.setValue(6)
    dialog.link_distance.setValue(1.7)
    dialog.mask_radius.setValue(.9)
    dialog.geometry_mode.setCurrentIndex(1)
    assert window.controller.result is base and not window.controller.is_busy
    assert "nieprzeliczone" in dialog.validation.text()
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    tuned = window.controller.result
    assert tuned.parameters["minimum_domain_size"] == 6
    assert tuned.parameters["edge_distance_factor"] == 1.7
    assert tuned.parameters["raster_radius_factor"] == .9
    assert tuned.parameters["geometry_mode"] == "off"
    dialog.comparison.setCurrentIndex(1)
    assert window.controller.result is base
    assert "Poprzedni" in window.details_label.text()
    assert (window.image_view.geometry(), window.image_view.transform(),
            window.image_view.horizontalScrollBar().value(), window.image_view.verticalScrollBar().value()) == before
    dialog.comparison.setCurrentIndex(0)
    dialog.geometry_mode.setCurrentIndex(0)
    dialog.edge_threshold.setValue(.7)
    assert not dialog.calculate.isEnabled() and "≤" in dialog.validation.text()
    assert window.controller.result is tuned
    qtbot.mouseClick(dialog.baseline, Qt.MouseButton.LeftButton)
    assert dialog.calculate.isEnabled() and dialog.minimum.value() == 8
    assert dialog.edge_threshold.value() == .2 and dialog.region_diameter.value() == .5
    assert window.controller.result is tuned
    qtbot.mouseClick(dialog.calculate, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    assert window.controller.result.assignments == base.assignments
    dialog.close()
    action.trigger()
    assert window.domain_settings_dialog is dialog and dialog.isVisible()
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert not dialog.comparison.isEnabled() and "Klatka 2" in dialog.context.text()
    assert dialog.minimum.value() == 8
    window.close()
    qtbot.waitUntil(lambda: not window.controller.pending_task_count and not window.filmstrip.pending_task_count)
