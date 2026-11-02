"""RoMa exports retain global geometry, source provenance and missing samples."""
import json
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.mpp import open_mpp_series
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.manual_movie import apply_movie_correction
from stmviewer.graph_application import apply_graph_to_movie
from test_manual_movie import cpu_result, corrected_trial
from test_roma_session import roma_evidence, roma_graph


@pytest.mark.parametrize('manual', [False, True])
@pytest.mark.parametrize('finite_fill', [False, True])
def test_roma_chain_export_keeps_points_preparation_after_manual_edit(tmp_path, manual, finite_fill):
    base = cpu_result()
    diagnostics = (None, roma_evidence(shape=base.frames[0].original.data.shape),
                   roma_evidence((-3., 2.), shape=base.frames[0].original.data.shape))
    base = replace(base, method='RoMa v2', correspondence_diagnostics=diagnostics)
    corrected = apply_movie_correction(base, corrected_trial(base, 1, 1, 0)) if manual else base
    path = tmp_path / 'roma-corrected.mpp'
    save_aligned_mpp(path, corrected, wsxm_compatible=finite_fill)
    reopened = open_mpp_series(path, check_cancelled=lambda: None)
    assert reopened[1].alignment.correspondence == diagnostics[1]
    for expected, actual in zip(corrected.frames, reopened, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.shift_xy == expected.shift_xy
    metadata = json.loads(path.with_name(path.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 9


def test_roma_graph_export_restores_worker_configuration_and_manual_positions(tmp_path):
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    graph = roma_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    edited = apply_movie_correction(applied, corrected_trial(applied, 1, 1, 0))
    path = tmp_path / 'roma-graph.mpp'
    save_aligned_mpp(path, edited)
    restored = open_mpp_series(path, check_cancelled=lambda: None)
    history = restored[1].alignment.manual_movie.graph_provenance
    assert history.config == graph.config
    assert dict(history.config.backend_settings)['interpreter_path'] == '/absent/bin/python'
    for image, expected in zip(restored, edited.frames, strict=True):
        np.testing.assert_array_equal(image.data, expected.image.data)
        assert image.alignment.shift_xy == expected.shift_xy
    metadata = json.loads(path.with_name(path.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 9
