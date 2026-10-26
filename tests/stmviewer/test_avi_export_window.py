"""Public AVI controls with real movie writing and decoding."""
import numpy as np
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QLabel, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_avi_export import decode
from test_mpp_export_window import open_movie, FIXTURES


def configure_dialog(window, *, codec='FFV1', start=1, end=1, fps=7, shared=False):
    dialog = window.findChild(QDialog, 'aviOptions')
    assert dialog is not None and dialog.isVisible()
    assert dialog.findChild(QComboBox, 'aviCodec').currentText() == 'MJPG'
    assert dialog.findChild(QSpinBox, 'aviFps').value() == 5
    dialog.findChild(QComboBox, 'aviRange').setCurrentIndex(1)
    dialog.findChild(QSpinBox, 'aviStart').setValue(start)
    dialog.findChild(QSpinBox, 'aviEnd').setValue(end)
    dialog.findChild(QSpinBox, 'aviFps').setValue(fps)
    dialog.findChild(QComboBox, 'aviCodec').setCurrentText(codec)
    if shared:
        dialog.findChild(QComboBox, 'aviContrast').setCurrentIndex(1)
        dialog.findChild(QComboBox, 'aviBackground').setCurrentIndex(1)
    summary = dialog.findChild(QLabel, 'aviSummary').text()
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
    return summary


def test_avi_dialog_exports_range_and_snapshot_of_gamma_without_changing_play(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    save = window.findChild(QPushButton, 'saveAvi')
    assert save is not None and not save.isEnabled()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'mpp/known-times.mpp')
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'deleteFrame').click()
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(2)
    window.findChild(QPushButton, 'zoomIn').click()
    path = tmp_path / 'movie'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    summaries = []
    QTimer.singleShot(10, lambda: summaries.append(configure_dialog(window, start=2, end=2)))
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'aviExportInfo').text()
    fps, decoded = decode(path.with_suffix('.avi'))
    assert fps == 7 and len(decoded) == 1
    assert '1 kl.' in summaries[0] and '0.143 s' in summaries[0]
    assert window.findChild(QComboBox, 'playbackFps').currentText() == '5'
    assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 2
    assert window.findChild(QSpinBox, 'frameNumber').value() == 2


@pytest.mark.parametrize('outcome', ['cancel', 'error', 'close', 'success'])
@pytest.mark.parametrize('shared', [False, True])
def test_avi_worker_responsive_with_frozen_options_and_safe_cancellation(qtbot, monkeypatch, tmp_path, outcome, shared):
    from threading import Event
    import cv2
    from PyQt6.QtWidgets import QMessageBox, QProgressBar
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation, movie_contrast_levels, render_movie_frame
    from stmviewer.series import open_frame_series
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    source = FIXTURES / 'mpp/known-times.mpp'
    open_movie(qtbot, window, monkeypatch, source)
    frames = open_frame_series([source])
    path = tmp_path / 'existing.avi'
    save_avi(path, prepare_avi(frames, start=1, end=1, codec='FFV1'))
    previous = path.read_bytes()
    entered, release = Event(), Event()
    real_writer = cv2.VideoWriter

    class DelayedWriter:
        def __init__(self, *args):
            self.writer = real_writer(*args)
        def isOpened(self):
            return self.writer.isOpened()
        def release(self):
            self.writer.release()
        def write(self, raster):
            entered.set()
            if not release.wait(5):
                raise OSError('Timeout')
            if outcome == 'error':
                raise OSError('Dysk pełny')
            self.writer.write(raster)

    monkeypatch.setattr(cv2, 'VideoWriter', DelayedWriter)
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    save = window.findChild(QPushButton, 'saveAvi')
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(2)
    window.findChild(QPushButton, 'playPause').click()
    QTimer.singleShot(10, lambda: configure_dialog(window, start=1, end=3, shared=shared))
    try:
        save.click()
        qtbot.waitUntil(entered.is_set)
        assert window.findChild(QProgressBar, 'aviExportProgress').isVisible()
        for name in ('saveAvi', 'saveOriginalMpp', 'openFrames', 'deleteFrame', 'registerFrames', 'playPause'):
            assert not window.findChild(QPushButton, name).isEnabled(), name
        assert window.findChild(QPushButton, 'playPause').text() == 'Play'
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        window.findChild(QSpinBox, 'frameNumber').setValue(3)
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(3)
        window.findChild(QPushButton, 'zoomIn').click()
        if outcome == 'cancel':
            window.findChild(QPushButton, 'cancelAviExport').click()
        elif outcome == 'close':
            window.close()
            assert window.isVisible()
    finally:
        release.set()
        qtbot.waitUntil(save.isEnabled)
    if outcome == 'success':
        plan = prepare_avi(frames, presentation=MoviePresentation(
            gamma=2, background=128 if shared else 0, contrast='movie' if shared else 'per_frame'))
        fps, decoded = decode(path)
        assert fps == 7 and len(decoded) == 3
        for actual, image in zip(decoded, frames, strict=True):
            np.testing.assert_array_equal(actual, render_movie_frame(
                image, plan.presentation, plan.geometry, contrast_limits=movie_contrast_levels(frames)))
    else:
        assert path.read_bytes() == previous
        assert ('Dysk pełny' if outcome == 'error' else 'Anulowano') in window.findChild(QLabel, 'aviExportInfo').text()
    if outcome == 'close':
        assert not window.isVisible()


def test_invalid_range_and_cancel_leave_no_movie(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'mpp/known-times.mpp')

    def cancel_invalid():
        dialog = window.findChild(QDialog, 'aviOptions')
        dialog.findChild(QComboBox, 'aviRange').setCurrentIndex(1)
        dialog.findChild(QSpinBox, 'aviStart').setValue(3)
        dialog.findChild(QSpinBox, 'aviEnd').setValue(2)
        assert not dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).isEnabled()
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()

    QTimer.singleShot(10, cancel_invalid)
    window.findChild(QPushButton, 'saveAvi').click()
    assert not list(tmp_path.iterdir())
