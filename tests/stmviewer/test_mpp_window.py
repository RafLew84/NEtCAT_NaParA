"""Movie browsing and import failures through public GUI controls."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QLabel, QListView, QPushButton, QSpinBox, QWidget

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / 'fixtures'


def labels(window):
    return '\n'.join(label.text() for label in window.findChildren(QLabel) if label.isVisible())


def open_selection(qtbot, window, monkeypatch, paths):
    filters = []

    def choose(*args):
        filters.append(args[3])
        return [str(path) for path in paths], ''

    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', choose)
    button = window.findChild(QPushButton, 'openFrames')
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)
    return filters[0]


def test_movie_navigation_shows_source_frame_and_partial_times(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()

    filters = open_selection(qtbot, window, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])

    assert '*.mpp' in filters and '*.MPP' in filters
    assert 'Klatka 1 z 3' in window.statusBar().currentMessage()
    assert 'Klatka źródłowa MPP: 1' in labels(window)
    assert 'Czas pomiaru: 1.5 s' in labels(window)
    assert 'Zapis czasu: 1500 ms' in labels(window)
    strip = window.findChild(QListView, 'frameThumbnails')
    thumbnail = strip.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).toImage()
    assert thumbnail.pixelColor(8, 12).red() == 255
    assert thumbnail.pixelColor(40, 60).red() == 255
    assert thumbnail.pixelColor(40, 12).red() == 0
    first_image = window.findChild(QWidget, 'imagePreview').grab().toImage()
    qtbot.mouseClick(window.findChild(QPushButton, 'nextFrame'), Qt.MouseButton.LeftButton)
    assert 'Klatka źródłowa MPP: 2' in labels(window)
    assert 'Czas pomiaru: nieznane' in labels(window)
    assert 'Zapis czasu:' not in labels(window)
    assert window.findChild(QWidget, 'imagePreview').grab().toImage() != first_image
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    assert 'Klatka 3 z 3' in window.statusBar().currentMessage()
    assert 'Klatka źródłowa MPP: 3' in labels(window)
    assert 'Czas pomiaru: 4.25 s' in labels(window)
    assert 'Klatka źródłowa MPP: 3' in strip.currentIndex().data(Qt.ItemDataRole.ToolTipRole)
    qtbot.mouseClick(window.findChild(QPushButton, 'previousFrame'), Qt.MouseButton.LeftButton)
    assert 'Klatka źródłowa MPP: 2' in labels(window)

    open_selection(qtbot, window, monkeypatch, [FIXTURES / 'asymmetric.stp'])
    assert 'Klatka źródłowa MPP' not in labels(window)
    assert 'Czas pomiaru: nieznane' in labels(window)


def test_long_movie_can_select_frame_1000(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_selection(qtbot, window, monkeypatch, [FIXTURES / 'mpp/long.mpp'])
    number = window.findChild(QSpinBox, 'frameNumber')
    assert number.maximum() == 1000
    number.setValue(1000)
    assert 'Klatka 1000 z 1000' in window.statusBar().currentMessage()
    assert 'Klatka źródłowa MPP: 1000' in labels(window)
    assert 'Czas pomiaru: 999 s' in labels(window)
    strip = window.findChild(QListView, 'frameThumbnails')
    assert strip.currentIndex().row() == 999
    assert strip.viewport().rect().contains(strip.visualRect(strip.currentIndex()).center())


def test_failed_and_disallowed_movie_imports_keep_previous_movie(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_selection(qtbot, window, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(3)
    previous = window.findChild(QWidget, 'imagePreview').grab().toImage()
    denied = tmp_path / 'denied.mpp'
    real_open = Path.open

    def open_with_denied_access(path, *args, **kwargs):
        if path == denied:
            raise PermissionError('Brak uprawnień')
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', open_with_denied_access)
    for paths, message_text in (
        ([FIXTURES / 'mpp/truncated.mpp'], 'truncated.mpp'),
        ([FIXTURES / 'mpp/timed.MPP', FIXTURES / 'asymmetric.stp'], 'jeden MPP'),
        ([FIXTURES / 'mpp/timed.MPP', FIXTURES / 'mpp/no-times.mpp'], 'jeden MPP'),
        ([denied], 'denied.mpp'),
    ):
        open_selection(qtbot, window, monkeypatch, paths)
        message = window.findChild(QMessageBox)
        assert message.isVisible() and message_text in message.text()
        message.accept()
        qtbot.waitUntil(lambda: not window.findChildren(QMessageBox))
        assert number.value() == 3
        assert 'Klatka źródłowa MPP: 3' in labels(window)
        assert 'Czas pomiaru: 4.25 s' in labels(window)
        assert window.findChild(QWidget, 'imagePreview').grab().toImage() == previous


def test_movie_import_can_cancel_after_a_decoded_frame(qtbot, monkeypatch):
    from threading import Event
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QProgressBar

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_selection(qtbot, window, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    pixels = window.findChild(QCheckBox, 'pixelProportions')
    gamma.setValue(2)
    pixels.setChecked(True)
    window.findChild(QPushButton, 'zoomIn').click()
    previous = window.findChild(QWidget, 'imagePreview').grab().toImage()
    path = (FIXTURES / 'mpp/long.mpp').resolve()
    entered, release = Event(), Event()
    real_open = Path.open

    class SlowRead:
        def __init__(self, stream):
            self.stream = stream
            self.reads = 0

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def read(self, count):
            self.reads += 1
            if self.reads == 2:
                entered.set()
                if not release.wait(5):
                    raise OSError('File I/O did not finish')
            return self.stream.read(count)

    def slow_open(source, *args, **kwargs):
        stream = real_open(source, *args, **kwargs)
        return SlowRead(stream) if source == path else stream

    monkeypatch.setattr(Path, 'open', slow_open)
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(path)], ''))
    button = window.findChild(QPushButton, 'openFrames')
    try:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(entered.is_set)
        progress = window.findChild(QProgressBar, 'importProgress')
        qtbot.waitUntil(lambda: progress.value() == 1)
        assert progress.maximum() == 2000 and progress.isVisible()
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        cancel = window.findChild(QPushButton, 'cancelImport')
        qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)
        assert not cancel.isEnabled()
    finally:
        release.set()
        qtbot.waitUntil(button.isEnabled)
    assert gamma.value() == 2 and pixels.isChecked()
    assert 'Klatka 3 z 3' in window.statusBar().currentMessage()
    assert 'Klatka źródłowa MPP: 3' in labels(window)
    assert window.findChild(QWidget, 'imagePreview').grab().toImage() == previous
    open_selection(qtbot, window, monkeypatch, [FIXTURES / 'mpp/no-times.mpp'])
    assert 'Klatka 1 z 1' in window.statusBar().currentMessage()
    assert 'Czas pomiaru: nieznane' in labels(window)
    assert gamma.value() == 1 and not pixels.isChecked()
