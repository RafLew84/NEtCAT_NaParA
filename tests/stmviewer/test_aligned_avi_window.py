"""Aligned AVI through public controls and actual decoded movies."""
from dataclasses import replace

import numpy as np
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QLabel, QPushButton, QSpinBox, QWidget

from stmviewer.series import open_frame_series
from stmviewer.ui.main_window import STMViewerMainWindow
from test_avi_export import decode
from test_mpp_export_window import open_movie, FIXTURES


@pytest.mark.parametrize('codec', ['MJPG', 'FFV1'])
@pytest.mark.parametrize('removed', [0, 1])
def test_aligned_subset_after_removal_keeps_full_canvas(qtbot, monkeypatch, tmp_path, codec, removed):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    source = FIXTURES / 'registration/integer.mpp'
    originals = open_frame_series([source])
    open_movie(qtbot, window, monkeypatch, source)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(removed + 1)
    window.findChild(QPushButton, 'deleteFrame').click()
    window.findChild(QCheckBox, 'pixelProportions').setChecked(True)
    preview = window.findChild(QWidget, 'imagePreview')
    before = preview.grab().toImage()
    path = tmp_path / 'aligned.avi'
    filenames = []

    def filename(parent, title, initial, *args, **kwargs):
        filenames.append((title, initial))
        return str(path), ''

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', filename)
    summaries = []

    def choose():
        dialog = window.findChild(QDialog, 'aviOptions')
        try:
            version = dialog.findChild(QComboBox, 'aviVersion')
            assert version is not None
            assert version.currentText() == 'aligned'
            dialog.findChild(QComboBox, 'aviRange').setCurrentIndex(1)
            dialog.findChild(QSpinBox, 'aviEnd').setValue(1)
            dialog.findChild(QSpinBox, 'aviFps').setValue(7)
            dialog.findChild(QComboBox, 'aviCodec').setCurrentText(codec)
            dialog.findChild(QComboBox, 'aviBackground').setCurrentIndex(1)
            summaries.append(dialog.findChild(QLabel, 'aviSummary').text())
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
        finally:
            if dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(10, choose)
    save = window.findChild(QPushButton, 'saveAvi')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'aviExportInfo').text()
    assert '54 × 34' in summaries[0]
    assert 'aligned' in filenames[0][0] and filenames[0][1].endswith('-aligned.avi')
    fps, images = decode(path)
    assert fps == 7 and len(images) == 1
    actual = images[0][:, :, 0]
    assert actual.shape == (34, 54)
    data = originals[1 if removed == 0 else 0].data
    x, y = (5, 0) if removed == 0 else (2, 2)
    expected = np.full((34, 54), 128, dtype=np.uint8)
    expected[y:y + 32, x:x + 48] = (255 * (data - data.min()) / (data.max() - data.min())).astype(np.uint8)
    difference = np.abs(actual.astype(int) - expected)
    if codec == 'FFV1':
        assert difference.max() <= 1
        assert np.all(actual[:, 53] == 128)
    else:
        assert difference.mean() < 5
    assert preview.grab().toImage() == before


@pytest.mark.parametrize('invalid', ['missing', 'other-series', 'wrong-canvas'])
def test_incomplete_registration_cannot_be_selected_for_movie(qtbot, invalid):
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.registration import register_series
    from stmviewer.ui.avi_dialog import AviDialog

    frames = open_frame_series([FIXTURES / 'registration/integer.mpp'])
    result = register_series(frames)
    if invalid == 'missing':
        result = result.without_frame(0)
    elif invalid == 'other-series':
        frames = tuple(replace(f, source=FIXTURES / 'another.mpp') for f in frames)
    else:
        result = replace(result, canvas_shape=(32, 48))
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = AviDialog(frames, MoviePresentation(), 5, parent,
                       registration=result, current_view='aligned')
    qtbot.addWidget(dialog)
    dialog.show()
    version = dialog.findChild(QComboBox, 'aviVersion')
    assert [version.itemText(i) for i in range(version.count())] == ['original']
    assert version.currentText() == 'original'


def test_version_defaults_to_preview_and_can_be_changed_without_changing_preview(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'registration/integer.mpp')
    window.findChild(QCheckBox, 'pixelProportions').setChecked(True)
    save = window.findChild(QPushButton, 'saveAvi')

    def inspect_unavailable():
        dialog = window.findChild(QDialog, 'aviOptions')
        try:
            version = dialog.findChild(QComboBox, 'aviVersion')
            assert version.count() == 1 and version.currentText() == 'original'
        finally:
            dialog.reject()

    QTimer.singleShot(10, inspect_unavailable)
    save.click()
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QComboBox, 'frameView').setCurrentText('original')
    path = tmp_path / 'chosen-original.avi'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))

    def choose_original():
        dialog = window.findChild(QDialog, 'aviOptions')
        try:
            version = dialog.findChild(QComboBox, 'aviVersion')
            summary = dialog.findChild(QLabel, 'aviSummary')
            assert version.currentText() == 'original' and version.count() == 2
            assert '48 × 32' in summary.text()
            version.setCurrentText('aligned')
            assert '54 × 34' in summary.text()
            version.setCurrentText('original')
            assert '48 × 32' in summary.text()
            dialog.findChild(QComboBox, 'aviCodec').setCurrentText('FFV1')
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
        finally:
            if dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(10, choose_original)
    save.click()
    qtbot.waitUntil(save.isEnabled)
    _, images = decode(path)
    assert len(images) == 3 and images[0].shape == (32, 48, 3)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'original'
