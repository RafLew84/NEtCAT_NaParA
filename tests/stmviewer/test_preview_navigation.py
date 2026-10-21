"""Mouse gestures through the GUI, verified on the visible synthetic STP."""

from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton, QWidget
import pytest

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def opened_window(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    preview = window.findChild(QWidget, "imagePreview")
    preview.setFixedSize(400, 300)
    window.show()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **kw: (
        [str(FIXTURES / "unknown.stp")], ""
    ))
    qtbot.mouseClick(window.findChild(QPushButton, "openStp"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(window.findChild(QPushButton, "openStp").isEnabled)
    return window, preview


def wheel(widget, delta, position=QPoint(100, 100)):
    event = QWheelEvent(
        QPointF(position), QPointF(widget.mapToGlobal(position)), QPoint(),
        QPoint(0, delta), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    QApplication.sendEvent(widget, event)


def screenshot(widget):
    # Compare logical coordinates also when Qt runs on a high-DPI display.
    return widget.grab().toImage().scaled(widget.size())


def white_run(image, y):
    pixels = [x for x in range(image.width()) if image.pixelColor(x, y).red() == 255]
    assert pixels, "The bright marker must remain visible"
    return pixels[0], pixels[-1]


def test_wheel_zooms_at_cursor_and_reverse_wheel_restores_view(opened_window):
    _, preview = opened_window
    initial = screenshot(preview)
    assert white_run(initial, 150) == (200, 299)
    assert white_run(initial, 50)[0] == 100

    wheel(preview, 120)

    zoomed = screenshot(preview)
    assert white_run(zoomed, 150) == (220, 339)
    assert white_run(zoomed, 50)[0] == 100  # The edge under the cursor stays put.
    wheel(preview, -120)
    assert screenshot(preview) == initial


def test_drag_moves_the_zoomed_marker_without_changing_its_size(opened_window, qtbot):
    _, preview = opened_window
    wheel(preview, 120)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    qtbot.mouseMove(preview, QPoint(180, 170))
    assert white_run(screenshot(preview), 170) == (250, 369)
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))

    moved = screenshot(preview)
    assert white_run(moved, 170) == (250, 369)  # Same 120 px width, translated by 30 px.
    assert moved.pixelColor(200, 110).red() == 255  # Upper row moved down by 20 px.
    assert moved.pixelColor(200, 130).red() == 0
    qtbot.mouseMove(preview, QPoint(220, 200))  # Released button no longer pans.
    assert screenshot(preview) == moved
    assert preview.cursor().shape() == Qt.CursorShape.OpenHandCursor


def test_fit_button_restores_the_whole_image_after_navigation(opened_window, qtbot):
    window, preview = opened_window
    fitted = screenshot(preview)
    wheel(preview, 240)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(185, 175))
    assert screenshot(preview) != fitted
    button = window.findChild(QPushButton, "fitImage")
    assert button is not None and button.isEnabled()

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)

    assert screenshot(preview) == fitted


def test_import_cancel_and_error_keep_navigation_but_success_resets_it(
    opened_window, qtbot, monkeypatch
):
    window, preview = opened_window
    fitted = screenshot(preview)
    wheel(preview, 120)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))
    navigated = screenshot(preview)
    choices = iter(["", str(FIXTURES / "truncated.stp"), str(FIXTURES / "unknown.stp")])
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **kw: ([choice] if (choice := next(choices)) else [], ""))
    button = window.findChild(QPushButton, "openStp")

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    assert screenshot(preview) == navigated
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    message = window.findChild(QMessageBox)
    assert message is not None and "truncated.stp" in message.text()
    message.accept()
    assert screenshot(preview) == navigated
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    assert screenshot(preview) == fitted


def test_empty_window_has_no_navigation(qtbot):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    preview = window.findChild(QWidget, "imagePreview")
    empty = screenshot(preview)
    assert not window.findChild(QPushButton, "fitImage").isEnabled()

    wheel(preview, 120)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    qtbot.mouseMove(preview, QPoint(180, 170))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))
    assert screenshot(preview) == empty
