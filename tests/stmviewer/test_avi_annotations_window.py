"""Annotation choices through GUI and actual decoded movie pixels."""
import pytest

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QLabel, QPushButton, QSpinBox

from stmviewer.mpp_export import save_original_mpp
from stmviewer.ui.main_window import STMViewerMainWindow
from make_avi_annotation_fixtures import annotation_frames
from test_avi_annotations import has_text
from test_avi_export import decode
from test_mpp_export_window import open_movie


@pytest.mark.parametrize('codec', ['FFV1', 'MJPG'])
@pytest.mark.parametrize('version', ['original', 'aligned'])
def test_user_exports_scale_number_and_measurement_time(qtbot, monkeypatch, tmp_path, codec, version):
    source = save_original_mpp(tmp_path / 'source.mpp', annotation_frames())
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, source)
    window.findChild(QSpinBox, 'frameNumber').setValue(3)
    window.findChild(QPushButton, 'deleteFrame').click()
    if version == 'aligned':
        register = window.findChild(QPushButton, 'registerFrames')
        register.click()
        qtbot.waitUntil(register.isEnabled)
    path = tmp_path / 'labels.avi'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))

    def options():
        dialog = window.findChild(QDialog, 'aviOptions')
        try:
            assert dialog.findChild(QComboBox, 'aviVersion').currentText() == version
            for name in ('aviScaleBar', 'aviFrameNumber', 'aviMeasurementTime'):
                control = dialog.findChild(QCheckBox, name)
                assert control is not None and not control.isChecked()
                control.setChecked(True)
            dialog.findChild(QComboBox, 'aviRange').setCurrentIndex(1)
            dialog.findChild(QSpinBox, 'aviStart').setValue(5)
            dialog.findChild(QSpinBox, 'aviEnd').setValue(10)
            dialog.findChild(QSpinBox, 'aviFps').setValue(7)
            dialog.findChild(QComboBox, 'aviCodec').setCurrentText(codec)
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
        finally:
            if dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(10, options)
    save = window.findChild(QPushButton, 'saveAvi')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'aviExportInfo').text()
    fps, images = decode(path)
    assert fps == 7 and len(images) == 6
    assert images[0].shape == (256, 512, 3)
    tolerance = .02 if codec == 'MJPG' else 1e-5
    assert has_text(images[0], '100 nm', tolerance)
    assert has_text(images[0], 'Klatka 5/20', tolerance) and has_text(images[0], 'Czas: 75 s', tolerance)
    assert has_text(images[1], 'Klatka 6/20', tolerance) and has_text(images[1], 'Czas: brak', tolerance)
    assert has_text(images[-1], 'Klatka 10/20', tolerance) and has_text(images[-1], 'Czas: 150 s', tolerance)


def test_small_image_disables_save_only_while_requested_labels_do_not_fit(qtbot):
    import numpy as np
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.ui.avi_dialog import AviDialog
    from test_avi_raster import frame
    from PyQt6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = AviDialog((frame(np.ones((48, 64))),), MoviePresentation(), 5, parent)
    qtbot.addWidget(dialog)
    dialog.show()
    save = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save)
    assert save.isEnabled()
    for name in ('aviScaleBar', 'aviFrameNumber', 'aviMeasurementTime'):
        check = dialog.findChild(QCheckBox, name)
        check.setChecked(True)
        assert not save.isEnabled()
        assert 'za mały' in dialog.findChild(QLabel, 'aviSummary').text()
        check.setChecked(False)
        assert save.isEnabled()
