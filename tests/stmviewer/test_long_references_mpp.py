"""Exported long-reference movies keep compact, unambiguous provenance."""
import json

import numpy as np
import pytest

from test_long_references_session import extended_candidate
from test_manual_movie import corrected_trial
from stmviewer.graph_application import apply_graph_to_movie
from stmviewer.manual_movie import apply_movie_correction
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.mpp_metadata import mpp_sidecar_path
from stmviewer.series import open_frame_series


@pytest.mark.parametrize('finite_fill', [False, True])
def test_long_reference_mpp_preserves_choice_and_pairs_without_raw_graph_measurements(tmp_path, finite_fill):
    frames, graph = extended_candidate(robust=True)
    active = apply_graph_to_movie(frames, graph, robust_revision=graph.robust_trials[0].revision)
    active = apply_movie_correction(active, corrected_trial(active, 2, 1, 0))
    path = save_aligned_mpp(tmp_path / 'long-reference.mpp', active, wsxm_compatible=finite_fill)
    body = json.loads(mpp_sidecar_path(path).read_text())
    assert body['version'] == 6
    summary = body['manual_results'][0]['graph_provenance']
    assert summary['settings_version'] == 2
    extension = summary['extension']
    assert extension['base_revision'] == graph.extension.base.revision
    assert extension['base_robust_revision'] == graph.extension.base_robust_revision
    assert extension['references'] == [0]
    assert (extension['target_start'], extension['target_end']) == (3, 5)
    assert extension['base_pairs'] == [[e.i, e.j] for e in graph.extension.base.edges]
    assert extension['added_pairs'] == [[0, 4], [0, 5]]
    assert dict(extension['base_solver_settings'])['threshold_px'] == '2.0'
    assert extension['measurement_config']['pair_code_version'] == graph.config.pair_code_version
    assert extension['measurement_config']['code_version'] == 'extension-code'
    assert summary['config']['code_version'] == 'stored-code'
    assert 'edges' not in json.dumps(body) and 'residuals' not in json.dumps(body)
    loaded = open_frame_series([path])
    provenance = loaded[0].alignment.manual_movie.graph_provenance
    assert provenance.robust_revision == graph.robust_trials[0].revision
    assert provenance.extension.base_revision == graph.extension.base.revision
    for before, after in zip(active.frames, loaded, strict=True):
        np.testing.assert_array_equal(before.image.data, after.data)
        assert after.alignment.shift_xy == before.shift_xy
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState
    session = save_session(tmp_path / 'imported.stmsession', SessionState(loaded))
    reopened = load_session(session)
    assert reopened.graph is None and reopened.registration is None
    assert reopened.frames[0].alignment.manual_movie.graph_provenance == provenance


def test_deleted_long_reference_mpp_keeps_original_indices_and_rejects_changed_plan(tmp_path):
    import copy

    frames, graph = extended_candidate()
    active = apply_graph_to_movie(frames, graph).without_frame(0)
    path = save_aligned_mpp(tmp_path / 'deleted-reference.mpp', active, wsxm_compatible=True)
    loaded = open_frame_series([path])
    summary = loaded[0].alignment.manual_movie.graph_provenance
    assert summary.extension.references == (0,)
    assert len(summary.final_positions) == 6
    assert [frame.alignment.manual_frame_index for frame in loaded] == [1, 2, 3, 4, 5]
    assert summary.extension.base_robust_revision is None
    assert summary.extension.base_solver_settings == ()
    sidecar = mpp_sidecar_path(path)
    original = json.loads(sidecar.read_text())
    changes = (
        lambda e: e.update(settings_version=99),
        lambda e: e.update(base_revision=graph.revision),
        lambda e: e.update(references=[1]),
        lambda e: e.update(references=[0, 0]),
        lambda e: e.update(target_end=6),
        lambda e: e['base_pairs'].pop(),
        lambda e: e['added_pairs'].pop(),
        lambda e: e.update(base_robust_revision='not-without-solver-settings'),
        lambda e: e['measurement_config'].update(pair_code_version='sha256:' + 'c' * 64),
    )
    for change in changes:
        damaged = copy.deepcopy(original)
        change(damaged['manual_results'][0]['graph_provenance']['extension'])
        sidecar.write_text(json.dumps(damaged))
        ignored = open_frame_series([path])
        assert all(frame.alignment is None for frame in ignored)
        assert all('pominięto' in frame.metadata_note for frame in ignored)
        assert all(np.isfinite(frame.data).all() for frame in ignored)
