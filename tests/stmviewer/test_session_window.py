"""Resume work from a portable session through visible application actions."""
from pathlib import Path
import shutil

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QWidget, QDialog, QListView, QLineEdit, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QLabel, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file

CPU = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


def test_session_reopens_without_source_and_restores_active_view(qtbot, monkeypatch, tmp_path):
    source = tmp_path / 'input.mpp'
    shutil.copyfile(CPU, source)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, source)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(1.7)
    window.findChild(QPushButton, 'zoomIn').click()
    window.findChild(QCheckBox, 'pixelProportions').setChecked(True)
    window.findChild(QComboBox, 'playbackFps').setCurrentText('10')
    window.findChild(QCheckBox, 'playbackLoop').setChecked(True)
    pixels = image(window)
    registration = window.findChild(QLabel, 'registrationInfo').text()
    view = window.findChild(QComboBox, 'frameView')
    view.setCurrentText('original')
    window.findChild(QPushButton, 'zoomIn').click()
    window.findChild(QPushButton, 'zoomIn').click()
    preview = window.findChild(QWidget, 'imagePreview')
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(120, 120))
    qtbot.mouseMove(preview, QPoint(145, 135))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(145, 135))
    original = image(window)
    view.setCurrentText('aligned')
    assert image(window) == pixels
    model = window.findChild(QListView, 'frameThumbnails').model()
    warnings = [model.data(model.index(i), Qt.ItemDataRole.ToolTipRole) for i in range(3)]
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('deep_matcher_translation'))
    missing_weights = str(tmp_path / 'absent-checkpoint.ckpt')
    window.findChild(QLineEdit, 'deepWeights').setText(missing_weights)
    device = window.findChild(QComboBox, 'deepDevice')
    device.setCurrentText('CUDA')
    path = tmp_path / 'work.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    save = window.findChild(QPushButton, 'saveSession')
    assert save is not None and save.isEnabled()
    save.click()
    qtbot.waitUntil(save.isEnabled, timeout=5000)
    assert path.exists(), window.findChild(QLabel, 'sessionInfo').text()
    window.close()
    source.unlink()
    restored = STMViewerMainWindow()
    qtbot.addWidget(restored)
    restored.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    open_session = restored.findChild(QPushButton, 'openSession')
    open_session.click()
    qtbot.waitUntil(open_session.isEnabled, timeout=5000)
    assert restored.findChild(QSpinBox, 'frameNumber').value() == 3
    assert restored.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    assert restored.findChild(QLabel, 'registrationInfo').text() == registration
    assert image(restored) == pixels
    assert restored.findChild(QComboBox, 'playbackFps').currentText() == '10'
    assert restored.findChild(QCheckBox, 'playbackLoop').isChecked()
    assert restored.findChild(QPushButton, 'playPause').text() == 'Play'
    assert restored.findChild(QPushButton, 'saveTrialB') is None
    assert restored.findChild(QComboBox, 'registrationMethod').currentData() == 'deep_matcher_translation'
    assert restored.findChild(QLineEdit, 'deepWeights').text() == missing_weights
    assert restored.findChild(QComboBox, 'deepDevice').currentText() == 'CUDA'
    assert not restored.findChild(QPushButton, 'registerFrames').isEnabled()
    assert restored.findChild(QPushButton, 'comparePair').isEnabled()
    assert restored.findChild(QPushButton, 'saveOriginalMpp').isEnabled()
    assert restored.findChild(QPushButton, 'saveAvi').isEnabled()

    view = restored.findChild(QComboBox, 'frameView')
    view.setCurrentText('original')
    assert image(restored) == original
    view.setCurrentText('aligned')
    assert image(restored) == pixels
    model = restored.findChild(QListView, 'frameThumbnails').model()
    assert [model.data(model.index(i), Qt.ItemDataRole.ToolTipRole) for i in range(3)] == warnings


def reopen_session(qtbot, window, monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    save = window.findChild(QPushButton, 'saveSession')
    save.click()
    qtbot.waitUntil(save.isEnabled, timeout=5000)
    assert path.exists(), window.findChild(QLabel, 'sessionInfo').text()
    window.close()

    def no_estimation(*args, **kwargs):
        raise AssertionError('Loading a session or manual editing must not estimate registration')

    restored = STMViewerMainWindow(registration_backend=no_estimation)
    qtbot.addWidget(restored)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    opening = restored.findChild(QPushButton, 'openSession')
    opening.click()
    qtbot.waitUntil(opening.isEnabled, timeout=5000)
    assert 'Otwarto sesję' in restored.findChild(QLabel, 'sessionInfo').text()
    return restored


def test_resume_two_manual_corrections_undo_and_export_active_aligned(qtbot, monkeypatch, tmp_path):
    from test_manual_movie_gui import registered_pair, assert_shifts
    from test_manual_pair_gui import button

    window, dialog = registered_pair(qtbot, monkeypatch)
    for pair, direction in ((2, 'X'), (3, 'Y')):
        dialog.findChild(QSpinBox, 'pairNumber').setValue(pair)
        button(dialog, 'manualMovieStart').click()
        button(dialog, f'manualPair{direction}Plus').click()
        button(dialog, 'manualPairApply').click()
        button(dialog, 'manualMovieApply').click()
        qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (0, 2)])
    dialog.close()
    window = reopen_session(qtbot, window, monkeypatch, tmp_path / 'corrections.stmsession')
    assert_shifts(window, [(0, 0), (3, -1), (0, 2)])
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert button(dialog, 'manualMovieRemove').isEnabled()
    button(dialog, 'manualMovieRemove').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (2, -1), (-1, 2)])
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (0, 2)])
    dialog.close()
    path = tmp_path / 'resumed.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), 'MPP aligned (*.mpp *.MPP)'))
    button(window, 'saveOriginalMpp').click()
    qtbot.waitUntil(button(window, 'saveOriginalMpp').isEnabled)
    assert path.exists(), window.findChild(QLabel, 'mppExportInfo').text()
    open_file(qtbot, window, monkeypatch, path)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    history = window.findChild(QLabel, 'registrationInfo').text()
    assert 'Ręczne korekty filmu: 2' in history
    assert 'ΔX: 0 px · ΔY: 2 px' in history
    assert 'Wynik XY: (-3, 3)' in history


def test_deleted_reference_reopens_with_same_canvas_and_manual_edits_still_locked(qtbot, monkeypatch, tmp_path):
    from test_manual_movie_gui import registered_pair, assert_shifts
    from test_manual_pair_gui import button

    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    dialog.close()
    window.findChild(QSpinBox, 'frameNumber').setValue(1)
    button(window, 'deleteFrame').click()
    registration = window.findChild(QLabel, 'registrationInfo').text()
    window = reopen_session(qtbot, window, monkeypatch, tmp_path / 'deleted.stmsession')
    assert window.findChild(QSpinBox, 'frameNumber').maximum() == 2
    assert window.findChild(QLabel, 'registrationInfo').text() == registration
    assert_shifts(window, [(3, -1), (0, 1)])
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert not button(dialog, 'manualMovieStart').isEnabled()
    assert 'Po usunięciu klatki' in dialog.findChild(QLabel, 'manualMovieInfo').text()
    dialog.close()
    assert button(window, 'saveOriginalMpp').isEnabled()
    assert button(window, 'saveAvi').isEnabled()
