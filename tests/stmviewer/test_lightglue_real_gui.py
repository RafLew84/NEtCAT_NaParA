"""Opt-in actual CPU/CUDA Qt workflow, distinct from manual acceptance."""
import json
import os
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox
from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_LIGHTGLUE'),
                               reason='Requires local LightGlue/SuperPoint resources')


@pytest.mark.parametrize('device', ['CPU', 'CUDA'])
def test_real_gui_check_align_cancel_and_bad_either_checkpoint_preserve_movie(qtbot, monkeypatch, tmp_path, device):
    import torch
    if device == 'CUDA' and not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    root = Path(os.environ.get('STMVIEWER_LIGHTGLUE_GUI_ARTIFACTS', '/tmp/stmviewer-reg13-gui'))
    root.mkdir(parents=True, exist_ok=True)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.resize(1024, 768)
    window.show()
    open_file(qtbot, window, monkeypatch, Path(__file__).parent / 'fixtures/registration/cpu.mpp')
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData('lightglue_superpoint'))
    window.findChild(QComboBox, 'deepDevice').setCurrentText(device)
    check = window.findChild(QPushButton, 'checkDeepModel')
    register = window.findChild(QPushButton, 'registerFrames')
    status = window.findChild(QLabel, 'deepModelStatus')
    info = window.findChild(QLabel, 'registrationInfo')
    view = window.findChild(QComboBox, 'frameView')
    check.click()
    qtbot.waitUntil(check.isEnabled, timeout=90000)
    assert 'Sprawdzono model' in status.text() and device in status.text(), status.text()
    assert view.currentText() == 'original'
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=90000)
    assert view.currentText() == 'aligned', status.text()
    assert 'LightGlue + SuperPoint' in info.text() and device in info.text()
    assert 'Zgodne punkty:' in info.text()
    assert window.findChild(QSpinBox, 'frameNumber').value() == 2
    retained, retained_info = image(window), info.text()
    window.findChild(QScrollArea).ensureWidgetVisible(info)
    window.grab().save(str(root / f'lightglue-{device.lower()}-aligned.png'))
    register.click()
    qtbot.waitUntil(window.findChild(QPushButton, 'cancelRegistration').isEnabled)
    window.findChild(QPushButton, 'cancelRegistration').click()
    qtbot.waitUntil(register.isEnabled, timeout=10000)
    assert image(window) == retained and info.text() == retained_info
    errors = {}
    for name in ('deepWeights', 'superpointWeights'):
        field = window.findChild(QLineEdit, name)
        original_path = field.text()
        invalid = tmp_path / f'invalid-{name}.pth'
        with invalid.open('wb') as stream:
            stream.truncate(Path(original_path).stat().st_size)
        field.setText(str(invalid))
        assert register.isEnabled()
        register.click()
        qtbot.waitUntil(register.isEnabled, timeout=90000)
        message = window.findChild(QMessageBox)
        assert message is not None and 'SHA-256' in message.text()
        errors[name] = message.text()
        message.accept()
        assert image(window) == retained and info.text() == retained_info
        field.setText(original_path)
    (root / f'lightglue-{device.lower()}-gui.json').write_text(json.dumps({
        'device': device, 'qt_mode': os.environ.get('QT_QPA_PLATFORM'),
        'check_register_cancel': 'passed', 'checkpoint_errors_preserved_movie': errors,
        'registration_info': retained_info}, indent=2))
    window.close()
