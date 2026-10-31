"""Mask editing changes future estimates while retaining active images and trials."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLabel, QMessageBox, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_manual_pair_gui import CPU, button
from test_registration_gui import image, open_file


def draw_fraction(editor, x0, y0, x1, y1, mode='Dodaj: pomiń'):
    from stmviewer.ui.image_preview import ImagePreview
    editor.findChild(QComboBox, 'maskEditMode').setCurrentText(mode)
    preview = editor.findChild(ImagePreview, 'maskPreview')
    rect = preview.image_rect()
    assert rect is not None
    start = QPointF(rect.left() + rect.width() * x0, rect.top() + rect.height() * y0)
    end = QPointF(rect.left() + rect.width() * x1, rect.top() + rect.height() * y1)
    for event_type, pos, buttons in [(QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton),
                                     (QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)]:
        QApplication.sendEvent(preview, QMouseEvent(event_type, pos, pos,
                              Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier))


def test_excluding_all_pixels_refuses_new_registration_and_keeps_previous_movie(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    register = button(window, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    assert window.findChild(QMessageBox) is None
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    aligned = image(window)
    before = window.findChild(QLabel, 'registrationInfo').text()
    button(window, 'editRegistrationMasks').click()
    editor = window.findChild(QDialog, 'maskEditor')
    assert editor is not None
    assert editor.findChild(QSpinBox, 'maskFrameNumber').value() == 2
    draw_fraction(editor, .0001, .0001, .9999, .9999)
    assert '0 / 6400' in editor.findChild(QLabel, 'maskSummary').text()
    assert image(window) == aligned
    assert window.findChild(QLabel, 'registrationInfo').text() == before
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('masked_correlation'))
    assert window.findChild(QCheckBox, 'registrationUseMasks').isChecked()
    register.click()
    qtbot.waitUntil(register.isEnabled)
    error = window.findChild(QMessageBox)
    assert error is not None
    assert 'mask' in error.text().lower() or 'piksel' in error.text().lower()
    error.accept()
    assert image(window) == aligned
    assert window.findChild(QLabel, 'registrationInfo').text() == before
    # Same NCC method with selections off can run; selections remain in the editor.
    window.findChild(QCheckBox, 'registrationUseMasks').setChecked(False)
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert window.findChild(QMessageBox) is None
    assert 'Korelacja z maskami' in window.findChild(QLabel, 'registrationInfo').text()
    assert '0 / 6400' in editor.findChild(QLabel, 'maskSummary').text()
    editor.close()


def test_masked_pair_and_movie_use_same_sources_and_keep_saved_comparison(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QScrollArea

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU.with_name('masked-artifact.mpp'))
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('masked_correlation'))
    button(window, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    font = pair.font()
    font.setPointSize(11)  # Desktop font: catches card overflow hidden by offscreen defaults.
    pair.setFont(font)
    use = pair.findChild(QCheckBox, 'pairUseMasks')
    use.setChecked(False)
    run = button(pair, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    old = pair.findChild(QLabel, 'pairResult').text()
    assert 'ΔX: 0 px · ΔY: 0 px' in old
    assert 'wyłączone' in old
    button(pair, 'pinPair').click()
    button(pair, 'editPairMasks').click()
    editor = window.findChild(QDialog, 'maskEditor')
    for number in (2, 1, 3):
        editor.findChild(QSpinBox, 'maskFrameNumber').setValue(number)
        draw_fraction(editor, .0001, .0001, .9999, 12/64 - .0001)
        assert '4160 / 5120' in editor.findChild(QLabel, 'maskSummary').text()
    editor.close()
    assert pair.findChild(QLabel, 'pairResult').text() == old
    use.setChecked(True)
    run.click()
    qtbot.waitUntil(run.isEnabled)
    current = pair.findChild(QLabel, 'pairResult').text()
    assert 'ΔX: -4 px · ΔY: 3 px' in current
    assert 'włączone' in current
    button(pair, 'pairSavedResult').click()
    assert pair.findChild(QLabel, 'pairResult').text() == old
    button(pair, 'pairCurrentResult').click()
    assert pair.findChild(QLabel, 'pairResult').text() == current
    pair.resize(1080, 760)
    qtbot.wait(30)
    assert pair.findChild(QScrollArea, 'pairSidebar').horizontalScrollBar().maximum() == 0
    register = button(window, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    for number, (x, y) in enumerate(((0, 0), (-4, 3), (-7, 1)), 1):
        window.findChild(QSpinBox, 'frameNumber').setValue(number)
        assert f'ΔX: {x} px · ΔY: {y} px' in window.findChild(QLabel, 'registrationInfo').text()
    assert pair.findChild(QLabel, 'pairResult').text() == current
    pair.close()


def test_mask_sources_survive_deletion_and_failed_import_but_new_series_clears(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QListWidget

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    original = image(window)
    button(window, 'editRegistrationMasks').click()
    editor = window.findChild(QDialog, 'maskEditor')
    draw_fraction(editor, .1, .1, .2, .2)
    editor.findChild(QSpinBox, 'maskFrameNumber').setValue(3)
    draw_fraction(editor, .25, .25, .50, .50, mode='Dodaj: użyj')
    third_rect = editor.findChild(QListWidget, 'maskRectangles').item(0).text()
    assert image(window) == original
    button(window, 'deleteFrame').click()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'maskEditor') is None)
    assert '1 / 2' in window.findChild(QLabel, 'registrationMasksInfo').text()
    button(window, 'editRegistrationMasks').click()
    editor = window.findChild(QDialog, 'maskEditor')
    assert editor.findChild(QSpinBox, 'maskFrameNumber').value() == 2
    assert 'MPP 3' in editor.findChild(QLabel, 'maskSource').text()
    assert editor.findChild(QListWidget, 'maskRectangles').item(0).text() == third_rect
    open_file(qtbot, window, monkeypatch, CPU.with_name('absent-mask-series.mpp'))
    window.findChild(QMessageBox).accept()
    assert editor.findChild(QListWidget, 'maskRectangles').item(0).text() == third_rect
    open_file(qtbot, window, monkeypatch, CPU)
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'maskEditor') is None)
    assert '0 / 3' in window.findChild(QLabel, 'registrationMasksInfo').text()
    button(window, 'editRegistrationMasks').click()
    editor = window.findChild(QDialog, 'maskEditor')
    for number in (1, 2, 3):
        editor.findChild(QSpinBox, 'maskFrameNumber').setValue(number)
        assert editor.findChild(QListWidget, 'maskRectangles').count() == 0
    editor.close()


def test_masked_job_locks_editor_but_allows_browsing_and_cancel_preserves_movie(qtbot, monkeypatch):
    from threading import Event
    from skimage import registration
    from PyQt6.QtWidgets import QDoubleSpinBox

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    register = button(window, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    aligned = image(window)
    info = window.findChild(QLabel, 'registrationInfo').text()
    button(window, 'editRegistrationMasks').click()
    editor = window.findChild(QDialog, 'maskEditor')
    draw_fraction(editor, .001, .001, .25, .25)
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('masked_correlation'))
    entered, release = Event(), Event()
    correlate = registration.phase_cross_correlation

    def blocked_estimator(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('NCC wait timed out')
        return correlate(*args, **kwargs)

    monkeypatch.setattr(registration, 'phase_cross_correlation', blocked_estimator)
    try:
        register.click()
        qtbot.waitUntil(entered.is_set)
        assert not editor.findChild(QComboBox, 'maskEditMode').isEnabled()
        assert not button(editor, 'clearFrameMask').isEnabled()
        assert not button(window, 'deleteFrame').isEnabled()
        assert not button(window, 'saveOriginalMpp').isEnabled()
        assert editor.findChild(QDoubleSpinBox, 'maskGamma').isEnabled()
        editor.findChild(QSpinBox, 'maskFrameNumber').setValue(2)
        button(window, 'cancelRegistration').click()
    finally:
        release.set()
        qtbot.waitUntil(register.isEnabled)
    assert image(window) == aligned
    assert window.findChild(QLabel, 'registrationInfo').text() == info
    assert editor.findChild(QComboBox, 'maskEditMode').isEnabled()
    editor.findChild(QSpinBox, 'maskFrameNumber').setValue(1)
    assert button(editor, 'clearFrameMask').isEnabled()
    editor.close()
