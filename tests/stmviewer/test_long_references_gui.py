"""Explicit far-reference plans and their effect through visible graph controls."""
import numpy as np
from PyQt6.QtWidgets import QLineEdit, QLabel, QPushButton, QSpinBox, QTableWidget, QWidget

from stmviewer.ui.graph_dialog import GraphComparisonDialog
from test_graph_dialog import candidate
from test_pair_comparison import frame


def test_reference_plan_lists_only_new_pairs_with_source_numbers(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(120).reshape(10, 12), i + 2) for i in range(8))
    dialog = GraphComparisonDialog(frames, parent, trial=candidate(frames))
    qtbot.addWidget(dialog)
    dialog.show()
    references = dialog.findChild(QLineEdit, 'longReferences')
    assert references is not None
    references.setText('8, 1, 1')
    dialog.findChild(QSpinBox, 'longTargetStart').setValue(4)
    dialog.findChild(QSpinBox, 'longTargetEnd').setValue(8)
    pairs = dialog.findChild(QTableWidget, 'longPairs')
    assert [pairs.item(row, 0).text() for row in range(pairs.rowCount())] == [
        '1 → 5', '1 → 6', '1 → 7', '1 → 8', '4 → 8']
    assert 'MPP 3' in pairs.item(0, 1).text()
    assert 'MPP 7' in pairs.item(0, 2).text()
    assert '5 nowych par' in dialog.findChild(QLabel, 'longPlanSummary').text()
    assert not dialog.findChild(QPushButton, 'runLongReferences').isEnabled()
    assert 'wag' in dialog.findChild(QLabel, 'longPlanReason').text().lower()
    references.setText('9')
    assert pairs.rowCount() == 0
    assert not dialog.findChild(QPushButton, 'runLongReferences').isEnabled()
    assert '8' in dialog.findChild(QLabel, 'longPlanReason').text()
    dialog.close()


def test_extended_result_compares_same_solver_and_never_applies_the_baseline(qtbot):
    from PyQt6.QtWidgets import QComboBox
    from stmviewer.graph_types import GraphEdge
    from stmviewer.long_references import solve_extended_graph
    from stmviewer.ui.image_preview import ImagePreview
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(120).reshape(10, 12), i + 2) for i in range(6))
    base = candidate(frames)
    trial = solve_extended_graph(base, (GraphEdge(0, 5, (9., -5.), 'ok'),),
                                 references=(0,), target_start=5, target_end=5,
                                 measurement_config=base.config)
    dialog = GraphComparisonDialog(frames, parent, trial=trial)
    qtbot.addWidget(dialog)
    dialog.show()
    variants = dialog.findChild(QComboBox, 'graphVariant')
    baseline_index = variants.findData('base:graph')
    assert baseline_index >= 0
    dialog.findChild(QSpinBox, 'graphFrame').setValue(6)
    delta = dialog.findChild(QLabel, 'graphReferenceDelta').text()
    assert f'X {trial.positions[5][0] - base.positions[5][0]:+.3f}' in delta
    assert 'LS' in delta
    preview = dialog.findChild(ImagePreview, 'graphPreview')
    preview.zoom_in()
    navigation = preview.navigation_states()
    variants.setCurrentIndex(baseline_index)
    assert preview.navigation_states() == navigation
    assert not dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    assert 'podgląd bazy' in dialog.findChild(QLabel, 'graphApplicationInfo').text().lower()
    selection = dialog.findChild(QComboBox, 'graphApplicationVariant')
    selection.setCurrentIndex(selection.findData('graph'))
    assert variants.currentData() == 'graph'
    assert dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    edges = dialog.findChild(QTableWidget, 'graphEdges')
    origin = next(i for i in range(edges.columnCount()) if edges.horizontalHeaderItem(i).text() == 'Pochodzenie')
    assert sum(edges.item(row, origin).text() == 'Dalsze odniesienie' for row in range(edges.rowCount())) == 1
    assert dialog.findChild(QLineEdit, 'longReferences').text() == '1'
    assert dialog.findChild(QSpinBox, 'longTargetStart').value() == 6
    dialog.close()


from test_deep_registration import local_model as local_model  # noqa: E402
import pytest  # noqa: E402


@pytest.mark.parametrize('huber', [False, True])
def test_explicit_run_retains_baseline_and_selects_the_same_solver(qtbot, local_model, huber):  # noqa: F811
    from dataclasses import replace
    from PyQt6.QtWidgets import QComboBox
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.graph_registration import register_graph
    from stmviewer.registration import register_series
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    from stmviewer.series import open_frame_series
    from test_deep_registration import FIXTURE
    parent = QWidget()
    qtbot.addWidget(parent)
    originals = open_frame_series([FIXTURE])
    frames = tuple(replace(originals[i % 3], source_frame_index=i + 2) for i in range(6))
    options = DeepMatcherOptions(local_model, 'cpu')
    base = register_graph(frames, deep_options=options)
    if huber:
        robust = solve_robust_graph(base, RobustConfig(threshold_px=2.5))
        assert robust.positions is not None
        base = replace(base, robust_trials=(robust,))
    active = register_series(frames)
    original_pixels = tuple(f.image.data.copy() for f in active.frames)
    dialog = GraphComparisonDialog(frames, parent, trial=base, registration=active, deep_options=options)
    qtbot.addWidget(dialog)
    dialog.show()
    requested = []
    dialog.movie_apply_requested.connect(lambda *args: requested.append(args))
    if huber:
        solver = dialog.findChild(QComboBox, 'longBaseSolver')
        solver.setCurrentIndex(solver.findData(f'huber:{robust.revision}'))
    dialog.findChild(QLineEdit, 'longReferences').setText('1')
    dialog.findChild(QSpinBox, 'longTargetStart').setValue(5)
    dialog.findChild(QComboBox, 'graphWindow').setCurrentIndex(1)
    run = dialog.findChild(QPushButton, 'runLongReferences')
    assert run.isEnabled()
    run.click()
    assert dialog.busy
    qtbot.waitUntil(lambda: not dialog.busy, timeout=10000)
    extended = dialog.trial
    assert extended is not base and extended.extension.base is base
    assert extended.extension.references == (0,)
    assert extended.extension.target_start == 4
    assert extended.measured_pairs == 2
    assert extended.config.window == base.config.window == 3
    assert requested == []
    for before, after in zip(original_pixels, active.frames):
        np.testing.assert_array_equal(before, after.image.data)
    selection = dialog.findChild(QComboBox, 'graphApplicationVariant')
    expected = f'huber:{extended.robust_trials[0].revision}' if huber else 'graph'
    assert selection.currentData() == expected
    if huber:
        assert extended.robust_trials[0].config == robust.config
        assert 'Huber' in dialog.findChild(QLabel, 'graphReferenceDelta').text()
    dialog.findChild(QPushButton, 'applyGraphMovie').click()
    assert requested == [(extended, extended.robust_trials[0].revision if huber else None)]
    dialog.close()


def test_restored_incomplete_matching_huber_stays_selected_without_ls_substitution(qtbot):
    from dataclasses import replace
    from PyQt6.QtWidgets import QComboBox
    from stmviewer.graph_types import GraphEdge
    from stmviewer.long_references import solve_extended_graph
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(120).reshape(10, 12), i + 2) for i in range(6))
    base = candidate(frames)
    robust = solve_robust_graph(base, RobustConfig(threshold_px=.1, max_iterations=1))
    assert robust.positions is not None
    base = replace(base, robust_trials=(robust,))
    trial = solve_extended_graph(base, (GraphEdge(0, 5, (9., -5.), 'ok'),),
                                 references=(0,), target_start=5, target_end=5,
                                 measurement_config=base.config, robust_revision=robust.revision)
    assert trial.robust_trials[0].positions is None
    dialog = GraphComparisonDialog(frames, parent, trial=trial)
    qtbot.addWidget(dialog)
    dialog.show()
    selection = dialog.findChild(QComboBox, 'graphApplicationVariant')
    assert selection.currentData() == f'huber:{trial.robust_trials[0].revision}'
    assert not dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    baseline = dialog.findChild(QComboBox, 'longBaseSolver')
    assert baseline.currentData() == f'huber:{robust.revision}'
    movie = dialog.findChild(QComboBox, 'graphVariant')
    movie.setCurrentIndex(movie.findData(f'base:huber:{robust.revision}'))
    assert 'nie ma dwóch kompletnych' in dialog.findChild(QLabel, 'graphReferenceDelta').text()
    assert not dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    dialog.close()


@pytest.mark.parametrize('outcome', ['cancel', 'error', 'close'])
def test_extension_cancel_or_error_keeps_candidate_movie_and_global_locks(
        qtbot, local_model, monkeypatch, tmp_path, outcome):  # noqa: F811
    from dataclasses import replace
    from threading import Event
    import kornia.feature
    from PyQt6.QtWidgets import QDialog, QFileDialog, QTabWidget
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.graph_registration import register_graph
    from stmviewer.registration import register_series
    from stmviewer.series import open_frame_series
    from stmviewer.session_archive import save_session
    from stmviewer.session_state import SessionState, SessionViewState
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_deep_registration import FIXTURE
    from test_manual_movie_gui import shifts
    from test_registration_gui import image
    originals = open_frame_series([FIXTURE])
    frames = tuple(replace(originals[i % 3], source_frame_index=i) for i in range(6))
    options = DeepMatcherOptions(local_model, 'cpu')
    base = register_graph(frames, deep_options=options)
    active = register_series(frames)
    path = tmp_path / 'before-extension.stmsession'
    save_session(path, SessionState(frames, active, SessionViewState(index=1, view='aligned'), base))
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'openSession').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openSession').isEnabled)
    window.findChild(QPushButton, 'openGraph').click()
    dialog = window.findChild(QDialog, 'graphComparison')
    before_trial, before_shifts, before_image = dialog.trial, shifts(window), image(window)
    dialog.findChild(QTabWidget).setCurrentIndex(2)
    dialog.findChild(QLineEdit, 'longReferences').setText('1')
    dialog.findChild(QSpinBox, 'longTargetStart').setValue(5)
    entered, release = Event(), Event()
    forward = kornia.feature.LoFTR.forward

    def controlled(self, images):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Controlled matcher gate timed out')
        if outcome == 'error':
            raise MemoryError('Controlled far-reference failure')
        return forward(self, images)

    try:
        monkeypatch.setattr(kornia.feature.LoFTR, 'forward', controlled)
        dialog.findChild(QPushButton, 'runLongReferences').click()
        qtbot.waitUntil(entered.is_set, timeout=10000)
        assert dialog.busy and dialog.trial is before_trial
        for name in ('openFrames', 'openSession', 'saveSession', 'deleteFrame', 'registerFrames',
                     'saveOriginalMpp', 'saveAvi', 'playPause', 'comparePair'):
            assert not window.findChild(QPushButton, name).isEnabled(), name
        for name in ('runGraph', 'runRobustGraph', 'runLongReferences', 'applyGraphMovie'):
            assert not dialog.findChild(QPushButton, name).isEnabled(), name
        if outcome == 'cancel':
            dialog.findChild(QPushButton, 'cancelLongReferences').click()
        elif outcome == 'close':
            dialog.close()
            assert dialog.isVisible()
        release.set()
        qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled, timeout=10000)
        assert shifts(window) == before_shifts
        assert image(window) == before_image
        if outcome != 'close':
            assert dialog.trial is before_trial
            assert 'Poprzedni kandydat' in dialog.findChild(QLabel, 'longReferenceMessage').text()
            dialog.close()
        else:
            window.findChild(QPushButton, 'openGraph').click()
            reopened = window.findChild(QDialog, 'graphComparison')
            assert reopened.trial is before_trial
            reopened.close()
    finally:
        release.set()
