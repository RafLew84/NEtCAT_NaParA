"""Deleting through public GUI controls retains the surviving measurement frames."""

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QLabel, QListView, QPushButton,
    QSlider, QSpinBox, QWidget,
)

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / 'fixtures'


def open_files(qtbot, window, monkeypatch, paths):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(p) for p in paths], ''))
    button = window.findChild(QPushButton, 'openFrames')
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)


def image(window):
    return window.findChild(QWidget, 'imagePreview').grab().toImage()


def labels(window):
    return '\n'.join(label.text() for label in window.findChildren(QLabel) if label.isVisible())


def thumbnail(strip, row):
    return strip.model().index(row, 0).data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).toImage()


@pytest.fixture
def window(qtbot):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    return window


def test_delete_middle_pauses_and_keeps_following_frame_origin_and_time(window, qtbot, monkeypatch, tmp_path):
    source = tmp_path / 'movie.mpp'
    original = (FIXTURES / 'mpp/timed.MPP').read_bytes()
    source.write_bytes(original)
    open_files(qtbot, window, monkeypatch, [source])
    number = window.findChild(QSpinBox, 'frameNumber')
    strip = window.findChild(QListView, 'frameThumbnails')
    number.setValue(3)
    following_image, following_thumbnail = image(window), thumbnail(strip, 2)
    number.setValue(2)
    window.findChild(QComboBox, 'playbackFps').setCurrentText('1')
    window.findChild(QCheckBox, 'playbackLoop').setChecked(True)
    play = window.findChild(QPushButton, 'playPause')
    play.click()
    remove = window.findChild(QPushButton, 'deleteFrame')
    assert remove is not None and remove.isEnabled()

    qtbot.mouseClick(remove, Qt.MouseButton.LeftButton)

    assert play.text() == 'Play'
    assert number.value() == number.maximum() == 2
    slider = window.findChild(QSlider, 'frameSlider')
    assert slider.value() == slider.maximum() == 2
    assert 'Klatka 2 z 2' in window.statusBar().currentMessage()
    assert 'Klatka źródłowa MPP: 3' in labels(window)
    assert 'Czas pomiaru: 4.25 s' in labels(window)
    assert 'Zapis czasu: 4.25 s' in labels(window)
    assert image(window) == following_image
    assert strip.model().rowCount() == 2 and strip.currentIndex().row() == 1
    assert [index.row() for index in strip.selectionModel().selectedIndexes()] == [1]
    assert strip.currentIndex().data() == '2 · movie.mpp'
    assert 'Klatka źródłowa MPP: 3' in strip.currentIndex().data(Qt.ItemDataRole.ToolTipRole)
    assert thumbnail(strip, 1) == following_thumbnail
    qtbot.wait(1100)
    assert number.value() == 2 and image(window) == following_image
    window.findChild(QPushButton, 'previousFrame').click()
    assert 'Czas pomiaru: 1.5 s' in labels(window)
    assert 'Klatka źródłowa MPP: 1' in labels(window)
    assert source.read_bytes() == original


def test_delete_last_then_only_frame_leaves_empty_program_and_can_reopen(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QDoubleSpinBox

    empty = image(window)
    remove = window.findChild(QPushButton, 'deleteFrame')
    assert not remove.isEnabled()
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])
    number = window.findChild(QSpinBox, 'frameNumber')
    strip = window.findChild(QListView, 'frameThumbnails')
    number.setValue(2)
    second = image(window)
    number.setValue(3)
    remove.click()
    assert number.value() == number.maximum() == 2
    assert image(window) == second
    assert 'Klatka źródłowa MPP: 2' in labels(window)
    assert 'Czas pomiaru: nieznane' in labels(window)
    remove.click()
    assert number.value() == number.maximum() == 1
    assert remove.isEnabled()
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    gamma.setValue(2)
    window.findChild(QPushButton, 'zoomIn').click()

    remove.click()

    assert image(window) == empty
    assert strip.model().rowCount() == 0 and not strip.currentIndex().isValid()
    assert not strip.selectionModel().selectedIndexes()
    assert number.value() == number.maximum() == 0 and not number.isEnabled()
    slider = window.findChild(QSlider, 'frameSlider')
    assert slider.value() == slider.maximum() == 0 and not slider.isEnabled()
    for name in ('deleteFrame', 'playPause', 'nextFrame', 'previousFrame', 'zoomIn', 'zoomOut', 'fitImage', 'resetGamma'):
        assert not window.findChild(QPushButton, name).isEnabled()
    assert not gamma.isEnabled()
    assert not window.findChild(QCheckBox, 'pixelProportions').isEnabled()
    assert window.windowTitle() == 'STM Viewer'
    assert window.statusBar().currentMessage() == 'Brak otwartego obrazu'
    assert 'Brak danych.' in labels(window) and 'timed.MPP' not in labels(window)
    assert 'Czas pomiaru:' not in labels(window)

    open_files(qtbot, window, monkeypatch, [FIXTURES / 'mpp/timed.MPP'])

    assert number.value() == 1 and number.maximum() == strip.model().rowCount() == 3
    assert gamma.value() == 1 and gamma.isEnabled() and remove.isEnabled()
    assert 'Klatka źródłowa MPP: 1' in labels(window)
    window.findChild(QPushButton, 'nextFrame').click()
    assert number.value() == 2 and image(window) == second


@pytest.mark.parametrize('remove_number, expected, selected', [
    (1, [(2, 20), (3, 35)], 1),
    (2, [(1, 10), (3, 35)], 2),
    (3, [(1, 10), (2, 20)], 2),
])
def test_remaining_times_keep_gaps_and_original_indices(
    window, qtbot, monkeypatch, remove_number, expected, selected
):
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'mpp/known-times.mpp'])
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(remove_number)
    window.findChild(QPushButton, 'deleteFrame').click()
    assert number.value() == selected
    for position, (source_index, time) in enumerate(expected, start=1):
        number.setValue(position)
        assert f'Klatka źródłowa MPP: {source_index}' in labels(window)
        assert f'Czas pomiaru: {time} s' in labels(window)
        assert f'Zapis czasu: {time} s' in labels(window)


@pytest.mark.parametrize('paths', [
    ['series/klatka1.stp', 'series/klatka2.stp', 'series/klatka10.stp'],
    ['series/klatka1.stp', 's94/frame2.s94', 's94/frame10.S94'],
])
def test_deletion_keeps_images_metadata_and_preview_settings_with_mixed_sources(
    window, qtbot, monkeypatch, tmp_path, paths
):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QDoubleSpinBox

    sources = []
    for relative in paths:
        source = tmp_path / Path(relative).name
        source.write_bytes((FIXTURES / relative).read_bytes())
        sources.append(source)
    original_files = {p: p.read_bytes() for p in sources}
    open_files(qtbot, window, monkeypatch, sources)
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    pixels = window.findChild(QCheckBox, 'pixelProportions')
    gamma.setValue(2)
    pixels.setChecked(True)
    window.findChild(QPushButton, 'zoomIn').click()
    preview = window.findChild(QWidget, 'imagePreview')
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(120, 100))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(145, 115))
    number = window.findChild(QSpinBox, 'frameNumber')
    strip = window.findChild(QListView, 'frameThumbnails')

    def snapshot(row):
        number.setValue(row + 1)
        metadata = next(label.text() for label in window.findChildren(QLabel)
                        if label.text().startswith('Rozmiar:'))
        return image(window), metadata, thumbnail(strip, row), strip.currentIndex().data(Qt.ItemDataRole.ToolTipRole)

    first, last = snapshot(0), snapshot(2)
    assert first[0] != last[0] and first[1] != last[1]
    number.setValue(2)
    window.findChild(QPushButton, 'deleteFrame').click()
    assert number.value() == 2 and gamma.value() == 2 and pixels.isChecked()
    assert snapshot(1) == last
    assert snapshot(0) == first
    assert {p: p.read_bytes() for p in sources} == original_files
    # A new correct import restores every source and resets preview settings.
    open_files(qtbot, window, monkeypatch, sources)
    assert number.maximum() == 3 and gamma.value() == 1 and not pixels.isChecked()


def test_failed_import_does_not_restore_deleted_frames(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    open_files(qtbot, window, monkeypatch, [FIXTURES / 'mpp/known-times.mpp'])
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(2)
    window.findChild(QPushButton, 'deleteFrame').click()
    retained = image(window)
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'mpp/truncated.mpp'])
    message = window.findChild(QMessageBox)
    assert message.isVisible()
    message.accept()
    assert number.value() == number.maximum() == 2 and image(window) == retained
    assert 'Klatka źródłowa MPP: 3' in labels(window) and 'Czas pomiaru: 35 s' in labels(window)


@pytest.mark.parametrize('cancel', [True, False])
def test_delete_only_old_frame_during_import_keeps_worker_result_independent(
    window, qtbot, monkeypatch, cancel
):
    from threading import Event

    open_files(qtbot, window, monkeypatch, [FIXTURES / 'asymmetric.stp'])
    path = (FIXTURES / 'mpp/known-times.mpp').resolve()
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
    button = window.findChild(QPushButton, 'openFrames')
    number = window.findChild(QSpinBox, 'frameNumber')
    try:
        button.click()
        qtbot.waitUntil(entered.is_set)
        window.findChild(QPushButton, 'deleteFrame').click()
        assert number.maximum() == 0 and 'Brak danych.' in labels(window)
        if cancel:
            window.findChild(QPushButton, 'cancelImport').click()
    finally:
        release.set()
        qtbot.waitUntil(button.isEnabled)
    if cancel:
        assert number.maximum() == 0 and not window.findChild(QPushButton, 'deleteFrame').isEnabled()
    else:
        assert number.maximum() == 3 and number.value() == 1
        assert 'Czas pomiaru: 10 s' in labels(window)
        assert window.findChild(QPushButton, 'deleteFrame').isEnabled()
