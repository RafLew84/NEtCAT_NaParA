"""Saved measurements → block-Huber solution, independent of a learned matcher."""
from dataclasses import replace

import numpy as np

from stmviewer.graph_registration import graph_pairs, solve_graph
from stmviewer.graph_types import GraphEdge
from test_graph_registration import config, sources


def four_node_outlier():
    # K4, true positions zero, one incorrect (12,16) measurement of length20.
    edges = tuple(GraphEdge(i, j, (12., 16.) if (i, j) == (0, 3) else (0., 0.), 'ok')
                  for i, j in graph_pairs(4, 3))
    return solve_graph(sources(4), edges, config())


def test_block_huber_matches_the_analytic_two_dimensional_optimum():
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig

    graph = four_node_outlier()
    result = solve_robust_graph(graph, RobustConfig(threshold_px=2.))
    assert result.status == 'converged'
    # Analytic minimum along u=(.6,.8): p1=p2=delta*u/2, p3=delta*u.
    np.testing.assert_allclose(result.positions, ((0, 0), (.6, .8), (.6, .8), (1.2, 1.6)), atol=1e-5)
    assert result.positions == result.last_positions
    assert abs(result.objective - 36.) < 1e-7
    assert result.objective < result.ls_objective
    # Block weight for the incorrect edge is delta/(20-delta)=1/9 in BOTH axes.
    assert abs(result.weights[2] - 1/9) < 1e-7
    assert all(w == 1 for index, w in enumerate(result.weights) if index != 2)
    assert graph.robust_trials == ()


def test_condition_limit_refuses_complete_positions_but_retains_diagnostics():
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig

    graph = four_node_outlier()
    result = solve_robust_graph(graph, RobustConfig(max_condition=1.))
    assert result.status == 'numerical_failure'
    assert result.positions is None
    assert result.last_positions == graph.positions
    assert result.condition_estimate > result.config.max_condition
    assert result.iterations == 0
    assert 'uwarunkowan' in result.reason


import pytest  # noqa: E402


@pytest.mark.parametrize('failure', ['nonfinite', 'native_error', 'memory'])
def test_failed_native_solve_never_publishes_invalid_positions(monkeypatch, failure):
    from scipy.sparse import linalg
    from stmviewer.robust_graph import solve_robust_graph

    factorize = linalg.splu

    class FailedFactor:
        def __init__(self, matrix):
            self.factor = factorize(matrix)

        def solve(self, rhs, *args, **kwargs):
            if rhs.ndim == 2:
                if failure == 'memory':
                    raise MemoryError('allocation refused')
                if failure == 'native_error':
                    raise RuntimeError('native solve refused')
                return np.full(rhs.shape, np.nan)
            return self.factor.solve(rhs, *args, **kwargs)

    monkeypatch.setattr(linalg, 'splu', FailedFactor)
    graph = four_node_outlier()
    if failure == 'memory':
        with pytest.raises(MemoryError, match='allocation refused'):
            solve_robust_graph(graph)
    else:
        result = solve_robust_graph(graph)
        assert result.status == 'numerical_failure'
        assert result.positions is None
        assert result.last_positions == graph.positions
        assert np.isfinite(result.last_positions).all()
        assert result.iterations == 0


def test_signed_turns_and_missing_relation_keep_the_same_measurements():
    from stmviewer.robust_graph import measurement_id, solve_robust_graph

    truth = ((0., 0.), (3., -2.), (-2., 1.), (2., 4.))
    edges = tuple(GraphEdge(i, j, None if (i, j) == (0, 1) else
                           (truth[j][0]-truth[i][0], truth[j][1]-truth[i][1]),
                           'missing' if (i, j) == (0, 1) else 'ok',
                           'No matches' if (i, j) == (0, 1) else None)
                  for i, j in graph_pairs(4, 3))
    graph = solve_graph(sources(4), edges, config())
    previous = graph.edges
    result = solve_robust_graph(graph)
    assert result.status == 'converged'
    np.testing.assert_allclose(result.positions, truth, atol=1e-10)
    assert result.weights[0] is None and result.residuals[0] is None
    assert graph.edges is previous and graph.chain_positions is None
    assert result.measurement_id == measurement_id(graph)
    assert result.measurement_id == measurement_id(replace(graph, robust_trials=(result,)))
    # Native path separators can change when opening a portable session.
    native = tuple(replace(source, source='C:\\different\\spelling.mpp') for source in graph.sources)
    assert measurement_id(replace(graph, sources=native)) == result.measurement_id


@pytest.mark.parametrize('kind', ['tree', 'bridge', 'disconnected', 'periodic_alias', 'dominant_bad'])
def test_topology_or_consistent_wrong_measurements_do_not_acquire_guarantees(kind):
    from stmviewer.robust_graph import solve_robust_graph

    false_positions = ((0., 0.), (24., 0.), (48., 0.), (72., 0.))
    edges = []
    for i, j in graph_pairs(4, 3):
        missing = ((kind == 'tree' and j-i != 1)
                   or (kind == 'bridge' and j == 3 and i != 2)
                   or (kind == 'disconnected' and i < 2 <= j))
        shift = (false_positions[j][0]-false_positions[i][0], 0.)
        if kind == 'dominant_bad' and (i, j) == (0, 3):
            shift = (0., 0.)  # The lone physically true relation loses to coherent bad ones.
        edges.append(GraphEdge(i, j, None if missing else shift,
                               'missing' if missing else 'ok', 'Known missing edge' if missing else None))
    graph = solve_graph(sources(4), tuple(edges), config())
    result = solve_robust_graph(graph)
    if kind == 'disconnected':
        assert result.status == 'disconnected'
        assert result.positions is None and result.last_positions is None
        assert result.weights == (None,)*6
        assert graph.components == ((0, 1), (2, 3))
    else:
        assert result.status == 'converged'
        if kind == 'dominant_bad':
            assert result.positions[3][0] > 65  # Robustness cannot determine physical truth.
            assert result.weights[2] < .05
        else:
            np.testing.assert_allclose(result.positions, false_positions, atol=1e-10)
            assert all(w is None or w == 1 for w in result.weights)
        if kind == 'tree':
            assert graph.bridges == ((0, 1), (1, 2), (2, 3))
        if kind == 'bridge':
            assert graph.bridges == ((2, 3),)


def test_iteration_limit_and_cancel_leave_prior_attempt_unchanged():
    from threading import Event
    from stmviewer.registration import RegistrationCancelled
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig

    graph = four_node_outlier()
    old = solve_robust_graph(graph)
    graph = replace(graph, robust_trials=(old,))
    failed = solve_robust_graph(graph, RobustConfig(max_iterations=1))
    assert failed.status == 'iteration_limit' and failed.positions is None
    assert failed.last_positions is not None and failed.iterations == 1
    assert failed.gradient_inf > failed.config.gradient_tolerance
    assert graph.robust_trials == (old,)
    stopped = Event()
    with pytest.raises(RegistrationCancelled):
        solve_robust_graph(graph, cancelled=stopped.is_set,
                           progress=lambda *args: stopped.set())
    assert graph.robust_trials == (old,)


@pytest.mark.parametrize('changes', [
    {'threshold_px': 0}, {'threshold_px': -2}, {'threshold_px': float('nan')},
    {'threshold_px': float('inf')}, {'max_iterations': 0}, {'max_iterations': True},
    {'position_tolerance_px': 0}, {'objective_relative_tolerance': float('nan')},
    {'gradient_tolerance': -1}, {'max_condition': .5}, {'solver': 'unknown'},
    {'condition_method': 'unknown'},
])
def test_invalid_configuration_is_refused_without_creating_an_attempt(changes):
    from stmviewer.registration import RegistrationError
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig

    with pytest.raises(RegistrationError):
        solve_robust_graph(four_node_outlier(), replace(RobustConfig(), **changes))


def test_outlier_network_with_real_direction_changes_preserves_its_anchor():
    from stmviewer.robust_graph import solve_robust_graph

    positions = ((0., 0.), (3., -2.), (-2., 1.), (2., 4.))
    noisy = []
    for i, j in graph_pairs(4, 3):
        dx = positions[j][0] - positions[i][0]
        dy = positions[j][1] - positions[i][1]
        if (i, j) == (0, 3):
            dx, dy = dx+12, dy+16
        noisy.append(GraphEdge(i, j, (dx, dy), 'ok'))
    graph = solve_graph(sources(4), tuple(noisy), config())
    result = solve_robust_graph(graph)
    np.testing.assert_allclose(result.positions, ((0, 0), (3.6, -1.2), (-1.4, 1.8), (3.2, 5.6)), atol=1e-5)
    # LS is biased by10px on the last node; block Huber by2px for this known graph.
    assert np.linalg.norm(np.asarray(graph.positions)[3] - positions[3]) == 10.
    assert abs(np.linalg.norm(np.asarray(result.positions)[3] - positions[3]) - 2.) < 1e-5


def test_raw_measurement_identity_changes_for_each_changed_measurement_field():
    from stmviewer.robust_graph import measurement_id

    graph = four_node_outlier()
    original = measurement_id(graph)
    for change in ({'shift_xy': (1., 2.)}, {'status': 'low_confidence'}, {'reason': 'operator note'},
                   {'quality_score': .3}):
        changed = replace(graph, edges=(replace(graph.edges[0], **change),) + graph.edges[1:])
        assert measurement_id(changed) != original
    changed = replace(graph, sources=(replace(graph.sources[0], pixels_sha256='f'*64),) + graph.sources[1:])
    assert measurement_id(changed) != original


def test_numerically_weak_cut_is_refused_even_in_a_connected_graph():
    from stmviewer.robust_graph import solve_robust_graph

    shifts = {(0, 1): 0., (2, 3): 0., (0, 2): 1e15, (0, 3): -1e15,
              (1, 2): -1e15, (1, 3): 1e15}
    edges = tuple(GraphEdge(i, j, (shifts[i, j], 0.), 'ok') for i, j in graph_pairs(4, 3))
    graph = solve_graph(sources(4), edges, config())
    assert graph.components == ((0, 1, 2, 3),) and not graph.bridges
    result = solve_robust_graph(graph)
    assert result.status == 'numerical_failure' and result.positions is None
    assert result.condition_estimate > result.config.max_condition
    assert result.weights[0] == result.weights[5] == 1.
    assert max(result.weights[1:5]) < 1e-12


def test_saved_measurements_can_be_analyzed_without_any_model_import(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys

    from make_registration_fixtures import frames_with_data
    from stmviewer.graph_provenance import graph_sources
    from stmviewer.session_archive import save_session
    from stmviewer.session_state import SessionState

    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) for _ in range(4)))
    graph = replace(four_node_outlier(), sources=graph_sources(frames))
    path = tmp_path / 'measurements.stmsession'
    save_session(path, SessionState(frames, graph=graph))
    code = '''
import importlib.abc
import pathlib
import sys
class NoModel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('torch', 'kornia'):
            raise ImportError('Model libraries prohibited during saved-edge analysis')
sys.meta_path.insert(0, NoModel())
from stmviewer.session_archive import load_session
from stmviewer.robust_graph import solve_robust_graph
state = load_session(pathlib.Path(sys.argv[1]))
result = solve_robust_graph(state.graph)
assert result.status == 'converged'
assert abs(result.positions[3][0] - 1.2) < 1e-5
assert abs(result.positions[3][1] - 1.6) < 1e-5
assert 'torch' not in sys.modules and 'kornia' not in sys.modules
'''
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    completed = subprocess.run([sys.executable, '-c', code, str(path)], cwd=Path(__file__).parents[2],
                                env=environment, text=True, capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
