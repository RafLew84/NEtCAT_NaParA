"""Registration driven by the public window controls and observed pixels/labels."""

from pathlib import Path

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QFileDialog, QLabel, QPushButton, QSpinBox, QWidget

from make_mpp_fixtures import movie_bytes
from stmviewer.ui.main_window import STMViewerMainWindow


def shifted_movie(tmp_path):
    frame = np.random.default_rng(42).normal(size=(32, 48))
    frame[8:15, 10:18] += 4
    frames = [frame, np.roll(frame, (2, -3), (0, 1)), np.roll(frame, (1, 2), (0, 1))]
    path = tmp_path / 'shifted.mpp'
    path.write_bytes(movie_bytes([a[::-1, ::-1].ravel() for a in frames], rows=32, columns=48))
    return path


def open_file(qtbot, window, monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(path)], ''))
    button = window.findChild(QPushButton, 'openFrames')
    button.click()
    qtbot.waitUntil(button.isEnabled)


def image(window):
    return window.findChild(QWidget, 'imagePreview').grab().toImage()


def labels(window):
    return '\n'.join(label.text() for label in window.findChildren(QLabel))


def test_register_switch_views_and_keep_gamma_and_separate_zoom(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(2)
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    gamma.setValue(2)
    window.findChild(QPushButton, 'zoomIn').click()
    original = image(window)
    register = window.findChild(QPushButton, 'registerFrames')
    assert register is not None and register.isEnabled()

    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)

    view = window.findChild(QComboBox, 'frameView')
    assert view.currentText() == 'aligned' and number.value() == 2
    assert gamma.value() == 2 and window.findChild(QPushButton, 'playPause').text() == 'Play'
    assert '53 × 34 px' in labels(window)
    assert 'ΔX: 3 px' in labels(window) and 'ΔY: -2 px' in labels(window)
    assert 'Odniesienie: shifted.mpp · MPP 1' in labels(window)
    window.findChild(QPushButton, 'zoomIn').click()
    window.findChild(QPushButton, 'zoomIn').click()
    aligned = image(window)
    view.setCurrentText('original')
    assert image(window) == original
    view.setCurrentText('aligned')
    assert image(window) == aligned
    assert aligned != original


def test_deleting_reference_keeps_aligned_pixels_canvas_and_origin_until_reregistration(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    path = shifted_movie(tmp_path)
    original_bytes = path.read_bytes()
    open_file(qtbot, window, monkeypatch, path)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(2)
    second = image(window)
    number.setValue(1)

    window.findChild(QPushButton, 'deleteFrame').click()

    assert image(window) == second
    assert '53 × 34 px' in labels(window) and 'Odniesienie: shifted.mpp · MPP 1' in labels(window)
    assert number.value() == 1 and number.maximum() == 2
    assert 'Klatka źródłowa MPP: 2' in labels(window)
    # Drop the extreme right image too: the third retains the original canvas.
    window.findChild(QPushButton, 'deleteFrame').click()
    assert '53 × 34 px' in labels(window) and 'ΔX: -2 px' in labels(window)
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert '48 × 32 px' in labels(window) and 'ΔX: 0 px' in labels(window)
    assert 'Odniesienie: shifted.mpp · MPP 3' in labels(window)
    window.findChild(QPushButton, 'deleteFrame').click()
    assert not register.isEnabled() and not window.findChild(QComboBox, 'frameView').isEnabled()
    assert 'Aligned:' not in labels(window) and 'Brak danych.' in labels(window)
    assert path.read_bytes() == original_bytes
    open_file(qtbot, window, monkeypatch, path)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'original'
    assert number.maximum() == 3


class GatedPhase:
    """Controllable boundary to the external estimator; uses real Phase results."""
    def __init__(self):
        from threading import Event
        self.entered, self.release = Event(), Event()
        self.block = False

    def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
        from nanotrack.registration.phase_correlation import PhaseCorrelationShiftBackend
        if self.block:
            self.entered.set()
            if not self.release.wait(5):
                raise RuntimeError('Backend wait timed out')
        return PhaseCorrelationShiftBackend().estimate(reference_frame, moving_frame,
                                                       moving_frame_index=moving_frame_index)


def test_busy_registration_keeps_navigation_and_publishes_current_frame_after_success(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QProgressBar

    backend = GatedPhase()
    window = STMViewerMainWindow(registration_backend=backend)
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    window.findChild(QComboBox, 'playbackFps').setCurrentText('1')
    window.findChild(QPushButton, 'playPause').click()
    register = window.findChild(QPushButton, 'registerFrames')
    backend.block = True
    try:
        register.click()
        qtbot.waitUntil(backend.entered.is_set)
        assert window.findChild(QPushButton, 'playPause').text() == 'Play'
        for name in ('openFrames', 'deleteFrame', 'playPause', 'registerFrames'):
            assert not window.findChild(QPushButton, name).isEnabled()
        assert not window.findChild(QComboBox, 'registrationMethod').isEnabled()
        assert window.findChild(QProgressBar, 'registrationProgress').isVisible()
        window.findChild(QSpinBox, 'frameNumber').setValue(3)
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(2)
        window.findChild(QPushButton, 'zoomIn').click()
        original = image(window)
    finally:
        backend.release.set()
        qtbot.waitUntil(register.isEnabled)
    assert window.findChild(QSpinBox, 'frameNumber').value() == 3
    assert 'Klatka źródłowa MPP: 3' in labels(window) and 'ΔX: -2 px' in labels(window)
    assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 2
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    window.findChild(QComboBox, 'frameView').setCurrentText('original')
    assert image(window) == original


def test_close_waits_for_cancelled_backend_without_destroying_thread(qtbot, monkeypatch, tmp_path):
    backend = GatedPhase()
    backend.block = True
    window = STMViewerMainWindow(registration_backend=backend)
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    try:
        window.findChild(QPushButton, 'registerFrames').click()
        qtbot.waitUntil(backend.entered.is_set)
        window.close()
        assert window.isVisible()
        assert not window.findChild(QPushButton, 'cancelRegistration').isEnabled()
        assert not window.findChild(QPushButton, 'openFrames').isEnabled()
    finally:
        backend.release.set()
        qtbot.waitUntil(window.findChild(QPushButton, 'registerFrames').isEnabled)
    qtbot.waitUntil(lambda: not window.isVisible())


@pytest.mark.parametrize('cancel', [True, False])
def test_cancel_or_materialization_error_keeps_previous_aligned_and_current_view(
    qtbot, monkeypatch, tmp_path, cancel
):
    from threading import Event
    from scipy import ndimage
    from PyQt6.QtWidgets import QMessageBox, QProgressBar

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    entered, release = Event(), Event()
    real_transform = ndimage.affine_transform
    calls = 0

    def blocked_transform(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Interpolation wait timed out')
            if not cancel:
                raise MemoryError('controlled allocation failure')
        return real_transform(*args, **kwargs)

    monkeypatch.setattr(ndimage, 'affine_transform', blocked_transform)
    try:
        register.click()
        qtbot.waitUntil(entered.is_set)
        window.findChild(QSpinBox, 'frameNumber').setValue(3)
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(1.5)
        window.findChild(QPushButton, 'zoomIn').click()
        view = window.findChild(QComboBox, 'frameView')
        view.setCurrentText('original')
        original = image(window)
        view.setCurrentText('aligned')
        retained = image(window)
        if cancel:
            window.findChild(QPushButton, 'cancelRegistration').click()
            assert 'Anulowanie' in window.findChild(QProgressBar, 'registrationProgress').format()
        assert not window.findChild(QPushButton, 'openFrames').isEnabled()
        assert not window.findChild(QPushButton, 'deleteFrame').isEnabled()
    finally:
        release.set()
        qtbot.waitUntil(register.isEnabled)
    if not cancel:
        message = window.findChild(QMessageBox)
        assert message is not None and 'Aligned: klatka 2' in message.text()
        message.accept()
    assert image(window) == retained
    assert '53 × 34 px' in labels(window) and 'ΔX: -2 px' in labels(window)
    assert window.findChild(QSpinBox, 'frameNumber').value() == 3
    view.setCurrentText('original')
    assert image(window) == original
    view.setCurrentText('aligned')
    assert image(window) == retained


def test_low_confidence_marks_current_frame_and_thumbnails_including_inherited(qtbot, monkeypatch, tmp_path):
    from nanotrack.core import RegistrationFrameResult
    from PyQt6.QtWidgets import QListView

    class Uncertain:
        def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
            return RegistrationFrameResult(moving_frame_index, (0, 0), 'controlled', quality_score=0.2,
                                           status='low_confidence' if moving_frame_index == 1 else 'ok')

    window = STMViewerMainWindow(registration_backend=Uncertain())
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    strip = window.findChild(QListView, 'frameThumbnails')
    assert '⚠' not in strip.model().index(0).data()
    assert '⚠' in strip.model().index(1).data()
    assert 'odziedziczona' in strip.model().index(2).data(Qt.ItemDataRole.ToolTipRole)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    assert 'Do sprawdzenia' in labels(window) and 'odziedziczona' in labels(window)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'deleteFrame').click()
    assert '⚠' in strip.currentIndex().data()
    assert 'odziedziczona' in labels(window)


def test_missing_phase_dependency_is_visible_and_does_not_prevent_browsing(qtbot, monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def missing_scipy(name, *args, **kwargs):
        if name == 'scipy.ndimage':
            raise ModuleNotFoundError('No module named scipy.ndimage')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', missing_scipy)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    assert not window.findChild(QPushButton, 'registerFrames').isEnabled()
    assert 'Phase niedostępna' in labels(window) and 'scipy.ndimage' in labels(window)
    assert window.findChild(QPushButton, 'nextFrame').isEnabled()


@pytest.mark.parametrize('invalid, reason', [('nan', 'NaN'), ('flat', 'tekstur')])
def test_bad_input_keeps_original_and_explains_why_phase_cannot_run(qtbot, monkeypatch, tmp_path, invalid, reason):
    from PyQt6.QtWidgets import QMessageBox

    values = np.ones((12, 16))
    if invalid == 'nan':
        values[3, 4] = np.nan
    path = tmp_path / 'invalid.mpp'
    path.write_bytes(movie_bytes([values.ravel(), values.ravel()], rows=12, columns=16))
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, path)
    original = image(window)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    message = window.findChild(QMessageBox)
    assert message is not None and reason in message.text()
    message.accept()
    assert window.findChild(QComboBox, 'frameView').currentText() == 'original'
    assert not window.findChild(QComboBox, 'frameView').isEnabled()
    assert image(window) == original


def test_import_failure_keeps_aligned_and_new_series_resets_result_and_view(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    path = shifted_movie(tmp_path)
    open_file(qtbot, window, monkeypatch, path)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QPushButton, 'zoomIn').click()
    aligned = image(window)
    view = window.findChild(QComboBox, 'frameView')
    open_file(qtbot, window, monkeypatch, Path(__file__).parent / 'fixtures/mpp/truncated.mpp')
    window.findChild(QMessageBox).accept()
    assert view.currentText() == 'aligned' and image(window) == aligned
    assert 'Odniesienie:' in labels(window)
    open_file(qtbot, window, monkeypatch, path)
    assert view.currentText() == 'original' and not view.isEnabled()
    assert 'Odniesienie:' not in labels(window)
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QPushButton, 'zoomIn').click()
    assert image(window) == aligned
