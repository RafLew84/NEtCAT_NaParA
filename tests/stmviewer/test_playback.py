"""Playback through public controls, observing rendered frames rather than timer ticks."""

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QFileDialog, QListView, QPushButton, QSpinBox, QWidget

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / 'fixtures'


def open_files(qtbot, window, monkeypatch, paths):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(p) for p in paths], ''))
    button = window.findChild(QPushButton, 'openFrames')
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)


def image(window):
    preview = window.findChild(QWidget, 'imagePreview')
    return preview.grab().toImage()


@pytest.fixture
def movie(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])
    return window


def test_play_displays_every_frame_and_stops_at_end(movie, qtbot):
    number = movie.findChild(QSpinBox, 'frameNumber')
    expected = []
    for value in (1, 2, 3):
        number.setValue(value)
        expected.append(image(movie))
    assert expected[0] != expected[1] != expected[2]
    number.setValue(1)
    play = movie.findChild(QPushButton, 'playPause')
    assert play is not None and play.text() == 'Play'
    fps = movie.findChild(QComboBox, 'playbackFps')
    assert [fps.itemText(i) for i in range(fps.count())] == ['1', '2', '5', '10', '20', '30']
    assert fps.currentText() == '5'
    strip = movie.findChild(QListView, 'frameThumbnails')

    qtbot.mouseClick(play, Qt.MouseButton.LeftButton)

    assert play.text() == 'Pause'
    assert number.value() == 1 and image(movie) == expected[0]
    qtbot.waitUntil(lambda: number.value() == 2)
    assert image(movie) == expected[1] and strip.currentIndex().row() == 1
    qtbot.waitUntil(lambda: number.value() == 3)
    assert image(movie) == expected[2] and strip.currentIndex().row() == 2
    assert play.text() == 'Play'
    qtbot.wait(240)
    assert number.value() == 3


def test_pause_resume_restart_and_loop(movie, qtbot):
    from PyQt6.QtWidgets import QCheckBox

    number = movie.findChild(QSpinBox, 'frameNumber')
    play = movie.findChild(QPushButton, 'playPause')
    loop = movie.findChild(QCheckBox, 'playbackLoop')
    assert loop is not None and not loop.isChecked()
    play.click()
    qtbot.waitUntil(lambda: number.value() == 2)
    play.click()
    paused = image(movie)
    qtbot.wait(240)
    assert number.value() == 2 and image(movie) == paused and play.text() == 'Play'
    play.click()
    assert number.value() == 2
    qtbot.waitUntil(lambda: number.value() == 3)
    assert play.text() == 'Play'

    play.click()
    assert number.value() == 1 and play.text() == 'Pause'
    play.click()
    number.setValue(3)
    loop.setChecked(True)
    play.click()
    assert number.value() == 1
    for expected in (2, 3, 1):
        qtbot.waitUntil(lambda: number.value() == expected)
        assert play.text() == 'Pause'
    play.click()


@pytest.mark.parametrize('control', ['previous', 'next', 'slider', 'number', 'thumbnail', 'same-thumbnail', 'same-number', 'same-slider'])
def test_manual_selection_pauses_on_the_requested_frame(movie, qtbot, control):
    from PyQt6.QtWidgets import QLineEdit, QSlider

    number = movie.findChild(QSpinBox, 'frameNumber')
    number.setValue(2)
    play = movie.findChild(QPushButton, 'playPause')
    movie.findChild(QComboBox, 'playbackFps').setCurrentText('1')
    play.click()
    expected = 2 if control.startswith('same-') else (3 if control == 'next' else 1)
    if control in ('previous', 'next'):
        movie.findChild(QPushButton, control + 'Frame').click()
    elif control == 'slider':
        movie.findChild(QSlider, 'frameSlider').setValue(1)
    elif control in ('number', 'same-number'):
        editor = number.findChild(QLineEdit)
        editor.selectAll()
        qtbot.keyClicks(editor, str(expected))
        qtbot.keyClick(editor, Qt.Key.Key_Return)
    elif control == 'same-slider':
        slider = movie.findChild(QSlider, 'frameSlider')
        qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=slider.rect().center())
    else:
        strip = movie.findChild(QListView, 'frameThumbnails')
        index = strip.model().index(expected - 1, 0)
        qtbot.mouseClick(strip.viewport(), Qt.MouseButton.LeftButton, pos=strip.visualRect(index).center())
    assert play.text() == 'Play' and number.value() == expected
    selected = image(movie)
    qtbot.wait(1100)
    assert number.value() == expected and image(movie) == selected


def test_gamma_zoom_pan_and_tempo_can_change_while_playing(movie, qtbot):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QDoubleSpinBox

    number = movie.findChild(QSpinBox, 'frameNumber')
    gamma = movie.findChild(QDoubleSpinBox, 'previewGamma')
    fps = movie.findChild(QComboBox, 'playbackFps')
    preview = movie.findChild(QWidget, 'imagePreview')
    play = movie.findChild(QPushButton, 'playPause')
    fps.setCurrentText('1')
    play.click()
    gamma.setValue(2)
    movie.findChild(QPushButton, 'zoomIn').click()
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(130, 120))
    assert play.text() == 'Pause'
    fps.setCurrentText('30')
    qtbot.waitUntil(lambda: number.value() == 3, timeout=500)
    played = image(movie)
    assert gamma.value() == 2
    number.setValue(1)
    number.setValue(3)
    assert image(movie) == played
    # Resetting the view changes the pixels, confirming Play retained zoom/pan.
    movie.findChild(QPushButton, 'fitImage').click()
    assert image(movie) != played


def test_import_failure_preserves_play_and_success_stops_at_first_frame(movie, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QMessageBox

    play = movie.findChild(QPushButton, 'playPause')
    number = movie.findChild(QSpinBox, 'frameNumber')
    gamma = movie.findChild(QDoubleSpinBox, 'previewGamma')
    movie.findChild(QCheckBox, 'playbackLoop').setChecked(True)
    movie.findChild(QComboBox, 'playbackFps').setCurrentText('10')
    gamma.setValue(2)
    play.click()
    open_files(qtbot, movie, monkeypatch, [])
    assert play.text() == 'Pause' and gamma.value() == 2
    open_files(qtbot, movie, monkeypatch, [FIXTURES / 'mpp/truncated.mpp'])
    message = movie.findChild(QMessageBox)
    assert message.isVisible()
    message.accept()
    assert play.text() == 'Pause' and gamma.value() == 2
    old = number.value()
    qtbot.waitUntil(lambda: number.value() != old)
    open_files(qtbot, movie, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])
    assert play.text() == 'Play' and number.value() == 1 and gamma.value() == 1
    qtbot.wait(250)
    assert number.value() == 1


def test_empty_and_single_frame_do_not_play(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    play = window.findChild(QPushButton, 'playPause')
    assert not play.isEnabled()
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'asymmetric.stp'])
    assert not play.isEnabled() and play.text() == 'Play'
    play.click()
    assert window.findChild(QSpinBox, 'frameNumber').value() == 1


def test_closing_window_stops_playback(movie, qtbot):
    from PyQt6.QtWidgets import QCheckBox

    movie.findChild(QCheckBox, 'playbackLoop').setChecked(True)
    play = movie.findChild(QPushButton, 'playPause')
    play.click()
    movie.close()
    assert not movie.isVisible() and play.text() == 'Play'
    qtbot.wait(250)
    assert movie.findChild(QSpinBox, 'frameNumber').value() == 1


def test_overloaded_paint_displays_each_frame_without_catching_up_by_skipping(movie, qtbot):
    from time import perf_counter, sleep
    from PyQt6.QtCore import QEvent, QObject, QTimer

    number = movie.findChild(QSpinBox, 'frameNumber')
    expected = []
    for value in (1, 2, 3):
        number.setValue(value)
        expected.append(image(movie))
    number.setValue(1)
    qtbot.wait(30)
    preview = movie.findChild(QWidget, 'imagePreview')
    shown = [(perf_counter(), image(movie))]

    class PaintObserver(QObject):
        capturing = False

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint and not self.capturing:
                # An overloaded GUI/display: intentionally slower than the requested 30 fps.
                sleep(0.08)
                QTimer.singleShot(0, self.capture)
            return False

        def capture(self):
            self.capturing = True
            rendered = preview.grab().toImage()
            self.capturing = False
            if rendered != shown[-1][1]:
                shown.append((perf_counter(), rendered))

    observer = PaintObserver(preview)
    preview.installEventFilter(observer)
    movie.findChild(QComboBox, 'playbackFps').setCurrentText('30')
    play = movie.findChild(QPushButton, 'playPause')
    play.click()
    qtbot.waitUntil(lambda: len(shown) == 3, timeout=3000)
    assert [rendered for _, rendered in shown] == expected
    assert all(shown[i][0] - shown[i-1][0] >= 0.07 for i in (1, 2))
    assert play.text() == 'Play' and number.value() == 3


def test_cancelled_import_keeps_running_movie(movie, qtbot, monkeypatch):
    from threading import Event
    from PyQt6.QtWidgets import QCheckBox

    path = (FIXTURES / 'mpp/long.mpp').resolve()
    entered, release = Event(), Event()
    real_open = Path.open

    def slow_open(source, *args, **kwargs):
        if source == path:
            entered.set()
            if not release.wait(5):
                raise OSError('File I/O did not finish')
        return real_open(source, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', slow_open)
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(path)], ''))
    play = movie.findChild(QPushButton, 'playPause')
    number = movie.findChild(QSpinBox, 'frameNumber')
    movie.findChild(QCheckBox, 'playbackLoop').setChecked(True)
    movie.findChild(QComboBox, 'playbackFps').setCurrentText('10')
    play.click()
    button = movie.findChild(QPushButton, 'openFrames')
    try:
        button.click()
        qtbot.waitUntil(entered.is_set)
        qtbot.waitUntil(lambda: number.value() != 1)
        movie.findChild(QPushButton, 'cancelImport').click()
    finally:
        release.set()
        qtbot.waitUntil(button.isEnabled)
    assert play.text() == 'Pause' and number.maximum() == 3
    old = number.value()
    qtbot.waitUntil(lambda: number.value() != old)
    play.click()
