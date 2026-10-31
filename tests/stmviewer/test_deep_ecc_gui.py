"""Hybrid trials expose the exact Deep start without replacing saved comparisons."""

import pytest

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QDoubleSpinBox, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget

from stmviewer.ui.main_window import STMViewerMainWindow
from test_deep_registration import FIXTURE, local_model as local_model_fixture
from test_registration_gui import open_file

local_model = local_model_fixture
LABEL = 'Deep Matcher + ECC (v1)'


def test_user_compares_same_run_deep_and_ecc_with_saved_trial_and_view_intact(qtbot, monkeypatch, local_model):
    import kornia.feature
    base = kornia.feature.LoFTR
    calls = []

    class OffsetMatcher(base):
        def forward(self, images):
            calls.append(True)
            points = super().forward(images)
            points['keypoints1'] -= points['keypoints1'].new_tensor([0.35, -0.25])
            return points

    monkeypatch.setattr(kornia.feature, 'LoFTR', OffsetMatcher)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    method = window.findChild(QComboBox, 'registrationMethod')
    assert method.currentText() == 'Phase'
    assert method.findText(LABEL) >= 0
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    pinned_text = dialog.findChild(QLabel, 'pairResult').text()
    dialog.findChild(QPushButton, 'pinPair').click()
    layer = dialog.findChild(QComboBox, 'pairLayer')
    layer.setCurrentText('Klatka bazowa')
    preview = dialog.findChild(QWidget, 'pairPreview')
    preview.setFixedSize(400, 350)
    dialog.findChild(QPushButton, 'pairZoomIn').click()
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(200, 185))
    gamma = dialog.findChild(QDoubleSpinBox, 'pairGamma')
    gamma.setValue(1.8)
    reference_pixels = preview.grab().toImage()
    contrast = dialog.findChild(QLabel, 'pairContrast').text()

    dialog.findChild(QComboBox, 'pairMethod').setCurrentText(LABEL)
    dialog.findChild(QLineEdit, 'deepWeights').setText(str(local_model))
    dialog.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=10000)
    result = dialog.findChild(QLabel, 'pairResult').text()
    assert LABEL in result and 'pewność niezweryfikowana' in result
    assert 'wybrane urządzenie=cpu' in result and str(local_model) in result
    summary = dialog.findChild(QLabel, 'pairHybridDetails').text()
    assert 'Start Deep' in summary and 'Wynik ECC' in summary and 'Poprawka' in summary
    assert 'miary backendów' in summary and 'manual_review' in result
    assert calls == [True]
    stage = dialog.findChild(QComboBox, 'pairHybridStage')
    assert stage.isVisible()
    stage.setCurrentText('Start Deep tej próby')
    assert 'Start Deep' in dialog.findChild(QLabel, 'pairPreviewStatus').text()
    start = dialog.findChild(QLabel, 'pairResult').text()
    assert 'ΔX: 2.35 px' in start and 'ΔY: -1.25 px' in start
    assert preview.grab().toImage() == reference_pixels
    layer.setCurrentText('Nakładka 50/50')
    start_pixels = preview.grab().toImage()
    stage.setCurrentText('Wynik po ECC')
    assert preview.grab().toImage() != start_pixels
    layer.setCurrentText('Klatka bazowa')
    assert preview.grab().toImage() == reference_pixels
    assert gamma.value() == 1.8 and dialog.findChild(QLabel, 'pairContrast').text() == contrast
    dialog.findChild(QPushButton, 'pairSavedResult').click()
    assert dialog.findChild(QLabel, 'pairResult').text() == pinned_text
    assert not stage.isVisible()
    assert calls == [True]
    assert method.currentText() == 'Phase'
    dialog.close()


def test_hybrid_availability_and_complete_movie_are_visible(qtbot, monkeypatch, local_model):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentText(LABEL)
    run = window.findChild(QPushButton, 'registerFrames')
    assert not run.isEnabled()
    assert 'Wskaż lokalny plik wag' in window.findChild(QLabel, 'registrationAvailability').text()
    weights = window.findChild(QLineEdit, 'deepWeights')
    assert weights.isVisible()
    weights.setText(str(local_model))
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=10000)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    info = window.findChild(QLabel, 'registrationInfo').text()
    assert LABEL in info and 'pewność niezweryfikowana' in info
    assert 'Start Deep' in info and 'Wynik ECC' in info and 'Poprawka' in info
    assert 'ECC CPU' in info and str(local_model) in info
    window.findChild(QPushButton, 'playPause').click()
    qtbot.waitUntil(lambda: window.findChild(QSpinBox, 'frameNumber').value() == 3)
    assert window.findChild(QPushButton, 'saveOriginalMpp').isEnabled()
    assert window.findChild(QPushButton, 'saveAvi').isEnabled()


@pytest.mark.parametrize('stage', ['Deep Matcher', 'ECC'])
@pytest.mark.parametrize('outcome', ['error', 'cancel'])
def test_stage_failure_or_cancel_keeps_previous_movie_and_manual_correction(
        qtbot, monkeypatch, local_model, stage, outcome):
    from threading import Event
    import cv2
    import kornia.feature
    from PyQt6.QtWidgets import QMessageBox, QProgressBar
    from test_manual_movie_gui import registered_pair, assert_shifts
    from test_manual_pair_gui import button
    from test_registration_gui import image

    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    run = button(window, 'registerFrames')
    qtbot.waitUntil(run.isEnabled)
    dialog.close()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    window.findChild(QComboBox, 'registrationMethod').setCurrentText(LABEL)
    window.findChild(QLineEdit, 'deepWeights').setText(str(local_model))
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    before, info = image(window), window.findChild(QLabel, 'registrationInfo').text()
    entered, release = Event(), Event()
    base, real_ecc = kornia.feature.LoFTR, cv2.findTransformECC
    ecc_calls = []

    def pause():
        entered.set()
        if not release.wait(8):
            raise RuntimeError('External backend test timed out')
        if outcome == 'error':
            raise RuntimeError('controlled failure')

    class ControlledMatcher(base):
        def forward(self, images):
            if stage == 'Deep Matcher':
                pause()
            return super().forward(images)

    def controlled_ecc(*args, **kwargs):
        ecc_calls.append(True)
        if stage == 'ECC':
            pause()
        return real_ecc(*args, **kwargs)

    monkeypatch.setattr(kornia.feature, 'LoFTR', ControlledMatcher)
    monkeypatch.setattr(cv2, 'findTransformECC', controlled_ecc)
    try:
        run.click()
        qtbot.waitUntil(entered.is_set)
        qtbot.waitUntil(lambda: stage in window.findChild(QProgressBar, 'registrationProgress').format())
        assert not button(window, 'openFrames').isEnabled()
        assert not button(window, 'deleteFrame').isEnabled()
        if outcome == 'cancel':
            button(window, 'cancelRegistration').click()
    finally:
        release.set()
        qtbot.waitUntil(run.isEnabled, timeout=10000)
    assert image(window) == before
    assert window.findChild(QLabel, 'registrationInfo').text() == info
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    assert 'Ręczne korekty filmu: 1' in window.findChild(QLabel, 'registrationInfo').text()
    if stage == 'Deep Matcher':
        assert not ecc_calls
    if outcome == 'error':
        error = window.findChild(QMessageBox)
        assert error is not None and stage in error.text() and '1 → 2' in error.text()
        error.accept()
    else:
        assert not window.findChildren(QMessageBox)
