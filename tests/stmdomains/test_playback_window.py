"""Exercise thumbnail, playback and gamma controls with genuine small input files."""

import pytest
from PyQt6.QtCore import QPointF, Qt

from stmdomains.tools.browsing_demo import create_browsing_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


def test_navigation_gamma_playback_and_single_frame_share_one_view(qtbot, tmp_path):
    paths = create_browsing_demo(tmp_path)
    window = STMDomainsMainWindow()
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(paths["series"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    controls = window.playback_controls
    assert controls.rate.currentData() == 5
    strip = window.filmstrip
    qtbot.waitUntil(lambda: strip.is_ready(1))
    target = strip.visualRect(strip.model().index(1, 0)).center()
    qtbot.mouseClick(strip.viewport(), Qt.MouseButton.LeftButton, pos=target)
    qtbot.waitUntil(lambda: window.frame_number.value() == 2)
    assert strip.current_index == 1
    assert window.frame_slider.value() == 2
    point = window.image_view.mapFromScene(QPointF(20.5, 20.5))
    before = window.image_view.viewport().grab().toImage().pixelColor(point).red()
    controls.gamma.setValue(2)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    after = window.image_view.viewport().grab().toImage().pixelColor(point).red()
    assert after > before
    window.image_view.zoom_by(1.5)
    scale = window.image_view.transform().m11()
    controls.rate.setCurrentIndex(4)
    shown = []
    window.controller.frame_changed.connect(lambda view: shown.append(
        (view.frame.working_index, [d.detection_id for d in view.annotations.detections])
    ))
    qtbot.mouseClick(controls.play, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_playing)
    assert shown == [(2, []), (3, []), (4, ["frame-5"]), (5, ["frame-6"]),
                     (6, ["frame-7"]), (7, ["frame-8"])]
    assert strip.current_index == 7
    assert window.frame_number.value() == window.frame_slider.value() == 8
    assert window.image_view.transform().m11() == pytest.approx(scale)
    assert controls.gamma.value() == 2
    assert "Od początku" in controls.play.text()
    window.controller.open_session(paths["single"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert not controls.play.isEnabled()
    assert not controls.restart.isEnabled()
    assert not controls.rate.isEnabled()
    assert controls.gamma.isEnabled()
    assert controls.gamma.value() == 2
    assert strip.current_index == 0
    assert strip.model().rowCount() == 1
