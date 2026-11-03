"""Portable graph candidates coexist with the active movie in a session archive."""
import json
import zipfile

import numpy as np

from make_registration_fixtures import frames_with_data
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState


def test_session_without_graph_stays_readable_as_original_v1(tmp_path):
    frames = frames_with_data(np.arange(12.).reshape(3, 4))
    path = tmp_path / 'old-format.stmsession'
    save_session(path, SessionState(frames))
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['version'] == 1
        assert manifest['state']['schema'] == 'stmviewer-state-v1'
        assert 'graph' not in manifest['state']
    restored = load_session(path)
    assert restored.graph is None
    np.testing.assert_array_equal(restored.frames[0].data, frames[0].data)


def candidate(frames):
    import hashlib
    from stmviewer.graph_types import GraphConfig, GraphEdge, GraphSource, GraphTrial

    sources = tuple(GraphSource(str(frame.source), frame.source_frame_index, frame.data.shape,
                                hashlib.sha256(np.ascontiguousarray(frame.data, dtype='<f8').tobytes()).hexdigest())
                    for frame in frames)
    config = GraphConfig(3, '/unavailable/weights-outdoor.ckpt', 'a' * 64, 'auto', 'cuda',
                         (('confidence_threshold', '0.2'),), (('torch', '2.0'),), 'saved-code')
    return GraphTrial(sources, config, (
        GraphEdge(0, 1, (2., -1.), 'ok', quality_score=0.7, residual_xy=(0., 0.)),
        GraphEdge(0, 2, (-1., 1.), 'low_confidence', quality_score=0.1, residual_xy=(0., 0.)),
        GraphEdge(1, 2, (-3., 2.), 'ok', quality_score=0.9, residual_xy=(0., 0.)),
    ), ((0., 0.), (2., -1.), (-1., 1.)), ((0., 0.), (2., -1.), (-1., 1.)),
        ((0, 1, 2),), (), measured_pairs=3, measurement_s=1.2, solver_s=0.01)


def test_graph_round_trip_preserves_active_manual_movie_without_extra_images(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.session_state import SessionViewState

    base = cpu_result()
    aligned = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    frames = tuple(item.original for item in aligned.frames)
    graph = candidate(frames)
    display = SessionViewState(index=2, view='aligned', gamma=1.8, fps=7)
    path = tmp_path / 'graph-and-active-movie.stmsession'
    save_session(path, SessionState(frames, aligned, display, graph))
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {
            'manifest.json', 'original/000000.npy', 'original/000001.npy', 'original/000002.npy',
            'aligned/000000.npy', 'aligned/000001.npy', 'aligned/000002.npy',
        }
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['state']['schema'] == 'stmviewer-state-v2'
        assert manifest['state']['graph']['schema'] == 'stmviewer-graph-v1'
    restored = load_session(path)
    assert restored.graph == graph
    assert restored.display == display
    assert restored.registration is not None
    assert restored.registration.corrections == aligned.corrections
    assert restored.registration.baseline == aligned.baseline
    assert restored.registration.revision == aligned.revision
    for before, after in zip(aligned.frames, restored.registration.frames):
        assert after.shift_xy == before.shift_xy
        assert after.image.data.tobytes() == before.image.data.tobytes()
        assert after.original.data.tobytes() == before.original.data.tobytes()


def rewrite_archive(source, destination, change):
    with zipfile.ZipFile(source) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    body = json.loads(contents['manifest.json'])
    change(body)
    contents['manifest.json'] = json.dumps(body).encode()
    with zipfile.ZipFile(destination, 'w') as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)


def test_graph_cannot_be_attached_to_different_frames_or_pixels(tmp_path):
    import pytest
    from stmviewer.session_archive import SessionError

    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) + index for index in range(3)))
    path = tmp_path / 'bound.stmsession'
    save_session(path, SessionState(frames, graph=candidate(frames)))
    changes = (
        ('source', '/somewhere/other.mpp'), ('source_frame_index', 999),
        ('shape', [4, 3]), ('pixels_sha256', 'b' * 64),
    )
    for field, value in changes:
        damaged = tmp_path / f'changed-{field}.stmsession'
        rewrite_archive(path, damaged, lambda body: body['state']['graph']['sources'][1].update({field: value}))
        with pytest.raises(SessionError, match='[Gg]raf'):
            load_session(damaged)


def test_session_preserves_actual_cuda_device_label_without_loading_model(tmp_path):
    from dataclasses import replace

    frames = frames_with_data(*(np.zeros((3, 4)) + index for index in range(3)))
    graph = candidate(frames)
    graph = replace(graph, config=replace(graph.config, device='CUDA:0 — NVIDIA GeForce RTX 5090'))
    path = tmp_path / 'cuda.stmsession'
    save_session(path, SessionState(frames, graph=graph))
    assert load_session(path).graph == graph


def test_inconsistent_graph_positions_topology_and_versions_are_rejected(tmp_path):
    import pytest
    from stmviewer.session_archive import SessionError

    frames = frames_with_data(*(np.zeros((3, 4)) + index for index in range(3)))
    path = tmp_path / 'valid-geometry.stmsession'
    save_session(path, SessionState(frames, graph=candidate(frames)))

    def non_solution(graph):
        graph['positions'][1] = [3., -1.]
        graph['edges'][0]['residual_xy'] = [1., 0.]
        graph['edges'][2]['residual_xy'] = [-1., 0.]

    changes = [
        lambda g: g.update(anchor=1),
        lambda g: g.update(solver='another-solver'),
        lambda g: g.update(schema='stmviewer-graph-v99'),
        lambda g: g['config'].update(settings_version=99),
        lambda g: g['positions'].__setitem__(0, [1., 0.]),
        lambda g: g['positions'].__setitem__(1, [float('nan'), 0.]),
        lambda g: g['positions'].pop(),
        lambda g: g['chain_positions'].__setitem__(2, [999., 0.]),
        lambda g: g['edges'][0].update(residual_xy=[3., 0.]),
        lambda g: g['edges'][0].update(j=2),
        lambda g: g['edges'].pop(),
        lambda g: g.update(components=[[0, 1], [2]]),
        lambda g: g.update(bridges=[[0, 1]]),
        lambda g: g.update(positions=None),
        non_solution,
    ]
    for index, change in enumerate(changes):
        damaged = tmp_path / f'bad-geometry-{index}.stmsession'
        rewrite_archive(path, damaged, lambda body: change(body['state']['graph']))
        with pytest.raises(SessionError):
            load_session(damaged)


def test_disconnected_graph_preserves_reasons_and_bridges_without_model_or_solver(tmp_path):
    from dataclasses import replace
    from pathlib import Path
    import subprocess
    import sys
    import pytest
    from stmviewer.graph_types import GraphEdge
    from stmviewer.session_archive import SessionError

    frames = frames_with_data(*(np.zeros((3, 4)) + index for index in range(3)))
    graph = candidate(frames)
    graph = replace(graph, edges=(
        replace(graph.edges[0], residual_xy=None),
        GraphEdge(0, 2, None, 'missing', reason='Tearing: no stable matches'),
        GraphEdge(1, 2, None, 'missing', reason='No matches'),
    ), positions=None, chain_positions=None, components=((0, 1), (2,)), bridges=((0, 1),))
    path = tmp_path / 'disconnected.stmsession'
    save_session(path, SessionState(frames, graph=graph))
    assert load_session(path).graph == graph
    connected_path = tmp_path / 'connected.stmsession'
    save_session(connected_path, SessionState(frames, graph=candidate(frames)))
    # Independent process lacks model packages and disallows native solver entrypoints.
    code = '''
import sys
sys.modules['torch'] = None
sys.modules['kornia'] = None
import numpy.linalg
import scipy.sparse.linalg

def unavailable(*args, **kwargs):
    raise AssertionError('Opening a session must not run a solver.')
numpy.linalg.lstsq = unavailable
scipy.sparse.linalg.spsolve = unavailable
from pathlib import Path
from stmviewer.session_archive import load_session
state = load_session(Path(sys.argv[1]))
assert state.graph.positions is None
assert state.graph.components == ((0, 1), (2,))
assert state.graph.edges[1].reason == 'Tearing: no stable matches'
connected = load_session(Path(sys.argv[2]))
assert connected.graph.positions == ((0., 0.), (2., -1.), (-1., 1.))
'''
    subprocess.run([sys.executable, '-c', code, str(path), str(connected_path)], check=True,
                   cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    invalid = tmp_path / 'invented-positions.stmsession'
    rewrite_archive(path, invalid, lambda body: body['state']['graph'].update(
        positions=[[0., 0.], [2., -1.], [0., 0.]]))
    with pytest.raises(SessionError, match='spójnego grafu'):
        load_session(invalid)


def test_graph_session_can_be_resaved_on_windows_and_reopened_on_linux(tmp_path, monkeypatch):
    from pathlib import Path, PureWindowsPath
    from stmviewer import session_paths
    from stmviewer.frame import FrameProvenance

    class WindowsSessionPath(PureWindowsPath):
        def resolve(self):
            return Path(self.as_posix()).resolve()

    frames = frames_with_data(*(np.arange(12.).reshape(3, 4) + index for index in range(3)))
    graph = candidate(frames)
    linux_path = tmp_path / 'from-linux.stmsession'
    windows_path = tmp_path / 'from-windows.stmsession'
    save_session(linux_path, SessionState(frames, graph=graph))
    with monkeypatch.context() as windows:
        windows.setattr(session_paths, 'Path', WindowsSessionPath)
        windows_state = load_session(linux_path)
        assert str(windows_state.frames[0].source).startswith('\\home\\')
        save_session(windows_path, windows_state)
    restored = load_session(windows_path)
    assert restored.graph.positions == graph.positions
    assert restored.graph.edges == graph.edges
    assert restored.graph.config == graph.config
    assert restored.frames[0].provenance == FrameProvenance(str(frames[0].source), 0)
    assert restored.graph.sources[0].source == str(restored.frames[0].source)
