"""Final graph movies export samples and provenance without editable graph state."""
import json

import numpy as np
import pytest

from test_graph_application_session import graph_movie
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.mpp_metadata import mpp_sidecar_path
from stmviewer.series import open_frame_series


@pytest.mark.parametrize('finite_fill', [False, True])
def test_graph_mpp_keeps_final_samples_frozen_base_and_model_solver_provenance(tmp_path, finite_fill):
    frames, graph, chain, edited = graph_movie()
    path = save_aligned_mpp(tmp_path / 'graph.mpp', edited, wsxm_compatible=finite_fill)
    loaded = open_frame_series([path])
    body = json.loads(mpp_sidecar_path(path).read_text())
    assert body['version'] == 5
    assert len(body['manual_results']) == 1
    assert 'edges' not in json.dumps(body)
    for expected, actual in zip(edited.frames, loaded, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.original_rect == expected.original_rect
        assert actual.alignment.shift_xy == expected.shift_xy
        assert actual.alignment.manual_movie.baseline == edited.baseline
        assert actual.alignment.manual_movie.corrections == edited.corrections
    provenance = loaded[0].alignment.manual_movie.graph_provenance
    assert provenance.config == graph.config
    assert provenance.graph_revision == graph.revision
    assert provenance.robust_revision is None
    assert provenance.solver == 'equal-ls-v1'
    assert provenance.final_positions == ((0., 0.), (2., -1.), (-1., 2.))
    assert loaded[0].alignment.manual_movie is loaded[1].alignment.manual_movie
    # Import is a new movie of final samples, with provenance only.
    from stmviewer.session_archive import save_session, load_session
    from stmviewer.session_state import SessionState
    saved = save_session(tmp_path / 'imported.stmsession', SessionState(loaded))
    reopened = load_session(saved)
    assert reopened.registration is None and reopened.graph is None
    assert reopened.frames[0].alignment.manual_movie.graph_provenance == provenance


def test_deleted_graph_mpp_keeps_full_history_and_rejects_inconsistent_sidecar(tmp_path):
    import copy

    frames, graph, chain, edited = graph_movie()
    surviving = edited.without_frame(1)
    path = save_aligned_mpp(tmp_path / 'deleted.mpp', surviving, wsxm_compatible=True)
    loaded = open_frame_series([path])
    assert [frame.alignment.manual_frame_index for frame in loaded] == [0, 2]
    assert loaded[1].alignment.manual_movie.baseline == edited.baseline
    assert loaded[1].alignment.manual_movie.corrections == edited.corrections
    assert loaded[1].alignment.manual_movie.graph_provenance.final_positions == ((0., 0.), (2., -1.), (-1., 2.))
    np.testing.assert_array_equal(loaded[1].data, edited.frames[2].image.data)
    sidecar = mpp_sidecar_path(path)
    original = json.loads(sidecar.read_text())
    changes = (
        lambda p: p['config'].update(device='unrelated-device'),
        lambda p: p['final_positions'].__setitem__(2, [99., 0.]),
        lambda p: p.update(solver='not-a-solver'),
        lambda p: p['config'].update(weights_sha256='not-a-digest'),
    )
    for change in changes:
        damaged = copy.deepcopy(original)
        change(damaged['manual_results'][0]['graph_provenance'])
        sidecar.write_text(json.dumps(damaged))
        ignored = open_frame_series([path])
        assert all(frame.alignment is None and frame.provenance is None for frame in ignored)
        assert all('pominięto' in frame.metadata_note for frame in ignored)
        assert all(np.isfinite(frame.data).all() for frame in ignored)


def test_huber_mpp_retains_chosen_threshold_without_graph_diagnostics(tmp_path):
    from test_robust_graph_session import outlier_session_graph
    from stmviewer.graph_application import apply_graph_to_movie

    frames, graph = outlier_session_graph()
    variant = graph.robust_trials[0]
    active = apply_graph_to_movie(frames, graph, robust_revision=variant.revision)
    path = save_aligned_mpp(tmp_path / 'huber.mpp', active)
    restored = open_frame_series([path])
    summary = restored[0].alignment.manual_movie.graph_provenance
    assert summary.robust_revision == variant.revision
    assert summary.solver == 'block-huber-irls-v1'
    assert dict(summary.solver_settings)['threshold_px'] == '2.0'
    assert summary.final_positions == variant.positions
    assert tuple(item.shift_xy for item in restored[0].alignment.manual_movie.baseline) == variant.positions
    body = json.loads(mpp_sidecar_path(path).read_text())
    assert 'residuals' not in json.dumps(body) and 'edges' not in json.dumps(body)
