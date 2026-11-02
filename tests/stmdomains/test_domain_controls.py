"""A user can display region layers without input molecule masks or new analysis."""

from PyQt6.QtCore import Qt

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from stmdomains.ui.result_style import domain_color
from test_analysis_window import Prompts
from test_domain_overlay import pixel


def test_window_exposes_independent_region_controls_and_keeps_layout(qtbot, tmp_path):
    paths = create_analysis_demo(tmp_path)
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.resize(900, 650)
    window.show()
    regions = window.result_controls.regions
    assert not regions.isEnabled()
    window.controller.open_session(paths["series"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.annotation_controls.masks.text() == "Maski molekuł"
    assert not window.annotation_controls.masks.isEnabled()
    before = window.image_view.geometry()
    qtbot.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    result = window.controller.result
    assert regions.isEnabled()
    assert regions.fill.isChecked() and regions.outlines.isChecked() and regions.numbers.isChecked()
    assert window.image_view.geometry() == before
    window.annotation_controls.centers.setChecked(False)
    regions.outlines.setChecked(False)
    regions.numbers.setChecked(False)
    regions.opacity.setValue(100)
    member = next(m for m in result.assignments.values() if m.domain_local_id)
    x, y = member.metadata["x_px"], member.metadata["y_px"]
    assert pixel(window.image_view, x, y) == domain_color(member.domain_local_id)
    regions.fill.setChecked(False)
    assert pixel(window.image_view, x, y) != domain_color(member.domain_local_id)
    assert window.controller.result is result and not window.controller.is_busy
    window.result_controls.mode.setCurrentIndex(2)
    assert not regions.isEnabled()
    window.result_controls.mode.setCurrentIndex(0)
    assert regions.isEnabled() and not regions.fill.isChecked()
    window.controller.show_frame(2)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert not regions.isEnabled()
    window.controller.show_frame(0)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert regions.isEnabled() and not regions.fill.isChecked()
    window.close()
    qtbot.waitUntil(lambda: not window.controller.pending_task_count and not window.filmstrip.pending_task_count)
