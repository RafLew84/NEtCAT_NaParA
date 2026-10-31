"""Operator corrections are explicitly published to the active complete movie."""

from PyQt6.QtWidgets import QDialog, QLabel, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_manual_pair_gui import CPU, button
from test_registration_gui import open_file


def registered_pair(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    register = button(window, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    button(window, 'comparePair').click()
    return window, window.findChild(QDialog, 'pairComparison')


def shifts(window):
    number = window.findChild(QSpinBox, 'frameNumber')
    descriptions = []
    for i in range(1, number.maximum() + 1):
        number.setValue(i)
        descriptions.append(window.findChild(QLabel, 'registrationInfo').text())
    return descriptions


def assert_shifts(window, expected):
    for text, (x, y) in zip(shifts(window), expected, strict=True):
        assert f'ΔX: {x:g} px · ΔY: {y:g} px' in text


def test_apply_and_remove_two_pair_corrections_preserves_other_overrides(qtbot, monkeypatch):
    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    assert 'ΔX: 2 px · ΔY: -1 px' in dialog.findChild(QLabel, 'manualPairInfo').text()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    assert_shifts(window, [(0, 0), (2, -1), (-1, 1)])
    apply = button(dialog, 'manualMovieApply')
    assert apply.isEnabled()
    assert '2–3' in dialog.findChild(QLabel, 'manualMovieInfo').text()
    apply.click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    assert not apply.isEnabled()  # A second click cannot add the same shift twice.
    assert 'zastosowana do filmu' in dialog.findChild(QLabel, 'manualMovieInfo').text()
    dialog.findChild(QSpinBox, 'pairNumber').setValue(3)
    button(dialog, 'manualMovieStart').click()
    assert 'ΔX: -3 px · ΔY: 2 px' in dialog.findChild(QLabel, 'manualPairInfo').text()
    button(dialog, 'manualPairYPlus').click()
    button(dialog, 'manualPairApply').click()
    apply.click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (0, 2)])
    dialog.findChild(QSpinBox, 'pairNumber').setValue(2)
    remove = button(dialog, 'manualMovieRemove')
    assert remove.isEnabled()
    remove.click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (2, -1), (-1, 2)])
    dialog.findChild(QSpinBox, 'pairNumber').setValue(3)
    remove.click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (2, -1), (-1, 1)])
    assert not remove.isEnabled()
    dialog.close()


def test_applied_correction_survives_dialog_close_and_export_history_is_visible(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog

    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    dialog.close()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert button(dialog, 'manualMovieRemove').isEnabled()
    dialog.close()
    path = tmp_path / 'corrected.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(path), 'MPP aligned (*.mpp *.MPP)'))
    save = button(window, 'saveOriginalMpp')
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'mppExportInfo').text()
    open_file(qtbot, window, monkeypatch, path)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    history = window.findChild(QLabel, 'registrationInfo').text()
    assert 'Ręczne korekty filmu: 1' in history
    assert 'Baza XY: (2, -1)' in history
    assert 'Wynik XY: (3, -1)' in history
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert not button(dialog, 'manualMovieStart').isEnabled()
    assert 'Najpierw wykonaj pełną rejestrację' in dialog.findChild(QLabel, 'manualMovieInfo').text()
    dialog.close()


def test_cancel_from_pair_window_preserves_previous_corrected_movie(qtbot, monkeypatch):
    from threading import Event
    from scipy import ndimage
    from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QProgressBar
    from test_registration_gui import image

    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    before = image(window)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairYPlus').click()
    button(dialog, 'manualPairApply').click()
    entered, release = Event(), Event()
    transform = ndimage.affine_transform

    def blocked_transform(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Interpolation wait timed out')
        return transform(*args, **kwargs)

    monkeypatch.setattr(ndimage, 'affine_transform', blocked_transform)
    try:
        button(dialog, 'manualMovieApply').click()
        qtbot.waitUntil(entered.is_set)
        assert window.findChild(QProgressBar, 'registrationProgress').isVisible()
        for name in ('openFrames', 'deleteFrame', 'registerFrames', 'saveOriginalMpp', 'saveAvi', 'playPause'):
            assert not button(window, name).isEnabled()
        for name in ('manualMovieStart', 'manualMovieApply', 'manualMovieRemove', 'runPair'):
            assert not button(dialog, name).isEnabled()
        assert dialog.findChild(QDoubleSpinBox, 'pairGamma').isEnabled()
        assert window.findChild(QComboBox, 'frameView').isEnabled()
        cancel = button(dialog, 'cancelManualMovie')
        assert cancel.isVisible() and cancel.isEnabled()
        cancel.click()
        assert not cancel.isEnabled()
    finally:
        release.set()
        qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert image(window) == before
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    assert button(dialog, 'manualMovieRemove').isEnabled()
    assert button(dialog, 'manualMovieApply').isEnabled()  # Retry against the same preserved result.
    dialog.close()


def test_new_registration_invalidates_draft_and_deletion_locks_further_movie_edits(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    register = button(window, 'registerFrames')
    qtbot.waitUntil(register.isEnabled)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairYPlus').click()
    open_file(qtbot, window, monkeypatch, CPU.with_name('absent.mpp'))
    window.findChild(QMessageBox).accept()
    assert 'ΔX: 3 px · ΔY: 0 px' in dialog.findChild(QLabel, 'manualPairInfo').text()
    register.click()
    qtbot.waitUntil(register.isEnabled)
    button(dialog, 'manualPairApply').click()
    assert not button(dialog, 'manualMovieApply').isEnabled()
    assert 'aktualnego wyniku' in dialog.findChild(QLabel, 'manualMovieInfo').text()
    assert_shifts(window, [(0, 0), (2, -1), (-1, 1)])
    assert not button(dialog, 'manualMovieRemove').isEnabled()
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(register.isEnabled)
    # Remove the reference itself: surviving coordinates and ready exports remain.
    window.findChild(QSpinBox, 'frameNumber').setValue(1)
    button(window, 'deleteFrame').click()
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    assert_shifts(window, [(3, -1), (0, 1)])
    assert button(window, 'saveOriginalMpp').isEnabled()
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert not button(dialog, 'manualMovieStart').isEnabled()
    assert not button(dialog, 'manualMovieRemove').isEnabled()
    assert 'Po usunięciu klatki' in dialog.findChild(QLabel, 'manualMovieInfo').text()
    register.click()
    qtbot.waitUntil(register.isEnabled)
    assert button(dialog, 'manualMovieStart').isEnabled()
    assert_shifts(window, [(0, 0), (-3, 2)])
    open_file(qtbot, window, monkeypatch, CPU)
    qtbot.waitUntil(lambda: window.findChild(QDialog, 'pairComparison') is None)
    button(window, 'comparePair').click()
    dialog = window.findChild(QDialog, 'pairComparison')
    assert not button(dialog, 'manualMovieStart').isEnabled()
    dialog.close()


def test_failed_reconstruction_keeps_applied_corrections_and_allows_retry(qtbot, monkeypatch):
    from scipy import ndimage
    from PyQt6.QtWidgets import QMessageBox
    from test_registration_gui import image

    window, dialog = registered_pair(qtbot, monkeypatch)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairXPlus').click()
    button(dialog, 'manualPairApply').click()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    before = image(window)
    button(dialog, 'manualMovieStart').click()
    button(dialog, 'manualPairYPlus').click()
    button(dialog, 'manualPairApply').click()

    def fail_allocation(*args, **kwargs):
        raise MemoryError('controlled allocation failure')

    with monkeypatch.context() as fault:
        fault.setattr(ndimage, 'affine_transform', fail_allocation)
        button(dialog, 'manualMovieApply').click()
        qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    message = window.findChild(QMessageBox)
    assert message is not None and 'controlled allocation failure' in message.text()
    message.accept()
    assert image(window) == before
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    assert button(dialog, 'manualMovieRemove').isEnabled()
    assert button(dialog, 'manualMovieApply').isEnabled()
    button(dialog, 'manualMovieApply').click()
    qtbot.waitUntil(button(window, 'registerFrames').isEnabled)
    assert_shifts(window, [(0, 0), (3, 0), (0, 2)])
    dialog.close()
