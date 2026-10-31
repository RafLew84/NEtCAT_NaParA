"""Public method controls preserve the current result until a complete replacement."""

import pytest
from PyQt6.QtWidgets import QComboBox, QLabel, QPushButton, QSpinBox, QWidget

from make_cpu_registration_fixtures import cpu_frames
from make_registration_fixtures import write_movie
from test_registration_gui import image, labels, open_file
from stmviewer.ui.main_window import STMViewerMainWindow


def cpu_movie(tmp_path):
    path = tmp_path / 'cpu.mpp'
    write_movie(path, cpu_frames())
    return path


@pytest.mark.parametrize('method', ['Tile+RANSAC', 'ECC', 'Optical Flow', 'Korelacja bez normalizacji'])
def test_selecting_method_keeps_old_aligned_until_success(qtbot, monkeypatch, tmp_path, method):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, cpu_movie(tmp_path))
    number = window.findChild(QSpinBox, 'frameNumber')
    number.setValue(2)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    view = window.findChild(QComboBox, 'frameView')
    assert view.currentText() == 'aligned'
    window.findChild(QPushButton, 'zoomIn').click()
    before = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()

    combo = window.findChild(QComboBox, 'registrationMethod')
    assert [combo.itemText(i) for i in range(combo.count())] == ['Phase', 'Korelacja bez normalizacji', 'Tile+RANSAC', 'ECC', 'Optical Flow', 'Deep Matcher']
    combo.setCurrentText(method)
    assert image(window) == before
    assert window.findChild(QLabel, 'registrationInfo').text() == info
    assert register.isEnabled()

    register.click()
    qtbot.waitUntil(register.isEnabled, timeout=5000)
    assert view.currentText() == 'aligned' and number.value() == 2
    assert window.findChild(QLabel, 'registrationInfo').text().startswith(method + ' ·')
    assert image(window) != before  # Successful new canvas is fitted, as for Phase.
    after = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()
    number.setValue(1)
    window.findChild(QPushButton, 'deleteFrame').click()
    assert image(window) == after
    assert window.findChild(QLabel, 'registrationInfo').text() == info
    assert 'Klatka źródłowa MPP: 2' in labels(window)


def test_missing_opencv_disables_only_ecc_and_keeps_old_result(qtbot, monkeypatch, tmp_path):
    import builtins
    original_import = builtins.__import__

    def without_cv2(name, *args, **kwargs):
        if name == 'cv2':
            raise ModuleNotFoundError("No module named 'cv2'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', without_cv2)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, cpu_movie(tmp_path))
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    before = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()

    combo = window.findChild(QComboBox, 'registrationMethod')
    combo.setCurrentText('ECC')
    assert not register.isEnabled()
    assert 'ECC niedostępna' in labels(window) and 'cv2' in labels(window)
    assert image(window) == before
    assert window.findChild(QLabel, 'registrationInfo').text() == info
    for method in ['Tile+RANSAC', 'Optical Flow', 'Phase']:
        combo.setCurrentText(method)
        assert register.isEnabled()
        assert window.findChild(QLabel, 'registrationAvailability').isHidden()
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert window.findChild(QLabel, 'registrationInfo').text().startswith('Phase ·')


@pytest.mark.parametrize('method,key', [
    ('Tile+RANSAC', 'tile_correlation_ransac'),
    ('ECC', 'ecc_translation'),
    ('Optical Flow', 'optical_flow_median'),
    ('Korelacja bez normalizacji', 'phase_no_normalization'),
])
@pytest.mark.parametrize('outcome', ['cancel', 'exception', 'failed', 'incomplete', 'invalid', 'uncertain'])
def test_retry_preserves_old_result_or_publishes_complete_uncertainty(
        qtbot, monkeypatch, tmp_path, method, key, outcome):
    from dataclasses import replace
    from threading import Event
    import numpy as np
    from stmviewer.registration import create_shift_backend
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QListView, QMessageBox, QProgressBar

    class ControlledBackend:
        def __init__(self):
            self.real = create_shift_backend('phase_correlation')
            self.controlled = False
            self.entered, self.release = Event(), Event()

        def estimate(self, *args, **kwargs):
            result = self.real.estimate(*args, **kwargs)
            if not self.controlled:
                return result
            if outcome == 'cancel':
                self.entered.set()
                if not self.release.wait(5):
                    raise RuntimeError('Backend wait timed out')
            elif outcome == 'exception':
                raise RuntimeError('controlled CPU failure')
            elif outcome == 'failed':
                return replace(result, status='failed')
            elif outcome == 'incomplete':
                return None
            elif outcome == 'invalid':
                result.shift_xy = (np.nan, 0)
            elif outcome == 'uncertain' and result.frame_index == 1:
                return replace(result, status='manual_review', quality_score=0.1)
            return result

    backend = ControlledBackend()
    window = STMViewerMainWindow(registration_backend=backend)
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, cpu_movie(tmp_path))
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    window.findChild(QPushButton, 'zoomIn').click()
    before = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()
    combo = window.findChild(QComboBox, 'registrationMethod')
    combo.setCurrentText(method)
    backend.real = create_shift_backend(key)
    backend.controlled = True
    try:
        register.click()
        if outcome == 'cancel':
            qtbot.waitUntil(backend.entered.is_set)
            assert not combo.isEnabled()
            assert window.findChild(QProgressBar, 'registrationProgress').isVisible()
            window.findChild(QPushButton, 'cancelRegistration').click()
            backend.release.set()
        qtbot.waitUntil(register.isEnabled, timeout=5000)
    finally:
        backend.release.set()
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    if outcome == 'uncertain':
        assert window.findChild(QLabel, 'registrationInfo').text().startswith(method + ' · ⚠')
        assert 'niepewność odziedziczona' in labels(window)
        strip = window.findChild(QListView)
        model = strip.model()
        assert 'odziedziczona' in model.data(model.index(2, 0), Qt.ItemDataRole.ToolTipRole)
        assert not window.findChildren(QMessageBox)
    else:
        assert image(window) == before
        assert window.findChild(QLabel, 'registrationInfo').text() == info
        if outcome == 'cancel':
            assert not window.findChildren(QMessageBox)
        else:
            error = window.findChild(QMessageBox)
            assert '1 → 2' in error.text()
            error.accept()


@pytest.mark.parametrize('missing', ['cv2', 'scipy', 'skimage', 'torch', 'kornia'])
def test_fresh_process_can_browse_without_registration_dependency(missing):
    """An empty import cache must not turn an optional dependency into a startup crash."""
    import os
    from pathlib import Path
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent('''
        import importlib.abc
        import sys
        class MissingLibrary(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path, target=None):
                if fullname.split('.')[0] == sys.argv[1]:
                    raise ModuleNotFoundError("Test: missing " + sys.argv[1])
        sys.meta_path.insert(0, MissingLibrary())
        from PyQt6.QtWidgets import QApplication, QFileDialog, QComboBox, QLabel, QPushButton, QLineEdit
        from PyQt6.QtTest import QTest
        from stmviewer.ui.main_window import STMViewerMainWindow
        app = QApplication([])
        window = STMViewerMainWindow()
        window.show()
        QFileDialog.getOpenFileNames = lambda *args: (['tests/stmviewer/fixtures/registration/cpu.mpp'], '')
        button = window.findChild(QPushButton, 'openFrames')
        button.click()
        for i in range(500):
            QTest.qWait(10)
            if button.isEnabled():
                break
        assert button.isEnabled()
        assert '80 × 80 px' in '\\n'.join(w.text() for w in window.findChildren(QLabel))
        combo = window.findChild(QComboBox, 'registrationMethod')
        register = window.findChild(QPushButton, 'registerFrames')
        for name in ['Phase', 'Korelacja bez normalizacji', 'Tile+RANSAC', 'ECC', 'Optical Flow']:
            combo.setCurrentText(name)
            if sys.argv[1] in ('scipy', 'skimage') or (sys.argv[1] == 'cv2' and name == 'ECC'):
                assert not register.isEnabled()
                assert sys.argv[1] in window.findChild(QLabel, 'registrationAvailability').text()
            else:
                assert register.isEnabled()
        if sys.argv[1] in ('torch', 'kornia'):
            combo.setCurrentText('Deep Matcher')
            window.findChild(QLineEdit, 'deepWeights').setText('tests/stmviewer/fixtures/registration/cpu.mpp')
            assert not register.isEnabled()
            assert sys.argv[1] in window.findChild(QLabel, 'registrationAvailability').text()
        window.close()
        print('browsing works')
    ''')
    run = subprocess.run([sys.executable, '-c', code, missing],
                         cwd=Path(__file__).resolve().parents[2],
                         env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'browsing works' in run.stdout
