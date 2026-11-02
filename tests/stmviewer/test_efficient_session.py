"""EfficientLoFTR work can be reopened without model files or runtime imports."""
from pathlib import Path

from stmviewer.mpp import open_mpp_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState

CPU = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def test_selected_local_source_survives_portable_session(tmp_path):
    frames = open_mpp_series(CPU, check_cancelled=lambda: None)
    display = SessionViewState(deep_source='/unavailable/EfficientLoFTR/source')
    path = save_session(tmp_path / 'prepared.stmsession', SessionState(frames, display=display))
    restored = load_session(path)
    assert restored.display.deep_source == '/unavailable/EfficientLoFTR/source'


def evidence(shift=(2., -1.), shape=(48, 64)):
    from stmviewer.correspondence_types import CorrespondenceDiagnostics, ImagePreparation
    height, width = shape
    bottom, right = -height % 32, -width % 32
    preparation = ImagePreparation(shape, (height + bottom, width + right), (1., 1.), (0, 0, right, bottom), (0., 4.))
    return CorrespondenceDiagnostics(
        shift, 24, 20, 16, .8, (1,) * 16, (1,) * 16, (.8, .75), (.8, .75),
        .15, 'manual_review', 'Global support; inspect structures.', 'consensus-v1',
        (preparation, preparation),
        (('weights_path', '/absent/eloftr_outdoor.ckpt'), ('weights_sha256', 'a' * 64),
         ('source_commit', 'b' * 40), ('source_sha256', 'c' * 64), ('source_path', '/absent/source'),
         ('requested_device', 'cpu'), ('actual_device', 'CPU'), ('precision', 'FP32'),
         ('model_config', 'full_default_cfg')),
    )


def test_saved_chain_keeps_preparation_and_evidence_after_manual_correction(tmp_path):
    from dataclasses import replace
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    result = cpu_result()
    shape = result.frames[0].original.data.shape
    original_diagnostics = (None, evidence(shape=shape), evidence((-3., 2.), shape))
    result = replace(result, method='EfficientLoFTR', correspondence_diagnostics=original_diagnostics)
    edited = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    path = save_session(tmp_path / 'model-evidence.stmsession',
                        SessionState(tuple(f.original for f in edited.frames), edited))
    loaded = load_session(path)
    assert loaded.registration.correspondence_diagnostics == original_diagnostics
    assert loaded.registration.corrections == edited.corrections
    assert loaded.registration.frames[1].shift_xy == (3., -1.)


def efficient_graph(frames):
    from dataclasses import replace
    from test_graph_session import candidate
    graph = candidate(frames)
    prototype = evidence(shape=frames[0].data.shape)
    config = replace(graph.config, settings_version=2, method='efficient_loftr',
        weights_path='/absent/eloftr_outdoor.ckpt', requested_device='cpu', device='CPU',
        backend_settings=prototype.model_provenance + (('settings_text', prototype.settings_text),))
    edges = tuple(replace(edge, status='manual_review', quality_score=None,
        correspondence_diagnostics=evidence(edge.shift_xy, frames[0].data.shape)) for edge in graph.edges)
    return replace(graph, config=config, edges=edges)


def test_active_graph_candidate_and_chain_predecessor_reopen_without_runtime(tmp_path):
    from dataclasses import replace
    import os
    import subprocess
    import sys
    from test_manual_movie import cpu_result
    from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    diagnostics = (None, evidence(shape=frames[0].data.shape), evidence((-3., 2.), frames[0].data.shape))
    base = replace(base, method='EfficientLoFTR', correspondence_diagnostics=diagnostics)
    graph = efficient_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    pending = replace(graph, revision='unapplied-efficient-candidate')
    path = save_session(tmp_path / 'efficient-graph.stmsession',
                        SessionState(frames, applied, graph=pending))
    restored = load_session(path)
    assert restored.graph.revision == 'unapplied-efficient-candidate'
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
assert state.graph.revision == 'unapplied-efficient-candidate'
assert state.registration.graph_application.graph.config.method == 'efficient_loftr'
assert state.registration.predecessor.correspondence_diagnostics[1].inlier_count == 16
assert all(sys.modules[name] is None for name in ('torch', 'kornia', 'pytorch_lightning', 'einops', 'scipy', 'cv2'))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    subprocess.run([sys.executable, '-c', script, str(path)], env=env, check=True, capture_output=True, text=True)


def test_inconsistent_correspondence_metadata_is_rejected_before_restoration():
    import copy
    import json
    import pytest
    from dataclasses import replace
    from test_manual_movie import cpu_result
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    result = replace(base, method='EfficientLoFTR', correspondence_diagnostics=(None, evidence(shape=base.frames[0].original.data.shape), None))
    manifest, arrays = encode_session(SessionState(tuple(item.original for item in base.frames), result))
    mutations = (
        lambda d: d.update(inlier_count=21),
        lambda d: d.update(reference_support=[1] * 15),
        lambda d: d.update(inlier_fraction=float('nan')),
        lambda d: d.update(settings_version=2),
        lambda d: d.update(status='failed'),
        lambda d: d['preparation'][0].update(scale_xy=[2, 1]),
        lambda d: d.update(preparation=d['preparation'][:1]),
        lambda d: d['model_provenance'][1].__setitem__(1, 'broken-SHA256'),
        lambda d: d['model_provenance'].append(d['model_provenance'][0]),
    )
    portable = json.loads(json.dumps(manifest))
    for mutation in mutations:
        invalid = copy.deepcopy(portable)
        mutation(invalid['registration']['correspondence_diagnostics'][1])
        with pytest.raises(ValueError):
            decode_session(invalid, arrays)


def test_diagnostic_preparation_must_describe_archived_original_dimensions():
    import json
    import pytest
    from dataclasses import replace
    from test_manual_movie import cpu_result
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    shape = base.frames[0].original.data.shape
    result = replace(base, method='EfficientLoFTR', correspondence_diagnostics=(None, evidence(shape=shape), None))
    manifest, arrays = encode_session(SessionState(tuple(item.original for item in base.frames), result))
    manifest = json.loads(json.dumps(manifest))
    preparation = manifest['registration']['correspondence_diagnostics'][1]['preparation'][0]
    preparation['original_shape'][0] -= 1
    preparation['padding_ltrb'][3] += 1
    with pytest.raises(ValueError, match='orygina'):
        decode_session(manifest, arrays)
