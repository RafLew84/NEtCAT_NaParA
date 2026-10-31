"""Manual alignment through visible controls keeps trials separate from the movie."""

from pathlib import Path

from PyQt6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QWidget

from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file

CPU = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


def button(dialog, name):
    control = dialog.findChild(QPushButton, name)
    assert control is not None, f'Missing button: {name}'
    return control


def open_pair(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    button(window, 'comparePair').click()
    return window, window.findChild(QDialog, 'pairComparison')


def test_manual_zero_start_moves_original_pixels_without_an_available_backend(qtbot, monkeypatch):
    window, dialog = open_pair(qtbot, monkeypatch)
    original = image(window)
    dialog.findChild(QComboBox, 'pairMethod').setCurrentText('Deep Matcher')
    assert not button(dialog, 'runPair').isEnabled()  # No local weights selected.
    button(dialog, 'manualPairZero').click()
    for name in ('manualPairXPlus', 'manualPairXPlus', 'manualPairYMinus'):
        button(dialog, name).click()
    info = dialog.findChild(QLabel, 'manualPairInfo').text()
    assert 'ΔX: 2 px' in info and 'ΔY: -1 px' in info
    assert dialog.findChild(QComboBox, 'pairAlignment').currentText() == 'Z dopasowaniem'
    assert not button(dialog, 'runPair').isEnabled()
    assert not button(dialog, 'pinPair').isEnabled()
    assert not button(dialog, 'pairCurrentResult').isEnabled()
    assert not button(dialog, 'pairSavedResult').isEnabled()
    assert 'Brak wyniku' in dialog.findChild(QLabel, 'pairResult').text()
    before_apply = dialog.findChild(QWidget, 'pairPreview').grab().toImage()
    button(dialog, 'manualPairApply').click()
    result = dialog.findChild(QLabel, 'pairResult').text()
    assert 'Ręczne' in result and 'ustawione ręcznie — jakość nieoceniona' in result
    assert 'ΔX: 2 px' in result and 'ΔY: -1 px' in result
    assert 'OK backendu' not in result
    assert dialog.findChild(QWidget, 'pairPreview').grab().toImage() == before_apply
    assert button(dialog, 'pinPair').isEnabled()
    assert image(window) == original
    dialog.close()


def test_correction_reset_discard_and_apply_preserve_pinned_fractional_trial(qtbot):
    from nanotrack.core import RegistrationFrameResult
    from stmviewer.series import open_frame_series
    from stmviewer.ui.pair_dialog import PairComparisonDialog

    class FractionalBackend:
        def estimate(self, *args, **kwargs):
            return RegistrationFrameResult(1, (2.4, -1.25), 'fixture', quality_score=0.9)

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PairComparisonDialog(open_frame_series([CPU]), 1, parent, backend=FractionalBackend())
    dialog.show()
    run = button(dialog, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    button(dialog, 'pinPair').click()
    current = button(dialog, 'pairCurrentResult')
    saved = button(dialog, 'pairSavedResult')
    saved.click()
    assert saved.isChecked() and not current.isChecked()
    result_a = dialog.findChild(QLabel, 'pairResult').text()
    pixels_a = dialog.findChild(QWidget, 'pairPreview').grab().toImage()
    button(dialog, 'manualPairCorrect').click()
    button(dialog, 'manualPairXPlus').click()
    assert 'ΔX: 3.4 px' in dialog.findChild(QLabel, 'manualPairInfo').text()
    assert 'ΔY: -1.25 px' in dialog.findChild(QLabel, 'manualPairInfo').text()
    assert not run.isEnabled() and not current.isEnabled() and not saved.isEnabled()
    button(dialog, 'manualPairReset').click()
    assert dialog.findChild(QWidget, 'pairPreview').grab().toImage() == pixels_a
    button(dialog, 'manualPairYPlus').click()
    button(dialog, 'manualPairDiscard').click()
    assert saved.isChecked() and not current.isChecked()
    assert dialog.findChild(QLabel, 'pairResult').text() == result_a
    assert dialog.findChild(QWidget, 'pairPreview').grab().toImage() == pixels_a
    button(dialog, 'manualPairCorrect').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    assert current.isChecked() and not saved.isChecked()
    result_b = dialog.findChild(QLabel, 'pairResult').text()
    assert 'ΔX: 3.4 px' in result_b and 'Ręczne' in result_b
    assert '2.4' in result_b and 'Phase' in result_b  # Starting value and its provenance.
    assert 'jakość nieoceniona' in result_b and 'OK backendu' not in result_b
    saved.click()
    assert saved.isChecked() and not current.isChecked()
    assert dialog.findChild(QLabel, 'pairResult').text() == result_a
    assert dialog.findChild(QWidget, 'pairPreview').grab().toImage() == pixels_a
    dialog.close()


def test_manual_view_controls_preserve_shift_and_inverse_steps_restore_raster(qtbot, monkeypatch):
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox

    _, dialog = open_pair(qtbot, monkeypatch)
    preview = dialog.findChild(QWidget, 'pairPreview')
    preview.setFixedSize(400, 360)
    button(dialog, 'manualPairZero').click()
    button(dialog, 'manualPairXPlus').click()
    info = dialog.findChild(QLabel, 'manualPairInfo').text()
    contrast = dialog.findChild(QLabel, 'pairContrast').text()
    QApplication.sendEvent(preview, QWheelEvent(
        QPointF(180, 170), QPointF(preview.mapToGlobal(QPoint(180, 170))),
        QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False))
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(190, 160))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(215, 180))
    gamma = dialog.findChild(QDoubleSpinBox, 'pairGamma')
    gamma.setValue(1.7)
    dialog.findChild(QCheckBox, 'pairPixelProportions').setChecked(False)
    assert dialog.findChild(QLabel, 'manualPairInfo').text() == info
    image_before = preview.grab().toImage()
    for plus, minus in [('manualPairXPlus', 'manualPairXMinus'),
                        ('manualPairYPlus', 'manualPairYMinus')]:
        button(dialog, plus).click()
        assert preview.grab().toImage() != image_before
        button(dialog, minus).click()
        assert preview.grab().toImage() == image_before
    alignment = dialog.findChild(QComboBox, 'pairAlignment')
    alignment.setCurrentText('Bez przesunięcia')
    assert preview.grab().toImage() != image_before
    assert dialog.findChild(QLabel, 'manualPairInfo').text() == info
    alignment.setCurrentText('Z dopasowaniem')
    assert preview.grab().toImage() == image_before
    button(dialog, 'pairToggleImage').click()
    assert dialog.findChild(QComboBox, 'pairLayer').currentText() == 'Klatka bazowa'
    button(dialog, 'pairToggleImage').click()
    assert dialog.findChild(QComboBox, 'pairLayer').currentText() == 'Klatka przesuwana'
    assert dialog.findChild(QLabel, 'manualPairInfo').text() == info
    assert dialog.findChild(QLabel, 'pairContrast').text() == contrast
    assert gamma.value() == 1.7
    alignment.setCurrentText('Bez przesunięcia')
    button(dialog, 'manualPairYMinus').click()
    assert alignment.currentText() == 'Z dopasowaniem'
    dialog.close()


def test_manual_no_overlap_and_series_lifecycle_discard_only_replaced_data(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox, QSpinBox
    from stmviewer.series import open_frame_series

    window, dialog = open_pair(qtbot, monkeypatch)
    button(dialog, 'manualPairZero').click()
    for _ in range(open_frame_series([CPU])[0].data.shape[1]):
        button(dialog, 'manualPairXPlus').click()
    assert 'Brak wspólnego ważnego obszaru' in dialog.findChild(QLabel, 'pairOverlap').text()
    button(dialog, 'manualPairApply').click()
    assert 'Brak wspólnego ważnego obszaru' in dialog.findChild(QLabel, 'pairOverlap').text()
    button(dialog, 'manualPairZero').click()
    assert 'Brak wspólnego ważnego obszaru' not in dialog.findChild(QLabel, 'pairOverlap').text()
    button(dialog, 'manualPairYPlus').click()
    info = dialog.findChild(QLabel, 'manualPairInfo').text()
    open_file(qtbot, window, monkeypatch, CPU.with_name('missing-file.mpp'))
    window.findChild(QMessageBox).accept()
    assert dialog.findChild(QLabel, 'manualPairInfo').text() == info
    assert button(dialog, 'manualPairApply').isEnabled()
    dialog.findChild(QSpinBox, 'pairNumber').setValue(3)
    assert not button(dialog, 'manualPairApply').isEnabled()
    assert 'Brak wyniku' in dialog.findChild(QLabel, 'pairResult').text()
    button(dialog, 'manualPairZero').click()
    button(dialog, 'manualPairYMinus').click()
    dialog.close()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert not button(dialog, 'manualPairApply').isEnabled()
    button(dialog, 'manualPairZero').click()
    open_file(qtbot, window, monkeypatch, CPU)
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    button(dialog, 'manualPairZero').click()
    button(window, 'deleteFrame').click()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)


def test_full_registration_locks_manual_edit_without_losing_draft(qtbot, monkeypatch):
    from test_registration_gui import GatedPhase
    from PyQt6.QtWidgets import QDoubleSpinBox

    backend = GatedPhase()
    window = STMViewerMainWindow(registration_backend=backend)
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    button(dialog, 'manualPairZero').click()
    button(dialog, 'manualPairXPlus').click()
    backend.block = True
    register = button(window, 'registerFrames')
    try:
        register.click()
        qtbot.waitUntil(backend.entered.is_set)
        for name in ('manualPairZero', 'manualPairCorrect', 'manualPairXPlus',
                     'manualPairReset', 'manualPairDiscard', 'manualPairApply'):
            assert not button(dialog, name).isEnabled()
        gamma = dialog.findChild(QDoubleSpinBox, 'pairGamma')
        assert gamma.isEnabled()
        gamma.setValue(1.5)
    finally:
        backend.release.set()
        qtbot.waitUntil(register.isEnabled)
    assert button(dialog, 'manualPairApply').isEnabled()
    assert 'ΔX: 1 px' in dialog.findChild(QLabel, 'manualPairInfo').text()
    button(dialog, 'manualPairApply').click()
    assert 'Ręczne' in dialog.findChild(QLabel, 'pairResult').text()
    dialog.close()


def test_manual_controls_fit_the_panel_without_horizontal_scroll(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QScrollArea

    _, dialog = open_pair(qtbot, monkeypatch)
    button(dialog, 'manualPairZero').click()
    qtbot.waitUntil(dialog.isVisible)
    scroll = dialog.findChild(QScrollArea)
    assert scroll.horizontalScrollBar().maximum() == 0
    dialog.close()


def test_manual_trial_preserves_full_aligned_and_mpp_avi_exports(qtbot, monkeypatch, tmp_path):
    import numpy as np
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QFileDialog, QSpinBox
    from stmviewer.series import open_frame_series
    from test_avi_export import decode
    from test_avi_export_window import configure_dialog

    window, dialog = open_pair(qtbot, monkeypatch)
    register = button(window, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    full_image = image(window)
    full_info = window.findChild(QLabel, 'registrationInfo').text()

    def export_versions(stem):
        mpp = tmp_path / f'{stem}.mpp'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(mpp), 'MPP aligned (*.mpp *.MPP)'))
        save = button(window, 'saveOriginalMpp')
        save.click()
        qtbot.waitUntil(save.isEnabled)
        assert 'Zapisano' in window.findChild(QLabel, 'mppExportInfo').text()
        avi = tmp_path / f'{stem}.avi'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(avi), ''))
        QTimer.singleShot(10, lambda: configure_dialog(window, end=3))
        save = button(window, 'saveAvi')
        save.click()
        qtbot.waitUntil(save.isEnabled)
        assert 'Zapisano' in window.findChild(QLabel, 'aviExportInfo').text()
        return open_frame_series([mpp]), decode(avi)

    originals, (fps, frames) = export_versions('before')
    button(dialog, 'manualPairZero').click()
    for _ in range(5):
        button(dialog, 'manualPairYPlus').click()
    button(dialog, 'manualPairApply').click()
    assert 'ΔY: 5 px' in dialog.findChild(QLabel, 'pairResult').text()
    assert image(window) == full_image
    assert window.findChild(QLabel, 'registrationInfo').text() == full_info
    after, (after_fps, after_frames) = export_versions('after')
    assert fps == after_fps and len(originals) == len(after) == len(frames) == len(after_frames) == 3
    for first, second in zip(originals, after):
        np.testing.assert_array_equal(first.data, second.data)
        assert first.alignment == second.alignment
    for first, second in zip(frames, after_frames):
        np.testing.assert_array_equal(first, second)
    dialog.close()
