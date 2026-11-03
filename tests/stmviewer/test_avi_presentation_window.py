"""Presentation choices through public controls and actual decoded movies."""
import numpy as np
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QLabel, QPushButton, QSpinBox

from stmviewer.mpp_export import save_original_mpp
from stmviewer.ui.main_window import STMViewerMainWindow
from make_avi_presentation_fixtures import presentation_frames
from test_avi_export import decode
from test_mpp_export_window import open_movie


def choose_presentation(window, *, codec, background, contrast, gamma_mode):
    dialog = window.findChild(QDialog, 'aviOptions')
    try:
        for name, default, chosen in (('aviGamma', 'preview', gamma_mode),
                                      ('aviContrast', 'per_frame', contrast),
                                      ('aviBackground', 0, background)):
            control = dialog.findChild(QComboBox, name)
            assert control is not None, name
            assert control.currentData() == default
            control.setCurrentIndex(control.findData(chosen))
        dialog.findChild(QComboBox, 'aviRange').setCurrentIndex(1)
        dialog.findChild(QSpinBox, 'aviStart').setValue(2)
        dialog.findChild(QSpinBox, 'aviEnd').setValue(5)
        dialog.findChild(QComboBox, 'aviCodec').setCurrentText(codec)
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
    finally:
        if dialog.isVisible():
            dialog.reject()


@pytest.mark.parametrize('codec', ['MJPG', 'FFV1'])
@pytest.mark.parametrize('background', [0, 128, 255])
@pytest.mark.parametrize('contrast', ['per_frame', 'movie'])
@pytest.mark.parametrize('gamma_mode', ['preview', 'neutral'])
def test_user_exports_chosen_presentation(qtbot, monkeypatch, tmp_path, codec, background, contrast, gamma_mode):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    source = tmp_path / 'input.mpp'
    save_original_mpp(source, presentation_frames())
    open_movie(qtbot, window, monkeypatch, source)
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(2)
    path = tmp_path / 'presentation.avi'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    QTimer.singleShot(10, lambda: choose_presentation(
        window, codec=codec, background=background, contrast=contrast, gamma_mode=gamma_mode))
    save = window.findChild(QPushButton, 'saveAvi')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'aviExportInfo').text()
    fps, images = decode(path)
    assert fps == 5 and len(images) == 4
    assert images[0].shape == (50, 66, 3)
    quarter = 127 if gamma_mode == 'preview' else 63
    constant = quarter if contrast == 'movie' else (180 if gamma_mode == 'preview' else 127)
    tolerance = 0 if codec == 'FFV1' else 3
    expected = ((0, quarter), (quarter, 255)) if contrast == 'movie' else ((0, 255), (0, 255))
    for actual, (left, right) in zip(images[:2], expected, strict=True):
        assert abs(int(actual[10, 10, 0]) - left) <= tolerance
        assert abs(int(actual[10, 30, 0]) - right) <= tolerance
        assert abs(int(actual[10, 55, 0]) - background) <= tolerance
    assert np.max(np.abs(images[2].astype(int) - background)) <= tolerance
    assert abs(int(images[3][10, 10, 0]) - constant) <= tolerance
    if codec == 'FFV1':
        assert np.all(images[0][:49, 40:] == background) and np.all(images[0][-1] == background)
    assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 2
