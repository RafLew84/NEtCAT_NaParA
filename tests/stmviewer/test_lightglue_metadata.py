"""Stored LightGlue evidence cannot lose a component or masquerade as another method."""
from dataclasses import replace
from pathlib import Path

import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_metadata import decode_graph, encode_graph
from stmviewer.session_metadata import decode_session, encode_session
from stmviewer.session_state import SessionState, SessionViewState
from test_manual_movie import cpu_result
from test_lightglue_session import lightglue_evidence, lightglue_graph


def _chain(evidence):
    base = cpu_result()
    result = replace(base, method='LightGlue + SuperPoint', correspondence_diagnostics=(None, evidence, None))
    return SessionState(tuple(item.original for item in result.frames), result)


@pytest.mark.parametrize('field', ['extractor_weights_sha256', 'weights_sha256', 'source_sha256',
                                   'extractor_config', 'model_config', 'extractor_weights_path'])
def test_incomplete_two_model_provenance_is_rejected(field):
    evidence = lightglue_evidence(shape=cpu_result().frames[0].original.data.shape)
    incomplete = replace(evidence, model_provenance=tuple((k, v) for k, v in evidence.model_provenance if k != field))
    with pytest.raises(ValueError):
        encode_session(_chain(incomplete))


def test_lightglue_evidence_cannot_be_relabelled_as_efficientloftr():
    base = cpu_result()
    evidence = lightglue_evidence(shape=base.frames[0].original.data.shape)
    relabelled = replace(base, method='EfficientLoFTR', correspondence_diagnostics=(None, evidence, None))
    with pytest.raises(ValueError, match='model|metod'):
        encode_session(SessionState(tuple(f.original for f in base.frames), relabelled))


def test_saved_controls_require_session_v8_and_keep_active_and_remembered_models():
    frames = tuple(item.original for item in cpu_result().frames)
    options = DeepMatcherOptions(Path('/missing/matcher.pth'), 'cuda', Path('/missing/source'),
                                 extractor_weights=Path('/missing/superpoint.pth'))
    roma = DeepMatcherOptions(Path('/missing/roma.pt'), 'cpu', Path('/missing/roma'), Path('/missing/python'))
    display = SessionViewState(method='lightglue_superpoint', deep_weights=str(options.weights),
                               deep_source=str(options.source), deep_device='cuda',
                               deep_extractor_weights=str(options.extractor_weights),
                               lightglue_options=options, roma_options=roma)
    manifest, arrays = encode_session(SessionState(frames, display=display))
    assert manifest['schema'] == 'stmviewer-state-v8'
    assert decode_session(manifest, arrays).display == display
    manifest['schema'] = 'stmviewer-state-v7'
    with pytest.raises(ValueError, match='v8'):
        decode_session(manifest, arrays)


def test_graph_cannot_be_disguised_as_matchanything_schema():
    frames = tuple(item.original for item in cpu_result().frames)
    graph = lightglue_graph(frames)
    record = encode_graph(graph)
    assert record['schema'] == 'stmviewer-graph-v8'
    record['schema'] = 'stmviewer-graph-v7'
    with pytest.raises(ValueError, match='format|metod'):
        decode_graph(record, frames, lambda: None)


def test_native_coordinate_policy_rejects_rescaled_preparation():
    evidence = lightglue_evidence(shape=cpu_result().frames[0].original.data.shape)
    p = evidence.preparation[0]
    scaled = replace(p, model_shape=(p.model_shape[0] * 2, p.model_shape[1] * 2), scale_xy=(2., 2.))
    with pytest.raises(ValueError, match='geometria'):
        encode_session(_chain(replace(evidence, preparation=(scaled, scaled))))
