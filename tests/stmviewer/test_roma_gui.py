"""RoMa setup through visible controls, without starting the model on selection."""
from pathlib import Path

import pytest

from PyQt6.QtWidgets import QComboBox, QLineEdit, QSpinBox, QWidget

from stmviewer.ui.deep_matcher_controls import DeepMatcherControls


def test_roma_settings_are_editable_and_preserved_when_switching_models(qtbot, tmp_path):
    parent = QWidget()
    qtbot.addWidget(parent)
    controls = DeepMatcherControls(parent)
    controls.show()
    controls.set_method('deep_matcher_translation')
    weights = controls.findChild(QLineEdit, 'deepWeights')
    weights.setText(str(tmp_path / 'deep.ckpt'))
    controls.set_method('roma_v2')
    interpreter = controls.findChild(QLineEdit, 'romaInterpreter')
    assert interpreter is not None
    interpreter.setText(str(tmp_path / 'worker-python'))
    controls.findChild(QLineEdit, 'efficientSource').setText(str(tmp_path / 'dinov3'))
    weights.setText(str(tmp_path / 'roma.pt'))
    controls.findChild(QComboBox, 'romaPreset').setCurrentIndex(1)
    controls.findChild(QSpinBox, 'romaSamples').setValue(2048)
    controls.findChild(QSpinBox, 'romaSeed').setValue(74)
    saved = controls.options()
    assert saved.interpreter == tmp_path / 'worker-python'
    assert saved.source == tmp_path / 'dinov3'
    assert (saved.preset, saved.samples, saved.seed) == ('fast', 2048, 74)
    controls.set_method('deep_matcher_translation')
    assert controls.options().weights == tmp_path / 'deep.ckpt'
    assert controls.options().interpreter is None
    controls.set_method('efficient_loftr')
    assert controls.options().weights.name == 'eloftr_outdoor.ckpt'
    assert controls.options().interpreter is None
    controls.set_method('roma_v2')
    assert controls.options() == saved


def test_selecting_roma_shows_missing_interpreter_without_starting_a_process(qtbot, monkeypatch, tmp_path):
    import subprocess
    from PyQt6.QtWidgets import QLabel, QPushButton
    from stmviewer.ui.main_window import STMViewerMainWindow

    def unexpected_process(*args, **kwargs):
        raise AssertionError('Selecting a method must not execute its interpreter')

    monkeypatch.setattr(subprocess, 'Popen', unexpected_process)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    method = window.findChild(QComboBox, 'registrationMethod')
    index = method.findData('roma_v2')
    assert index >= 0
    method.setCurrentIndex(index)
    interpreter = window.findChild(QLineEdit, 'romaInterpreter')
    assert interpreter.isVisible()
    interpreter.setText(str(tmp_path / 'missing-python'))
    text = window.findChild(QLabel, 'registrationAvailability').text().lower()
    assert 'python' in text or 'interpreter' in text
    assert not window.findChild(QPushButton, 'checkDeepModel').isEnabled()
    window.close()


def test_session_restores_roma_process_settings_without_running_saved_interpreter(qtbot, monkeypatch, tmp_path):
    import subprocess
    from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, Path(__file__).parent / 'fixtures/registration/cpu.mpp')
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('roma_v2'))
    configured = {'romaInterpreter': str(tmp_path / 'old-python'),
                  'efficientSource': str(tmp_path / 'old-dino'),
                  'deepWeights': str(tmp_path / 'old-weights.pt')}
    for name, value in configured.items():
        window.findChild(QLineEdit, name).setText(value)
    window.findChild(QComboBox, 'romaPreset').setCurrentIndex(2)
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    window.findChild(QSpinBox, 'romaSamples').setValue(321)
    window.findChild(QSpinBox, 'romaSeed').setValue(135)
    session = tmp_path / 'roma.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(session), ''))
    window.findChild(QPushButton, 'saveSession').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'saveSession').isEnabled)
    assert session.exists(), window.findChild(QLabel, 'sessionInfo').text()
    window.close()

    def unexpected_process(*args, **kwargs):
        raise AssertionError('Opening a session must not execute its saved interpreter')

    monkeypatch.setattr(subprocess, 'Popen', unexpected_process)
    restored = STMViewerMainWindow()
    qtbot.addWidget(restored)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(session), ''))
    restored.findChild(QPushButton, 'openSession').click()
    qtbot.waitUntil(restored.findChild(QPushButton, 'openSession').isEnabled)
    assert 'Otwarto sesję' in restored.findChild(QLabel, 'sessionInfo').text()
    assert restored.findChild(QComboBox, 'registrationMethod').currentData() == 'roma_v2'
    for name, value in configured.items():
        assert restored.findChild(QLineEdit, name).text() == value
    assert restored.findChild(QComboBox, 'romaPreset').currentData() == 'base'
    assert restored.findChild(QComboBox, 'deepDevice').currentText() == 'CPU'
    assert restored.findChild(QSpinBox, 'romaSamples').value() == 321
    assert restored.findChild(QSpinBox, 'romaSeed').value() == 135
    assert not restored.findChild(QPushButton, 'registerFrames').isEnabled()
    restored.close()


def test_saved_roma_graph_and_its_pair_restore_model_settings_and_support(qtbot, tmp_path):
    from dataclasses import replace
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidget
    from stmviewer.correspondence_types import CorrespondenceDiagnostics
    from stmviewer.series import open_frame_series
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    from test_graph_dialog import candidate
    frames = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])
    base = candidate(frames)
    details = CorrespondenceDiagnostics((1., -1.), 100, 96, 80, 80 / 96, (5,) * 16, (5,) * 16,
                                        (.8, .9), (.8, .9), .2, 'manual_review',
                                        'Oceń struktury na obrazie.', 'Zapisany konsensus v2')
    config = replace(base.config, method='roma_v2', backend_settings=(
        ('source_path', str(tmp_path / 'dinov3')), ('interpreter_path', str(tmp_path / 'python')),
        ('preset', 'fast'), ('samples', '360'), ('seed', '19')))
    saved = replace(base, config=config, edges=tuple(replace(edge, correspondence_diagnostics=details)
                                                    for edge in base.edges))
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = GraphComparisonDialog(frames, parent, trial=saved)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.findChild(QComboBox, 'graphMethod').currentData() == 'roma_v2'
    assert dialog.findChild(QLineEdit, 'romaInterpreter').text() == str(tmp_path / 'python')
    assert dialog.findChild(QComboBox, 'romaPreset').currentData() == 'fast'
    assert dialog.findChild(QSpinBox, 'romaSamples').value() == 360
    assert not dialog.findChild(QPushButton, 'runGraph').isEnabled()
    dialog.findChild(QTableWidget, 'graphEdges').selectRow(0)
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    assert pair.findChild(QComboBox, 'pairMethod').currentData() == 'roma_v2'
    assert pair.findChild(QLineEdit, 'romaInterpreter').text() == str(tmp_path / 'python')
    assert pair.findChild(QSpinBox, 'romaSamples').value() == 360
    assert pair.findChild(QSpinBox, 'romaSeed').value() == 19
    assert '80 / 96' in pair.findChild(QLabel, 'pairCorrespondenceDetails').text()
    assert 'RoMa v2' in pair.findChild(QLabel, 'pairResult').text()
    assert not pair.findChild(QPushButton, 'runPair').isEnabled()
    pair.close()
    dialog.close()


def test_explicit_model_check_reports_missing_roma_environment(qtbot, tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.ui.registration_job import RegistrationJob
    parent = QWidget()
    qtbot.addWidget(parent)
    options = DeepMatcherOptions(interpreter=tmp_path / 'missing-python')
    job = RegistrationJob((), parent, method='roma_v2', deep_options=options, check_only=True)
    job.run()
    assert job.error is not None
    assert 'RoMa' in job.error and 'interpreter' in job.error
    assert job.checked_device is None
    assert job.result is None


def test_applied_roma_graph_exposes_weak_pair_count_without_inventing_solver_confidence():
    from dataclasses import replace
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.ui.registration_info import registration_info
    from test_manual_movie import cpu_result
    from test_roma_session import roma_graph
    frames = tuple(item.original for item in cpu_result().frames)
    graph = roma_graph(frames)
    first = graph.edges[0]
    details = replace(first.correspondence_diagnostics, status='low_confidence',
                      reason='Słabe poparcie: dopasowania skupione w małym obszarze.')
    graph = replace(graph, edges=(replace(first, status='low_confidence',
                                          correspondence_diagnostics=details),) + graph.edges[1:])
    result = apply_graph_to_movie(frames, graph)
    text = registration_info(result, 1, False)
    assert 'Słabe poparcie par grafu: 1 / 3' in text
    assert 'Słabe pary zachowano' in text
    assert result.frames[1].status == 'manual_review'
    assert result.frames[1].quality_score is None


def test_opening_graph_keeps_selected_roma_even_with_empty_interpreter(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QPushButton
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, Path(__file__).parent / 'fixtures/registration/cpu.mpp')
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData('roma_v2'))
    window.findChild(QLineEdit, 'romaInterpreter').clear()
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert graph.findChild(QComboBox, 'graphMethod').currentData() == 'roma_v2'
    assert graph.findChild(QLineEdit, 'romaInterpreter').text() == ''
    assert not graph.findChild(QPushButton, 'runGraph').isEnabled()
    graph.close()
    window.close()


@pytest.mark.parametrize('active_method', ['phase_correlation', 'efficient_loftr'])
def test_session_keeps_roma_configuration_when_another_method_is_selected(
    qtbot, monkeypatch, tmp_path, active_method
):
    import subprocess
    from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, Path(__file__).parent / 'fixtures/registration/cpu.mpp')
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData('roma_v2'))
    expected_paths = {'romaInterpreter': str(tmp_path / 'portable-python'),
                      'efficientSource': str(tmp_path / 'custom-dino'),
                      'deepWeights': str(tmp_path / 'custom-roma.pt')}
    for name, value in expected_paths.items():
        window.findChild(QLineEdit, name).setText(value)
    window.findChild(QComboBox, 'romaPreset').setCurrentIndex(2)
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    window.findChild(QSpinBox, 'romaSamples').setValue(321)
    window.findChild(QSpinBox, 'romaSeed').setValue(135)
    methods.setCurrentIndex(methods.findData(active_method))
    session = tmp_path / 'remembered-roma.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(session), ''))
    window.findChild(QPushButton, 'saveSession').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'saveSession').isEnabled)
    assert session.exists(), window.findChild(QLabel, 'sessionInfo').text()
    window.close()

    def unexpected_process(*args, **kwargs):
        raise AssertionError('Restoring a remembered model must not execute its interpreter')

    monkeypatch.setattr(subprocess, 'Popen', unexpected_process)
    restored = STMViewerMainWindow()
    qtbot.addWidget(restored)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(session), ''))
    restored.findChild(QPushButton, 'openSession').click()
    qtbot.waitUntil(restored.findChild(QPushButton, 'openSession').isEnabled)
    assert 'Otwarto sesję' in restored.findChild(QLabel, 'sessionInfo').text()
    restored_methods = restored.findChild(QComboBox, 'registrationMethod')
    assert restored_methods.currentData() == active_method
    restored_methods.setCurrentIndex(restored_methods.findData('roma_v2'))
    for name, value in expected_paths.items():
        assert restored.findChild(QLineEdit, name).text() == value
    assert restored.findChild(QComboBox, 'romaPreset').currentData() == 'base'
    assert restored.findChild(QComboBox, 'deepDevice').currentText() == 'CPU'
    assert restored.findChild(QSpinBox, 'romaSamples').value() == 321
    assert restored.findChild(QSpinBox, 'romaSeed').value() == 135
    assert not restored.findChild(QPushButton, 'registerFrames').isEnabled()
    restored.close()
