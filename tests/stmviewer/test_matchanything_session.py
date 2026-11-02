"""MatchAnything configuration and results remain portable without model resources."""
from dataclasses import replace
from pathlib import Path

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.mpp import open_mpp_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState

CPU = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_inactive_matchanything_options_survive_without_affecting_selected_method(tmp_path):
    options = DeepMatcherOptions(Path('/absent/matchanything.ckpt'), 'cuda', Path('/absent/code'))
    frames = open_mpp_series(CPU, check_cancelled=lambda: None)
    display = SessionViewState(method='phase_correlation', deep_weights='/other/loftr.ckpt',
                               deep_device='cpu', matchanything_options=options)
    path = save_session(tmp_path / 'remembered.stmsession', SessionState(frames, display=display))
    restored = load_session(path)
    assert restored.display == display


def matchanything_evidence(shift=(2., -1.), shape=(48, 64)):
    from test_efficient_session import evidence
    from stmviewer.correspondence_types import ImagePreparation
    preparation = ImagePreparation(shape, (640, 640), (640 / shape[1], 480 / shape[0]),
        (0, 0, 0, 160), (0., 4.), 'minmax-uint8-demo-gray-v1', 1)
    metadata = (
        ('model', 'MatchAnything-ELoFTR'), ('model_config', 'configs/models/eloftr_model.py'),
        ('precision', 'FP32'), ('inference_policy', 'hf-match-images-preset-v1'),
        ('model_threshold', '0.001'), ('position_encoding', 'NPE 832,832,832,832'),
        ('weights_path', '/absent/matchanything_eloftr.ckpt'),
        ('weights_sha256', 'a' * 64), ('source_path', '/absent/matchanything'),
        ('source_sha256', 'c' * 64), ('source_commit', 'b' * 40),
        ('requested_device', 'cpu'), ('actual_device', 'CPU'),
    )
    return replace(evidence(shift, shape), preparation=(preparation, preparation),
                   model_provenance=metadata, settings_version=2)


def test_chain_and_manual_correction_preserve_matchanything_evidence(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    result = cpu_result()
    shape = result.frames[0].original.data.shape
    diagnostics = (None, matchanything_evidence(shape=shape), matchanything_evidence((-3., 2.), shape))
    result = replace(result, method='MatchAnything-ELoFTR', correspondence_diagnostics=diagnostics)
    edited = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    path = save_session(tmp_path / 'edited.stmsession',
                        SessionState(tuple(f.original for f in edited.frames), edited))
    restored = load_session(path)
    assert restored.registration.correspondence_diagnostics == diagnostics
    assert restored.registration.frames[1].shift_xy == (3., -1.)
    assert restored.registration.corrections == edited.corrections


def matchanything_graph(frames):
    from dataclasses import asdict
    from test_graph_session import candidate
    from stmviewer.graph_provenance import matchanything_graph_config
    from stmviewer.correspondence_consensus import CorrespondenceConfig
    graph = candidate(frames)
    config = matchanything_graph_config(3, matchanything_evidence(shape=frames[0].data.shape).model_provenance,
                                       asdict(CorrespondenceConfig()))
    edges = tuple(replace(edge, status='manual_review', quality_score=None,
        correspondence_diagnostics=matchanything_evidence(edge.shift_xy, frames[0].data.shape)) for edge in graph.edges)
    return replace(graph, config=config, edges=edges)


def test_active_graph_and_pending_candidate_reopen_without_model_runtime(tmp_path):
    import os
    import subprocess
    import sys
    from test_manual_movie import cpu_result
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    diagnostics = (None, matchanything_evidence(shape=frames[0].data.shape),
                   matchanything_evidence((-3., 2.), frames[0].data.shape))
    base = replace(base, method='MatchAnything-ELoFTR', correspondence_diagnostics=diagnostics)
    graph = matchanything_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    pending = replace(graph, revision='unapplied-matchanything-candidate')
    path = save_session(tmp_path / 'graph.stmsession', SessionState(frames, applied, graph=pending))
    restored = load_session(path)
    assert restored.graph.revision == 'unapplied-matchanything-candidate'
    assert restored.registration.graph_application.graph == graph
    assert restored.registration.predecessor.correspondence_diagnostics == diagnostics
    previous = restore_movie_result(restored.frames, restored.registration)
    assert previous.correspondence_diagnostics == diagnostics
    script = '''
import sys
for name in ('torch', 'kornia', 'pytorch_lightning', 'einops', 'scipy', 'cv2'):
    sys.modules[name] = None
from stmviewer.session_archive import load_session
state = load_session(sys.argv[1])
assert state.graph.revision == 'unapplied-matchanything-candidate'
assert state.registration.graph_application.graph.config.method == 'matchanything_eloftr'
assert state.registration.predecessor.correspondence_diagnostics[1].preparation[0].channels == 1
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'pytorch_lightning', 'einops', 'scipy', 'cv2'))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    subprocess.run([sys.executable, '-c', script, str(path)], env=env, check=True, capture_output=True, text=True)
