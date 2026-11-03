"""MatchAnything inputs and saved evidence through visible application controls."""
from pathlib import Path

import pytest

from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QWidget

from stmviewer.ui.deep_matcher_controls import DeepMatcherControls


METHOD = 'matchanything_eloftr'
FIXTURE = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_matchanything_has_separate_local_paths_and_keeps_other_models(qtbot, tmp_path):
    parent = QWidget()
    qtbot.addWidget(parent)
    controls = DeepMatcherControls(parent)
    parent.show()
    controls.show()
    controls.set_method('efficient_loftr')
    weights = controls.findChild(QLineEdit, 'deepWeights')
    source = controls.findChild(QLineEdit, 'efficientSource')
    weights.setText(str(tmp_path / 'efficient.ckpt'))
    source.setText(str(tmp_path / 'efficient-source'))
    controls.set_method(METHOD)
    assert controls.options().weights == Path.home() / '.cache/stmviewer/matchanything/weights/matchanything_eloftr.ckpt'
    assert controls.options().source == Path.home() / '.cache/stmviewer/matchanything/source'
    assert source.isVisible()
    assert 'MatchAnything-ELoFTR' in source.accessibleName()
    assert 'MatchAnything-ELoFTR' in weights.accessibleName()
    weights.setText(str(tmp_path / 'matchanything.ckpt'))
    source.setText(str(tmp_path / 'matchanything-source'))
    controls.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    saved = controls.options()
    controls.set_method('efficient_loftr')
    assert controls.options().weights == tmp_path / 'efficient.ckpt'
    assert controls.options().source == tmp_path / 'efficient-source'
    controls.set_method('roma_v2')
    assert controls.options().weights.name == 'romav2.0.1.pt'
    controls.set_method(METHOD)
    assert controls.options() == saved
    assert controls.options().interpreter is None


def test_missing_matchanything_source_has_its_own_availability_reason(tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.ui.registration_options import method_unavailable_reason

    reason = method_unavailable_reason(
        METHOD, DeepMatcherOptions(tmp_path / 'weights.ckpt', 'cpu', tmp_path / 'missing-source'), {})
    assert reason is not None
    assert 'MatchAnything' in reason
    assert 'kod' in reason.lower()


def test_explicit_model_check_reports_missing_matchanything_source(qtbot, tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.ui.registration_job import RegistrationJob

    parent = QWidget()
    qtbot.addWidget(parent)
    options = DeepMatcherOptions(tmp_path / 'weights.ckpt', 'cpu', tmp_path / 'missing-source')
    job = RegistrationJob((), parent, method=METHOD, deep_options=options, check_only=True)
    job.run()
    assert job.error is not None
    assert 'MatchAnything' in job.error and 'kod' in job.error.lower()
    assert job.checked_device is None
    assert job.result is None


def test_main_window_passes_matchanything_to_pair_and_graph_even_without_source(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    method = window.findChild(QComboBox, 'registrationMethod')
    method.setCurrentIndex(method.findData(METHOD))
    assert method.currentText() == 'MatchAnything-ELoFTR'
    window.findChild(QLineEdit, 'efficientSource').clear()
    assert 'kod' in window.findChild(QLabel, 'registrationAvailability').text().lower()
    assert not window.findChild(QPushButton, 'registerFrames').isEnabled()
    assert not window.findChild(QPushButton, 'checkDeepModel').isEnabled()
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    assert pair.findChild(QComboBox, 'pairMethod').currentData() == METHOD
    assert not pair.findChild(QPushButton, 'runPair').isEnabled()
    pair.close()
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert graph.findChild(QComboBox, 'graphMethod').currentData() == METHOD
    assert not graph.findChild(QPushButton, 'runGraph').isEnabled()
    graph.close()
    window.close()


@pytest.mark.parametrize('active_method', ['phase_correlation', METHOD])
def test_session_keeps_matchanything_paths_when_active_or_remembered(qtbot, monkeypatch, tmp_path, active_method):
    from PyQt6.QtWidgets import QFileDialog
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData(METHOD))
    paths = {'deepWeights': str(tmp_path / 'matchanything.ckpt'),
             'efficientSource': str(tmp_path / 'matchanything-source')}
    for name, value in paths.items():
        window.findChild(QLineEdit, name).setText(value)
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    methods.setCurrentIndex(methods.findData(active_method))
    session = tmp_path / 'matchanything.stmsession'
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
    restored_methods = restored.findChild(QComboBox, 'registrationMethod')
    assert restored_methods.currentData() == active_method
    restored_methods.setCurrentIndex(restored_methods.findData(METHOD))
    for name, value in paths.items():
        assert restored.findChild(QLineEdit, name).text() == value
    assert restored.findChild(QComboBox, 'deepDevice').currentText() == 'CPU'
    assert not restored.findChild(QPushButton, 'registerFrames').isEnabled()
    restored.close()


def test_applied_matchanything_graph_reports_weak_pairs_without_solver_confidence():
    from dataclasses import replace
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.ui.registration_info import registration_info
    from test_manual_movie import cpu_result
    from test_matchanything_session import matchanything_graph

    frames = tuple(item.original for item in cpu_result().frames)
    graph = matchanything_graph(frames)
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
