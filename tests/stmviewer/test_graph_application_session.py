"""Applied graph sessions keep the frozen base independent of later candidates."""
from dataclasses import replace
import json
import zipfile

import numpy as np

from test_graph_session import candidate, rewrite_archive
from test_manual_movie import cpu_result, corrected_trial
from stmviewer.manual_movie import apply_movie_correction, remove_movie_correction
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState


def graph_movie():
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.graph_provenance import graph_sources

    chain = cpu_result()
    chain = apply_movie_correction(chain, corrected_trial(chain, 1, 1, 0))
    frames = tuple(frame.original for frame in chain.frames)
    graph = replace(candidate(frames), sources=graph_sources(frames))
    applied = apply_graph_to_movie(frames, graph, previous=chain)
    edited = apply_movie_correction(applied, corrected_trial(applied, 2, 0, 1))
    return frames, graph, chain, edited


def test_session_keeps_frozen_applied_graph_after_new_candidate(tmp_path):
    from stmviewer.graph_application import apply_graph_to_movie

    frames, graph, chain, _ = graph_movie()
    edited = apply_graph_to_movie(frames, graph)
    next_candidate = replace(graph, revision='unapplied-new-candidate')
    path = tmp_path / 'frozen-and-candidate.stmsession'
    save_session(path, SessionState(frames, edited, graph=next_candidate))
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 7  # manifest + original + active aligned; no predecessor images
        assert json.loads(archive.read('manifest.json'))['state']['schema'] == 'stmviewer-state-v3'
    loaded = load_session(path)
    assert loaded.graph == next_candidate
    active = loaded.registration
    assert active.graph_application.graph == graph
    assert active.graph_application.positions == ((0., 0.), (2., -1.), (-1., 1.))
    assert active.baseline == edited.baseline
    assert active.corrections == edited.corrections
    assert active.revision == edited.revision
    assert [item.shift_xy for item in active.frames] == [(0., 0.), (2., -1.), (-1., 1.)]
    for before, after in zip(edited.frames, active.frames, strict=True):
        np.testing.assert_array_equal(after.image.data, before.image.data)


def test_saved_graph_manual_overrides_restore_previous_chain_and_its_diagnostics(tmp_path):
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    from stmviewer.deep_ecc import HybridDiagnostics

    frames, graph, chain, _ = graph_movie()
    diagnostic = HybridDiagnostics((2., -1.), (2., -1.), (0., 0.), 'ok', .8,
                                   'ok', .9, 'recorded-settings', '/missing/model', 'cuda', 'CUDA')
    chain = replace(chain, method='Deep Matcher', pair_diagnostics=(None, diagnostic, None))
    applied = apply_graph_to_movie(frames, graph, previous=chain)
    edited = apply_movie_correction(applied, corrected_trial(applied, 2, 0, 1))
    path = tmp_path / 'restore-chain.stmsession'
    save_session(path, SessionState(frames, edited))
    loaded = load_session(path)
    active = loaded.registration
    assert active.corrections == edited.corrections
    assert active.graph_application == edited.graph_application
    assert active.predecessor == edited.predecessor
    reverted = remove_movie_correction(active, 2)
    assert [item.shift_xy for item in reverted.frames] == [(0., 0.), (2., -1.), (-1., 1.)]
    restored = restore_movie_result(loaded.frames, active)
    assert restored.baseline == chain.baseline
    assert restored.corrections == chain.corrections
    assert restored.method == chain.method
    assert restored.pair_diagnostics == chain.pair_diagnostics
    assert restored.revision != chain.revision
    for before, after in zip(chain.frames, restored.frames, strict=True):
        assert after.shift_xy == before.shift_xy
        np.testing.assert_array_equal(after.image.data, before.image.data)
    # The restored chain retains the graph as the next lightweight restore option.
    second = tmp_path / 'restore-graph.stmsession'
    save_session(second, SessionState(loaded.frames, restored))
    loaded_chain = load_session(second)
    graph_again = restore_movie_result(loaded_chain.frames, loaded_chain.registration)
    assert graph_again.graph_application == edited.graph_application
    assert graph_again.corrections == edited.corrections


def test_deleted_source_session_retains_full_graph_and_geometry_without_renumbering(tmp_path):
    import pytest
    from stmviewer.manual_movie import movie_pair_trial
    from stmviewer.graph_application import restore_movie_result
    from stmviewer.registration import RegistrationError

    frames, graph, chain, edited = graph_movie()
    surviving = edited.without_frame(0)
    path = tmp_path / 'deleted-anchor.stmsession'
    save_session(path, SessionState(tuple(item.original for item in surviving.frames), surviving))
    restored = load_session(path).registration
    assert not restored.corrections_editable
    assert restored.graph_application.graph == graph
    assert restored.baseline == edited.baseline
    assert restored.corrections == edited.corrections
    assert restored.predecessor == edited.predecessor
    assert restored.reference == edited.reference
    assert restored.canvas_shape == edited.canvas_shape
    for before, after in zip(surviving.frames, restored.frames, strict=True):
        assert before.origin_xy == after.origin_xy
        np.testing.assert_array_equal(before.image.data, after.image.data)
    with pytest.raises(RegistrationError):
        movie_pair_trial(restored, 1)
    with pytest.raises(RegistrationError):
        restore_movie_result(tuple(item.original for item in restored.frames), restored)


def test_corrupt_applied_graph_or_predecessor_never_loads_as_a_valid_movie(tmp_path):
    import pytest
    from stmviewer.session_archive import SessionError

    frames, graph, chain, edited = graph_movie()
    path = tmp_path / 'valid-active.stmsession'
    save_session(path, SessionState(frames, edited, graph=replace(graph, revision='candidate')))

    def provenance_config(state):
        state['manual_histories'][0]['graph_provenance']['config']['weights_sha256'] = 'b' * 64

    mutations = [
        provenance_config,
        lambda state: state['registration'].pop('graph_application'),
        lambda state: state['registration']['graph_application'].update(settings_version=99),
        lambda state: state['registration']['graph_application']['graph']['sources'][0].update(pixels_sha256='b' * 64),
        lambda state: state['registration']['graph_application']['graph']['positions'].__setitem__(1, [4., -1.]),
        lambda state: state['registration']['predecessor']['sources'][0].update(source='/other/source.mpp'),
        lambda state: state['registration']['predecessor']['source_geometry'][0].__setitem__(0, 999.),
        lambda state: state['registration']['predecessor']['final']['baseline'][1].update(shift_xy=[999., 0.]),
        lambda state: state['registration']['predecessor'].update(canvas_shape=[1, 1]),
    ]
    for index, mutation in enumerate(mutations):
        broken = tmp_path / f'corrupted-active-{index}.stmsession'
        rewrite_archive(path, broken, lambda body: mutation(body['state']))
        with pytest.raises(SessionError):
            load_session(broken)
    assert load_session(path).registration.graph_application == edited.graph_application


def test_applied_huber_roundtrip_needs_no_model_or_solver_and_keeps_selected_variant(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    from test_robust_graph_session import outlier_session_graph
    from stmviewer.graph_application import apply_graph_to_movie

    frames, graph = outlier_session_graph()
    variant = graph.robust_trials[0]
    active = apply_graph_to_movie(frames, graph, robust_revision=variant.revision)
    active = apply_movie_correction(active, corrected_trial(active, 2, 1, 0))
    path = tmp_path / 'applied-huber.stmsession'
    save_session(path, SessionState(frames, active))
    loaded = load_session(path)
    assert loaded.registration.graph_application.graph == graph
    assert loaded.registration.graph_application.robust_revision == variant.revision
    assert loaded.registration.corrections == active.corrections
    code = """
import sys
for package in ('torch', 'kornia', 'scipy'):
    sys.modules[package] = None
import numpy.linalg

def unavailable(*args, **kwargs):
    raise AssertionError('Saved active results must not rerun a solver.')
numpy.linalg.lstsq = unavailable
numpy.linalg.solve = unavailable
from pathlib import Path
from stmviewer.session_archive import load_session
state = load_session(Path(sys.argv[1]))
assert state.registration.graph_application.solver == 'block-huber-irls-v1'
assert len(state.registration.corrections) == 1
assert state.registration.corrections_editable
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'scipy'))
"""
    subprocess.run([sys.executable, '-c', code, str(path)], check=True,
                   cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)


def test_graph_and_predecessor_paths_survive_session_host_change(tmp_path, monkeypatch):
    from pathlib import Path, PureWindowsPath
    from stmviewer import session_paths
    from stmviewer.graph_application import restore_movie_result

    class WindowsSessionPath(PureWindowsPath):
        def resolve(self):
            return Path(self.as_posix()).resolve()

    frames, graph, chain, edited = graph_movie()
    original = tmp_path / 'linux.stmsession'
    returned = tmp_path / 'windows.stmsession'
    save_session(original, SessionState(frames, edited, graph=graph))
    # Emulate only pathlib's host spelling at the filesystem boundary.
    with monkeypatch.context() as windows:
        windows.setattr(session_paths, 'Path', WindowsSessionPath)
        loaded = load_session(original)
        active = loaded.registration
        assert active.graph_application.graph.sources[0].source == str(loaded.frames[0].source)
        assert active.predecessor.sources[0].source == str(loaded.frames[0].source)
        changed = apply_movie_correction(active, corrected_trial(active, 1, 1, 0))
        save_session(returned, SessionState(loaded.frames, changed, graph=loaded.graph))
    loaded = load_session(returned)
    assert loaded.registration.graph_application.graph.sources[0].source == str(loaded.frames[0].source)
    restored = restore_movie_result(loaded.frames, loaded.registration)
    assert [frame.shift_xy for frame in restored.frames] == [(0., 0.), (3., -1.), (0., 1.)]
    assert restored.corrections[0].moving.source == str(loaded.frames[1].source)
