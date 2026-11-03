"""Choose aligned in the save window, reopen it, and inspect its public preview."""
from PyQt6.QtWidgets import QComboBox, QFileDialog, QLabel, QPushButton, QSpinBox, QWidget, QMessageBox

from stmviewer.series import open_frame_series
from stmviewer.ui.main_window import STMViewerMainWindow
from test_mpp_export_window import open_movie, FIXTURES


def test_save_defaults_to_aligned_and_reopens_history_with_outline(qtbot, monkeypatch, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    preview = window.findChild(QWidget, 'imagePreview')
    preview.setFixedSize(400, 300)
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'registration/integer.mpp')
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QPushButton, 'deleteFrame').click()  # historical reference is absent
    before = preview.grab().toImage()
    path = tmp_path / 'aligned.mpp'
    choices = []

    def choose_file(parent, title, initial, filters, **kwargs):
        choices.append((filters.split(';;'), kwargs.get('initialFilter', '')))
        return str(path), kwargs.get('initialFilter', '')

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose_file)
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert choices[0] == (['MPP original (*.mpp *.MPP)', 'MPP aligned (*.mpp *.MPP)'],
                          'MPP aligned (*.mpp *.MPP)')
    import numpy as np
    from napara.io.mpp_reader import read_mpp_file
    assert all(np.isfinite(f.data).all() for f in read_mpp_file(str(path)))
    assert 'Zapisano' in window.findChild(QLabel, 'mppExportInfo').text()
    saved = open_frame_series([path])
    assert len(saved) == 2 and saved[0].data.shape == (34, 53)
    assert saved[0].alignment.reference.source_frame_index == 0
    open_movie(qtbot, window, monkeypatch, path)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'original'
    assert not window.findChild(QComboBox, 'frameView').isEnabled()
    assert preview.grab().toImage() == before
    text = window.findChild(QLabel, 'registrationInfo').text()
    assert 'Historia' in text and '53 × 34' in text and 'klatka 1' in text
    assert '48 × 32' in text
    # Imported NaN samples, rather than a history label, reject a new registration.
    register.click()
    qtbot.waitUntil(register.isEnabled)
    dialog = next(w for w in window.findChildren(QMessageBox) if w.isVisible())
    assert 'NaN/Inf' in dialog.text()
    dialog.accept()
    assert preview.grab().toImage() == before
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    assert 'ΔX: -2' in window.findChild(QLabel, 'registrationInfo').text()
    window.findChild(QPushButton, 'deleteFrame').click()
    assert preview.grab().toImage() == before


def test_input_view_defaults_to_original_and_does_not_offer_unavailable_aligned(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'registration/integer.mpp')
    offered = []
    def cancel_dialog(parent, title, initial, filters, **kwargs):
        offered.append((filters.split(';;'), kwargs['initialFilter']))
        return '', ''
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', cancel_dialog)
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    save.click()
    assert offered == [(['MPP original (*.mpp *.MPP)'], 'MPP original (*.mpp *.MPP)')]
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QComboBox, 'frameView').setCurrentText('original')
    save.click()
    assert len(offered[-1][0]) == 2 and offered[-1][1] == 'MPP original (*.mpp *.MPP)'


def test_real_save_dialog_exposes_version_choice(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QLineEdit, QDialogButtonBox

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, FIXTURES / 'registration/integer.mpp')
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    real_picker = QFileDialog.getSaveFileName
    def qt_picker(*args, **kwargs):
        kwargs['options'] |= QFileDialog.Option.DontUseNativeDialog
        return real_picker(*args, **kwargs)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', qt_picker)
    path = tmp_path / 'real-dialog.mpp'
    observed = []
    def answer():
        dialog = next(w for w in window.findChildren(QFileDialog) if w.isVisible())
        observed.append((dialog.nameFilters(), dialog.selectedNameFilter()))
        dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: [w.reject() for w in window.findChildren(QFileDialog) if w.isVisible()])
    timer.start(3000)
    QTimer.singleShot(100, answer)
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    save.click()
    timer.stop()
    qtbot.waitUntil(save.isEnabled)
    assert observed == [(['MPP original (*.mpp *.MPP)', 'MPP aligned (*.mpp *.MPP)'],
                         'MPP aligned (*.mpp *.MPP)')]
    assert path.exists() and open_frame_series([path])[0].alignment is not None


def test_old_aligned_can_be_resaved_as_original_with_bright_background(qtbot, monkeypatch, tmp_path):
    import numpy as np
    from napara.io.mpp_reader import read_mpp_file
    from stmviewer.mpp_export import save_aligned_mpp
    from test_aligned_mpp import subpixel_result

    old = save_aligned_mpp(tmp_path / 'old-nan.mpp', subpixel_result().without_frame(0))
    expected, = open_frame_series([old])
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_movie(qtbot, window, monkeypatch, old)
    path = tmp_path / 'bright.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), kw['initialFilter']))
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    physical = np.rot90(read_mpp_file(str(path))[0].data, 2)
    missing = ~np.isfinite(expected.data)
    assert np.all(physical[missing] == 7.5)
    assert physical[~missing].tobytes() == expected.data[~missing].tobytes()
    reopened, = open_frame_series([path])
    assert reopened.data.tobytes() == expected.data.tobytes()
    assert reopened.alignment == expected.alignment
