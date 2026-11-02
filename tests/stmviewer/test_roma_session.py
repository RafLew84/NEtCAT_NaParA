"""Portable RoMa results never need the worker interpreter when opened."""
from dataclasses import replace
from pathlib import Path

from stmviewer.mpp import open_mpp_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState

CPU = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_worker_configuration_survives_session_without_executing_interpreter(tmp_path):
    frames = open_mpp_series(CPU, check_cancelled=lambda: None)
    interpreter = tmp_path / 'must-not-run'
    marker = tmp_path / 'executed'
    interpreter.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
    interpreter.chmod(0o700)
    display = SessionViewState(deep_interpreter=str(interpreter), deep_preset='fast',
        deep_samples=2048, deep_seed=1234, deep_source='/absent/dinov3')
    path = save_session(tmp_path / 'prepared.stmsession', SessionState(frames, display=display))
    restored = load_session(path)
    assert restored.display == display
    assert not marker.exists()


def roma_evidence(shift=(2., -1.), shape=(48, 64)):
    from stmviewer.correspondence_types import ImagePreparation
    from test_efficient_session import evidence
    preparation = ImagePreparation(shape, (320, 320), (320 / shape[1], 320 / shape[0]),
        (0, 0, 0, 0), (0., 4.), 'minmax-float32-rgb-v1', 3)
    metadata = (
        ('weights_path', '/absent/romav2.0.1.pt'), ('weights_sha256', 'a' * 64),
        ('source_commit', 'b' * 40), ('source_sha256', 'c' * 64), ('source_path', '/absent/dinov3'),
        ('requested_device', 'cpu'), ('actual_device', 'CPU'), ('model', 'RoMa v2'),
        ('interpreter_path', '/absent/bin/python'), ('preset', 'turbo'),
        ('samples', '1000'), ('seed', '20261102'), ('sampling_version', 'roma-sampling-v1'),
    )
    return replace(evidence(shift, shape), preparation=(preparation, preparation),
                   model_provenance=metadata, settings_version=2)


def test_roma_chain_and_manual_edit_roundtrip_with_original_preparation(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    result = cpu_result()
    shape = result.frames[0].original.data.shape
    diagnostics = (None, roma_evidence(shape=shape), roma_evidence((-3., 2.), shape))
    result = replace(result, method='RoMa v2', correspondence_diagnostics=diagnostics)
    edited = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    path = save_session(tmp_path / 'roma-edited.stmsession',
                        SessionState(tuple(f.original for f in edited.frames), edited))
    loaded = load_session(path)
    assert loaded.registration.correspondence_diagnostics == diagnostics
    assert loaded.registration.frames[1].shift_xy == (3., -1.)
    assert loaded.registration.corrections == edited.corrections


def roma_graph(frames):
    from test_graph_session import candidate
    from stmviewer.graph_provenance import roma_graph_config
    from stmviewer.correspondence_consensus import CorrespondenceConfig
    from dataclasses import asdict
    graph = candidate(frames)
    config = roma_graph_config(3, roma_evidence(shape=frames[0].data.shape).model_provenance,
                               asdict(CorrespondenceConfig()))
    edges = tuple(replace(edge, status='manual_review', quality_score=None,
        correspondence_diagnostics=roma_evidence(edge.shift_xy, frames[0].data.shape)) for edge in graph.edges)
    return replace(graph, config=config, edges=edges)


def test_active_roma_graph_and_pending_candidate_restore_without_model_runtime(tmp_path):
    import os
    import subprocess
    import sys
    from test_manual_movie import cpu_result
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    diagnostics = (None, roma_evidence(shape=frames[0].data.shape), roma_evidence((-3., 2.), frames[0].data.shape))
    base = replace(base, method='RoMa v2', correspondence_diagnostics=diagnostics)
    graph = roma_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    pending = replace(graph, revision='unapplied-roma-candidate')
    path = save_session(tmp_path / 'roma-graph.stmsession', SessionState(frames, applied, graph=pending))
    restored = load_session(path)
    assert restored.graph.revision == 'unapplied-roma-candidate'
    assert restored.registration.graph_application.graph == graph
    assert restored.registration.predecessor.correspondence_diagnostics == diagnostics
    previous = restore_movie_result(restored.frames, restored.registration)
    assert previous.correspondence_diagnostics == diagnostics
    script = '''
import sys
for name in ('torch', 'romav2', 'kornia', 'einops', 'scipy', 'cv2'):
    sys.modules[name] = None
from stmviewer.session_archive import load_session
state = load_session(sys.argv[1])
assert state.graph.revision == 'unapplied-roma-candidate'
assert state.registration.graph_application.graph.config.method == 'roma_v2'
assert state.registration.predecessor.correspondence_diagnostics[1].preparation[0].channels == 3
assert all(sys.modules[name] is None for name in ('torch', 'romav2', 'kornia', 'einops', 'scipy', 'cv2'))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    subprocess.run([sys.executable, '-c', script, str(path)], env=env, check=True, capture_output=True, text=True)


def test_inactive_roma_options_survive_session_separately_from_selected_method(tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    options = DeepMatcherOptions(Path('/absent/roma.pt'), 'cuda', Path('/absent/dino'),
                                Path('/absent/python'), 'base', 2048, 135)
    frames = open_mpp_series(CPU, check_cancelled=lambda: None)
    display = SessionViewState(method='phase_correlation', deep_weights='/other/loftr.ckpt',
                               deep_device='cpu', roma_options=options)
    path = save_session(tmp_path / 'roma-remembered.stmsession', SessionState(frames, display=display))
    restored = load_session(path)
    assert restored.display.method == 'phase_correlation'
    assert restored.display.deep_weights == '/other/loftr.ckpt'
    assert restored.display.deep_device == 'cpu'
    assert restored.display.roma_options == options
