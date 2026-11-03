"""Public GUI operations release obsolete images; observe external SciPy allocations."""

from threading import Event
import weakref

import pytest
from scipy import ndimage
from PyQt6.QtWidgets import QComboBox, QMessageBox, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file, shifted_movie


def track_allocations(monkeypatch):
    allocations = []
    transform = ndimage.affine_transform

    def observed(*args, **kwargs):
        result = transform(*args, **kwargs)
        allocations.append(weakref.ref(result))
        return result

    monkeypatch.setattr(ndimage, 'affine_transform', observed)
    return allocations


def test_delete_reregister_and_reopen_release_obsolete_aligned_images(qtbot, monkeypatch, tmp_path):
    allocations = track_allocations(monkeypatch)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    path = shifted_movie(tmp_path)
    register = window.findChild(QPushButton, 'registerFrames')
    number = window.findChild(QSpinBox, 'frameNumber')
    for _ in range(2):
        open_file(qtbot, window, monkeypatch, path)
        register.click()
        qtbot.waitUntil(register.isEnabled)
        original_result = tuple(allocations[-3:])
        assert all(ref() is not None for ref in original_result)
        number.setValue(1)
        window.findChild(QPushButton, 'deleteFrame').click()
        qtbot.waitUntil(lambda: original_result[0]() is None)
        assert all(ref() is not None for ref in original_result[1:])
        assert number.maximum() == 2
        register.click()
        qtbot.waitUntil(register.isEnabled)
        qtbot.waitUntil(lambda: all(ref() is None for ref in original_result))
        assert all(ref() is not None for ref in allocations[-2:])
        open_file(qtbot, window, monkeypatch, path)
        qtbot.waitUntil(lambda: all(ref() is None for ref in allocations))
        assert window.findChild(QComboBox, 'frameView').currentText() == 'original'
        assert number.maximum() == 3


@pytest.mark.parametrize('cancel', [False, True])
def test_abandoned_registration_releases_partial_images_and_retains_old_result(
    qtbot, monkeypatch, tmp_path, cancel
):
    allocations = track_allocations(monkeypatch)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, shifted_movie(tmp_path))
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    previous = image(window)
    retained = tuple(allocations)
    transform = ndimage.affine_transform
    entered, release = Event(), Event()
    calls = 0

    def gated(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Allocation gate timed out')
            if not cancel:
                raise MemoryError('controlled resource exhaustion')
        return transform(*args, **kwargs)

    monkeypatch.setattr(ndimage, 'affine_transform', gated)
    try:
        register.click()
        qtbot.waitUntil(entered.is_set)
        if cancel:
            window.findChild(QPushButton, 'cancelRegistration').click()
    finally:
        release.set()
        qtbot.waitUntil(register.isEnabled)
    if not cancel:
        message = window.findChild(QMessageBox)
        assert message.isVisible() and 'controlled resource exhaustion' in message.text()
        message.accept()
    qtbot.waitUntil(lambda: all(ref() is None for ref in allocations[len(retained):]))
    assert all(ref() is not None for ref in retained)
    assert image(window) == previous
