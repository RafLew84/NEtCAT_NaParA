"""Saved registration trials through user-visible controls and files."""
from pathlib import Path

from PyQt6.QtWidgets import QComboBox, QFileDialog, QLabel, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file

CPU = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


def test_save_reopen_trial_keeps_active_aligned_and_original_sources(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    before = image(window)
    active = window.findChild(QLabel, 'registrationInfo').text()
    path = tmp_path / 'phase.stmtrial.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    save = window.findChild(QPushButton, 'saveTrialB')
    assert save is not None and save.isEnabled()
    save.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    assert path.exists() and path.stat().st_size < 100_000
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'openTrial').click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    assert window.findChild(QComboBox, 'trialB').count() == 2
    assert window.findChild(QLabel, 'registrationInfo').text() == active
    assert image(window) == before
    window.findChild(QComboBox, 'trialView').setCurrentText('Próba B')
    assert image(window) == before
    window.findChild(QPushButton, 'deleteFrame').click()
    assert window.findChild(QComboBox, 'trialB').count() == 0
    assert window.findChild(QSpinBox, 'frameNumber').maximum() == 2


def test_manual_pair_reopens_as_diagnostic_without_promoting_to_movie(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QDialog, QPlainTextEdit
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    pair.findChild(QPushButton, 'manualPairZero').click()
    pair.findChild(QPushButton, 'manualPairXPlus').click()
    pair.findChild(QPushButton, 'manualPairApply').click()
    pair.close()
    path = tmp_path / 'manual.stmtrial.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'saveTrialB').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openTrial').isEnabled)
    open_file(qtbot, window, monkeypatch, CPU)  # New session state with original data only.
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'openTrial').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openTrial').isEnabled)
    assert not window.findChild(QComboBox, 'frameView').isEnabled()
    window.findChild(QPushButton, 'compareTrialPair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    result = pair.findChild(QLabel, 'pairResult').text()
    assert 'ΔX: 1 px' in result and 'jakość nieoceniona' in result
    pair.close()
    window.findChild(QPushButton, 'trialDetails').click()
    text = window.findChild(QPlainTextEdit, 'trialDetailsText').toPlainText()
    assert 'Początkowe XY' in text and 'Korekta XY' in text
    assert 'niezależnej oceny' in text


def test_failed_attempt_survives_save_load_without_becoming_aligned(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU.with_name('flat.mpp'))
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    window.findChild(QMessageBox).accept()
    path = tmp_path / 'failed.stmtrial.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'saveTrialB').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openTrial').isEnabled)
    assert path.exists()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'openTrial').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openTrial').isEnabled)
    assert 'przerwana' in window.findChild(QComboBox, 'trialB').currentText()
    window.findChild(QComboBox, 'trialView').setCurrentText('Próba B')
    assert 'kompletnych prób' in window.findChild(QLabel, 'trialInfo').text()
    assert not window.findChild(QComboBox, 'frameView').isEnabled()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QPushButton, 'openTrial').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openTrial').isEnabled)
    assert window.findChild(QComboBox, 'trialB').count() == 0
    assert 'Nie udało' in window.findChild(QLabel, 'trialInfo').text()


def test_two_movie_corrections_reopen_compare_and_export_active_movie(qtbot, monkeypatch, tmp_path):
    import numpy as np
    from PyQt6.QtWidgets import QDialog, QDoubleSpinBox
    from stmviewer.series import open_frame_series
    from test_manual_movie_gui import registered_pair
    window, pair = registered_pair(qtbot, monkeypatch)
    register = window.findChild(QPushButton, 'registerFrames')
    for index, nudge in ((2, 'manualPairXPlus'), (3, 'manualPairYPlus')):
        pair.findChild(QSpinBox, 'pairNumber').setValue(index)
        pair.findChild(QPushButton, 'manualMovieStart').click()
        pair.findChild(QPushButton, nudge).click()
        pair.findChild(QPushButton, 'manualPairApply').click()
        pair.findChild(QPushButton, 'manualMovieApply').click()
        qtbot.waitUntil(register.isEnabled)
    pair.close()
    path = tmp_path / 'corrected.stmtrial.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'saveTrialB').click()
    qtbot.waitUntil(register.isEnabled)
    assert path.exists(), window.findChild(QLabel, 'trialInfo').text()
    # Keep an uncorrected Phase result as the active export; imported B differs.
    register.click()
    qtbot.waitUntil(register.isEnabled)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'openTrial').click()
    qtbot.waitUntil(register.isEnabled)
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(3)
    active = window.findChild(QLabel, 'registrationInfo').text()
    view = window.findChild(QComboBox, 'trialView')
    view.setCurrentText('Próba A')
    window.findChild(QPushButton, 'zoomIn').click()
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(1.7)
    a = image(window)
    view.setCurrentText('Próba B')
    b = image(window)
    assert a != b
    view.setCurrentText('Próba A')
    assert image(window) == a  # Same zoom, gamma and canvas when switching.
    view.setCurrentText('Próba B')
    window.findChild(QPushButton, 'playPause').click()
    qtbot.waitUntil(lambda: window.findChild(QPushButton, 'playPause').text() == 'Play', timeout=3000)
    assert number.value() == 3
    assert window.findChild(QLabel, 'registrationInfo').text() == active
    exported = tmp_path / 'active.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(exported), 'MPP aligned (*.mpp *.MPP)'))
    window.findChild(QPushButton, 'saveOriginalMpp').click()
    qtbot.waitUntil(register.isEnabled)
    loaded = open_frame_series([exported])
    assert loaded[2].alignment.shift_xy == (-1.0, 1.0)  # Active Phase, not saved B (0, 2).
    assert np.isfinite(loaded[2].data).any()
    window.findChild(QPushButton, 'compareTrialPair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    assert 'ΔX: -3 px' in pair.findChild(QLabel, 'pairResult').text()
    assert 'jakość nieoceniona' in pair.findChild(QLabel, 'pairResult').text()
    pair.close()
