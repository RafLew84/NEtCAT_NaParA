"""Session IO failures leave the visible work and its export usable."""
from pathlib import Path
from threading import Event
import json
import zipfile

import numpy as np
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QLabel, QMessageBox, QProgressBar,
    QPushButton, QSpinBox, QWidget,
)

from stmviewer.series import open_frame_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState
from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import image, open_file

CPU = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'
LOCKED_BUTTONS = (
    'openFrames', 'registerFrames', 'deleteFrame', 'comparePair', 'saveOriginalMpp',
    'saveAvi', 'openSession', 'saveSession', 'playPause',
)


def registered_window(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    open_file(qtbot, window, monkeypatch, CPU)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QDoubleSpinBox, 'previewGamma').setValue(1.7)
    window.findChild(QPushButton, 'zoomIn').click()
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    return window


def view_snapshot(window):
    number = window.findChild(QSpinBox, 'frameNumber')
    return (
        image(window), number.value(), number.maximum(),
        window.findChild(QLabel, 'registrationInfo').text(),
        window.findChild(QComboBox, 'frameView').currentText(),
        window.findChild(QDoubleSpinBox, 'previewGamma').value(),
    )


def export_aligned(qtbot, monkeypatch, window, destination):
    monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                        lambda *args, **kwargs: (str(destination), 'MPP aligned (*.mpp *.MPP)'))
    save = window.findChild(QPushButton, 'saveOriginalMpp')
    assert save.isEnabled()
    save.click()
    qtbot.waitUntil(save.isEnabled)
    assert 'Zapisano' in window.findChild(QLabel, 'mppExportInfo').text()
    return open_frame_series([destination])


def assert_same_export(actual, expected):
    assert len(actual) == len(expected)
    for frame, original in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(frame.data, original.data)
        assert frame.alignment == original.alignment
        assert frame.measurement_time_s == original.measurement_time_s
        assert (frame.size_x_nm, frame.size_y_nm) == (original.size_x_nm, original.size_y_nm)


def assert_ready(window):
    for name in LOCKED_BUTTONS:
        assert window.findChild(QPushButton, name).isEnabled(), name
    assert window.findChild(QComboBox, 'registrationMethod').isEnabled()
    assert not window.findChild(QProgressBar, 'sessionProgress').isVisible()
    assert not window.findChild(QPushButton, 'cancelSession').isVisible()
    assert window.findChild(QPushButton, 'playPause').text() == 'Play'


def choose_session(monkeypatch, path, operation):
    dialog = 'getOpenFileName' if operation == 'load' else 'getSaveFileName'
    monkeypatch.setattr(QFileDialog, dialog, lambda *args, **kwargs: (str(path), ''))


class ArchiveGate:
    """Delay real ZIP image IO, without replacing the session implementation."""

    def __init__(self, monkeypatch, operation, *, fail=False):
        self.entered, self.release = Event(), Event()
        gated_mode = 'r' if operation == 'load' else 'w'
        real_open = zipfile.ZipFile.open

        def delayed_open(archive, name, mode='r', *args, **kwargs):
            filename = name.filename if isinstance(name, zipfile.ZipInfo) else str(name)
            if mode == gated_mode and filename.endswith('.npy') and not self.entered.is_set():
                self.entered.set()
                if not self.release.wait(10):
                    raise OSError('Session IO test timed out')
                if fail:
                    raise OSError('Controlled session storage failure')
            return real_open(archive, name, mode, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, 'open', delayed_open)


def confirm_replace(window):
    def answer():
        dialog = next(w for w in window.findChildren(QMessageBox) if w.isVisible())
        dialog.button(QMessageBox.StandardButton.Yes).click()
    QTimer.singleShot(20, answer)


@pytest.mark.parametrize('invalid', ['broken_archive', 'unknown_version'])
def test_rejected_session_keeps_display_registration_and_real_mpp_export(
    qtbot, monkeypatch, tmp_path, invalid,
):
    window = registered_window(qtbot, monkeypatch)
    expected = export_aligned(qtbot, monkeypatch, window, tmp_path / 'before.mpp')
    before = view_snapshot(window)
    path = tmp_path / 'invalid.stmsession'
    if invalid == 'broken_archive':
        path.write_bytes(b'This file is not a session ZIP archive.')
    else:
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', json.dumps({
                'format': 'stmviewer-session', 'version': 987, 'state': {},
            }))
    choose_session(monkeypatch, path, 'load')
    opening = window.findChild(QPushButton, 'openSession')
    opening.click()
    qtbot.waitUntil(opening.isEnabled)
    info = window.findChild(QLabel, 'sessionInfo').text()
    assert 'nie powiodła' in info
    if invalid == 'unknown_version':
        assert 'wersja' in info
    assert view_snapshot(window) == before
    assert_ready(window)
    assert_same_export(export_aligned(qtbot, monkeypatch, window, tmp_path / 'after.mpp'), expected)


@pytest.mark.parametrize('operation', ['load', 'save'])
@pytest.mark.parametrize('outcome', ['cancel', 'error'])
def test_session_io_keeps_browsing_locks_operations_and_protects_work_and_file(
    qtbot, monkeypatch, tmp_path, operation, outcome,
):
    window = registered_window(qtbot, monkeypatch)
    expected = export_aligned(qtbot, monkeypatch, window, tmp_path / 'before.mpp')
    path = tmp_path / 'existing.stmsession'
    save_session(path, SessionState(open_frame_series([CPU])))
    original_bytes = path.read_bytes()
    choose_session(monkeypatch, path, operation)
    gate = ArchiveGate(monkeypatch, operation, fail=outcome == 'error')
    window.findChild(QComboBox, 'playbackFps').setCurrentText('1')
    window.findChild(QPushButton, 'playPause').click()
    if operation == 'save':
        confirm_replace(window)
    button = window.findChild(QPushButton, 'openSession' if operation == 'load' else 'saveSession')
    try:
        button.click()
        qtbot.waitUntil(gate.entered.is_set)
        for name in LOCKED_BUTTONS:
            assert not window.findChild(QPushButton, name).isEnabled(), name
        assert not window.findChild(QComboBox, 'registrationMethod').isEnabled()
        assert window.findChild(QProgressBar, 'sessionProgress').isVisible()
        assert window.findChild(QPushButton, 'playPause').text() == 'Play'
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        number = window.findChild(QSpinBox, 'frameNumber')
        assert number.isEnabled()
        number.setValue(3)
        gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
        assert gamma.isEnabled()
        gamma.setValue(2.2)
        zoom = window.findChild(QPushButton, 'zoomIn')
        assert zoom.isEnabled()
        zoom.click()
        before = view_snapshot(window)
        if outcome == 'cancel':
            cancel = window.findChild(QPushButton, 'cancelSession')
            assert cancel.isEnabled()
            cancel.click()
            assert not cancel.isEnabled()
    finally:
        gate.release.set()
        qtbot.waitUntil(button.isEnabled)
    message = window.findChild(QLabel, 'sessionInfo').text()
    assert ('Anulowano' if outcome == 'cancel' else 'Controlled session storage failure') in message
    assert view_snapshot(window) == before
    assert_ready(window)
    assert path.read_bytes() == original_bytes
    assert load_session(path).registration is None
    assert list(tmp_path.glob('.*.tmp')) == []
    assert_same_export(export_aligned(qtbot, monkeypatch, window, tmp_path / 'after.mpp'), expected)


def test_close_during_session_load_waits_for_io_cancellation(qtbot, monkeypatch, tmp_path):
    window = registered_window(qtbot, monkeypatch)
    before = view_snapshot(window)
    path = tmp_path / 'input.stmsession'
    save_session(path, SessionState(open_frame_series([CPU])))
    original_bytes = path.read_bytes()
    choose_session(monkeypatch, path, 'load')
    gate = ArchiveGate(monkeypatch, 'load')
    opening = window.findChild(QPushButton, 'openSession')
    try:
        opening.click()
        qtbot.waitUntil(gate.entered.is_set)
        window.close()
        assert window.isVisible()
        assert not window.findChild(QPushButton, 'cancelSession').isEnabled()
        assert not opening.isEnabled()
        assert view_snapshot(window) == before
    finally:
        gate.release.set()
        qtbot.waitUntil(lambda: not window.isVisible())
    assert 'Anulowano' in window.findChild(QLabel, 'sessionInfo').text()
    assert path.read_bytes() == original_bytes
    assert view_snapshot(window) == before
