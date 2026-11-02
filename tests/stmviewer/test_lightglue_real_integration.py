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


@pytest.mark.parametrize('custom', [False, True])
def test_real_estimator_is_shared_by_pair_chain_graph_and_preserved_in_session(tmp_path, custom):
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.graph_registration import register_graph
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import register_series
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState, SessionViewState
    from stmviewer.method_parameters import MethodProfiles, LightGlueParameters, ContrastParameters
    from stmviewer.feature_provenance import recorded_profile
    frames = original_frames((137, 219))
    options = replace(default_lightglue_options(), device='cpu')
    profiles = (MethodProfiles(lightglue=LightGlueParameters(max_keypoints=1024,
        detection_threshold=.001, nms_radius=2, filter_threshold=.05, full_computation=True,
        radius=1.5, contrast=ContrastParameters(mode='percentiles'))) if custom else MethodProfiles())
    original_bytes = tuple(frame.data.tobytes() for frame in frames)
    chain = register_series(frames, method=METHOD, deep_options=options, method_profiles=profiles)
    graph = register_graph(frames, method=METHOD, deep_options=options, method_profiles=profiles)
    pair = estimate_pair(frames[0], frames[1], method=METHOD, deep_options=options, method_profiles=profiles)
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
    save_session(session, SessionState(frames, applied, SessionViewState(method_profiles=profiles), graph=graph))
    restored = load_session(session)
    assert restored.registration.method == applied.method
    assert restored.registration.graph_application.graph.config.method == METHOD
    assert restored.registration.graph_application.graph.config == graph.config
    assert restored.graph.config == graph.config
    assert restored.display.method_profiles == profiles
    assert recorded_profile(METHOD, restored.graph.config.backend_settings) == profiles.lightglue
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.mpp import open_mpp_series
    path = tmp_path / 'lightglue-parameters.mpp'
    save_aligned_mpp(path, applied)
    exported = open_mpp_series(path, check_cancelled=lambda: None)
    assert exported[1].alignment.manual_movie.graph_provenance.config == graph.config
    for edge in restored.graph.edges:
        assert dict(edge.correspondence_diagnostics.model_provenance)['extractor_weights_sha256']
    assert tuple(frame.data.tobytes() for frame in frames) == original_bytes
