"""Portable long-reference candidates preserve the untouched window experiment."""
from dataclasses import replace
import json
import zipfile

import numpy as np

from make_registration_fixtures import frames_with_data
from stmviewer.graph_metadata import decode_graph_config, encode_graph
from stmviewer.graph_provenance import graph_sources
from stmviewer.graph_registration import graph_pairs
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphExtension, GraphTrial
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState


def extended_candidate(*, robust=False):
    """Exact six-frame experiment, including an explicitly missing distant match."""
    frames = frames_with_data(*(np.arange(30.).reshape(5, 6) + i for i in range(6)))
    config = GraphConfig(3, '/missing/outdoor.ckpt', 'a' * 64, 'cpu', 'cpu',
                         (('confidence_threshold', '0.2'),), (('torch', '2.0'),),
                         'stored-code', pair_code_version='sha256:' + 'b' * 64)
    positions = tuple((float(i), -float(i)) for i in range(6))
    edges = tuple(GraphEdge(i, j, (float(j - i), float(i - j)), 'ok',
                            quality_score=.8, residual_xy=(0., 0.))
                  for i, j in graph_pairs(6, 3))
    base = GraphTrial(graph_sources(frames), config, edges, positions, positions,
                      (tuple(range(6)),), (), revision='window-base', measured_pairs=len(edges))
    if robust:
        from test_robust_graph_session import exact_variant
        base = replace(base, robust_trials=(exact_variant(base),))
    extension = GraphExtension(base, (0,), 3, 5,
                               base.robust_trials[0].revision if robust else None,
                               replace(config, code_version='extension-code'))
    added = (GraphEdge(0, 4, (4., -4.), 'ok', quality_score=.8, residual_xy=(0., 0.)),
             GraphEdge(0, 5, None, 'missing', reason='No common structures'))
    trial = replace(base, edges=tuple(sorted(edges + added, key=lambda e: (e.i, e.j))),
                    revision='window-plus-references', measured_pairs=2, reused_pairs=len(edges),
                    robust_trials=(), extension=extension)
    if robust:
        from stmviewer.robust_graph import solve_robust_graph
        trial = replace(trial, robust_trials=(solve_robust_graph(trial, base.robust_trials[0].config),))
    return frames, trial


def test_graph_config_roundtrip_preserves_optional_pair_identity_and_legacy_shape():
    frames, trial = extended_candidate()
    modern = encode_graph(trial.extension.base)['config']
    assert decode_graph_config(modern) == trial.config
    legacy = replace(trial.extension.base, config=replace(trial.config, pair_code_version=None))
    old_record = encode_graph(legacy)
    assert old_record['schema'] == 'stmviewer-graph-v1'
    assert 'extension' not in old_record
    assert 'pair_code_version' not in old_record['config']
    assert decode_graph_config(old_record['config']) == legacy.config


def test_extended_candidate_session_keeps_base_edges_configuration_and_missing_reason(tmp_path):
    frames, trial = extended_candidate()
    path = save_session(tmp_path / 'long-references.stmsession', SessionState(frames, graph=trial))
    loaded = load_session(path)
    assert loaded.graph == trial
    assert loaded.graph.extension.base == trial.extension.base
    assert next(e for e in loaded.graph.edges if (e.i, e.j) == (0, 5)).reason == 'No common structures'
    with zipfile.ZipFile(path) as archive:
        record = json.loads(archive.read('manifest.json'))['state']['graph']
        assert record['schema'] == 'stmviewer-graph-v3'
        assert record['extension']['base']['schema'] == 'stmviewer-graph-v1'
        assert len(archive.namelist()) == 7  # original arrays, no duplicated images for base


def test_extended_active_huber_candidate_predecessor_and_deleted_sources_survive(tmp_path):
    from test_manual_movie import corrected_trial
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.manual_movie import apply_movie_correction

    frames, graph = extended_candidate(robust=True)
    window = apply_graph_to_movie(frames, graph.extension.base,
                                  robust_revision=graph.extension.base_robust_revision)
    active = apply_graph_to_movie(frames, graph, robust_revision=graph.robust_trials[0].revision,
                                  previous=window)
    active = apply_movie_correction(active, corrected_trial(active, 2, 1, 0))
    candidate = replace(graph, revision='separate-unapplied-candidate', robust_trials=())
    # An LS-base candidate can coexist with an applied Huber extension.
    candidate = replace(candidate, extension=replace(candidate.extension, base_robust_revision=None))
    path = save_session(tmp_path / 'active.stmsession', SessionState(frames, active, graph=candidate))
    loaded = load_session(path)
    assert loaded.graph == candidate
    assert loaded.registration.graph_application == active.graph_application
    assert loaded.registration.corrections == active.corrections
    assert loaded.registration.predecessor == active.predecessor
    restored_window = restore_movie_result(loaded.frames, loaded.registration)
    assert restored_window.graph_application == window.graph_application
    deleted = active.without_frame(0)
    path = save_session(tmp_path / 'deleted.stmsession', SessionState(
        tuple(item.original for item in deleted.frames), deleted))
    loaded = load_session(path)
    assert loaded.graph is None
    assert loaded.registration.graph_application == active.graph_application
    assert len(loaded.registration.graph_application.graph.extension.base.sources) == 6
    assert not loaded.registration.corrections_editable
    for before, after in zip(deleted.frames, loaded.registration.frames, strict=True):
        np.testing.assert_array_equal(before.image.data, after.image.data)


def test_long_reference_sessions_reject_mismatched_base_sources_config_and_plan(tmp_path):
    import pytest
    from test_graph_session import rewrite_archive
    from stmviewer.session_archive import SessionError

    frames, trial = extended_candidate()
    path = save_session(tmp_path / 'valid.stmsession', SessionState(frames, graph=trial))
    changes = (
        lambda e: e.update(settings_version=99),
        lambda e: e.update(references=[True]),
        lambda e: e.update(references=[1]),
        lambda e: e.update(target_end=99),
        lambda e: e.update(base_robust_revision='not-a-selected-variant'),
        lambda e: e['measurement_config'].update(weights_sha256='c' * 64),
        lambda e: e['measurement_config'].update(pair_code_version='sha256:' + 'c' * 64),
        lambda e: e['base']['sources'][0].update(pixels_sha256='d' * 64),
        lambda e: e['base']['edges'][0].update(quality_score=.5),
        lambda e: e['base'].update(schema='stmviewer-graph-v3'),
    )
    for index, change in enumerate(changes):
        broken = tmp_path / f'invalid-{index}.stmsession'
        rewrite_archive(path, broken, lambda body: change(body['state']['graph']['extension']))
        with pytest.raises(SessionError):
            load_session(broken)


def test_extended_session_load_needs_neither_original_files_model_nor_solver(tmp_path):
    from pathlib import Path
    import subprocess
    import sys

    frames, graph = extended_candidate(robust=True)
    from stmviewer.graph_application import apply_graph_to_movie
    active = apply_graph_to_movie(frames, graph, robust_revision=graph.robust_trials[0].revision)
    path = save_session(tmp_path / 'offline.stmsession', SessionState(frames, active, graph=graph))
    code = '''
import sys
for name in ('torch', 'kornia', 'scipy'):
    sys.modules[name] = None
import numpy.linalg

def unavailable(*args, **kwargs):
    raise AssertionError('Opening a session must not solve or estimate.')
numpy.linalg.solve = unavailable
numpy.linalg.lstsq = unavailable
from pathlib import Path
from stmviewer.session_archive import load_session
state = load_session(Path(sys.argv[1]))
assert state.graph.extension.base_robust_revision
assert len(state.graph.robust_trials) == 1
assert state.graph.extension.base.robust_trials[0].status == 'converged'
assert state.registration.graph_application.graph == state.graph
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'scipy'))
'''
    subprocess.run([sys.executable, '-c', code, str(path)], check=True,
                   cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)


def test_extended_graph_sources_follow_session_host_paths(tmp_path, monkeypatch):
    from pathlib import Path, PureWindowsPath
    from stmviewer import session_paths
    from stmviewer.graph_application import apply_graph_to_movie

    class WindowsSessionPath(PureWindowsPath):
        def resolve(self):
            return Path(self.as_posix()).resolve()

    frames, graph = extended_candidate(robust=True)
    active = apply_graph_to_movie(frames, graph, robust_revision=graph.robust_trials[0].revision)
    path = save_session(tmp_path / 'linux.stmsession', SessionState(frames, active, graph=graph))
    with monkeypatch.context() as windows:
        windows.setattr(session_paths, 'Path', WindowsSessionPath)
        loaded = load_session(path)
        for result in (loaded.graph, loaded.registration.graph_application.graph):
            assert result.sources == result.extension.base.sources
            assert result.sources[0].source == str(loaded.frames[0].source)
        returned = save_session(tmp_path / 'windows.stmsession', loaded)
    reopened = load_session(returned)
    assert reopened.graph.sources == reopened.graph.extension.base.sources
    assert reopened.graph.sources[0].source == str(reopened.frames[0].source)
    assert reopened.graph.positions == graph.positions
    assert reopened.graph.extension.base.robust_trials == graph.extension.base.robust_trials


def test_selected_huber_extension_cannot_load_after_its_new_solver_attempt_is_removed(tmp_path):
    import pytest
    from test_graph_session import rewrite_archive
    from stmviewer.session_archive import SessionError

    frames, trial = extended_candidate(robust=True)
    path = save_session(tmp_path / 'chosen-huber.stmsession', SessionState(frames, graph=trial))
    broken = tmp_path / 'lost-huber.stmsession'
    rewrite_archive(path, broken, lambda body: body['state']['graph'].update(robust_trials=[]))
    with pytest.raises(SessionError, match='Huber'):
        load_session(broken)
