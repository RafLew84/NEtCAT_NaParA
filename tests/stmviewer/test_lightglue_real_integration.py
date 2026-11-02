"""Opt-in real LightGlue through pair, film, graph and exported/session results."""
from dataclasses import replace
import os
from pathlib import Path

import numpy as np
import pytest

from stmviewer.lightglue_matcher import default_lightglue_options
from test_matchanything_real_integration import original_frames

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_LIGHTGLUE'),
                               reason='Requires prepared local LightGlue and SuperPoint resources')
METHOD = 'lightglue_superpoint'


def test_real_estimator_is_shared_by_pair_chain_graph_and_preserved_in_session(tmp_path):
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.graph_registration import register_graph
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import register_series
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState
    frames = original_frames((137, 219))
    options = replace(default_lightglue_options(), device='cpu')
    original_bytes = tuple(frame.data.tobytes() for frame in frames)
    chain = register_series(frames, method=METHOD, deep_options=options)
    graph = register_graph(frames, method=METHOD, deep_options=options)
    pair = estimate_pair(frames[0], frames[1], method=METHOD, deep_options=options)
    np.testing.assert_allclose([f.shift_xy for f in chain.frames], [(0, 0), (-7, 5), (3, -4)], atol=.6)
    np.testing.assert_allclose(graph.positions, [(0, 0), (-7, 5), (3, -4)], atol=.6)
    np.testing.assert_allclose(graph.edges[0].shift_xy, pair.shift_xy, atol=1e-7)
    assert all(edge.correspondence_diagnostics for edge in graph.edges)
    assert all(edge.quality_score is None for edge in graph.edges)
    robust = solve_robust_graph(graph)
    assert robust.positions is not None
    np.testing.assert_allclose(robust.positions, graph.positions, atol=.1)
    applied = apply_graph_to_movie(frames, graph, previous=chain)
    session = tmp_path / 'actual-lightglue.stmsession'
    save_session(session, SessionState(frames, applied, graph=graph))
    restored = load_session(session)
    assert restored.registration.method == applied.method
    assert restored.registration.graph_application.graph.config.method == METHOD
    assert restored.registration.graph_application.graph.config == graph.config
    assert restored.graph.config == graph.config
    for edge in restored.graph.edges:
        assert dict(edge.correspondence_diagnostics.model_provenance)['extractor_weights_sha256']
    assert tuple(frame.data.tobytes() for frame in frames) == original_bytes
