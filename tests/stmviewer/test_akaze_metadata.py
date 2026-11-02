"""AKAZE provenance and schema cannot silently change on session/graph restore."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_metadata import encode_graph, decode_graph
from stmviewer.graph_registration import register_graph
from stmviewer.registration import register_series
from stmviewer.session_metadata import encode_session, decode_session
from stmviewer.session_state import SessionState, SessionViewState
from test_akaze_integration import frames


def test_akaze_and_remembered_lightglue_share_session_v9_without_loading_models():
    originals = frames()
    result = register_series(originals, method='akaze')
    remembered = DeepMatcherOptions(Path('/absent/lg.pth'), 'cuda', Path('/absent/code'),
                                      extractor_weights=Path('/absent/sp.pth'))
    view = SessionViewState(method='phase_correlation', lightglue_options=remembered)
    manifest, arrays = encode_session(SessionState(originals, result, view))
    assert manifest['schema'] == 'stmviewer-state-v9'
    restored = decode_session(manifest, arrays)
    assert restored.display == view
    assert restored.registration.correspondence_diagnostics == result.correspondence_diagnostics
    manifest['schema'] = 'stmviewer-state-v8'
    with pytest.raises(ValueError, match='v9'):
        decode_session(manifest, arrays)


@pytest.mark.parametrize('field,wrong', [('detector','SIFT'), ('matcher','L2'),
                                        ('actual_device','CUDA'), ('adapter_version','unknown'),
                                        ('opencv_build_sha256','missing')])
def test_saved_detector_matcher_and_cpu_identity_are_validated(field, wrong):
    originals = frames()
    graph = register_graph(originals, method='akaze')
    record = encode_graph(graph)
    assert record['schema'] == 'stmviewer-graph-v9'
    changed = dict(record['config']['backend_settings'])
    changed[field] = wrong
    record['config']['backend_settings'] = list(changed.items())
    with pytest.raises(ValueError, match='AKAZE|SHA-256'):
        decode_graph(record, originals, lambda: None)


def test_akaze_graph_cannot_be_labelled_as_older_model_schema():
    originals = frames()
    record = encode_graph(register_graph(originals, method='akaze'))
    record['schema'] = 'stmviewer-graph-v8'
    with pytest.raises(ValueError, match='format|metod'):
        decode_graph(record, originals, lambda: None)
