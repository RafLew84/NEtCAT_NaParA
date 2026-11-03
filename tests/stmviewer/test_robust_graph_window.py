"""Saved graph → Huber variants → portable session, without a matcher or active-film changes."""
from PyQt6.QtWidgets import QDialog, QFileDialog, QPushButton

from stmviewer.session_archive import save_session
from stmviewer.session_state import SessionState
from stmviewer.series import open_frame_series
from stmviewer.ui.main_window import STMViewerMainWindow
from test_deep_registration import FIXTURE
from test_graph_session import candidate


def test_saved_graph_offers_huber_without_local_weights(qtbot, monkeypatch, tmp_path):
    frames = open_frame_series([FIXTURE])
    path = tmp_path / 'graph-without-model.stmsession'
    save_session(path, SessionState(frames, graph=candidate(frames)))
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    opening = window.findChild(QPushButton, 'openSession')
    opening.click()
    qtbot.waitUntil(opening.isEnabled)
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    assert not graph.findChild(QPushButton, 'runGraph').isEnabled()
    run = graph.findChild(QPushButton, 'runRobustGraph')
    assert run is not None
    assert run.isEnabled()


def open_session_window(qtbot, monkeypatch, path):
    from PyQt6.QtWidgets import QLabel, QWidget

    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(path), ''))
    opening = window.findChild(QPushButton, 'openSession')
    opening.click()
    qtbot.waitUntil(opening.isEnabled, timeout=5000)
    assert 'Otwarto sesję' in window.findChild(QLabel, 'sessionInfo').text()
    return window


def saved_manual_movie(tmp_path):
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.session_state import SessionViewState
    from test_manual_movie import cpu_result, corrected_trial

    base = cpu_result()
    active = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    frames = tuple(item.original for item in active.frames)
    graph = candidate(frames)
    path = tmp_path / 'manual-and-ls.stmsession'
    save_session(path, SessionState(frames, active, SessionViewState(view='aligned'), graph))
    return path, active, graph


def test_two_huber_variants_resume_in_gui_and_export_preserves_active_manual_movie(
        qtbot, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QLabel, QSpinBox
    from stmviewer.session_archive import load_session
    from test_manual_movie_gui import assert_shifts
    from test_registration_gui import image

    source, active, original_graph = saved_manual_movie(tmp_path)
    window = open_session_window(qtbot, monkeypatch, source)
    expected_shifts = [item.shift_xy for item in active.frames]
    assert_shifts(window, expected_shifts)
    raster = image(window)
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    run = graph.findChild(QPushButton, 'runRobustGraph')
    saved_variants = graph.findChild(QComboBox, 'robustVariant')
    for count, threshold in enumerate((2., 4.), start=1):
        graph.findChild(QDoubleSpinBox, 'robustThreshold').setValue(threshold)
        run.click()
        qtbot.waitUntil(lambda: saved_variants.count() == count and run.isEnabled(), timeout=5000)
        assert 'converged' in graph.findChild(QLabel, 'robustSummary').text()
    revisions = [saved_variants.itemData(i) for i in range(2)]
    graph.findChild(QSpinBox, 'graphFrame').setValue(2)
    assert_shifts(window, expected_shifts)
    assert image(window) == raster
    with qtbot.waitSignal(graph.destroyed):
        graph.close()
    session = tmp_path / 'with-two-huber-variants.stmsession'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(session), ''))
    saving = window.findChild(QPushButton, 'saveSession')
    saving.click()
    qtbot.waitUntil(saving.isEnabled, timeout=5000)
    state = load_session(session)
    assert [variant.revision for variant in state.graph.robust_trials] == revisions
    assert [variant.config.threshold_px for variant in state.graph.robust_trials] == [2., 4.]
    assert state.graph.revision == original_graph.revision
    assert state.graph.edges == original_graph.edges
    assert state.graph.positions == original_graph.positions
    assert state.registration.revision == active.revision
    assert state.registration.corrections == active.corrections
    for expected, actual in zip(active.frames, state.registration.frames, strict=True):
        assert actual.shift_xy == expected.shift_xy
        assert actual.image.data.tobytes() == expected.image.data.tobytes()
    window.close()
    window = open_session_window(qtbot, monkeypatch, session)
    assert_shifts(window, expected_shifts)
    assert image(window) == raster
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    saved_variants = graph.findChild(QComboBox, 'robustVariant')
    assert [saved_variants.itemData(i) for i in range(saved_variants.count())] == revisions
    assert graph.findChild(QPushButton, 'runRobustGraph').isEnabled()
    movies = graph.findChild(QComboBox, 'graphVariant')
    for revision in revisions:
        index = movies.findData(f'huber:{revision}')
        assert index >= 0
        movies.setCurrentIndex(index)
        assert graph.findChild(QPushButton, 'graphPlay').isEnabled()
    with qtbot.waitSignal(graph.destroyed):
        graph.close()
    exported = tmp_path / 'still-manual.mpp'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw:
                        (str(exported), 'MPP aligned (*.mpp *.MPP)'))
    saving = window.findChild(QPushButton, 'saveOriginalMpp')
    saving.click()
    qtbot.waitUntil(saving.isEnabled, timeout=5000)
    for expected, actual in zip(active.frames, open_frame_series([exported]), strict=True):
        assert actual.alignment.shift_xy == expected.shift_xy
        assert actual.data.tobytes() == expected.image.data.tobytes()
        assert actual.alignment.manual_movie.revision == active.revision
        assert actual.alignment.manual_movie.corrections == active.corrections


def test_huber_job_locks_main_actions_and_cancel_preserves_manual_movie_and_prior_variant(
        qtbot, monkeypatch, tmp_path):
    from threading import Event
    from scipy.sparse import linalg
    from PyQt6.QtWidgets import QComboBox, QLabel, QSpinBox
    from test_manual_movie_gui import assert_shifts
    from test_registration_gui import image

    source, active, original_graph = saved_manual_movie(tmp_path)
    window = open_session_window(qtbot, monkeypatch, source)
    window.findChild(QPushButton, 'openGraph').click()
    graph = window.findChild(QDialog, 'graphComparison')
    run = graph.findChild(QPushButton, 'runRobustGraph')
    variants = graph.findChild(QComboBox, 'robustVariant')
    run.click()
    qtbot.waitUntil(lambda: variants.count() == 1 and run.isEnabled(), timeout=5000)
    revision = variants.currentData()
    entered, release = Event(), Event()
    factorize = linalg.splu

    def delayed_factorize(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Timed out waiting for Huber cancellation test')
        return factorize(*args, **kwargs)

    monkeypatch.setattr(linalg, 'splu', delayed_factorize)
    try:
        run.click()
        qtbot.waitUntil(entered.is_set)
        for name in ('openFrames', 'openSession', 'saveSession', 'deleteFrame', 'registerFrames',
                     'saveOriginalMpp', 'saveAvi', 'playPause', 'comparePair', 'openGraph'):
            assert not window.findChild(QPushButton, name).isEnabled(), name
        window.findChild(QSpinBox, 'frameNumber').setValue(2)
        window.findChild(QPushButton, 'zoomIn').click()
        raster = image(window)
        info = window.findChild(QLabel, 'registrationInfo').text()
        graph.findChild(QPushButton, 'cancelRobustGraph').click()
        release.set()
        qtbot.waitUntil(lambda: run.isEnabled() and window.findChild(QPushButton, 'openGraph').isEnabled())
        assert variants.count() == 1 and variants.currentData() == revision
        assert 'Anulowano' in graph.findChild(QLabel, 'robustMessage').text()
        assert window.findChild(QLabel, 'registrationInfo').text() == info
        assert image(window) == raster
        assert_shifts(window, [item.shift_xy for item in active.frames])
    finally:
        release.set()
