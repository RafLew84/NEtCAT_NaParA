"""Open a saved result through the same controls used in the desktop browser."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor

from stmdomains.tools.result_demo import create_result_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from stmdomains.ui.result_style import UNASSIGNED_COLOR, domain_color
from test_result_session import Prompts


def center_color(window, x, y):
    point = window.image_view.mapFromScene(QPointF(x, y))
    return window.image_view.viewport().grab().toImage().pixelColor(point).name()


def test_open_result_controls_colors_clicks_and_absent_frames(qtbot, tmp_path):
    paths = create_result_demo(tmp_path)
    prompts = Prompts()
    prompts.choose_result = lambda: paths["manifest"]
    window = STMDomainsMainWindow(prompts=prompts)
    qtbot.addWidget(window)
    window.resize(1100, 760)
    window.show()
    assert not window.result_open_button.isEnabled()
    window.controller.open_session(paths["session"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    qtbot.mouseClick(window.result_open_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.result_controls.mode.currentData() == "domains"
    assert "eksperymentalny v0.4" in window.details_label.text()
    assert "Domeny: 2" in window.result_controls.summary.text()
    assert center_color(window, 4, 4) == QColor(domain_color(1)).name()
    assert center_color(window, 14, 4) == QColor(domain_color(2)).name()
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton,
                     pos=window.image_view.mapFromScene(QPointF(18, 4)))
    assert "niejednoznaczna klasa" in window.selection_label.toolTip()
    assert center_color(window, 18, 4) == QColor(UNASSIGNED_COLOR).name()
    window.image_view.zoom_by(1.2)
    zoom = window.image_view.transform().m11()
    window.result_controls.mode.setCurrentIndex(1)
    assert center_color(window, 4, 4) == center_color(window, 14, 4) == "#10b9bd"
    assert window.image_view.transform().m11() == zoom
    geometry = window.image_view.geometry()
    window.frame_number.setValue(3)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    qtbot.wait(30)
    assert "0 / 2" in window.result_controls.summary.text()
    assert window.image_view.geometry() == geometry
    window.frame_number.setValue(2)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert "Brak analizy" in window.result_controls.summary.text()
    assert not prompts.errors
