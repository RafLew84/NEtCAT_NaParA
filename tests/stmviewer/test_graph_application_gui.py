"""Explicit graph publication and predecessor restoration through visible actions."""
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QWidget

from stmviewer.ui.graph_dialog import GraphComparisonDialog
from test_graph_dialog import candidate
from test_pair_comparison import frame
import numpy as np
import pytest

from test_deep_registration import local_model as local_model


def test_disconnected_candidate_has_visible_application_refusal(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(24).reshape(4, 6), index) for index in range(3))
    dialog = GraphComparisonDialog(frames, parent, trial=candidate(frames, disconnected=True))
    qtbot.addWidget(dialog)
    dialog.show()
    apply = dialog.findChild(QPushButton, 'applyGraphMovie')
    assert apply is not None
    assert not apply.isEnabled()
    assert 'rozłącz' in dialog.findChild(QLabel, 'graphApplicationInfo').text().lower()
    assert not dialog.findChild(QPushButton, 'restoreGraphMovie').isEnabled()
    dialog.close()


def open_candidate_session(qtbot, monkeypatch, tmp_path, *, base=None):
    from PyQt6.QtWidgets import QFileDialog
    from stmviewer.graph_provenance import graph_sources
    from stmviewer.graph_registration import solve_graph
    from stmviewer.graph_types import GraphConfig, GraphEdge
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.session_archive import save_session
    from stmviewer.session_state import SessionState, SessionViewState
    from stmviewer.ui.main_window import STMViewerMainWindow
    from test_manual_movie import cpu_result, corrected_trial

    base = cpu_result() if base is None else base
    active = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    frames = tuple(item.original for item in active.frames)
    graph = solve_graph(graph_sources(frames), (
        GraphEdge(0, 1, (3., 0.), 'ok'), GraphEdge(0, 2, (3., 3.), 'ok'),
        GraphEdge(1, 2, (0., 0.), 'ok'),
    ), GraphConfig(3, '/missing/outdoor.ckpt', 'a' * 64, 'cpu', 'CPU', (), (), 'test'))
    path = tmp_path / 'candidate.stmsession'
    save_session(path, SessionState(frames, active, SessionViewState(index=1, view='aligned', gamma=1.7), graph))
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    window.findChild(QPushButton, 'openSession').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openSession').isEnabled)
    assert 'Otwarto sesję' in window.findChild(QLabel, 'sessionInfo').text()
    window.findChild(QPushButton, 'openGraph').click()
    return window, window.findChild(QDialog, 'graphComparison')


def test_apply_graph_then_manual_edit_then_restore_saved_corrected_movie(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox
    from stmviewer.ui.image_preview import ImagePreview
    from test_manual_movie_gui import assert_shifts

    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path)
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'zoomIn').click()
    info = graph.findChild(QLabel, 'graphApplicationInfo').text()
    for value in ('Deep Matcher', 'outdoor.ckpt', 'Okno: 3', 'equal-ls', 'Źródła',
                  'Ręczne korekty do zastąpienia: 1'):
        assert value in info
    graph.findChild(QPushButton, 'applyGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert window.findChild(QSpinBox, 'frameNumber').value() == 2
    assert window.findChild(QDoubleSpinBox, 'previewGamma').value() == 1.7
    assert window.findChild(QComboBox, 'frameView').currentText() == 'aligned'
    assert window.findChild(QPushButton, 'playPause').text() == 'Play'
    assert window.findChild(ImagePreview, 'imagePreview').navigation_states()['aligned'].zoom == 1
    assert_shifts(window, [(0, 0), (3, 1), (3, 2)])
    variants = graph.findChild(QComboBox, 'graphVariant')
    assert 'predecessor' in [variants.itemData(i) for i in range(variants.count())]
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    info = pair.findChild(QLabel, 'manualMovieInfo').text()
    assert 'Baza G' in info and 'surowy pomiar' in info
    pair.findChild(QPushButton, 'manualMovieStart').click()
    assert 'ΔX: 3 px · ΔY: 1 px' in pair.findChild(QLabel, 'manualPairInfo').text()
    pair.findChild(QPushButton, 'manualPairXPlus').click()
    pair.findChild(QPushButton, 'manualPairApply').click()
    assert_shifts(window, [(0, 0), (3, 1), (3, 2)])
    pair.findChild(QPushButton, 'manualMovieApply').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert_shifts(window, [(0, 0), (4, 1), (4, 2)])
    pair.close()
    graph.findChild(QPushButton, 'restoreGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    assert pair.findChild(QPushButton, 'manualMovieRemove').isEnabled()
    pair.close()
    graph.close()


def test_failed_huber_selection_never_silently_applies_previous_ls(qtbot):
    from PyQt6.QtWidgets import QComboBox, QSpinBox
    from stmviewer.graph_registration import solve_graph
    from stmviewer.graph_types import GraphEdge

    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(120).reshape(10, 12), index) for index in range(4))
    base = candidate(frames)
    graph = solve_graph(base.sources, tuple(
        GraphEdge(edge.i, edge.j, (12., 16.) if (edge.i, edge.j) == (0, 3) else (0., 0.), 'ok')
        for edge in base.edges), base.config)
    dialog = GraphComparisonDialog(frames, parent, trial=graph)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.findChild(QSpinBox, 'robustMaxIterations').setValue(1)
    dialog.findChild(QPushButton, 'runRobustGraph').click()
    qtbot.waitUntil(lambda: not dialog.busy)
    failed_revision = dialog.findChild(QComboBox, 'robustVariant').currentData()
    assert dialog.findChild(QComboBox, 'graphApplicationVariant').currentData() == f'huber:{failed_revision}'
    assert not dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    assert 'kompletn' in dialog.findChild(QLabel, 'graphApplicationInfo').text()
    dialog.close()


def test_selected_huber_and_predecessor_survive_session_and_restore_without_model(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QComboBox, QSpinBox
    from test_manual_movie_gui import assert_shifts
    from test_session_window import reopen_session

    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path)
    graph.findChild(QPushButton, 'runRobustGraph').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    application = graph.findChild(QComboBox, 'graphApplicationVariant')
    assert application.currentData().startswith('huber:')
    assert 'block-huber' in graph.findChild(QLabel, 'graphApplicationInfo').text()
    graph.findChild(QPushButton, 'applyGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert 'block-huber' in window.findChild(QLabel, 'registrationInfo').text()
    with qtbot.waitSignal(graph.destroyed):
        graph.close()
    window = reopen_session(qtbot, window, monkeypatch, tmp_path / 'applied-huber.stmsession')
    assert 'block-huber' in window.findChild(QLabel, 'registrationInfo').text()
    assert_shifts(window, [(0, 0), (3, 1), (3, 2)])
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert not graph.findChild(QPushButton, 'runGraph').isEnabled()
    assert graph.findChild(QPushButton, 'restoreGraphMovie').isEnabled()
    graph.findChild(QPushButton, 'restoreGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    window.findChild(QPushButton, 'comparePair').click()
    pair = window.findChild(QDialog, 'pairComparison')
    assert pair.findChild(QPushButton, 'manualMovieRemove').isEnabled()
    pair.close()
    graph.close()


def test_deleting_frame_keeps_ready_movie_but_explains_application_and_restore_refusal(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QSpinBox
    from test_manual_movie_gui import assert_shifts

    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path)
    graph.findChild(QPushButton, 'applyGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    with qtbot.waitSignal(graph.destroyed):
        graph.close()
    window.findChild(QSpinBox, 'frameNumber').setValue(1)
    window.findChild(QPushButton, 'deleteFrame').click()
    assert_shifts(window, [(3, 1), (3, 2)])
    assert window.findChild(QPushButton, 'saveOriginalMpp').isEnabled()
    assert window.findChild(QPushButton, 'saveAvi').isEnabled()
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert not graph.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    assert not graph.findChild(QPushButton, 'restoreGraphMovie').isEnabled()
    assert 'Po usunięciu klatki' in graph.findChild(QLabel, 'graphApplicationInfo').text()
    graph.close()


@pytest.mark.parametrize('action', ['applyGraphMovie', 'restoreGraphMovie'])
@pytest.mark.parametrize('outcome', ['cancel', 'error', 'close'])
def test_application_and_restore_are_cancellable_atomic_and_lock_mutations(
        qtbot, monkeypatch, tmp_path, action, outcome):
    from threading import Event
    from scipy import ndimage
    from PyQt6.QtWidgets import QMessageBox, QProgressBar
    from test_registration_gui import image
    from test_manual_movie_gui import shifts

    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path)
    if action == 'restoreGraphMovie':
        graph.findChild(QPushButton, 'applyGraphMovie').click()
        qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    before_shifts = shifts(window)
    before_image = image(window)
    entered, release = Event(), Event()
    transform = ndimage.affine_transform

    def controlled_interpolation(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Interpolation gate timed out')
        if outcome == 'error':
            raise MemoryError('Controlled graph allocation failure')
        return transform(*args, **kwargs)

    try:
        with monkeypatch.context() as external:
            external.setattr(ndimage, 'affine_transform', controlled_interpolation)
            graph.findChild(QPushButton, action).click()
            qtbot.waitUntil(entered.is_set)
            assert graph.findChild(QProgressBar, 'graphApplicationProgress').isVisible()
            for name in ('openFrames', 'openSession', 'saveSession', 'deleteFrame', 'registerFrames',
                         'saveOriginalMpp', 'saveAvi', 'playPause', 'comparePair'):
                assert not window.findChild(QPushButton, name).isEnabled(), name
            for name in ('applyGraphMovie', 'restoreGraphMovie', 'runGraph', 'runRobustGraph'):
                assert not graph.findChild(QPushButton, name).isEnabled(), name
            if outcome == 'cancel':
                graph.findChild(QPushButton, 'cancelGraphApplication').click()
                assert not graph.findChild(QPushButton, 'cancelGraphApplication').isEnabled()
            elif outcome == 'close':
                graph.close()
                assert graph.isVisible()
            release.set()
            qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    finally:
        release.set()
    if outcome == 'error':
        error = window.findChild(QMessageBox)
        assert error is not None and 'Controlled graph allocation failure' in error.text()
        error.accept()
    assert image(window) == before_image
    assert shifts(window) == before_shifts
    if outcome != 'close':
        assert 'Poprzedni film i korekty pozostają' in graph.findChild(QLabel, 'graphApplicationMessage').text()
        assert graph.findChild(QPushButton, action).isEnabled()
        graph.close()


def test_corrected_deep_chain_can_be_restored_in_gui_after_weights_are_removed(
        qtbot, monkeypatch, tmp_path, local_model):  # noqa: F811 — pytest fixture injection
    import kornia.feature
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.registration import register_series
    from stmviewer.series import open_frame_series
    from test_deep_registration import FIXTURE
    from test_manual_movie_gui import assert_shifts

    base = register_series(open_frame_series([FIXTURE]), method='deep_matcher_translation',
                           deep_options=DeepMatcherOptions(local_model, 'cpu'))
    local_model.unlink()

    def no_model(*args, **kwargs):
        raise AssertionError('Applying and restoring saved movies must not rerun Deep')

    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', no_model)
    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path, base=base)
    assert_shifts(window, [(0, 0), (3, -1), (5, -2)])
    graph.findChild(QPushButton, 'applyGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert_shifts(window, [(0, 0), (3, 1), (3, 2)])
    assert 'Deep Matcher' in graph.findChild(QLabel, 'graphPredecessorInfo').text()
    assert 'Ręczne korekty: 1' in graph.findChild(QLabel, 'graphPredecessorInfo').text()
    graph.findChild(QPushButton, 'restoreGraphMovie').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    assert_shifts(window, [(0, 0), (3, -1), (5, -2)])
    assert 'Deep Matcher' in window.findChild(QLabel, 'registrationInfo').text()
    graph.close()


def test_application_selection_shows_matching_movie_without_changing_active_film(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QComboBox
    from test_manual_movie_gui import assert_shifts

    window, graph = open_candidate_session(qtbot, monkeypatch, tmp_path)
    graph.findChild(QPushButton, 'runRobustGraph').click()
    qtbot.waitUntil(window.findChild(QPushButton, 'openGraph').isEnabled)
    application = graph.findChild(QComboBox, 'graphApplicationVariant')
    movie = graph.findChild(QComboBox, 'graphVariant')
    huber = application.currentData()
    assert huber.startswith('huber:')
    movie.setCurrentIndex(movie.findData('graph'))
    application.setCurrentIndex(application.findData(huber))
    assert movie.currentData() == huber
    movie.setCurrentIndex(movie.findData('active'))
    assert application.currentData() == huber
    assert_shifts(window, [(0, 0), (3, -1), (0, 1)])
    graph.close()
