"""LightGlue export preserves model provenance, measurements and manual geometry."""
import json
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.mpp import open_mpp_series
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.manual_movie import apply_movie_correction
from stmviewer.graph_application import apply_graph_to_movie
from test_manual_movie import cpu_result, corrected_trial
from test_lightglue_session import lightglue_evidence, lightglue_graph


@pytest.mark.parametrize('finite_fill', [False, True])
def test_chain_export_preserves_both_models_and_pixels_after_manual_edit(tmp_path, finite_fill):
    base = cpu_result()
    diagnostics = (None, lightglue_evidence(shape=base.frames[0].original.data.shape),
                   lightglue_evidence((-3., 2.), shape=base.frames[0].original.data.shape))
    base = replace(base, method='LightGlue + SuperPoint', correspondence_diagnostics=diagnostics)
    edited = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    path = tmp_path / 'lightglue.mpp'
    save_aligned_mpp(path, edited, wsxm_compatible=finite_fill)
    reopened = open_mpp_series(path, check_cancelled=lambda: None)
    assert reopened[1].alignment.correspondence == diagnostics[1]
    for expected, actual in zip(edited.frames, reopened, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.shift_xy == expected.shift_xy
    metadata = json.loads(path.with_name(path.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 11


def test_graph_export_retains_both_model_configurations_and_manual_positions(tmp_path):
    base = cpu_result()
    frames = tuple(item.original for item in base.frames)
    graph = lightglue_graph(frames)
    applied = apply_graph_to_movie(frames, graph, previous=base)
    edited = apply_movie_correction(applied, corrected_trial(applied, 1, 1, 0))
    path = tmp_path / 'lightglue-graph.mpp'
    save_aligned_mpp(path, edited)
    restored = open_mpp_series(path, check_cancelled=lambda: None)
    history = restored[1].alignment.manual_movie.graph_provenance
    assert history.config == graph.config
    assert dict(history.config.backend_settings)['extractor_weights_path'] == '/absent/superpoint_v1.pth'
    for image, expected in zip(restored, edited.frames, strict=True):
        np.testing.assert_array_equal(image.data, expected.image.data)
        assert image.alignment.shift_xy == expected.shift_xy
    sidecar = path.with_name(path.name + '.stmviewer.json')
    metadata = json.loads(sidecar.read_text())
    assert metadata['version'] == 11
    metadata['version'] = 10
    sidecar.write_text(json.dumps(metadata))
    declined = open_mpp_series(path, check_cancelled=lambda: None)
    assert declined[0].alignment is None
    assert 'V11' in declined[0].metadata_note
