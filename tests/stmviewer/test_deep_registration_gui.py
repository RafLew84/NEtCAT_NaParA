"""Deep Matcher controls -> validated local model and a stable visible result."""

from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QWidget

from test_deep_registration import FIXTURE, local_model
from test_registration_gui import image, open_file
from stmviewer.ui.main_window import STMViewerMainWindow


def test_model_check_and_registration_keep_existing_result_until_success(qtbot, monkeypatch, local_model):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    before = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentText('Deep Matcher')
    assert method.currentText() == 'Deep Matcher'
    assert not register.isEnabled()
    assert 'Wskaż lokalny plik wag' in window.findChild(QLabel, 'registrationAvailability').text()
    assert image(window) == before
    window.findChild(QLineEdit, 'deepWeights').setText(str(local_model))
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    check = window.findChild(QPushButton, 'checkDeepModel')
    check.click()
    qtbot.waitUntil(check.isEnabled, timeout=5000)
    assert 'Urządzenie: CPU' in window.findChild(QLabel, 'deepModelStatus').text()
    assert image(window) == before and window.findChild(QLabel, 'registrationInfo').text() == info
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    info = window.findChild(QLabel, 'registrationInfo').text()
    assert info.startswith('Deep Matcher ·') and 'Urządzenie: CPU' in info
    method.setCurrentText('Phase')
    assert window.findChild(QLabel, 'registrationInfo').text() == info


import pytest


@pytest.mark.parametrize('action', ['registerFrames', 'checkDeepModel'])
@pytest.mark.parametrize('outcome', ['cancel', 'bad_weights', 'out_of_memory'])
def test_preparation_failure_or_cancel_preserves_old_aligned(
        qtbot, monkeypatch, local_model, action, outcome):
    from threading import Event
    import torch
    from PyQt6.QtWidgets import QDoubleSpinBox, QMessageBox, QSpinBox

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentText('Deep Matcher')
    window.findChild(QLineEdit, 'deepWeights').setText(str(local_model))
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    entered, release = Event(), Event()
    load = torch.load
    def controlled_load(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Loader wait timed out')
        if outcome == 'out_of_memory':
            raise MemoryError('controlled allocation failure')
        return load(*args, **kwargs)
    monkeypatch.setattr(torch, 'load', controlled_load)
    if outcome == 'bad_weights':
        local_model.write_bytes(b'invalid local checkpoint')
    try:
        window.findChild(QPushButton, action).click()
        qtbot.waitUntil(entered.is_set)
        assert not method.isEnabled()
        assert not window.findChild(QLineEdit, 'deepWeights').isEnabled()
        assert not window.findChild(QPushButton, 'openFrames').isEnabled()
        window.findChild(QSpinBox, 'frameNumber').setValue(2)
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(2)
        window.findChild(QPushButton, 'zoomIn').click()
        before = image(window)
        info = window.findChild(QLabel, 'registrationInfo').text()
        if outcome == 'cancel':
            window.findChild(QPushButton, 'cancelRegistration').click()
        release.set()
        qtbot.waitUntil(register.isEnabled)
        assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
        assert image(window) == before
        assert window.findChild(QLabel, 'registrationInfo').text() == info
        assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 2
        if outcome == 'cancel':
            assert not window.findChildren(QMessageBox)
        else:
            message = window.findChild(QMessageBox)
            assert 'Deep Matcher' in message.text()
            assert 'Niepowodzenie próby' in window.findChild(QLabel, 'deepModelStatus').text()
            message.accept()
    finally:
        release.set()
