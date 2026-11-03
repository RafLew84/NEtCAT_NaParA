"""Configured public pair/movie/graph and portable evidence contracts."""
from dataclasses import replace

import numpy as np

from stmviewer.method_parameters import MethodProfiles, AkazeParameters, ContrastParameters
from stmviewer.feature_provenance import recorded_profile
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import register_series
from stmviewer.graph_registration import register_graph
from stmviewer.graph_metadata import encode_graph, decode_graph
from test_akaze_integration import frames


def test_configured_pair_movie_and_graph_share_estimator_and_keep_old_measurements():
    originals = frames()
    profiles = MethodProfiles(akaze=AkazeParameters(threshold=.0001, radius=1.5,
                                contrast=ContrastParameters(mode='percentiles')))
    pair = estimate_pair(*originals[:2], method='akaze', method_profiles=profiles)
    movie = register_series(originals, method='akaze', method_profiles=profiles)
    graph = register_graph(originals, method='akaze', method_profiles=profiles)
    assert pair.correspondence == movie.correspondence_diagnostics[1]
    assert pair.correspondence == graph.edges[0].correspondence_diagnostics
    assert recorded_profile('akaze', graph.config.backend_settings) == profiles.akaze
    np.testing.assert_allclose(graph.positions, [(0, 0), (-7, 5), (3, -4)], atol=.3)
    assert decode_graph(encode_graph(graph), originals, lambda: None).config == graph.config
    same = register_graph(originals, method='akaze', method_profiles=profiles, previous=graph)
    assert same.reused_pairs == 3
    changed = replace(profiles, akaze=replace(profiles.akaze, radius=2.5))
    fresh = register_graph(originals, method='akaze', method_profiles=changed, previous=graph)
    assert fresh.reused_pairs == 0
    assert recorded_profile('akaze', graph.config.backend_settings) == profiles.akaze
    from stmviewer.robust_graph import solve_robust_graph
    robust = solve_robust_graph(graph)
    assert robust.positions is not None


def test_session_profiles_do_not_relabel_old_result_and_legacy_loads_defaults(tmp_path):
    from stmviewer.session_metadata import encode_session, decode_session
    from stmviewer.session_archive import save_session, load_session
    from stmviewer.session_state import SessionState, SessionViewState
    from stmviewer.method_parameters import LightGlueParameters
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.mpp import open_mpp_series
    originals = frames()
    used = MethodProfiles(akaze=AkazeParameters(threshold=.0001,
                           contrast=ContrastParameters(mode='clahe')))
    old_result = register_series(originals, method='akaze', method_profiles=used)
    current = replace(used, akaze=replace(used.akaze, radius=3.),
                      lightglue=LightGlueParameters(max_keypoints=1024, full_computation=True))
    state = SessionState(originals, old_result,
                         SessionViewState(method='phase_correlation', method_profiles=current))
    restored = load_session(save_session(tmp_path/'parameters.stmsession', state))
    assert restored.display.method_profiles == current
    evidence = restored.registration.correspondence_diagnostics[1]
    assert recorded_profile('akaze', evidence.model_provenance) == used.akaze
    exported = tmp_path/'parameters.mpp'
    save_aligned_mpp(exported, old_result)
    images = open_mpp_series(exported, check_cancelled=lambda: None)
    assert images[1].alignment.correspondence == evidence
    np.testing.assert_array_equal(images[1].data, old_result.frames[1].image.data)
    manifest, arrays = encode_session(state)
    del manifest['display']['method_profiles']
    legacy = decode_session(manifest, arrays)
    assert legacy.display.method_profiles == MethodProfiles()
    assert legacy.registration.correspondence_diagnostics == old_result.correspondence_diagnostics


def test_integer_radius_remains_a_portable_valid_parameter():
    from stmviewer.session_metadata import encode_session, decode_session
    from stmviewer.session_state import SessionState
    originals = frames()
    profiles = MethodProfiles(akaze=AkazeParameters(radius=3))
    movie = register_series(originals, method='akaze', method_profiles=profiles)
    manifest, arrays = encode_session(SessionState(originals, movie))
    restored = decode_session(manifest, arrays)
    assert restored.registration.correspondence_diagnostics == movie.correspondence_diagnostics
