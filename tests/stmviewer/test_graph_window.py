"""Graph candidate is independent of the active movie through visible actions."""
from PyQt6.QtWidgets import QComboBox, QDialog, QFileDialog, QLabel, QLineEdit, QPushButton, QSpinBox

from test_deep_registration import local_model as local_model
from stmviewer.ui.main_window import STMViewerMainWindow
from test_registration_gui import open_file
from test_deep_registration import FIXTURE


def test_graph_is_available_for_a_movie_without_active_registration(qtbot, monkeypatch):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    opening = window.findChild(QPushButton, 'openGraph')
    assert opening is not None
    assert not opening.isEnabled()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    assert opening.isEnabled()


def test_graph_session_and_export_keep_the_active_manual_movie(qtbot, monkeypatch, tmp_path, local_model):  # noqa: F811 — pytest fixture injection
    from test_manual_movie_gui import registered_pair, assert_shifts
    from test_session_window import reopen_session
    from stmviewer.series import open_frame_series

    window, pair = registered_pair(qtbot, monkeypatch)
    pair.findChild(QPushButton, 'manualMovieStart').click()
    pair.findChild(QPushButton, 'manualPairXPlus').click()
    pair.findChild(QPushButton, 'manualPairApply').click()
    pair.findChild(QPushButton, 'manualMovieApply').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'registerFrames').isEnabled)
    pair.close()
    expected = [(0, 0), (3, -1), (0, 1)]
    assert_shifts(window, expected)
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    graph.findChild(QLineEdit, 'deepWeights').setText(str(local_model))
    graph.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    graph.findChild(QPushButton, 'runGraph').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled, timeout=5000)
    summary = graph.findChild(QLabel, 'graphSummary').text()
    assert '3' in summary
    variants = graph.findChild(QComboBox, 'graphVariant')
    assert {variants.itemData(i) for i in range(variants.count())} == {'graph', 'chain'}
    variants.setCurrentIndex(variants.findData('graph'))
    graph.findChild(QSpinBox, 'graphFrame').setValue(3)
    assert_shifts(window, expected)
    with qtbot.waitSignal(graph.destroyed):
        graph.close()
    path = tmp_path / 'active.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), 'MPP aligned (*.mpp *.MPP)'))
    window.findChild(QPushButton, 'saveOriginalMpp').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'saveOriginalMpp').isEnabled)
    assert [f.alignment.shift_xy for f in open_frame_series([path])] == expected
    window = reopen_session(qtbot, window, monkeypatch, tmp_path / 'graph.stmsession')
    assert_shifts(window, expected)
    local_model.unlink()
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert graph.findChild(QLabel, 'graphSummary').text() == summary
    assert graph.findChild(QLineEdit, 'deepWeights').text() == str(local_model)
    assert graph.findChild(QPushButton, 'graphPlay').isEnabled()
    assert not graph.findChild(QPushButton, 'runGraph').isEnabled()
    with qtbot.waitSignal(graph.destroyed):
        graph.close()
    window.findChild(QPushButton, 'deleteFrame').click()
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert graph.findChild(QComboBox, 'graphVariant').count() == 1  # Only remaining active aligned.
    assert graph.findChild(QComboBox, 'graphVariant').currentData() == 'active'


def test_graph_job_locks_series_and_can_cancel_while_main_preview_stays_available(
        qtbot, monkeypatch, local_model):  # noqa: F811 — pytest fixture injection
    from threading import Event
    import torch
    from test_registration_gui import image

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    register = window.findChild(QPushButton, 'registerFrames')
    register.click()
    qtbot.waitUntil(register.isEnabled)
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    graph.findChild(QLineEdit, 'deepWeights').setText(str(local_model))
    graph.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    entered, release = Event(), Event()
    load = torch.load

    def delayed_load(*a, **kw):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Timed out waiting for cancellation test')
        return load(*a, **kw)

    monkeypatch.setattr(torch, 'load', delayed_load)
    try:
        graph.findChild(QPushButton, 'runGraph').click()
        qtbot.waitUntil(entered.is_set)
        for name in ('openFrames', 'openSession', 'saveSession', 'deleteFrame', 'registerFrames',
                     'saveOriginalMpp', 'saveAvi', 'playPause', 'comparePair'):
            assert not window.findChild(QPushButton, name).isEnabled(), name
        window.findChild(QSpinBox, 'frameNumber').setValue(2)
        window.findChild(QPushButton, 'zoomIn').click()
        before = image(window)
        info = window.findChild(QLabel, 'registrationInfo').text()
        graph.findChild(QPushButton, 'cancelGraph').click()
        release.set()
        qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
        assert window.findChild(QLabel, 'registrationInfo').text() == info
        assert image(window) == before
        assert 'Anulowano' in graph.findChild(QLabel, 'graphMessage').text()
        assert graph.findChild(QComboBox, 'graphVariant').currentData() == 'active'
    finally:
        release.set()
