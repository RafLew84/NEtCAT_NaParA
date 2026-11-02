"""Changing graph measurement settings does not relabel an existing result."""
from pathlib import Path

from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QWidget

from stmviewer.series import open_frame_series
from stmviewer.ui.graph_dialog import GraphComparisonDialog
from test_graph_dialog import candidate


FIXTURE = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_selecting_cpu_method_keeps_existing_deep_candidate_and_needs_no_weights(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = open_frame_series([FIXTURE])
    saved = candidate(frames)
    dialog = GraphComparisonDialog(frames, parent, trial=saved)
    qtbot.addWidget(dialog)
    dialog.show()
    summary = dialog.findChild(QLabel, 'graphSummary').text()
    application = dialog.findChild(QLabel, 'graphApplicationInfo').text()
    method = dialog.findChild(QComboBox, 'graphMethod')
    assert method is not None
    assert method.currentData() == 'deep_matcher_translation'
    assert method.count() == 10
    assert method.findData('roma_v2') >= 0
    method.setCurrentIndex(method.findData('phase_correlation'))
    assert dialog.findChild(QPushButton, 'runGraph').isEnabled()
    assert not dialog.findChild(QLineEdit, 'deepWeights').isVisible()
    assert dialog.trial is saved
    assert dialog.findChild(QLabel, 'graphSummary').text() == summary
    assert dialog.findChild(QLabel, 'graphApplicationInfo').text() == application
    dialog.close()


def test_cpu_graph_run_and_saved_pair_keep_actual_method_after_next_run_selection_changes(qtbot):
    from PyQt6.QtWidgets import QDialog, QTableWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = open_frame_series([FIXTURE])
    dialog = GraphComparisonDialog(frames, parent)
    qtbot.addWidget(dialog)
    dialog.show()
    method = dialog.findChild(QComboBox, 'graphMethod')
    method.setCurrentIndex(method.findData('phase_correlation'))
    dialog.findChild(QPushButton, 'runGraph').click()
    qtbot.waitUntil(lambda: not dialog.busy)
    assert dialog.trial is not None, dialog.findChild(QLabel, 'graphMessage').text()
    assert dialog.trial.config.method == 'phase_correlation'
    assert dialog.trial.positions is not None
    for name in ('graphSummary', 'graphApplicationInfo'):
        text = dialog.findChild(QLabel, name).text()
        assert 'Phase' in text and 'Deep' not in text
        assert 'SHA-256 wag' not in text
    variants = dialog.findChild(QComboBox, 'graphVariant')
    assert all('Phase' in variants.itemText(i) for i in range(variants.count()))
    assert 'Deep' not in dialog.findChild(QLabel, 'robustSummary').text()
    saved = dialog.trial
    method.setCurrentIndex(method.findData('deep_matcher_translation'))
    assert dialog.trial is saved
    assert 'Phase' in dialog.findChild(QLabel, 'graphApplicationInfo').text()
    dialog.findChild(QTableWidget, 'graphEdges').selectRow(1)
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    result = pair.findChild(QLabel, 'pairResult').text()
    assert 'Phase' in result and 'Deep' not in result
    assert 'Klatka bazowa 1' in pair.findChild(QLabel, 'pairSource').text()
    assert 'Klatka przesuwana 3' in pair.findChild(QLabel, 'pairSource').text()
    assert pair.findChild(QComboBox, 'pairMethod').currentData() == 'phase_correlation'
    pair.close()
    dialog.close()


def test_missing_local_pair_opens_saved_refusal_and_evidence_without_a_fake_shift(qtbot):
    from dataclasses import replace
    from PyQt6.QtWidgets import QCheckBox, QDialog, QTableWidget
    from stmviewer.graph_registration import solve_graph
    from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = open_frame_series([FIXTURE])
    base = candidate(frames)
    details = LocalDiagnostics((2., -1.), None, (
        LocalPatchEvidence((0, 0, 16, 16), None, None, None, None, 'unmatched', 'Brak tekstury'),
    ), 'refused', 'Za mało zgodnych fragmentów', 'test')
    edges = tuple(replace(edge, shift_xy=None, status='missing', reason=details.reason,
                          local_diagnostics=details) if (edge.i, edge.j) == (0, 2) else edge
                  for edge in base.edges)
    saved = solve_graph(base.sources, edges, replace(base.config, method='deep_local_consensus', settings_version=2))
    dialog = GraphComparisonDialog(frames, parent, trial=saved)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.findChild(QTableWidget, 'graphEdges').selectRow(1)
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    assert details.reason in pair.findChild(QLabel, 'pairMessage').text()
    assert 'Brak wyniku lokalnego' in pair.findChild(QLabel, 'pairLocalDetails').text()
    assert pair.findChild(QTableWidget, 'pairLocalPatches').rowCount() == 1
    assert pair.findChild(QCheckBox, 'pairLocalFailure').isChecked()
    assert 'ΔX: 0' not in pair.findChild(QLabel, 'pairResult').text()
    assert not pair.findChild(QPushButton, 'manualMovieApply').isEnabled()
    pair.close()
    dialog.close()


def test_cpu_huber_application_and_session_restore_are_independent_of_main_method(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QDialog, QFileDialog, QSpinBox
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_registration_gui import open_file
    from test_manual_movie_gui import assert_shifts
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, FIXTURE)
    main_method = window.findChild(QComboBox, 'registrationMethod')
    main_method.setCurrentIndex(main_method.findData('ecc_translation'))
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    method = graph.findChild(QComboBox, 'graphMethod')
    assert method.currentData() == 'deep_matcher_translation'
    method.setCurrentIndex(method.findData('phase_correlation'))
    graph.findChild(QPushButton, 'runGraph').click()
    qtbot.waitUntil(lambda: not graph.busy)
    assert main_method.currentData() == 'ecc_translation'
    graph.findChild(QPushButton, 'runRobustGraph').click()
    qtbot.waitUntil(lambda: not graph.busy)
    assert graph.findChild(QComboBox, 'graphApplicationVariant').currentText().startswith('Huber')
    assert graph.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    graph.findChild(QPushButton, 'applyGraphMovie').click()
    qtbot.waitUntil(lambda: not graph.busy)
    assert_shifts(window, [(0, 0), (2, -1), (-1, 1)])
    text = window.findChild(QLabel, 'registrationInfo').text()
    assert 'Phase' in text and 'huber' in text.lower() and 'Deep' not in text
    graph.close()
    path = tmp_path / 'cpu.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'saveSession').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'saveSession').isEnabled)
    assert path.exists(), window.findChild(QLabel, 'sessionInfo').text()
    window.close()
    restored = STMViewerMainWindow()
    qtbot.addWidget(restored)
    restored.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    restored.findChild(QPushButton, 'openSession').click()
    qtbot.waitUntil(restored.findChild(QPushButton, 'openSession').isEnabled)
    assert 'Otwarto sesję' in restored.findChild(QLabel, 'sessionInfo').text()
    assert restored.findChild(QLabel, 'registrationInfo').text() == text
    restored.findChild(QPushButton, 'openGraph').click()
    graph = restored.findChild(QDialog, 'graphComparison')
    assert graph.findChild(QComboBox, 'graphMethod').currentData() == 'phase_correlation'
    assert graph.findChild(QPushButton, 'runGraph').isEnabled()
    assert not graph.findChild(QLineEdit, 'deepWeights').isVisible()
    graph.findChild(QSpinBox, 'graphFrame').setValue(3)
    assert 'Phase' in graph.findChild(QLabel, 'graphSummary').text()
    graph.close()


import pytest  # noqa: E402


@pytest.mark.parametrize('outcome', ['cancel', 'error'])
def test_cpu_job_failure_or_cancel_preserves_saved_candidate_and_active_movie(qtbot, monkeypatch, tmp_path, outcome):
    from threading import Event
    import cv2
    from test_graph_application_gui import open_candidate_session
    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path)
    previous = graph.trial
    active = window.findChild(QLabel, 'registrationInfo').text()
    method = graph.findChild(QComboBox, 'graphMethod')
    method.setCurrentIndex(method.findData('ecc_translation'))
    entered, release = Event(), Event()
    estimate = cv2.findTransformECC

    def controlled(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        if outcome == 'error':
            raise MemoryError('Controlled ECC memory failure')
        return estimate(*args, **kwargs)

    monkeypatch.setattr(cv2, 'findTransformECC', controlled)
    try:
        graph.findChild(QPushButton, 'runGraph').click()
        qtbot.waitUntil(entered.is_set)
        assert not method.isEnabled()
        for name in ('openFrames', 'openSession', 'saveSession', 'deleteFrame', 'registerFrames', 'saveOriginalMpp', 'saveAvi'):
            assert not window.findChild(QPushButton, name).isEnabled()
        assert window.findChild(QPushButton, 'zoomIn').isEnabled()
        if outcome == 'cancel':
            graph.findChild(QPushButton, 'cancelGraph').click()
        release.set()
        qtbot.waitUntil(lambda: not graph.busy)
        assert graph.trial is previous
        assert window.findChild(QLabel, 'registrationInfo').text() == active
        assert 'Poprzedni kandydat' in graph.findChild(QLabel, 'graphMessage').text()
        graph.close()
    finally:
        release.set()
