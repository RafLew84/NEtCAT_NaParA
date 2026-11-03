"""Method-aware graph measurements remain portable without runtime backends."""
from dataclasses import replace
import json
import zipfile

import numpy as np

from make_registration_fixtures import frames_with_data
from test_graph_session import candidate
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState


def method_graph(frames, method='optical_flow_median'):
    graph = candidate(frames)
    config = replace(graph.config, method=method, settings_version=2,
                     weights_path=None, weights_sha256=None, requested_device='cpu', device='CPU',
                     backend_settings=(('method', method),), libraries=(('opencv', '4.0'),))
    return replace(graph, config=config, edges=tuple(
        replace(edge, status='manual_review', quality_score=None) for edge in graph.edges))


def test_cpu_graph_roundtrip_has_real_method_and_no_model_metadata(tmp_path):
    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) + index for index in range(3)))
    graph = method_graph(frames)
    path = tmp_path / 'optical-flow.stmsession'
    save_session(path, SessionState(frames, graph=graph))
    restored = load_session(path)
    assert restored.graph == graph
    assert all(edge.quality_score is None for edge in restored.graph.edges)
    with zipfile.ZipFile(path) as archive:
        saved = json.loads(archive.read('manifest.json'))['state']['graph']
    assert saved['schema'] == 'stmviewer-graph-v4'
    assert saved['config']['method'] == 'optical_flow_median'
    assert saved['config']['weights_path'] is None
    assert saved['config']['weights_sha256'] is None


def test_cpu_graph_application_manual_history_and_previous_movie_survive_session(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.manual_movie import apply_movie_correction

    chain = cpu_result()
    frames = tuple(item.original for item in chain.frames)
    graph = method_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=chain)
    assert applied.method == 'Optical Flow — graf equal-ls-v1'
    assert not applied.pair_diagnostics and not applied.local_diagnostics
    edited = apply_movie_correction(applied, corrected_trial(applied, 2, 0, 1))
    next_candidate = replace(graph, config=replace(graph.config, method='phase_correlation'),
                             revision='next-phase-candidate')
    path = tmp_path / 'active-optical-flow.stmsession'
    save_session(path, SessionState(frames, edited, graph=next_candidate))
    state = load_session(path)
    assert state.graph == next_candidate
    assert state.registration.graph_application.graph == graph
    assert state.registration.corrections == edited.corrections
    restored = restore_movie_result(state.frames, state.registration)
    assert restored.method == chain.method
    second = tmp_path / 'previous-chain.stmsession'
    save_session(second, SessionState(state.frames, restored))
    state = load_session(second)
    again = restore_movie_result(state.frames, state.registration)
    assert again.method == 'Optical Flow — graf equal-ls-v1'
    assert again.corrections == edited.corrections
    for before, after in zip(edited.frames, again.frames, strict=True):
        np.testing.assert_array_equal(before.image.data, after.image.data)


def composite_graph(frames, method='deep_matcher_ecc'):
    from stmviewer.deep_ecc import HybridDiagnostics
    from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence

    graph = candidate(frames)
    config = replace(graph.config, settings_version=2, method=method)
    edges = []
    for edge in graph.edges:
        if method == 'deep_matcher_ecc':
            diagnostic = HybridDiagnostics(edge.shift_xy, edge.shift_xy, (0., 0.), 'ok', .7,
                                           'ok', .9, 'known ECC settings', config.weights_path,
                                           config.requested_device, config.device)
            edges.append(replace(edge, hybrid_diagnostics=diagnostic))
        else:
            patch = LocalPatchEvidence((0, 0, 2, 2), (0., 0., 2., 2.), edge.shift_xy,
                                       .9, .2, 'inlier', 'matched', 5.)
            local = LocalDiagnostics(edge.shift_xy, edge.shift_xy, (patch,), 'ok', 'consensus',
                                     'known local settings', config.weights_path,
                                     config.requested_device, config.device, 'ok', .7)
            edges.append(replace(edge, local_diagnostics=local))
    return replace(graph, config=config, edges=tuple(edges))


def test_composite_graph_keeps_pair_diagnostics_separate_from_applied_movie(tmp_path):
    from test_manual_movie import cpu_result
    from stmviewer.graph_application import apply_graph_to_movie
    from test_robust_graph_session import exact_variant

    frames = tuple(item.original for item in cpu_result().frames)
    for method, label in (('deep_matcher_ecc', 'Deep Matcher + ECC (v1)'),
                          ('deep_local_consensus', 'Deep Matcher + lokalne fragmenty (v1)')):
        graph = composite_graph(frames, method)
        variant = exact_variant(graph)
        graph = replace(graph, robust_trials=(variant,))
        active = apply_graph_to_movie(frames, graph, robust_revision=variant.revision)
        path = save_session(tmp_path / f'{method}.stmsession', SessionState(frames, active, graph=graph))
        saved = load_session(path)
        assert saved.graph == graph
        assert saved.registration.method == f'{label} — graf block-huber-irls-v1'
        assert saved.registration.graph_application.graph == graph
        assert not saved.registration.pair_diagnostics
        assert not saved.registration.local_diagnostics
        assert saved.registration.graph_application.robust_revision == variant.revision


def test_all_graph_formats_load_offline_without_estimators_or_solver(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    from test_robust_graph_session import exact_variant
    from stmviewer.graph_application import apply_graph_to_movie

    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) + index for index in range(3)))
    graphs = [candidate(frames), method_graph(frames), composite_graph(frames),
              composite_graph(frames, 'deep_local_consensus')]
    paths = []
    for index, graph in enumerate(graphs):
        graph = replace(graph, robust_trials=(exact_variant(graph),))
        active = apply_graph_to_movie(frames, graph, robust_revision=graph.robust_trials[0].revision)
        paths.append(save_session(tmp_path / f'offline-{index}.stmsession', SessionState(frames, active, graph=graph)))
    code = '''
import sys
for name in ('torch', 'kornia', 'scipy', 'cv2', 'skimage'):
    sys.modules[name] = None
import numpy.linalg
def no_solver(*args, **kwargs):
    raise AssertionError('Opening saved results must not rerun a solver.')
numpy.linalg.lstsq = no_solver
numpy.linalg.solve = no_solver
from pathlib import Path
from stmviewer.session_archive import load_session
for path in sys.argv[1:]:
    state = load_session(Path(path))
    assert state.registration.graph_application.graph == state.graph
    assert state.registration.graph_application.solver == 'block-huber-irls-v1'
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'scipy', 'cv2', 'skimage'))
'''
    subprocess.run([sys.executable, '-c', code, *(str(path) for path in paths)], check=True,
                   cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)


def test_session_rejects_ambiguous_versions_methods_and_model_metadata(tmp_path):
    import pytest
    from test_graph_session import rewrite_archive
    from stmviewer.session_archive import SessionError

    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) + index for index in range(3)))
    source = save_session(tmp_path / 'valid.stmsession', SessionState(frames, graph=method_graph(frames)))
    changes = (
        lambda g: g.update(schema='stmviewer-graph-v3'),
        lambda g: g.update(schema='stmviewer-graph-v2'),
        lambda g: g['config'].update(settings_version=1),
        lambda g: g['config'].update(method='unknown-estimator'),
        lambda g: g['config'].update(weights_path='/imaginary/model.ckpt'),
        lambda g: g['config'].update(weights_sha256='a' * 64),
        lambda g: g['config'].update(requested_device='cuda'),
        lambda g: g['edges'][0].update(status='failed'),
        lambda g: g['edges'][0].update(shift_xy=[float('nan'), 0.]),
    )
    for index, change in enumerate(changes):
        path = tmp_path / f'damaged-{index}.stmsession'
        rewrite_archive(source, path, lambda body: change(body['state']['graph']))
        with pytest.raises(SessionError):
            load_session(path)


def test_composite_session_rejects_corrupt_pair_diagnostic_values(tmp_path):
    import pytest
    from test_graph_session import rewrite_archive
    from stmviewer.session_archive import SessionError

    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) + index for index in range(3)))
    source = save_session(tmp_path / 'valid-composite.stmsession',
                          SessionState(frames, graph=composite_graph(frames)))
    changes = (
        lambda d: d.update(settings_version=99),
        lambda d: d.update(final_shift_xy=[float('inf'), 0.]),
        lambda d: d.update(final_shift_xy=[0., 0., 0.]),
        lambda d: d.update(actual_device=None),
    )
    for index, change in enumerate(changes):
        path = tmp_path / f'damaged-composite-{index}.stmsession'
        rewrite_archive(source, path, lambda body: change(
            body['state']['graph']['edges'][0]['hybrid_diagnostics']))
        with pytest.raises(SessionError):
            load_session(path)
