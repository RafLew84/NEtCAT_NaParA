"""Applied method-aware graphs export final pixels and truthful compact provenance."""
from dataclasses import replace
import json

import numpy as np
import pytest

from test_graph_methods_session import method_graph
from test_manual_movie import cpu_result, corrected_trial
from stmviewer.graph_application import apply_graph_to_movie
from stmviewer.manual_movie import apply_movie_correction
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.mpp_metadata import mpp_sidecar_path
from stmviewer.series import open_frame_series


@pytest.mark.parametrize('finite_fill', [False, True])
def test_cpu_graph_mpp_keeps_method_manual_changes_deleted_frames_and_samples(tmp_path, finite_fill):
    chain = cpu_result()
    frames = tuple(item.original for item in chain.frames)
    graph = method_graph(frames)
    applied = apply_graph_to_movie(frames, graph)
    edited = apply_movie_correction(applied, corrected_trial(applied, 2, 0, 1))
    movie = edited.without_frame(1)
    path = save_aligned_mpp(tmp_path / 'flow.mpp', movie, wsxm_compatible=finite_fill)
    loaded = open_frame_series([path])
    body = json.loads(mpp_sidecar_path(path).read_text())
    assert body['version'] == 7
    assert 'edges' not in json.dumps(body)
    assert [frame.alignment.manual_frame_index for frame in loaded] == [0, 2]
    for before, after in zip(movie.frames, loaded, strict=True):
        np.testing.assert_array_equal(before.image.data, after.data)
        assert after.alignment.original_rect == before.original_rect
        assert after.alignment.method == 'Optical Flow — graf equal-ls-v1'
        assert after.alignment.manual_movie.corrections == edited.corrections
        history = after.alignment.manual_movie.graph_provenance
        assert history.settings_version == 3
        assert history.config == graph.config
        assert history.final_positions == ((0., 0.), (2., -1.), (-1., 2.))
    from stmviewer.session_archive import save_session, load_session
    from stmviewer.session_state import SessionState
    restored = load_session(save_session(tmp_path / 'imported.stmsession', SessionState(loaded)))
    assert restored.registration is None
    assert restored.frames[0].alignment.manual_movie.graph_provenance.config == graph.config


def test_composite_huber_mpp_keeps_method_and_solver_but_not_raw_pair_diagnostics(tmp_path):
    from test_graph_methods_session import composite_graph
    from test_robust_graph_session import exact_variant

    frames = tuple(item.original for item in cpu_result().frames)
    graph = composite_graph(frames)
    variant = exact_variant(graph)
    graph = replace(graph, robust_trials=(variant,))
    active = apply_graph_to_movie(frames, graph, robust_revision=variant.revision)
    path = save_aligned_mpp(tmp_path / 'ecc-huber.mpp', active)
    loaded = open_frame_series([path])
    assert loaded[0].alignment.method == 'Deep Matcher + ECC (v1) — graf block-huber-irls-v1'
    summary = loaded[0].alignment.manual_movie.graph_provenance
    assert summary.config == graph.config
    assert summary.solver == 'block-huber-irls-v1'
    assert summary.robust_revision == variant.revision
    assert summary.final_positions == variant.positions
    body = mpp_sidecar_path(path).read_text()
    assert 'hybrid_diagnostics' not in body and 'edges' not in body
    for before, after in zip(active.frames, loaded, strict=True):
        np.testing.assert_array_equal(before.image.data, after.data)


def test_mpp_rejects_withdrawn_or_downgraded_method_aware_sidecar(tmp_path):
    from copy import deepcopy

    frames = tuple(item.original for item in cpu_result().frames)
    active = apply_graph_to_movie(frames, method_graph(frames))
    path = save_aligned_mpp(tmp_path / 'methods.mpp', active)
    sidecar = mpp_sidecar_path(path)
    valid = json.loads(sidecar.read_text())
    for version in (5, 6):
        damaged = deepcopy(valid)
        damaged['version'] = version
        sidecar.write_text(json.dumps(damaged))
        loaded = open_frame_series([path])
        assert all(frame.alignment is None for frame in loaded)
        assert all('pominięto' in frame.metadata_note for frame in loaded)
