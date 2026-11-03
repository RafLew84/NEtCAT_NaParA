"""S94 choices, metadata and failed mixed imports through public GUI controls."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / "fixtures" / "s94"


def text(window):
    return '\n'.join(label.text() for label in window.findChildren(QLabel) if label.isVisible())


def test_file_chooser_accepts_mixed_images_and_shows_raw_calibration(qtbot, monkeypatch):
    choices = [FIXTURES / name for name in ('unknown-gain.s94', 'frame1.stp', 'frame10.S94')]
    filters = []

    def choose(*args):
        filters.append(args[3])
        return [str(path) for path in choices], ''

    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', choose)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    button = next(b for b in window.findChildren(QPushButton) if b.text().startswith('Otwórz'))
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)

    assert '*.s94' in filters[0] and '*.S94' in filters[0] and '*.stp' in filters[0]
    assert 'Klatka 1 z 3' in window.statusBar().currentMessage()
    assert 'frame1.stp' in text(window)
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(2)
    assert 'frame10.S94' in text(window)
    assert 'Jednostka sygnału: nA' in text(window) and 'Pole X: 16 nm' in text(window)
    number.setValue(3)
    assert 'unknown-gain.s94' in text(window)
    assert 'Jednostka sygnału: nieznana' in text(window)
    assert 'Wartości surowe' in text(window) and 'wzmocnienie Z (99)' in text(window)
    number.setValue(1)
    assert 'Wartości surowe' not in text(window)


def test_bad_s94_keeps_the_previous_series_and_selection(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox, QWidget

    choices = iter([
        ['frame1.stp', 'frame10.S94'], ['frame1.stp', 'truncated.s94'],
        ['frame1.stp', 'swapped.s94'],
    ])
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: (
        [str(FIXTURES / name) for name in next(choices)], ''
    ))
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    button = window.findChild(QPushButton, 'openFrames')
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    image = window.findChild(QWidget, 'imagePreview').grab().toImage()

    for bad_source in ('truncated.s94', 'swapped.s94'):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(button.isEnabled)
        message = window.findChild(QMessageBox)
        assert message.isVisible() and bad_source in message.text()
        message.accept()
        qtbot.waitUntil(lambda: not window.findChildren(QMessageBox))
        assert 'Klatka 2 z 2' in window.statusBar().currentMessage()
        assert 'frame10.S94' in text(window)
        assert window.findChild(QWidget, 'imagePreview').grab().toImage() == image
