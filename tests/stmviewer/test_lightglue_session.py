"""LightGlue settings and registered results remain portable without model resources."""
from dataclasses import replace
from pathlib import Path

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.mpp import open_mpp_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState

CPU = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_inactive_lightglue_options_preserve_both_weights_without_loading_models(tmp_path):
    options = DeepMatcherOptions(Path('/absent/matcher.pth'), 'cuda', Path('/absent/code'),
                                 extractor_weights=Path('/absent/extractor.pth'))
    frames = open_mpp_series(CPU, check_cancelled=lambda: None)
    display = SessionViewState(method='phase_correlation', deep_weights='/other/loftr.ckpt',
                               deep_device='cpu', lightglue_options=options)
    path = save_session(tmp_path / 'remembered.stmsession', SessionState(frames, display=display))
    restored = load_session(path)
    assert restored.display == display


def lightglue_evidence(shift=(2., -1.), shape=(48, 64)):
    from test_efficient_session import evidence
    from stmviewer.correspondence_types import ImagePreparation
    preparation = ImagePreparation(shape, shape, (1., 1.), (0, 0, 0, 0), (0., 4.))
    metadata = (
        ('model', 'LightGlue + SuperPoint'),
        ('extractor_config', 'SuperPoint; max_num_keypoints=2048; detection_threshold=0.0005; nms_radius=4; remove_borders=4; descriptor_dim=256'),
        ('model_config', 'LightGlue; features=superpoint; n_layers=9; filter_threshold=0.1; depth_confidence=0.95; width_confidence=0.99; flash=True; mp=False; compile=False'),
        ('precision', 'FP32 parameters/input; FlashAttention FP16 on CUDA; mp=False'),
        ('max_keypoints', '2048'),
        ('coordinate_mapping', 'upstream-original-pixels; resize=None'),
        ('preprocessing', 'minmax-float32-v1; native; no padding'),
        ('aggregation', 'translation-consensus-v2'),
        ('weights_path', '/absent/superpoint_lightglue.pth'), ('weights_sha256', 'a' * 64),
        ('weights_variant', 'superpoint_lightglue.pth'),
        ('extractor_weights_path', '/absent/superpoint_v1.pth'), ('extractor_weights_sha256', 'd' * 64),
        ('extractor_weights_variant', 'superpoint_v1.pth'),
        ('source_path', '/absent/lightglue'), ('source_sha256', 'c' * 64),
        ('source_commit', 'b' * 40), ('interpreter_path', '/absent/python'),
        ('requested_device', 'cpu'), ('actual_device', 'CPU'),
    )
    return replace(evidence(shift, shape), preparation=(preparation, preparation),
                   model_provenance=metadata, settings_version=2)


def test_chain_and_manual_correction_preserve_both_models_and_native_coordinates(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    result = cpu_result()
    shape = result.frames[0].original.data.shape
    diagnostics = (None, lightglue_evidence(shape=shape), lightglue_evidence((-3., 2.), shape))
    result = replace(result, method='LightGlue + SuperPoint', correspondence_diagnostics=diagnostics)
    edited = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    path = save_session(tmp_path / 'edited.stmsession',
                        SessionState(tuple(f.original for f in edited.frames), edited))
    restored = load_session(path)
    assert restored.registration.correspondence_diagnostics == diagnostics
    assert restored.registration.frames[1].shift_xy == (3., -1.)
    assert restored.registration.corrections == edited.corrections


def lightglue_graph(frames):
    from dataclasses import asdict
    from test_graph_session import candidate
    from stmviewer.graph_provenance import lightglue_graph_config
    from stmviewer.correspondence_consensus import CorrespondenceConfig
    graph = candidate(frames)
    config = lightglue_graph_config(3, lightglue_evidence(shape=frames[0].data.shape).model_provenance,
                                   asdict(CorrespondenceConfig()))
    edges = tuple(replace(edge, status='manual_review', quality_score=None,
        correspondence_diagnostics=lightglue_evidence(edge.shift_xy, frames[0].data.shape)) for edge in graph.edges)
    return replace(graph, config=config, edges=edges)


def test_active_graph_and_pending_candidate_reopen_without_model_runtime(tmp_path):
    import os
    import subprocess
    import sys
    from test_manual_movie import cpu_result
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    diagnostics = (None, lightglue_evidence(shape=frames[0].data.shape),
                   lightglue_evidence((-3., 2.), frames[0].data.shape))
    base = replace(base, method='LightGlue + SuperPoint', correspondence_diagnostics=diagnostics)
    graph = lightglue_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    pending = replace(graph, revision='unapplied-lightglue-candidate')
    path = save_session(tmp_path / 'graph.stmsession', SessionState(frames, applied, graph=pending))
    restored = load_session(path)
    assert restored.graph.revision == 'unapplied-lightglue-candidate'
    assert restored.registration.graph_application.graph == graph
    assert restored.registration.predecessor.correspondence_diagnostics == diagnostics
    previous = restore_movie_result(restored.frames, restored.registration)
    assert previous.correspondence_diagnostics == diagnostics
    script = '''
import sys
for name in ('torch', 'kornia', 'lightglue', 'torchvision', 'cv2'):
    sys.modules[name] = None
from stmviewer.session_archive import load_session
state = load_session(sys.argv[1])
assert state.graph.revision == 'unapplied-lightglue-candidate'
assert state.registration.graph_application.graph.config.method == 'lightglue_superpoint'
assert dict(state.registration.predecessor.correspondence_diagnostics[1].model_provenance)['extractor_weights_path'] == '/absent/superpoint_v1.pth'
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'lightglue', 'torchvision', 'cv2'))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    subprocess.run([sys.executable, '-c', script, str(path)], env=env, check=True, capture_output=True, text=True)
