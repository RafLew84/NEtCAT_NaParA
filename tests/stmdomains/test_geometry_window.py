"""The floating card calculates current data and leaves base analysis untouched."""
import pytest
from PyQt6.QtCore import Qt
from test_analysis_window import Prompts
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


@pytest.fixture
def opened(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(create_analysis_demo(tmp_path)['series'])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    yield window
    window.close()
    window._finish_background_work()


def test_measure_card_move_collapse_and_current_frame_cache(qtbot, opened):
    window = opened
    window.controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=20000)
    original = window.controller.result
    before = window.image_view.geometry()
    window.geometry_action.trigger()
    card = window.geometry_card
    assert card.isVisible()
    qtbot.mouseClick(card.measure, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=20000)
    assert window.controller.result is original
    assert window.controller.geometry is not None
    assert window.image_view.geometry() == before
    x = card.x()
    qtbot.mouseClick(card.side, Qt.MouseButton.LeftButton)
    assert card.x() != x
    qtbot.mouseClick(card.collapse, Qt.MouseButton.LeftButton)
    assert not card.body.isVisible()
    assert window.image_view.geometry() == before
    qtbot.mouseClick(card.collapse, Qt.MouseButton.LeftButton)
    # Pick a real molecule on the image, then inspect the domain tab.
    detection = window._presented.annotations.detections[40]
    window._select_annotation(detection)
    assert detection.detection_id in card.title.text()
    assert 'Rozstaw' in card.details.text()
    card.tabs.setCurrentIndex(1)
    assert 'pomiar' in card.details.text().lower()
    window.controller.show_frame(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.controller.geometry is None
    assert 'Pomierz' in card.details.text()
    window.controller.show_frame(0)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.controller.geometry is not None


def test_cancel_or_leave_frame_never_publishes_obsolete_measurement(qtbot, opened):
    controller = opened.controller
    controller.measure_current_geometry()
    assert controller.is_busy
    controller.cancel()
    qtbot.waitUntil(lambda: controller.pending_task_count == 0, timeout=15000)
    assert controller.geometry is None
    controller.measure_current_geometry()
    controller.show_frame(1)
    qtbot.waitUntil(lambda: controller.pending_task_count == 0, timeout=15000)
    assert controller.current_index == 1 and controller.geometry is None
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.geometry is None


def test_small_card_scrolls_all_measurement_details_without_moving_image(qtbot, opened):
    window = opened
    window.resize(1024, 768)
    window.geometry_action.trigger()
    window.controller.measure_current_geometry()
    qtbot.waitUntil(lambda: not window.controller.is_busy, timeout=15000)
    window._select_annotation(window._presented.annotations.detections[40])
    card = window.geometry_card
    qtbot.waitUntil(lambda: card.body_scroll.verticalScrollBar().maximum() > 0)
    assert window.image_view.viewport().rect().contains(card.geometry())
    assert card.details.height() >= card.details.heightForWidth(card.details.width())
    qtbot.wait(20)  # Let Qt recompute the scroll range after replacing rich text.
    card.body_scroll.verticalScrollBar().setValue(card.body_scroll.verticalScrollBar().maximum())
    qtbot.wait(20)
    assert card.body_scroll.viewport().rect().contains(card.data_button.mapTo(card.body_scroll.viewport(), card.data_button.rect().center()))
