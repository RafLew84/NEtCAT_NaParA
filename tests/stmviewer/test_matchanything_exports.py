"""MatchAnything MPP export keeps measurements and geometry through manual edits."""
import json
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.mpp import open_mpp_series
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.manual_movie import apply_movie_correction
from stmviewer.graph_application import apply_graph_to_movie
from test_manual_movie import cpu_result, corrected_trial
from test_matchanything_session import matchanything_evidence, matchanything_graph


@pytest.mark.parametrize('finite_fill', [False, True])
def test_chain_export_keeps_preparation_after_manual_edit(tmp_path, finite_fill):
    base = cpu_result()
    diagnostics = (None, matchanything_evidence(shape=base.frames[0].original.data.shape),
                   matchanything_evidence((-3., 2.), shape=base.frames[0].original.data.shape))
    base = replace(base, method='MatchAnything-ELoFTR', correspondence_diagnostics=diagnostics)
    edited = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    path = tmp_path / 'matchanything.mpp'
    save_aligned_mpp(path, edited, wsxm_compatible=finite_fill)
    reopened = open_mpp_series(path, check_cancelled=lambda: None)
    assert reopened[1].alignment.correspondence == diagnostics[1]
    for expected, actual in zip(edited.frames, reopened, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.shift_xy == expected.shift_xy
    metadata = json.loads(path.with_name(path.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 10


def test_graph_export_retains_model_configuration_and_final_manual_positions(tmp_path):
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    graph = matchanything_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    edited = apply_movie_correction(applied, corrected_trial(applied, 1, 1, 0))
    path = tmp_path / 'matchanything-graph.mpp'
    save_aligned_mpp(path, edited)
    restored = open_mpp_series(path, check_cancelled=lambda: None)
    history = restored[1].alignment.manual_movie.graph_provenance
    assert history.config == graph.config
    assert dict(history.config.backend_settings)['model'] == 'MatchAnything-ELoFTR'
    for image, expected in zip(restored, edited.frames, strict=True):
        np.testing.assert_array_equal(image.data, expected.image.data)
        assert image.alignment.shift_xy == expected.shift_xy
    metadata = json.loads(path.with_name(path.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 10
