"""AKAZE in the real Qt pair/movie/graph workflow; no model resources."""
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QSpinBox
from stmviewer.mpp_export import save_original_mpp
from stmviewer.ui.main_window import STMViewerMainWindow
from test_akaze_integration import frames
from test_registration_gui import open_file, image


def opened_window(qtbot, monkeypatch, tmp_path):
    path = tmp_path/'akaze-known.mpp'
    save_original_mpp(path, frames())
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.resize(1100, 800)
    window.show()
    open_file(qtbot, window, monkeypatch, path)
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData('deep_matcher_translation'))
    window.findChild(QLineEdit, 'deepWeights').setText('/absent/unused.ckpt')
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CUDA')
    methods.setCurrentIndex(methods.findData('akaze'))
    return window


def test_cpu_without_weight_controls_in_pair_movie_graph_and_applied_result(qtbot, monkeypatch, tmp_path):
    window = opened_window(qtbot, monkeypatch, tmp_path)
    assert window.findChild(QComboBox, 'registrationMethod').currentData() == 'akaze'
    for name in ('deepWeights', 'superpointWeights'):
        assert not window.findChild(QLineEdit, name).isVisible()
    assert not window.findChild(QComboBox, 'deepDevice').isVisible()
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    assert pair.findChild(QComboBox, 'pairMethod').currentData() == 'akaze'
    run = pair.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    assert 'AKAZE' in pair.findChild(QLabel, 'pairResult').text()
    assert 'CPU' in pair.findChild(QLabel, 'pairResult').text()
    pair.close()
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    assert window.findChild(QSpinBox, 'frameNumber').value() == 2
    info = window.findChild(QLabel, 'registrationInfo')
    assert 'AKAZE' in info.text() and 'CPU' in info.text() and 'Zgodne punkty:' in info.text()
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert graph.findChild(QComboBox, 'graphMethod').currentData() == 'akaze'
    assert not graph.findChild(QLineEdit, 'deepWeights').isVisible()
    run_graph = graph.findChild(QPushButton, 'runGraph')
    run_graph.click()
    qtbot.waitUntil(run_graph.isEnabled)
    apply = graph.findChild(QPushButton, 'applyGraphMovie')
    assert apply.isEnabled(), graph.findChild(QLabel, 'graphMessage').text()
    apply.click()
    qtbot.waitUntil(register.isEnabled)
    assert 'AKAZE' in info.text()
    assert 'Słabe poparcie par grafu:' in info.text()
    graph.close()
    window.close()


@pytest.mark.parametrize('action', ['cancel', 'runtime-error', 'no-points'])
def test_interrupted_akaze_keeps_existing_aligned(qtbot, monkeypatch, tmp_path, action):
    import cv2
    from threading import Event
    from PyQt6.QtWidgets import QMessageBox
    window = opened_window(qtbot, monkeypatch, tmp_path)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    info = window.findChild(QLabel, 'registrationInfo')
    retained, retained_info = image(window), info.text()
    entered, release = Event(), Event()
    original_factory = cv2.AKAZE_create

    class DetectorBoundary:
        def __init__(self, *args, **kwargs):
            self.delegate = original_factory(*args, **kwargs)

        def detectAndCompute(self, *args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('OpenCV boundary wait timed out')
            if action == 'runtime-error':
                raise MemoryError('controlled OpenCV allocation failure')
            if action == 'no-points':
                return (), None
            return self.delegate.detectAndCompute(*args, **kwargs)

    monkeypatch.setattr(cv2, 'AKAZE_create', DetectorBoundary)
    try:
        register.click()
        qtbot.waitUntil(entered.is_set)
        if action == 'cancel':
            window.findChild(QPushButton, 'cancelRegistration').click()
    finally:
        release.set()
        qtbot.waitUntil(register.isEnabled)
    if action != 'cancel':
        message = window.findChild(QMessageBox)
        assert message is not None
        assert ('allocation failure' if action == 'runtime-error' else 'korespondencji') in message.text()
        message.accept()
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    assert image(window) == retained and info.text() == retained_info
    window.close()


def test_missing_opencv_akaze_disables_only_this_method(qtbot, monkeypatch, tmp_path):
    import cv2
    monkeypatch.setattr(cv2, 'AKAZE_create', None)
    window = opened_window(qtbot, monkeypatch, tmp_path)
    assert not window.findChild(QPushButton, 'registerFrames').isEnabled()
    message = window.findChild(QLabel, 'registrationAvailability').text()
    assert 'AKAZE' in message and 'OpenCV' in message
    assert window.findChild(QPushButton, 'nextFrame').isEnabled()
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData('phase_correlation'))
    assert window.findChild(QPushButton, 'registerFrames').isEnabled()
    window.close()
