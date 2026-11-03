"""Users compare raw correlation and can persist its unverified result."""

from PyQt6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_pair_comparison_gui import CPU
from test_registration_gui import open_file
from test_unnormalized_registration import LABEL


def test_user_compares_phase_and_raw_correlation_then_registers_series(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    method = window.findChild(QComboBox, 'registrationMethod')
    assert method.currentText() == 'Phase'
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    original_result = dialog.findChild(QLabel, 'pairResult').text()
    dialog.findChild(QPushButton, 'pinPair').click()
    dialog.findChild(QComboBox, 'pairMethod').setCurrentText(LABEL)
    run.click()
    qtbot.waitUntil(run.isEnabled)
    result = dialog.findChild(QLabel, 'pairResult').text()
    assert LABEL in result and 'pewność niezweryfikowana' in result
    assert 'ΔX: 2 px' in result and 'ΔY: -1 px' in result
    assert 'OK backendu' not in result
    dialog.findChild(QPushButton, 'pairSavedResult').click()
    assert dialog.findChild(QLabel, 'pairResult').text() == original_result
    assert method.currentText() == 'Phase'
    dialog.close()

    method.setCurrentText(LABEL)
    run = window.findChild(QPushButton, 'registerFrames')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    result = window.findChild(QLabel, 'registrationInfo').text()
    assert LABEL in result and 'pewność niezweryfikowana' in result
    assert 'ΔX: 2 px' in result and 'ΔY: -1 px' in result


def test_raw_correlation_exports_and_reopens_without_invented_confidence(qtbot, monkeypatch, tmp_path):
    import numpy as np
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QFileDialog
    from stmviewer.series import open_frame_series
    from test_avi_export import decode
    from test_avi_export_window import configure_dialog

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QComboBox, 'registrationMethod').setCurrentText(LABEL)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    mpp = tmp_path / 'raw-aligned.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(mpp), 'MPP aligned (*.mpp *.MPP)'))
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'mppExportInfo').text()
    restored = open_frame_series([mpp])
    assert len(restored) == 3
    assert [frame.alignment.shift_xy for frame in restored] == [(0, 0), (2, -1), (-1, 1)]
    assert [frame.alignment.quality_score for frame in restored] == [1, None, None]
    assert [frame.alignment.status for frame in restored] == ['ok', 'manual_review', 'manual_review']
    originals = open_frame_series([CPU])
    for frame, original in zip(restored, originals):
        assert frame.alignment.method == LABEL and frame.data.shape == (82, 83)
        x, y = map(int, frame.alignment.origin_xy)
        np.testing.assert_array_equal(frame.data[y:y + 80, x:x + 80], original.data)
        assert np.isnan(frame.data).any()

    avi = tmp_path / 'raw-aligned.avi'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(avi), ''))
    QTimer.singleShot(10, lambda: configure_dialog(window, end=3))
    save = window.findChild(QPushButton, 'saveAvi')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'aviExportInfo').text()
    fps, images = decode(avi)
    assert fps == 7 and len(images) == 3
    # Source calibration is 8 x 9 nm: 82 rows expand to 92; odd width is padded.
    assert all(im.shape[:2] == (92, 84) and np.ptp(im) > 0 for im in images)

    open_file(qtbot, window, monkeypatch, mpp)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    info = window.findChild(QLabel, 'registrationInfo').text()
    assert LABEL in info and 'pewność niezweryfikowana' in info
    assert 'Historia aligned' in info
