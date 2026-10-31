"""The full-film UI exposes local evidence without changing the default method."""

from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QSpinBox

from stmviewer.ui.main_window import STMViewerMainWindow
from deep_ecc_fixture import controlled_loftr as model_fixture, textured_pair
from make_registration_fixtures import write_movie
from test_registration_gui import open_file

controlled_loftr = model_fixture
LABEL = 'Deep Matcher + lokalne fragmenty (v1)'


def test_full_movie_reports_local_support_and_preserves_export_and_play_controls(qtbot, monkeypatch, controlled_loftr, tmp_path):
    _, weights = controlled_loftr
    path = tmp_path / 'textured.mpp'
    write_movie(path, tuple(frame.data for frame in textured_pair()))
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, path)
    method = window.findChild(QComboBox, 'registrationMethod')
    assert method.currentText() == 'Phase'
    method.setCurrentText(LABEL)
    window.findChild(QLineEdit, 'deepWeights').setText(str(weights))
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    run = window.findChild(QPushButton, 'registerFrames')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=10000)

    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    info = window.findChild(QLabel, 'registrationInfo').text()
    assert LABEL in info and 'pewność niezweryfikowana' in info
    assert 'Start Deep' in info and 'Wynik lokalny' in info
    assert 'Zgodne:' in info and 'przed ręcznymi korektami' in info
    assert str(weights) in info and 'search_radius=16' in info
    assert window.findChild(QPushButton, 'playPause').isEnabled()
    assert window.findChild(QPushButton, 'saveOriginalMpp').isEnabled()
    assert window.findChild(QPushButton, 'saveAvi').isEnabled()
