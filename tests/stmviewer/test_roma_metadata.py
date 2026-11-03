"""Reject contradictory RoMa provenance before restoring an active movie."""
from dataclasses import replace
import json

import pytest

from stmviewer.session_metadata import decode_session, encode_session
from stmviewer.session_state import SessionState, SessionViewState
from test_manual_movie import cpu_result
from test_roma_session import roma_evidence, roma_graph


def test_rgb_roma_diagnostics_cannot_be_relabelled_as_another_matcher():
    base = cpu_result()
    diagnostic = roma_evidence(shape=base.frames[0].original.data.shape)
    relabelled = replace(base, method='EfficientLoFTR', correspondence_diagnostics=(None, diagnostic, None))
    with pytest.raises(ValueError, match='metod|przygotowan'):
        encode_session(SessionState(tuple(f.original for f in base.frames), relabelled))


@pytest.mark.parametrize('key,value', [('preset', 'unknown'), ('samples', '0'), ('seed', '-1'),
                                     ('interpreter_path', ''), ('model', 'EfficientLoFTR')])
def test_graph_rejects_invalid_worker_configuration(key, value):
    from stmviewer.graph_metadata import decode_graph, encode_graph
    frames = tuple(item.original for item in cpu_result().frames)
    graph = roma_graph(frames)
    saved = json.loads(json.dumps(encode_graph(graph)))
    saved['config']['backend_settings'] = [
        [name, value if name == key else content]
        for name, content in saved['config']['backend_settings']]
    for edge in saved['edges']:
        edge['correspondence_diagnostics']['model_provenance'] = [
            [name, value if name == key else content]
            for name, content in edge['correspondence_diagnostics']['model_provenance']]
    with pytest.raises(ValueError):
        decode_graph(saved, frames, lambda: None)


@pytest.mark.parametrize('field,value', [('deep_preset', 'unknown'), ('deep_samples', 7),
                                        ('deep_seed', -1), ('deep_interpreter', '\x00bad')])
def test_session_rejects_invalid_worker_controls(field, value):
    frames = tuple(item.original for item in cpu_result().frames)
    manifest, arrays = encode_session(SessionState(frames, display=SessionViewState(deep_interpreter='/absent/python')))
    manifest['display'][field] = value
    with pytest.raises(ValueError):
        decode_session(manifest, arrays)
