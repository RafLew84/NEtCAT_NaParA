"""Original export through public Qt controls, with real writer and reader."""
from pathlib import Path

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QWidget

from stmviewer.series import open_frame_series
from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / 'fixtures'


def open_movie(qtbot, window, monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *a: ([str(path)], ''))
    button = window.findChild(QPushButton, 'openFrames')
    button.click()
    qtbot.waitUntil(button.isEnabled)


def test_save_uses_entire_remaining_original_and_preserves_preview(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    assert save is not None and not save.isEnabled()
    source = FIXTURES / 'mpp/known-times.mpp'
    open_movie(qtbot, window, monkeypatch, source)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'deleteFrame').click()
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(2)
    window.findChild(QPushButton, 'zoomIn').click()
    preview = window.findChild(QWidget, 'imagePreview').grab().toImage()
    destination = tmp_path / 'output'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(destination), ''))
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'mppExportInfo').text()
    assert save.isEnabled()
    restored = open_frame_series([destination.with_suffix('.mpp')])
    original = open_frame_series([source])
    for saved, source_frame in zip(restored, (original[0], original[2]), strict=True):
        np.testing.assert_array_equal(saved.data, source_frame.data)
    assert [f.measurement_time_s for f in restored] == [10, 35]
    assert window.findChild(QWidget, 'imagePreview').grab().toImage() == preview
    assert window.findChild(QSpinBox, 'frameNumber').value() == 2
    assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 2


def test_cancel_dialog_and_decline_overwrite_of_metadata_only(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import QTimer

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'asymmetric.stp')
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: ('', ''))
    save.click()
    assert not list(tmp_path.iterdir())
    path = tmp_path / 'existing.mpp'
    sidecar = path.with_name(path.name + '.stmviewer.json')
    sidecar.write_bytes(b'old metadata')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    confirmations = []

    def answer(button):
        dialog = next(w for w in window.findChildren(QMessageBox) if w.isVisible())
        confirmations.append(dialog.text())
        dialog.button(button).click()

    QTimer.singleShot(20, lambda: answer(QMessageBox.StandardButton.No))
    save.click()
    assert not path.exists() and sidecar.read_bytes() == b'old metadata'
    assert str(sidecar) in confirmations[0]
    QTimer.singleShot(20, lambda: answer(QMessageBox.StandardButton.Yes))
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert len(open_frame_series([path])) == 1
    assert 'wczytano' in open_frame_series([path])[0].metadata_note


def test_export_can_explicitly_choose_original_from_aligned_view(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QComboBox
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    source = FIXTURES / 'registration/integer.mpp'
    open_movie(qtbot, window, monkeypatch, source)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    path = tmp_path / 'original.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), 'MPP original — NaN (*.mpp *.MPP)'))
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    for actual, expected in zip(open_frame_series([path]), open_frame_series([source]), strict=True):
        np.testing.assert_array_equal(actual.data, expected.data)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'


@pytest.mark.parametrize('outcome', ['cancel', 'error', 'close', 'success'])
def test_export_worker_keeps_gui_responsive_and_locks_series(qtbot, monkeypatch, tmp_path, outcome):
    from threading import Event
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QProgressBar
    from stmviewer.mpp_export import save_original_mpp

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    source = FIXTURES / 'mpp/known-times.mpp'
    open_movie(qtbot, window, monkeypatch, source)
    path = tmp_path / 'result.mpp'
    save_original_mpp(path, open_frame_series([FIXTURES / 'asymmetric.stp']))
    sidecar = path.with_name(path.name + '.stmviewer.json')
    previous_pair = (path.read_bytes(), sidecar.read_bytes())
    entered, release = Event(), Event()
    real_open = Path.open

    class DelayedWriter:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def write(self, data):
            entered.set()
            if not release.wait(5):
                raise OSError('I/O timeout')
            if outcome == 'error':
                raise OSError('Disk full')
            return self.stream.write(data)

    def delayed_open(filename, mode='r', *args, **kwargs):
        stream = real_open(filename, mode, *args, **kwargs)
        return DelayedWriter(stream) if mode == 'xb' else stream

    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    monkeypatch.setattr(Path, 'open', delayed_open)
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    window.findChild(QPushButton, 'playPause').click()
    try:
        save.click()
        qtbot.waitUntil(entered.is_set)
        assert window.findChild(QProgressBar, 'mppExportProgress').isVisible()
        for name in ('saveOriginalMpp', 'openFrames', 'deleteFrame', 'registerFrames', 'playPause'):
            assert not window.findChild(QPushButton, name).isEnabled(), name
        assert window.findChild(QPushButton, 'playPause').text() == 'Play'
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        window.findChild(QSpinBox, 'frameNumber').setValue(3)
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(3)
        window.findChild(QPushButton, 'zoomIn').click()
        if outcome == 'cancel':
            cancel = window.findChild(QPushButton, 'cancelMppExport')
            cancel.click()
            assert not cancel.isEnabled()
        if outcome == 'close':
            window.close()
            assert window.isVisible()  # waits for the worker before destroying Qt objects
    finally:
        release.set()
        qtbot.waitUntil(save.isEnabled)
    if outcome != 'success':
        assert (path.read_bytes(), sidecar.read_bytes()) == previous_pair
        message = window.findChild(QLabel, 'mppExportInfo').text()
        assert ('Disk full' if outcome == 'error' else 'Anulowano') in message
    else:
        assert len(open_frame_series([path])) == 3
    if outcome == 'close':
        assert not window.isVisible()
    else:
        assert window.findChild(QSpinBox, 'frameNumber').value() == 3
        assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 3
        assert window.findChild(QPushButton, 'deleteFrame').isEnabled()
