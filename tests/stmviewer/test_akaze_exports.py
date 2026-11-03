"""AKAZE MPP export preserves original values, corrections and CPU provenance."""
import json
from dataclasses import replace
import numpy as np
import pytest

from stmviewer.graph_application import apply_graph_to_movie
from stmviewer.graph_registration import register_graph
from stmviewer.manual_movie import apply_movie_correction
from stmviewer.mpp import open_mpp_series
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.registration import register_series
from test_akaze_integration import frames
from test_manual_movie import corrected_trial


@pytest.mark.parametrize('graph_result', [False, True])
@pytest.mark.parametrize('finite_fill', [False, True])
def test_akaze_mpp_roundtrip_and_version_guard(tmp_path, graph_result, finite_fill):
    originals = frames()
    base = register_series(originals, method='akaze')
    graph = register_graph(originals, method='akaze') if graph_result else None
    result = apply_graph_to_movie(originals, graph, previous=base) if graph is not None else base
    corrected = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    path = tmp_path/'akaze.mpp'
    save_aligned_mpp(path, corrected, wsxm_compatible=finite_fill)
    loaded = open_mpp_series(path, check_cancelled=lambda: None)
    for actual, expected in zip(loaded, corrected.frames, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.shift_xy == expected.shift_xy
        assert actual.provenance.source_frame_index == expected.original.source_frame_index
    if graph is not None:
        assert loaded[1].alignment.manual_movie.graph_provenance.config == graph.config
    else:
        assert loaded[1].alignment.correspondence == base.correspondence_diagnostics[1]
    sidecar = path.with_name(path.name+'.stmviewer.json')
    metadata = json.loads(sidecar.read_text())
    assert metadata['version'] == 12
    metadata['version'] = 11
    sidecar.write_text(json.dumps(metadata))
    rejected = open_mpp_series(path, check_cancelled=lambda: None)
    assert rejected[0].alignment is None
    assert 'V12' in rejected[0].metadata_note
