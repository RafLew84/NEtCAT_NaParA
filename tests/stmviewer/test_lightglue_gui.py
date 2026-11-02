"""LightGlue paths and persistence through the public Qt controls."""
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QComboBox, QLineEdit, QWidget
from stmviewer.ui.deep_matcher_controls import DeepMatcherControls

METHOD = 'lightglue_superpoint'
FIXTURE = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_lightglue_remembers_both_checkpoints_without_overwriting_other_models(qtbot, tmp_path):
    parent = QWidget()
    qtbot.addWidget(parent)
    controls = DeepMatcherControls(parent)
    parent.show()
    controls.show()
    controls.set_method('matchanything_eloftr')
    previous = controls.options()
    controls.set_method(METHOD)
    assert controls.options().weights.name == 'superpoint_lightglue.pth'
    assert controls.options().extractor_weights.name == 'superpoint_v1.pth'
    extractor = controls.findChild(QLineEdit, 'superpointWeights')
    assert extractor.isVisible()
    extractor.setText(str(tmp_path / 'extractor.pth'))
    controls.findChild(QLineEdit, 'deepWeights').setText(str(tmp_path / 'matcher.pth'))
    controls.findChild(QLineEdit, 'efficientSource').setText(str(tmp_path / 'code'))
    controls.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    selected = controls.options()
    controls.set_method('matchanything_eloftr')
    assert controls.options() == previous
    assert not extractor.isVisible()
    controls.set_method(METHOD)
    assert controls.options() == selected


def test_selected_lightglue_and_both_paths_reach_pair_and_graph(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData(METHOD))
    assert method.currentText() == 'LightGlue + SuperPoint'
    paths = {'deepWeights': str(tmp_path / 'matcher.pth'),
             'superpointWeights': str(tmp_path / 'extractor.pth'),
             'efficientSource': str(tmp_path / 'missing-code')}
    for name, value in paths.items():
        window.findChild(QLineEdit, name).setText(value)
    assert not window.findChild(QPushButton, 'registerFrames').isEnabled()
    assert 'kod' in window.findChild(QLabel, 'registrationAvailability').text().lower()
    for button, dialog_name, selector in [('comparePair', 'pairComparison', 'pairMethod'),
                                         ('openGraph', 'graphComparison', 'graphMethod')]:
        window.findChild(QPushButton, button).click()
        dialog = window.findChild(QDialog, dialog_name)
        assert dialog.findChild(QComboBox, selector).currentData() == METHOD
        for name, value in paths.items():
            assert dialog.findChild(QLineEdit, name).text() == value
        dialog.close()
    window.close()


@pytest.mark.parametrize('active_method', [METHOD, 'phase_correlation'])
def test_session_restores_both_lightglue_checkpoints_even_when_inactive(qtbot, monkeypatch, tmp_path, active_method):
    from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData(METHOD))
    paths = {'deepWeights': str(tmp_path / 'matcher.pth'),
             'superpointWeights': str(tmp_path / 'extractor.pth'),
             'efficientSource': str(tmp_path / 'code')}
    for name, value in paths.items():
        window.findChild(QLineEdit, name).setText(value)
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    methods.setCurrentIndex(methods.findData(active_method))
    session = tmp_path / 'lightglue.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(session), ''))
    window.findChild(QPushButton, 'saveSession').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'saveSession').isEnabled)
    assert session.exists(), window.findChild(QLabel, 'sessionInfo').text()
    window.close()
    restored = STMViewerMainWindow()
    qtbot.addWidget(restored)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(session), ''))
    restored.findChild(QPushButton, 'openSession').click()
    qtbot.waitUntil(restored.findChild(QPushButton, 'openSession').isEnabled)
    assert 'Otwarto sesję' in restored.findChild(QLabel, 'sessionInfo').text()
    methods = restored.findChild(QComboBox, 'registrationMethod')
    assert methods.currentData() == active_method
    methods.setCurrentIndex(methods.findData(METHOD))
    for name, value in paths.items():
        assert restored.findChild(QLineEdit, name).text() == value
    assert restored.findChild(QComboBox, 'deepDevice').currentText() == 'CPU'
    restored.close()
