"""EfficientLoFTR inputs and saved evidence through the existing application windows."""
from pathlib import Path

from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton

from stmviewer.ui.main_window import STMViewerMainWindow


def test_user_selects_local_efficient_source_without_overwriting_existing_deep_weights(qtbot, tmp_path):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData('deep_matcher_translation'))
    weights = window.findChild(QLineEdit, 'deepWeights')
    existing = str(tmp_path / 'my-loftr.ckpt')
    weights.setText(existing)
    efficient_index = methods.findData('efficient_loftr')
    assert efficient_index >= 0
    methods.setCurrentIndex(efficient_index)
    source = window.findChild(QLineEdit, 'efficientSource')
    assert source.isVisible()
    assert source.text() == str(Path.home() / '.cache/stmviewer/efficientloftr/source')
    assert weights.text().endswith('/weights/eloftr_outdoor.ckpt')
    missing = str(tmp_path / 'missing-efficient-source')
    source.setText(missing)
    assert 'kod' in window.findChild(QLabel, 'registrationAvailability').text().lower()
    assert not window.findChild(QPushButton, 'checkDeepModel').isEnabled()
    methods.setCurrentIndex(methods.findData('deep_matcher_translation'))
    assert weights.text() == existing
    assert not source.isVisible()
    methods.setCurrentIndex(efficient_index)
    assert source.text() == missing
    window.close()


def test_saved_efficient_pair_exposes_support_and_original_model_settings_without_files(qtbot):
    from PyQt6.QtWidgets import QTableWidget, QWidget
    from stmviewer.correspondence_types import CorrespondenceDiagnostics
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.pair_comparison import PairTrial
    from stmviewer.registration import FrameOrigin
    from stmviewer.series import open_frame_series
    from stmviewer.ui.pair_dialog import PairComparisonDialog
    frames = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])
    details = CorrespondenceDiagnostics((-7., 5.), 60, 56, 48, 48 / 56, (3,) * 16, (3,) * 16,
                                        (.8, .8), (.8, .8), .15, 'manual_review',
                                        'Oceń struktury na obrazie.', 'Konsensus v1')
    saved = PairTrial(FrameOrigin(frames[0].source, frames[0].source_frame_index),
                      FrameOrigin(frames[1].source, frames[1].source_frame_index),
                      'efficient_loftr', 'EfficientLoFTR', 'Zapisany FP32; SHA-256 abc', 'CUDA:0',
                      (-7., 5.), 'manual_review', None, correspondence=details)
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PairComparisonDialog(frames, 1, parent, initial_trial=saved, method='efficient_loftr',
                                  deep_options=DeepMatcherOptions(Path('/missing/weights.ckpt'), 'cpu',
                                                                  Path('/missing/source')))
    qtbot.addWidget(dialog)
    dialog.show()
    summary = dialog.findChild(QLabel, 'pairCorrespondenceDetails')
    assert summary is not None and summary.isVisible()
    assert '48 / 56' in summary.text()
    assert 'bez niezależnej oceny' in summary.text()
    assert dialog.findChild(QTableWidget, 'correspondenceReferenceSupport').item(1, 2).text() == '3'
    assert 'CUDA:0' in dialog.findChild(QLabel, 'pairResult').text()
    assert not dialog.findChild(QPushButton, 'runPair').isEnabled()
    dialog.close()


def test_graph_refusal_displays_saved_support_without_inventing_a_pair_shift(qtbot):
    from dataclasses import replace
    from PyQt6.QtWidgets import QCheckBox, QDialog, QTableWidget, QWidget
    from stmviewer.correspondence_types import CorrespondenceDiagnostics
    from stmviewer.graph_registration import solve_graph
    from stmviewer.series import open_frame_series
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    from test_graph_dialog import candidate
    frames = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])
    base = candidate(frames)
    failure = CorrespondenceDiagnostics(None, 30, 24, 16, 16 / 24,
                                        (4, 4, 4, 4) + (0,) * 12, (4, 4, 4, 4) + (0,) * 12,
                                        (.9, .05), (.9, .05), .1, 'failed',
                                        'Poparcie skupione w wąskim pasie.', 'Konsensus v1')
    edges = tuple(replace(edge, shift_xy=None, status='missing', reason=failure.reason,
                          correspondence_diagnostics=failure) if (edge.i, edge.j) == (0, 2) else edge
                  for edge in base.edges)
    saved = solve_graph(base.sources, edges, replace(base.config, method='efficient_loftr', settings_version=2,
                                                    backend_settings=(('source_path', '/missing/source'),)))
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = GraphComparisonDialog(frames, parent, trial=saved)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.findChild(QPushButton, 'runGraph').isEnabled()
    dialog.findChild(QTableWidget, 'graphEdges').selectRow(1)
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    assert failure.reason in pair.findChild(QLabel, 'pairMessage').text()
    assert 'Odmowa' in pair.findChild(QLabel, 'pairCorrespondenceDetails').text()
    assert pair.findChild(QCheckBox, 'pairLocalFailure').isChecked()
    assert pair.findChild(QTableWidget, 'correspondenceReferenceSupport').item(0, 2).text() == '4'
    assert 'obrazy bez przesunięcia' in pair.findChild(QLabel, 'pairPreviewStatus').text()
    assert not pair.findChild(QPushButton, 'manualMovieApply').isEnabled()
    assert 'ΔX: 0' not in pair.findChild(QLabel, 'pairResult').text()
    assert pair.findChild(QLineEdit, 'efficientSource').text() == '/missing/source'
    pair.close()
    dialog.close()


def test_session_restores_selected_model_paths_even_if_code_and_weights_are_missing(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog
    from test_registration_gui import open_file
    fixture = Path(__file__).parent / 'fixtures/registration/cpu.mpp'
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_file(qtbot, window, monkeypatch, fixture)
    methods = window.findChild(QComboBox, 'registrationMethod')
    methods.setCurrentIndex(methods.findData('efficient_loftr'))
    source = str(tmp_path / 'source')
    weights = str(tmp_path / 'weights.ckpt')
    window.findChild(QLineEdit, 'efficientSource').setText(source)
    window.findChild(QLineEdit, 'deepWeights').setText(weights)
    window.findChild(QComboBox, 'deepDevice').setCurrentText('CPU')
    path = tmp_path / 'local-model.stmsession'
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
    assert restored.findChild(QComboBox, 'registrationMethod').currentData() == 'efficient_loftr'
    assert restored.findChild(QLineEdit, 'efficientSource').text() == source
    assert restored.findChild(QLineEdit, 'deepWeights').text() == weights
    assert restored.findChild(QComboBox, 'deepDevice').currentText() == 'CPU'
    assert not restored.findChild(QPushButton, 'registerFrames').isEnabled()
    restored.close()
