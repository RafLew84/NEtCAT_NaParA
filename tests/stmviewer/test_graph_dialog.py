"""Graph inspection uses saved measurements, including nonadjacent originals."""
from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import QLabel, QPushButton, QSpinBox, QWidget

from stmviewer.pair_comparison import PairTrial
from stmviewer.registration import FrameOrigin
from stmviewer.ui.pair_dialog import PairComparisonDialog
from test_pair_comparison import frame


def test_saved_nonadjacent_pair_uses_actual_sources_and_cannot_apply_to_movie(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(24).reshape(4, 6), index) for index in (2, 3, 4, 5))
    trial = PairTrial(FrameOrigin(frames[0].source, 2), FrameOrigin(frames[2].source, 4),
                      'deep_matcher', 'Pomiar grafu', 'Zapisana relacja 1 → 3', 'CPU', (2, -1), 'ok', None)
    dialog = PairComparisonDialog(frames, 2, parent, reference_index=0, initial_trial=trial)
    qtbot.addWidget(dialog)
    dialog.show()
    source = dialog.findChild(QLabel, 'pairSource').text()
    assert 'Klatka bazowa 1' in source and 'MPP 3' in source
    assert 'Klatka przesuwana 3' in source and 'MPP 5' in source
    assert 'ΔX: 2 px' in dialog.findChild(QLabel, 'pairResult').text()
    assert not dialog.findChild(QSpinBox, 'pairNumber').isEnabled()
    assert not dialog.findChild(QPushButton, 'manualMovieApply').isEnabled()
    dialog.close()


def candidate(frames, *, disconnected=False, chain=True):
    from stmviewer.graph_registration import graph_pairs, solve_graph
    from stmviewer.graph_types import GraphConfig, GraphSource, GraphEdge
    sources = tuple(GraphSource(str(f.source), f.source_frame_index, f.data.shape, '0' * 64) for f in frames)
    edges = tuple(GraphEdge(i, j, None, 'missing', 'Brak cech')
                  if (disconnected and j == len(frames) - 1) or (not chain and (i, j) == (1, 2))
                  else GraphEdge(i, j, (float(j - i), float(i - j)), 'ok')
                  for i, j in graph_pairs(len(frames), 3))
    return solve_graph(sources, edges, GraphConfig(3, '/unavailable/weights.ckpt', '1' * 64,
                                                  'cpu', 'CPU', (), (), 'test'))


def test_restored_graph_movie_is_viewable_without_model_and_pair_open_uses_saved_measurement(qtbot):
    from PyQt6.QtWidgets import QComboBox, QDialog, QTableWidget
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    from stmviewer.ui.image_preview import ImagePreview
    from stmviewer.deep_matcher import DeepMatcherOptions
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(24).reshape(4, 6), i + 2) for i in range(4))
    dialog = GraphComparisonDialog(frames, parent, trial=candidate(frames),
                                   deep_options=DeepMatcherOptions(Path('/unavailable/weights.ckpt')))
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.findChild(QPushButton, 'runGraph').isEnabled()
    assert '6 par' in dialog.findChild(QLabel, 'graphPairCount').text()
    variants = dialog.findChild(QComboBox, 'graphVariant')
    assert [variants.itemData(i) for i in range(variants.count())] == ['graph', 'chain']
    preview = dialog.findChild(ImagePreview, 'graphPreview')
    preview.zoom_in()
    before = preview.navigation_states()
    variants.setCurrentIndex(1)
    dialog.findChild(QSpinBox, 'graphFrame').setValue(3)
    assert preview.navigation_states() == before
    edges = dialog.findChild(QTableWidget, 'graphEdges')
    edges.selectRow(1)
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    assert 'MPP 3' in pair.findChild(QLabel, 'pairSource').text()
    assert 'MPP 5' in pair.findChild(QLabel, 'pairSource').text()
    assert 'ΔX: 2 px' in pair.findChild(QLabel, 'pairResult').text()
    assert not pair.findChild(QPushButton, 'manualMovieApply').isEnabled()
    pair.close()
    dialog.findChild(QSpinBox, 'graphFps').setValue(30)
    dialog.findChild(QPushButton, 'graphPlay').click()
    qtbot.waitUntil(lambda: dialog.findChild(QSpinBox, 'graphFrame').value() == 4)
    qtbot.waitUntil(lambda: dialog.findChild(QPushButton, 'graphPlay').text() == 'Play')
    assert dialog.trial.positions == candidate(frames).positions
    dialog.close()


def test_disconnected_diagnostics_keep_missing_pair_and_refuse_fictional_movie(qtbot):
    from PyQt6.QtWidgets import QComboBox, QTableWidget
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(24).reshape(4, 6), i) for i in range(3))
    dialog = GraphComparisonDialog(frames, parent, trial=candidate(frames, disconnected=True))
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.findChild(QComboBox, 'graphVariant').count() == 0
    assert not dialog.findChild(QPushButton, 'graphPlay').isEnabled()
    assert 'rozłączny' in dialog.findChild(QLabel, 'graphSummary').text()
    edges = dialog.findChild(QTableWidget, 'graphEdges')
    assert any('Brak cech' in edges.item(2, col).text() for col in range(edges.columnCount()))
    assert 'most' in edges.item(0, edges.columnCount() - 1).text().lower()
    dialog.close()


def test_missing_adjacent_edge_compares_active_result_with_explicit_provenance(qtbot):
    from PyQt6.QtWidgets import QComboBox
    from stmviewer.registration import register_series
    from stmviewer.series import open_frame_series
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])
    active = register_series(frames)
    dialog = GraphComparisonDialog(frames, parent, trial=candidate(frames, chain=False), registration=active)
    qtbot.addWidget(dialog)
    dialog.show()
    variants = dialog.findChild(QComboBox, 'graphVariant')
    assert [variants.itemData(i) for i in range(variants.count())] == ['graph', 'active']
    assert active.method in variants.itemText(1) and active.revision[:8] in variants.itemText(1)
    dialog.close()


# Native LoFTR is the replaceable external boundary; loading, measurement,
# caching, the solver and Qt job lifecycle remain real in these tests.
from test_deep_registration import local_model as local_model  # noqa: E402
import pytest  # noqa: E402


@pytest.mark.parametrize('outcome', ['cancel', 'error', 'close'])
def test_new_computation_keeps_previous_candidate_until_success(qtbot, local_model, monkeypatch, outcome):  # noqa: F811 — pytest fixture injection
    from dataclasses import replace
    from threading import Event
    import kornia.feature
    from PyQt6.QtWidgets import QComboBox, QDialog
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.graph_registration import register_graph
    from stmviewer.series import open_frame_series
    from stmviewer.ui.graph_controls import GraphControls
    parent = QWidget()
    qtbot.addWidget(parent)
    originals = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])
    frames = tuple(replace(originals[i % 3], source_frame_index=i) for i in range(6))
    options = DeepMatcherOptions(local_model, 'cpu')
    previous = register_graph(frames, deep_options=options)
    controls = GraphControls(parent)
    controls.restore(previous)
    controls.open_graph(frames, None, options)
    dialog = parent.findChild(QDialog, 'graphComparison')
    assert '12 par' in dialog.findChild(QLabel, 'graphPairCount').text()
    dialog.findChild(QComboBox, 'graphWindow').setCurrentIndex(1)
    assert '15 par' in dialog.findChild(QLabel, 'graphPairCount').text()
    entered, release = Event(), Event()
    forward = kornia.feature.LoFTR.forward
    def controlled(self, images):
        entered.set()
        assert release.wait(5)
        if outcome == 'error':
            raise MemoryError('Controlled memory failure')
        return forward(self, images)
    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', controlled)
    try:
        dialog.findChild(QPushButton, 'runGraph').click()
        qtbot.waitUntil(entered.is_set, timeout=10000)
        assert controls.busy and controls.trial is previous
        assert not dialog.findChild(QComboBox, 'graphWindow').isEnabled()
        if outcome == 'cancel':
            dialog.findChild(QPushButton, 'cancelGraph').click()
        elif outcome == 'close':
            dialog.close()
        release.set()
        qtbot.waitUntil(lambda: not controls.busy, timeout=10000)
        assert controls.trial is previous
        if outcome != 'close':
            assert 'Poprzedni kandydat' in dialog.findChild(QLabel, 'graphMessage').text()
            dialog.close()
    finally:
        release.set()


def test_closing_graph_also_closes_idle_edge_inspection(qtbot):
    from PyQt6.QtWidgets import QDialog
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(24).reshape(4, 6), i) for i in range(3))
    dialog = GraphComparisonDialog(frames, parent, trial=candidate(frames))
    dialog.show()
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    assert pair.isVisible()
    with qtbot.waitSignal(dialog.destroyed):
        dialog.close()


@pytest.mark.parametrize('had_preview', [False, True])
def test_unavailable_scipy_keeps_graph_diagnostics_without_stale_preview(qtbot, monkeypatch, had_preview):
    import builtins
    from PyQt6.QtWidgets import QDialog
    from stmviewer.ui.graph_dialog import GraphComparisonDialog
    from stmviewer.ui.image_preview import ImagePreview
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(24).reshape(4, 6), i) for i in range(3))
    saved = candidate(frames)
    dialog = None
    if had_preview:
        dialog = GraphComparisonDialog(frames, parent, trial=saved)
        dialog.show()
        assert not dialog.findChild(ImagePreview, 'graphPreview').findChild(QLabel).isVisible()
    original_import = builtins.__import__
    def without_scipy(name, *args, **kwargs):
        if name == 'scipy.ndimage':
            raise ImportError('SciPy unavailable for preview')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_scipy)
    if dialog is None:
        dialog = GraphComparisonDialog(frames, parent, trial=saved)
        dialog.show()
    else:
        dialog.findChild(QSpinBox, 'graphFrame').setValue(2)
    assert dialog.trial is saved
    assert 'SciPy unavailable' in dialog.findChild(QLabel, 'graphMovieStatus').text()
    assert dialog.findChild(ImagePreview, 'graphPreview').findChild(QLabel).isVisible()
    assert not dialog.findChild(QPushButton, 'graphPlay').isEnabled()
    assert 'Graf spójny' in dialog.findChild(QLabel, 'graphSummary').text()
    dialog.findChild(QPushButton, 'inspectGraphPair').click()
    pair = dialog.findChild(QDialog, 'pairComparison')
    assert 'ΔX: 1 px' in pair.findChild(QLabel, 'pairResult').text()
    assert 'SciPy unavailable' in pair.findChild(QLabel, 'pairOverlap').text()
    assert pair.findChild(ImagePreview).findChild(QLabel).isVisible()
    monkeypatch.setattr(builtins, '__import__', original_import)
    dialog.findChild(QSpinBox, 'graphFrame').setValue(3)
    assert dialog.findChild(QPushButton, 'graphPlay').isEnabled()
    assert not dialog.findChild(ImagePreview, 'graphPreview').findChild(QLabel).isVisible()
    with qtbot.waitSignal(dialog.destroyed):
        dialog.close()
