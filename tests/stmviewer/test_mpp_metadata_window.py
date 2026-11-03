"""Accompanying metadata through public file selection and navigation controls."""

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QLabel, QListView, QPushButton, QSpinBox
from PyQt6.QtCore import Qt

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / 'fixtures' / 'mpp-metadata'


def open_movie(qtbot, window, monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(path)], ''))
    button = window.findChild(QPushButton, 'openFrames')
    button.click()
    qtbot.waitUntil(button.isEnabled)


def visible_text(window):
    return '\n'.join(label.text() for label in window.findChildren(QLabel) if label.isVisible())


def test_navigation_shows_source_provenance_and_individual_parameters(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'mixed.MPP')

    assert 'Metadane towarzyszące: wczytano' in visible_text(window)
    assert 'Pochodzenie: /pomiary/first.stp' in visible_text(window)
    assert 'Kanał: Topo' in visible_text(window)
    assert 'Czas pomiaru: 10 s' in visible_text(window)
    assert 'Napięcie: 0 V' in visible_text(window)
    window.findChild(QPushButton, 'nextFrame').click()
    text = visible_text(window)
    assert r'Pochodzenie: C:\pomiary\movie.MPP' in text
    assert 'Klatka źródłowa: 8' in text
    assert 'Klatka w otwartym MPP: 2' in text
    assert 'Kanał: Current' in text and 'Pole X: 16 nm' in text and 'Pole Y: 6 nm' in text
    assert 'Czas pomiaru: nieznane' in text and 'Zapis czasu:' not in text
    strip = window.findChild(QListView, 'frameThumbnails')
    assert 'movie.MPP' in strip.currentIndex().data()
    assert 'Klatka źródłowa: 8' in strip.currentIndex().data(Qt.ItemDataRole.ToolTipRole)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    text = visible_text(window)
    assert 'Pochodzenie: archive/third.s94' in text
    assert 'Pole X: nieznane' in text and 'Pole Y: 12 nm' in text
    assert 'Jednostka sygnału: nieznana' in text and 'Czas pomiaru: 35 s' in text
    assert 'Nieznana kalibracja' in text
    window.findChild(QPushButton, 'deleteFrame').click()
    assert 'Klatka 2 z 2' in window.statusBar().currentMessage()
    assert 'Klatka źródłowa: 8' in visible_text(window)


def test_missing_rejected_and_new_series_replace_metadata_notices(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    path = tmp_path / 'copy.MPP'
    path.write_bytes((FIXTURES / 'mixed.MPP').read_bytes())
    sidecar = path.with_name(path.name + '.stmviewer.json')
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'mixed.MPP')
    assert 'Pochodzenie: /pomiary/first.stp' in visible_text(window)
    open_movie(qtbot, window, monkeypatch, path)
    assert 'Metadane towarzyszące: brak' in visible_text(window)
    assert 'Kanał: Current' in visible_text(window)
    assert 'Pochodzenie:' not in visible_text(window)
    sidecar.write_text('{"version": 999}')
    open_movie(qtbot, window, monkeypatch, path)
    assert 'Metadane towarzyszące: pominięto' in visible_text(window)
    assert 'Pola JSON' in visible_text(window)
    assert 'Klatka 1 z 3' in window.statusBar().currentMessage()
    assert not window.findChildren(QMessageBox)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    assert 'pominięto' in visible_text(window)
    for _ in range(3):
        window.findChild(QPushButton, 'deleteFrame').click()
    assert not window.findChild(QLabel, 'metadataImportInfo').text()
    open_movie(qtbot, window, monkeypatch, FIXTURES.parent / 'asymmetric.stp')
    assert 'Metadane towarzyszące:' not in visible_text(window)


def test_cancelling_metadata_read_preserves_previous_series_and_view(qtbot, monkeypatch):
    from threading import Event
    from PyQt6.QtWidgets import QDoubleSpinBox, QWidget
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES.parent / 'mpp/timed.MPP')
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    gamma.setValue(2)
    window.findChild(QPushButton, 'zoomIn').click()
    before = window.findChild(QWidget, 'imagePreview').grab().toImage()
    entered, release = Event(), Event()
    sidecar = (FIXTURES / 'mixed.MPP.stmviewer.json').resolve()
    real_open = Path.open
    class SlowRead:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def read(self, size):
            entered.set()
            if not release.wait(5):
                raise OSError('Test read timed out')
            return self.stream.read(size)
    def slow(p, *args, **kwargs):
        stream = real_open(p, *args, **kwargs)
        return SlowRead(stream) if p == sidecar else stream
    monkeypatch.setattr(Path, 'open', slow)
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(FIXTURES / 'mixed.MPP')], ''))
    button = window.findChild(QPushButton, 'openFrames')
    try:
        button.click()
        qtbot.waitUntil(entered.is_set)
        qtbot.waitUntil(lambda: 'weryfikacja metadanych' in visible_text(window))
        gamma.setValue(1.5)
        window.findChild(QPushButton, 'cancelImport').click()
    finally:
        release.set()
        qtbot.waitUntil(button.isEnabled)
    assert gamma.value() == 1.5
    gamma.setValue(2)
    assert 'Klatka 3 z 3' in window.statusBar().currentMessage()
    assert window.findChild(QWidget, 'imagePreview').grab().toImage() == before
    assert 'Pochodzenie:' not in visible_text(window)
    assert 'Czas pomiaru: 4.25 s' in visible_text(window)
