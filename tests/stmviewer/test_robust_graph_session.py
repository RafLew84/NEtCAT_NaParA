"""Portable Huber variants share one immutable measurement graph and active movie."""
from dataclasses import replace
import json
import zipfile

from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState
from stmviewer.robust_graph_types import RobustConfig, RobustTrial
from stmviewer.robust_graph import measurement_id
from test_graph_session import candidate


def exact_variant(graph, threshold=2.):
    return RobustTrial(
        measurement_id=measurement_id(graph), config=RobustConfig(threshold_px=threshold),
        positions=graph.positions, last_positions=graph.positions,
        residuals=((0., 0.),) * len(graph.edges), weights=(1.,) * len(graph.edges),
        status='converged', reason='Known exact measurements.', iterations=1,
        objective=0., ls_objective=0., max_step_px=0., relative_cost_change=0.,
        gradient_inf=0., condition_estimate=3., solver_s=.1,
    )


def test_two_huber_thresholds_round_trip_without_replacing_ls_or_active_movie(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction

    base = cpu_result()
    active = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    frames = tuple(item.original for item in active.frames)
    graph = candidate(frames)
    variants = (exact_variant(graph), exact_variant(graph, threshold=4.))
    graph = replace(graph, robust_trials=variants)
    path = tmp_path / 'huber.stmsession'
    save_session(path, SessionState(frames, active, graph=graph))
    restored = load_session(path)
    assert restored.graph == graph
    assert restored.registration.revision == active.revision
    assert restored.registration.corrections == active.corrections
    for before, after in zip(active.frames, restored.registration.frames, strict=True):
        assert after.image.data.tobytes() == before.image.data.tobytes()
        assert after.shift_xy == before.shift_xy
    with zipfile.ZipFile(path) as archive:
        assert len([name for name in archive.namelist() if name.endswith('.npy')]) == 6
        record = json.loads(archive.read('manifest.json'))['state']['graph']
        assert record['schema'] == 'stmviewer-graph-v2'
        assert len(record['robust_trials']) == 2
        assert record['revision'] == graph.revision


def test_saved_huber_result_cannot_be_attached_to_another_measurement_set(tmp_path):
    import numpy as np
    import pytest
    from make_registration_fixtures import frames_with_data
    from stmviewer.session_archive import SessionError
    from test_graph_session import rewrite_archive

    frames = frames_with_data(*(np.zeros((3, 4)) + index for index in range(3)))
    graph = candidate(frames)
    graph = replace(graph, robust_trials=(exact_variant(graph),))
    source = tmp_path / 'bound-huber.stmsession'
    save_session(source, SessionState(frames, graph=graph))
    for field in ('measurement_id', 'revision'):
        target = tmp_path / f'bad-{field}.stmsession'
        def change(body):
            if field == 'measurement_id':
                body['state']['graph']['robust_trials'][0].update(measurement_id='0' * 64)
            else:
                body['state']['graph'].update(revision='different-measurements')
        rewrite_archive(source, target, change)
        with pytest.raises(SessionError, match='Huber'):
            load_session(target)


def outlier_session_graph():
    import numpy as np
    from make_registration_fixtures import frames_with_data
    from stmviewer.graph_provenance import graph_sources
    from stmviewer.robust_graph import solve_robust_graph
    from test_robust_graph import four_node_outlier

    frames = frames_with_data(*(np.zeros((3, 4)) + index for index in range(4)))
    graph = replace(four_node_outlier(), sources=graph_sources(frames))
    result = solve_robust_graph(graph)
    return frames, replace(graph, robust_trials=(result,))


def test_huber_weights_positions_costs_and_termination_cannot_disagree(tmp_path):
    import pytest
    from stmviewer.session_archive import SessionError
    from test_graph_session import rewrite_archive

    frames, graph = outlier_session_graph()
    source = tmp_path / 'known-outlier.stmsession'
    save_session(source, SessionState(frames, graph=graph))
    assert load_session(source).graph == graph
    changes = [
        lambda r: r['config'].update(threshold_px=4.),
        lambda r: r['config'].update(solver='unknown-solver'),
        lambda r: r['config'].update(condition_method='unknown-condition-method'),
        lambda r: r['weights'].__setitem__(2, .25),
        lambda r: r['weights'].pop(),
        lambda r: r['residuals'][2].__setitem__(0, 100.),
        lambda r: r['residuals'].pop(),
        lambda r: r['positions'][1].__setitem__(0, .7),
        lambda r: r['last_positions'][1].__setitem__(0, .7),
        lambda r: r.update(objective=r['objective'] + 1),
        lambda r: r.update(ls_objective=r['ls_objective'] + 1),
        lambda r: r.update(gradient_inf=1.),
        lambda r: r.update(status='iteration_limit'),
        lambda r: r.update(status='unknown-status'),
        lambda r: r.update(iterations=0),
        lambda r: r.update(iterations=r['config']['max_iterations'] + 1),
        lambda r: r.update(max_step_px=.1),
        lambda r: r.update(relative_cost_change=.1),
        lambda r: r.update(condition_estimate=None),
        lambda r: r.update(condition_estimate=1e20),
        lambda r: r.update(schema='stmviewer-robust-graph-v99'),
    ]
    for index, change in enumerate(changes):
        target = tmp_path / f'inconsistent-{index}.stmsession'
        rewrite_archive(source, target, lambda body: change(body['state']['graph']['robust_trials'][0]))
        with pytest.raises(SessionError):
            load_session(target)
    duplicate = tmp_path / 'duplicated-variant.stmsession'
    rewrite_archive(source, duplicate, lambda body: body['state']['graph']['robust_trials'].append(
        body['state']['graph']['robust_trials'][0]))
    with pytest.raises(SessionError):
        load_session(duplicate)


def test_unfinished_huber_attempts_preserve_last_valid_diagnostics(tmp_path):
    import pytest
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.session_archive import SessionError
    from test_graph_session import rewrite_archive

    frames, graph = outlier_session_graph()
    limited = solve_robust_graph(graph, RobustConfig(max_iterations=1))
    refused = solve_robust_graph(graph, RobustConfig(max_condition=1.))
    assert limited.status == 'iteration_limit' and limited.last_positions is not None
    assert refused.status == 'numerical_failure' and refused.last_positions == graph.positions
    graph = replace(graph, robust_trials=graph.robust_trials + (limited, refused))
    source = tmp_path / 'unfinished.stmsession'
    save_session(source, SessionState(frames, graph=graph))
    assert load_session(source).graph == graph
    invalid_limit = tmp_path / 'limit-without-condition.stmsession'
    rewrite_archive(source, invalid_limit, lambda body: body['state']['graph']['robust_trials'][1].update(
        condition_estimate=None))
    with pytest.raises(SessionError, match='Huber'):
        load_session(invalid_limit)
    for index in (1, 2):
        invalid = tmp_path / f'promoted-failure-{index}.stmsession'
        def promote(body):
            variant = body['state']['graph']['robust_trials'][index]
            variant['positions'] = variant['last_positions']
        rewrite_archive(source, invalid, promote)
        with pytest.raises(SessionError, match='Huber'):
            load_session(invalid)


def test_missing_relations_and_disconnected_attempts_remain_explicit(tmp_path):
    import pytest
    from stmviewer.graph_registration import solve_graph
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.session_archive import SessionError
    from test_graph_session import rewrite_archive

    frames, original = outlier_session_graph()
    for disconnected in (False, True):
        edges = tuple(replace(edge, shift_xy=None, status='missing', reason='No stable matches',
                              residual_xy=None)
                      if (edge.i < 2 <= edge.j if disconnected else (edge.i, edge.j) == (0, 1))
                      else edge for edge in original.edges)
        graph = solve_graph(original.sources, edges, original.config)
        variant = solve_robust_graph(graph)
        assert variant.status == ('disconnected' if disconnected else 'converged')
        graph = replace(graph, robust_trials=(variant,))
        source = tmp_path / f'missing-{disconnected}.stmsession'
        save_session(source, SessionState(frames, graph=graph))
        assert load_session(source).graph == graph
        missing = next(index for index, edge in enumerate(graph.edges) if edge.shift_xy is None)
        assert variant.weights[missing] is None and variant.residuals[missing] is None
        invalid = tmp_path / f'invented-weight-{disconnected}.stmsession'
        rewrite_archive(source, invalid, lambda body: body['state']['graph']['robust_trials'][0][
            'weights'].__setitem__(missing, 1.))
        with pytest.raises(SessionError, match='Huber'):
            load_session(invalid)


def test_huber_session_load_requires_neither_model_packages_nor_solver(tmp_path):
    from pathlib import Path
    import subprocess
    import sys

    frames, graph = outlier_session_graph()
    path = tmp_path / 'portable-huber.stmsession'
    save_session(path, SessionState(frames, graph=graph))
    code = '''
import sys
for package in ('torch', 'kornia', 'scipy'):
    sys.modules[package] = None
import numpy.linalg

def unavailable(*args, **kwargs):
    raise AssertionError('Loading saved results must not optimize again.')
numpy.linalg.lstsq = unavailable
numpy.linalg.solve = unavailable
from pathlib import Path
from stmviewer.session_archive import load_session
state = load_session(Path(sys.argv[1]))
assert state.graph.robust_trials[0].status == 'converged'
assert abs(state.graph.robust_trials[0].objective - 36.) < 1e-7
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'scipy'))
'''
    subprocess.run([sys.executable, '-c', code, str(path)], check=True,
                   cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)


def test_huber_measurement_binding_survives_windows_session_resave(tmp_path, monkeypatch):
    from pathlib import Path, PureWindowsPath
    from stmviewer import session_paths

    class WindowsSessionPath(PureWindowsPath):
        def resolve(self):
            return Path(self.as_posix()).resolve()

    frames, graph = outlier_session_graph()
    linux_path = tmp_path / 'linux-huber.stmsession'
    windows_path = tmp_path / 'windows-huber.stmsession'
    save_session(linux_path, SessionState(frames, graph=graph))
    with monkeypatch.context() as windows:
        windows.setattr(session_paths, 'Path', WindowsSessionPath)
        windows_state = load_session(linux_path)
        assert str(windows_state.frames[0].source).startswith('\\home\\')
        assert windows_state.graph.robust_trials == graph.robust_trials
        assert measurement_id(windows_state.graph) == measurement_id(graph)
        save_session(windows_path, windows_state)
    restored = load_session(windows_path)
    assert restored.graph.robust_trials == graph.robust_trials
    assert restored.graph.sources[0].source == str(restored.frames[0].source)
    assert restored.graph.positions == graph.positions
    assert restored.graph.edges == graph.edges
