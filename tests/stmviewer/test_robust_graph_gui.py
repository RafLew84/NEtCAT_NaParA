"""Saved graph measurements can produce and compare Huber variants without a model."""
import numpy as np
from PyQt6.QtWidgets import QDoubleSpinBox, QPushButton, QWidget

from stmviewer.ui.graph_dialog import GraphComparisonDialog
from test_graph_dialog import candidate
from test_pair_comparison import frame


def make_dialog(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(120).reshape(10, 12), i) for i in range(4))
    graph = candidate(frames)
    dialog = GraphComparisonDialog(frames, parent, trial=graph)
    qtbot.addWidget(dialog)
    dialog.show()
    return parent, dialog, graph


def test_saved_measurements_offer_huber_even_when_model_weights_are_absent(qtbot):
    parent, dialog, graph = make_dialog(qtbot)
    assert not dialog.findChild(QPushButton, 'runGraph').isEnabled()
    threshold = dialog.findChild(QDoubleSpinBox, 'robustThreshold')
    assert threshold is not None
    assert threshold.value() > 0
    assert dialog.findChild(QPushButton, 'runRobustGraph').isEnabled()
    threshold.setValue(1.5)
    assert dialog.trial is graph


def test_computing_new_thresholds_keeps_saved_variants_and_original_ls(qtbot):
    from PyQt6.QtWidgets import QComboBox, QLabel, QTableWidget
    from stmviewer.graph_registration import solve_graph
    from stmviewer.graph_types import GraphEdge
    from stmviewer.ui.image_preview import ImagePreview

    parent, dialog, base = make_dialog(qtbot)
    dialog.close()
    frames = tuple(frame(np.arange(120).reshape(10, 12), i) for i in range(4))
    edges = tuple(GraphEdge(e.i, e.j, (12., 16.) if (e.i, e.j) == (0, 3) else (0., 0.), 'ok')
                  for e in base.edges)
    graph = solve_graph(base.sources, edges, base.config)
    dialog = GraphComparisonDialog(frames, parent, trial=graph)
    qtbot.addWidget(dialog)
    dialog.show()
    preview = dialog.findChild(ImagePreview, 'graphPreview')
    preview.zoom_in()
    before = preview.navigation_states()
    run = dialog.findChild(QPushButton, 'runRobustGraph')
    run.click()
    qtbot.waitUntil(lambda: len(dialog.trial.robust_trials) == 1)
    first = dialog.trial.robust_trials[0]
    assert first.positions is not None
    assert dialog.trial.edges == graph.edges
    assert dialog.trial.positions == graph.positions
    movie = dialog.findChild(QComboBox, 'graphVariant')
    assert movie.currentData() == f'huber:{first.revision}'
    assert preview.navigation_states() == before
    assert 'Huber − LS' in dialog.findChild(QLabel, 'graphFrameSource').text()
    table = dialog.findChild(QTableWidget, 'graphEdges')
    headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
    assert 'Waga Hubera' in headers
    assert float(table.item(2, headers.index('Waga Hubera')).text()) < .12
    dialog.findChild(QDoubleSpinBox, 'robustThreshold').setValue(1.)
    assert dialog.trial.robust_trials == (first,)
    run.click()
    qtbot.waitUntil(lambda: len(dialog.trial.robust_trials) == 2)
    assert dialog.trial.robust_trials[0] == first
    second = dialog.trial.robust_trials[1]
    assert first.measurement_id == second.measurement_id
    assert second.config.threshold_px == 1.
    saved = dialog.findChild(QComboBox, 'robustVariant')
    assert saved.count() == 2
    saved.setCurrentIndex(0)
    assert movie.currentData() == f'huber:{first.revision}'
    movie.setCurrentIndex(movie.findData('graph'))
    assert preview.navigation_states() == before


def test_adding_a_wider_huber_canvas_preserves_visible_source_pixel_scale_and_anchor(qtbot):
    from dataclasses import replace
    from PyQt6.QtGui import QImage
    from PyQt6.QtWidgets import QComboBox
    from stmviewer.graph_registration import solve_graph
    from stmviewer.graph_types import GraphEdge
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.ui.graph_movie import GraphMovieWidget
    from stmviewer.ui.image_preview import ImagePreview

    values = np.ones((30, 40))
    values[14:18, 18:22] = 0
    frames = tuple(frame(values, i) for i in range(4))
    base = candidate(frames)
    shifts = [(-4., -5.), (-7., -9.), (7., -3.), (-9., -4.), (8., 10.), (-6., 9.)]
    edges = tuple(GraphEdge(e.i, e.j, shift, 'ok') for e, shift in zip(base.edges, shifts, strict=True))
    graph = solve_graph(base.sources, edges, base.config)
    robust = solve_robust_graph(graph)
    assert robust.positions is not None
    parent = QWidget()
    qtbot.addWidget(parent)
    movie = GraphMovieWidget(frames, parent)
    qtbot.addWidget(movie)
    movie.resize(850, 700)
    movie.set_graph(graph, None)
    movie.show()
    preview = movie.findChild(ImagePreview, 'graphPreview')
    preview.zoom_in()

    def dark_marker_bounds():
        image = preview.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        pixels = np.frombuffer(image.constBits().asstring(image.sizeInBytes()), np.uint8)
        rgb = pixels.reshape(image.height(), image.bytesPerLine() // 4, 4)[:, :image.width(), :3]
        rows, columns = np.nonzero((rgb < 5).all(axis=2))
        return np.array([columns.min(), rows.min(), columns.max(), rows.max()])

    before = dark_marker_bounds()
    movie.set_graph(replace(graph, robust_trials=(robust,)), None)
    np.testing.assert_allclose(dark_marker_bounds(), before, atol=1)
    movie.findChild(QComboBox, 'graphVariant').setCurrentIndex(2)
    np.testing.assert_allclose(dark_marker_bounds(), before, atol=1)


def test_iteration_limit_preserves_previous_film_and_shows_only_failure_diagnostics(qtbot):
    from PyQt6.QtWidgets import QComboBox, QLabel, QMessageBox, QSpinBox
    from stmviewer.graph_registration import solve_graph
    from stmviewer.graph_types import GraphEdge

    parent, original, base = make_dialog(qtbot)
    original.close()
    del original
    frames = tuple(frame(np.arange(120).reshape(10, 12), i) for i in range(4))
    edges = tuple(GraphEdge(e.i, e.j, (12., 16.) if (e.i, e.j) == (0, 3) else (0., 0.), 'ok')
                  for e in base.edges)
    graph = solve_graph(base.sources, edges, base.config)
    dialog = GraphComparisonDialog(frames, parent, trial=graph)
    qtbot.addWidget(dialog)
    dialog.show()
    run = dialog.findChild(QPushButton, 'runRobustGraph')
    run.click()
    qtbot.waitUntil(lambda: len(dialog.trial.robust_trials) == 1)
    first = dialog.trial.robust_trials[0]
    assert dialog.findChild(QMessageBox) is None
    limit = dialog.findChild(QSpinBox, 'robustMaxIterations')
    assert limit is not None
    assert limit.value() == 200
    limit.setValue(1)
    assert dialog.trial.robust_trials == (first,)
    run.click()
    qtbot.waitUntil(lambda: len(dialog.trial.robust_trials) == 2)
    failure = dialog.trial.robust_trials[1]
    assert failure.config.max_iterations == 1
    assert failure.status == 'iteration_limit'
    assert failure.positions is None
    assert failure.last_positions is not None
    assert dialog.trial.robust_trials[0] == first
    movie = dialog.findChild(QComboBox, 'graphVariant')
    assert movie.currentData() == f'huber:{first.revision}'
    assert movie.findData(f'huber:{failure.revision}') < 0
    assert 'tylko diagnostyka' in dialog.findChild(QLabel, 'robustSummary').text()
    assert dialog.findChild(QComboBox, 'robustVariant').currentData() == failure.revision
    assert dialog.trial.positions == graph.positions

    message = dialog.findChild(QMessageBox)
    assert message is not None and message.isVisible()
    assert message.windowTitle() == 'Niekompletny wynik Hubera'
    information = message.text() + message.informativeText()
    assert failure.reason in information
    for text in ('1/1', 'nie można zastosować', 'podgląd', 'LS', 'Limit iteracji'):
        assert text in information
    assert not dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()
    with qtbot.waitSignal(message.destroyed):
        message.button(QMessageBox.StandardButton.Ok).click()
    selection = dialog.findChild(QComboBox, 'graphApplicationVariant')
    selection.setCurrentIndex(selection.findData('graph'))
    assert dialog.findChild(QPushButton, 'applyGraphMovie').isEnabled()


# Delay/failure is injected only at the external SciPy factorization boundary.
# The job, cancellation, solver, result handling and dialog remain real.
import pytest  # noqa: E402


@pytest.mark.parametrize('outcome', ['cancel', 'close', 'resource_error'])
def test_interrupted_huber_keeps_graph_and_all_previous_variants(qtbot, monkeypatch, outcome):
    from dataclasses import replace
    from threading import Event
    import scipy.sparse.linalg
    from PyQt6.QtWidgets import QDialog, QLabel, QSpinBox
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.ui.graph_controls import GraphControls

    parent = QWidget()
    qtbot.addWidget(parent)
    frames = tuple(frame(np.arange(120).reshape(10, 12), i) for i in range(4))
    graph = candidate(frames)
    previous = replace(graph, robust_trials=(solve_robust_graph(graph),))
    controls = GraphControls(parent)
    controls.restore(previous)
    controls.open_graph(frames, None, DeepMatcherOptions())
    dialog = parent.findChild(QDialog, 'graphComparison')
    entered, release = Event(), Event()
    original = scipy.sparse.linalg.splu

    def delayed_factorization(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        if outcome == 'resource_error':
            raise MemoryError('Controlled memory failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(scipy.sparse.linalg, 'splu', delayed_factorization)
    try:
        dialog.findChild(QPushButton, 'runRobustGraph').click()
        qtbot.waitUntil(entered.is_set)
        assert controls.busy and controls.trial is previous
        assert not dialog.findChild(QDoubleSpinBox, 'robustThreshold').isEnabled()
        assert not dialog.findChild(QSpinBox, 'robustMaxIterations').isEnabled()
        assert not dialog.findChild(QPushButton, 'inspectGraphPair').isEnabled()
        if outcome == 'cancel':
            dialog.findChild(QPushButton, 'cancelRobustGraph').click()
        elif outcome == 'close':
            dialog.close()
            assert dialog.isVisible()
        release.set()
        qtbot.waitUntil(lambda: not controls.busy)
        assert controls.trial is previous
        if outcome != 'close':
            assert 'Wcześniejsze warianty' in dialog.findChild(QLabel, 'robustMessage').text()
            assert dialog.findChild(QPushButton, 'runRobustGraph').isEnabled()
            with qtbot.waitSignal(dialog.destroyed):
                dialog.close()
    finally:
        release.set()
