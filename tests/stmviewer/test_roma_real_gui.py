"""Opt-in automated Qt acceptance with the actual isolated CPU/CUDA RoMa model."""
import json
import os
from pathlib import Path
from time import perf_counter

import pytest
from PyQt6.QtWidgets import (
    QComboBox, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSpinBox,
)

from stmviewer.roma_matcher import WEIGHTS_BYTES
from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_ROMA'),
                               reason='Requires prepared local netcat-romav2 and verified weights')


@pytest.mark.parametrize('device', ['CPU', 'CUDA'])
def test_real_roma_gui_check_register_and_preserve_previous_movie(qtbot, monkeypatch, tmp_path, device):
    """Only the native file chooser is substituted; workers and model remain real."""
    artifacts = Path(os.environ.get('STMVIEWER_ROMA_GUI_ARTIFACTS', '/tmp/stmviewer-reg11-gui'))
    artifacts.mkdir(parents=True, exist_ok=True)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.resize(1024, 768)
    window.show()
    open_file(qtbot, window, monkeypatch, Path(__file__).parent / 'fixtures/registration/cpu.mpp')
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('roma_v2'))
    window.findChild(QComboBox, 'deepDevice').setCurrentText(device)
    check = window.findChild(QPushButton, 'checkDeepModel')
    register = window.findChild(QPushButton, 'registerFrames')
    number = window.findChild(QSpinBox, 'frameNumber')
    status = window.findChild(QLabel, 'deepModelStatus')
    info = window.findChild(QLabel, 'registrationInfo')
    view = window.findChild(QComboBox, 'frameView')
    assert check.isEnabled()
    started = perf_counter()
    check.click()
    qtbot.waitUntil(check.isEnabled, timeout=90000)
    check_s = perf_counter() - started
    assert 'Sprawdzono model' in status.text(), status.text()
    assert device in status.text()
    assert view.currentText() == 'original'

    number.setValue(2)
    started = perf_counter()
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=90000)
    registration_s = perf_counter() - started
    assert view.currentText() == 'aligned', status.text()
    assert 'RoMa v2' in info.text() and device in info.text()
    assert 'Zgodne punkty:' in info.text()
    assert 'poparcie' in info.text().lower()
    assert number.value() == 2
    retained = image(window)
    retained_info = info.text()
    window.findChild(QScrollArea).ensureWidgetVisible(info)
    window.grab().save(str(artifacts / f'roma-{device.lower()}-aligned.png'))
    report = {'device': device, 'qt_mode': os.environ.get('QT_QPA_PLATFORM'),
              'fixture': 'fixtures/registration/cpu.mpp', 'check_s': check_s,
              'registration_s': registration_s, 'registration_info': retained_info,
              'cancel_preserved': None, 'bad_checkpoint_preserved': None}

    if device == 'CUDA':
        progress = window.findChild(QProgressBar, 'registrationProgress')
        register.click()
        qtbot.waitUntil(lambda: 'ładowanie modelu' in progress.format(), timeout=90000)
        window.findChild(QPushButton, 'cancelRegistration').click()
        qtbot.waitUntil(register.isEnabled, timeout=10000)
        assert view.currentText() == 'aligned'
        assert info.text() == retained_info and image(window) == retained
        report['cancel_preserved'] = True

        invalid = tmp_path / 'invalid-roma.pt'
        with invalid.open('wb') as stream:
            stream.truncate(WEIGHTS_BYTES)
        window.findChild(QLineEdit, 'deepWeights').setText(str(invalid))
        assert register.isEnabled(), 'Same-size corrupt checkpoint must reach content validation'
        register.click()
        qtbot.waitUntil(register.isEnabled, timeout=90000)
        message = window.findChild(QMessageBox)
        assert message is not None and 'SHA-256' in message.text()
        report['checkpoint_error'] = message.text()
        message.accept()
        assert view.currentText() == 'aligned'
        assert info.text() == retained_info and image(window) == retained
        report['bad_checkpoint_preserved'] = True

    (artifacts / f'roma-{device.lower()}-gui.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    window.close()
