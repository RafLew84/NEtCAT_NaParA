"""Opt-in public pair, movie and graph routes with the actual isolated RoMa model."""
from dataclasses import replace
import os

import numpy as np
import pytest

from test_efficient_real_integration import original_frames
from stmviewer.graph_application import apply_graph_to_movie
from stmviewer.graph_registration import register_graph
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import register_series
from stmviewer.roma_matcher import default_roma_options
from stmviewer.robust_graph import solve_robust_graph

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_ROMA'),
                               reason='Requires prepared local netcat-romav2 and verified weights')


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_real_roma_pair_preserves_known_original_pixel_shift(device):
    frames = original_frames()
    options = replace(default_roma_options(), device=device)
    trial = estimate_pair(frames[0], frames[1], method='roma_v2', deep_options=options)
    np.testing.assert_allclose(trial.shift_xy, (-7., 5.), atol=.2)
    assert trial.method == 'roma_v2' and trial.device.startswith(device.upper())
    assert trial.status == 'manual_review' and trial.quality_score is None
    evidence = trial.correspondence
    assert evidence is not None and evidence.settings_version == 2
    assert len(evidence.preparation) == 2 and all(p.channels == 3 for p in evidence.preparation)
    provenance = dict(evidence.model_provenance)
    assert provenance['weights_sha256'] == '1557dec0d21b62366465f7ff4d5fdf228cc695d0582e196ad2b80e05230828b7'
    assert provenance['preset'] == 'turbo'


def test_real_roma_chain_preserves_originals_and_known_accumulated_xy():
    frames = original_frames()
    snapshots = tuple(frame.data.copy() for frame in frames)
    options = replace(default_roma_options(), device='cpu')
    result = register_series(frames, method='roma_v2', deep_options=options)
    np.testing.assert_allclose([frame.shift_xy for frame in result.frames],
                               [(0., 0.), (-7., 5.), (3., -4.)], atol=.3)
    assert result.method == 'RoMa v2'
    assert len(result.correspondence_diagnostics) == len(frames)
    assert result.correspondence_diagnostics[0] is None
    assert all(d is not None for d in result.correspondence_diagnostics[1:])
    for frame, before in zip(frames, snapshots, strict=True):
        np.testing.assert_array_equal(frame.data, before)


def test_real_roma_graph_uses_same_pair_measurement_and_common_ls_huber():
    frames = original_frames()
    options = replace(default_roma_options(), device='cpu')
    graph = register_graph(frames, method='roma_v2', deep_options=options)
    np.testing.assert_allclose(graph.positions, [(0., 0.), (-7., 5.), (3., -4.)], atol=.3)
    pair = estimate_pair(frames[0], frames[1], method='roma_v2', deep_options=options)
    np.testing.assert_allclose(graph.edges[0].shift_xy, pair.shift_xy, atol=1e-5)
    assert all(edge.quality_score is None and edge.correspondence_diagnostics is not None
               for edge in graph.edges)
    robust = solve_robust_graph(graph)
    np.testing.assert_allclose(robust.positions, graph.positions, atol=.01)
    applied = apply_graph_to_movie(frames, graph)
    np.testing.assert_allclose([frame.shift_xy for frame in applied.frames], graph.positions)
    assert applied.graph_application.graph == graph
