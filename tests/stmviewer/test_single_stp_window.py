"""User controls to visible results, with only the OS chooser substituted."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QWidget, QMessageBox

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / "fixtures"


def visible_text(window):
    return "\n".join(label.text() for label in window.findChildren(QLabel) if label.isVisible())


def test_user_opens_one_stp_and_sees_image_and_parameters(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    button = window.findChild(QPushButton, "openFrames")
    assert button is not None and button.isEnabled()
    assert "Brak otwartego obrazu" in visible_text(window)
    preview = window.findChild(QWidget, "imagePreview")
    empty = preview.grab().toImage()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **kw: (
        [str(FIXTURES / "asymmetric.stp")], "STP (*.stp *.STP)"
    ))

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)

    text = visible_text(window)
    for expected in ["asymmetric.stp", "4 × 3 px", "Topo", "nm", "8 nm", "9 nm", "0 V"]:
        assert expected in text
    assert "Brak otwartego obrazu" not in text
    assert "Klatka 1 z 1" in window.statusBar().currentMessage()
    assert preview.grab().toImage() != empty


def test_replacement_cancel_and_bad_file_preserve_the_last_valid_preview(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    choices = iter([str(FIXTURES / "asymmetric.stp"), str(FIXTURES / "unknown.stp"),
                    "", str(FIXTURES / "truncated.stp")])
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **kw: ([choice] if (choice := next(choices)) else [], ""))
    button = window.findChild(QPushButton, "openFrames")
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    first_image = window.findChild(QWidget, "imagePreview").grab().toImage()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    assert "unknown.stp" in visible_text(window)
    assert "Kanał: nieznany" in visible_text(window)
    assert "Pole X: nieznane" in visible_text(window)
    last_text = visible_text(window)
    last_image = window.findChild(QWidget, "imagePreview").grab().toImage()
    assert last_image != first_image

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # Cancel the chooser.
    qtbot.waitUntil(button.isEnabled)
    assert visible_text(window) == last_text
    assert window.findChild(QWidget, "imagePreview").grab().toImage() == last_image
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # Real truncated payload.
    qtbot.waitUntil(button.isEnabled)
    message = window.findChild(QMessageBox)
    assert message is not None and message.isVisible()
    assert "truncated.stp" in message.text()
    message.accept()
    assert visible_text(window) == last_text
    assert window.findChild(QWidget, "imagePreview").grab().toImage() == last_image
    assert button.isEnabled()
