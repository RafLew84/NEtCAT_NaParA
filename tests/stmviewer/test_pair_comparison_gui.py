"""Pair experiments are driven through visible controls, independently of aligned."""

from pathlib import Path
from threading import Event

import pytest

from PyQt6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QSpinBox, QWidget
from PyQt6.QtWidgets import QDoubleSpinBox
from PyQt6.QtCore import QPoint, Qt

from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file


CPU = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


def test_pair_trial_keeps_full_aligned_and_uses_selected_source_pair(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    opener = window.findChild(QPushButton, 'comparePair')
    assert opener is not None and not opener.isEnabled()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    before = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()

    opener.click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert dialog is not None and dialog.isVisible()
    assert 'MPP 2' in dialog.findChild(QLabel, 'pairSource').text()
    assert 'MPP 3' in dialog.findChild(QLabel, 'pairSource').text()
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=5000)
    result = dialog.findChild(QLabel, 'pairResult').text()
    assert 'Phase' in result and 'ΔX: -3 px' in result and 'ΔY: 2 px' in result
    assert 'względem poprzedniej' in result
    assert image(window) == before
    assert window.findChild(QLabel, 'registrationInfo').text() == info
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    dialog.close()


def test_series_replacement_or_deletion_discards_pair_trials(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)

    def trial():
        window.findChild(QPushButton, 'comparePair').click()
        dialog = window.findChild(QDialog, 'pairComparison')
        run = dialog.findChild(QPushButton, 'runPair')
        run.click()
        qtbot.waitUntil(run.isEnabled)
        dialog.findChild(QPushButton, 'pinPair').click()
        return dialog

    trial()
    open_file(qtbot, window, monkeypatch, CPU.with_name('missing-file.mpp'))
    retained = window.findChild(QDialog, 'pairComparison')
    assert retained is not None and retained.findChild(QComboBox, 'pairTrial').count() == 2
    from PyQt6.QtWidgets import QMessageBox
    window.findChild(QMessageBox).accept()
    open_file(qtbot, window, monkeypatch, CPU)
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    trial()
    window.findChild(QPushButton, 'deleteFrame').click()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    window.findChild(QPushButton, 'comparePair').click()
    fresh = window.findChild(QDialog, 'pairComparison')
    assert 'MPP 2' in fresh.findChild(QLabel, 'pairSource').text()
    assert 'MPP 3' in fresh.findChild(QLabel, 'pairSource').text()
    assert fresh.findChild(QComboBox, 'pairTrial').count() == 1
    assert 'Brak wyniku' in fresh.findChild(QLabel, 'pairResult').text()
    fresh.close()


@pytest.mark.parametrize('outcome', ['cancel', 'error', 'escape'])
def test_pair_cancellation_failure_and_close_preserve_previous_trial(qtbot, monkeypatch, outcome):
    from PyQt6.QtCore import QThread
    from stmviewer.registration import create_shift_backend

    class ControlledBackend:
        def __init__(self):
            self.real = create_shift_backend('phase_correlation')
            self.hold = False
            self.entered, self.release = Event(), Event()

        def estimate(self, *args, **kwargs):
            if self.hold:
                self.entered.set()
                if not self.release.wait(5):
                    raise RuntimeError('test backend deadline')
                if outcome == 'error':
                    raise RuntimeError('controlled pair failure')
            return self.real.estimate(*args, **kwargs)

    backend = ControlledBackend()
    window = STMViewerMainWindow(registration_backend=backend)
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QPushButton, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    previous = dialog.findChild(QLabel, 'pairResult').text()
    pixels = dialog.findChild(QWidget, 'pairPreview').grab().toImage()
    backend.hold = True
    run.click()
    qtbot.waitUntil(backend.entered.is_set)
    worker = dialog.findChild(QThread)
    try:
        for name in ('openFrames', 'deleteFrame', 'registerFrames', 'saveOriginalMpp', 'playPause'):
            assert not window.findChild(QPushButton, name).isEnabled()
        assert not dialog.findChild(QSpinBox, 'pairNumber').isEnabled()
        if outcome == 'cancel':
            dialog.findChild(QPushButton, 'cancelPair').click()
        elif outcome == 'escape':
            qtbot.keyClick(dialog, Qt.Key.Key_Escape)
            assert dialog.isVisible()  # Closing waits for native estimation to finish safely.
    finally:
        backend.release.set()
        worker.wait(5000)
    if outcome == 'escape':
        qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    else:
        qtbot.waitUntil(run.isEnabled)
        assert dialog.findChild(QLabel, 'pairResult').text() == previous
        assert dialog.findChild(QWidget, 'pairPreview').grab().toImage() == pixels
        message = dialog.findChild(QLabel, 'pairMessage').text()
        assert ('Anulowano' if outcome == 'cancel' else 'controlled pair failure') in message
        dialog.close()
    assert window.findChild(QPushButton, 'openFrames').isEnabled()


def test_pinned_trials_share_reference_coordinates_zoom_and_contrast(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QPushButton, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    pin = dialog.findChild(QPushButton, 'pinPair')
    assert pin is not None and pin.isEnabled()
    pin.click()
    layer = dialog.findChild(QComboBox, 'pairLayer')
    layer.setCurrentText('Odniesienie')
    preview = dialog.findChild(QWidget, 'pairPreview')
    preview.setFixedSize(400, 360)
    dialog.findChild(QPushButton, 'pairZoomIn').click()
    dialog.findChild(QPushButton, 'pairZoomIn').click()
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(200, 180))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(220, 190))
    gamma = dialog.findChild(QDoubleSpinBox, 'pairGamma')
    gamma.setValue(1.7)
    reference_before = preview.grab().toImage()
    contrast = dialog.findChild(QLabel, 'pairContrast').text()
    dialog.findChild(QComboBox, 'pairMethod').setCurrentText('Optical Flow')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=5000)
    assert preview.grab().toImage() == reference_before
    trials = dialog.findChild(QComboBox, 'pairTrial')
    trials.setCurrentText('A — przypięta')
    assert 'Phase' in dialog.findChild(QLabel, 'pairResult').text()
    assert preview.grab().toImage() == reference_before
    trials.setCurrentText('B — ostatnia')
    assert 'Optical Flow' in dialog.findChild(QLabel, 'pairResult').text()
    assert preview.grab().toImage() == reference_before
    assert dialog.findChild(QLabel, 'pairContrast').text() == contrast
    assert gamma.value() == 1.7
    layer.setCurrentText('Nakładka 50/50')
    assert 'Wspólne ważne piksele' in dialog.findChild(QLabel, 'pairOverlap').text()
    dialog.findChild(QSpinBox, 'pairNumber').setValue(3)
    assert not pin.isEnabled()
    assert trials.count() == 1
    assert 'Brak wyniku' in dialog.findChild(QLabel, 'pairResult').text()
    dialog.close()
