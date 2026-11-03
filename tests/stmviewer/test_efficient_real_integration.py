"""Opt-in real EfficientLoFTR, exercised through the public application boundaries."""
from dataclasses import replace
import os
from pathlib import Path
import urllib.request

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.pair_comparison import estimate_pair
from stmviewer.series import open_frame_series

pytestmark = pytest.mark.skipif(
    not os.environ.get('STMVIEWER_TEST_EFFICIENT_ROOT'),
    reason='Requires the explicitly prepared local EfficientLoFTR source/checkpoint',
)


def original_frames():
    import cv2
    rng = np.random.default_rng(20261102)
    original = cv2.GaussianBlur(rng.random((256, 256), dtype=np.float32), (0, 0), 2)
    for _ in range(55):
        x, y = rng.integers(16, 240, size=2)
        cv2.circle(original, (int(x), int(y)), int(rng.integers(3, 13)),
                   float(rng.uniform(.05, .95)), -1)
    original = cv2.GaussianBlur(original, (0, 0), .6)
    template = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])[0]
    return tuple(replace(template, source_frame_index=index,
                         data=np.asarray(cv2.warpAffine(original,
                             np.array([[1, 0, dx], [0, 1, dy]], np.float32), (256, 256)),
                             dtype=np.float64))
                 for index, (dx, dy) in enumerate(((0, 0), (7, -5), (-3, 4))))


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_real_efficient_pair_recovers_known_shift_without_network(device, monkeypatch):
    import torch
    if device == 'cuda' and not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    torch.set_num_threads(4)
    def forbidden(*args, **kwargs):
        pytest.fail('The model attempted network access')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(torch.hub, 'download_url_to_file', forbidden)
    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', forbidden)
    root = Path(os.environ['STMVIEWER_TEST_EFFICIENT_ROOT'])
    options = DeepMatcherOptions(root / 'weights/eloftr_outdoor.ckpt', device, root / 'source')
    frames = original_frames()
    trial = estimate_pair(frames[0], frames[1], method='efficient_loftr', deep_options=options)
    np.testing.assert_allclose(trial.shift_xy, (-7, 5), atol=.2)
    assert trial.status == 'manual_review' and trial.quality_score is None
    assert trial.device.startswith(device.upper())
    assert trial.correspondence is not None
    assert sum(trial.correspondence.reference_support) == trial.correspondence.inlier_count
    assert dict(trial.correspondence.model_provenance)['weights_sha256'] == (
        '0af6291141c736e75e94b7f8aae4399b77c7731b3f08758212b2cfe370188878')


def test_real_efficient_chain_preserves_originals_and_pair_evidence():
    import torch
    from stmviewer.registration import register_series
    torch.set_num_threads(4)
    root = Path(os.environ['STMVIEWER_TEST_EFFICIENT_ROOT'])
    options = DeepMatcherOptions(root / 'weights/eloftr_outdoor.ckpt', 'cpu', root / 'source')
    frames = original_frames()
    before = [frame.data.copy() for frame in frames]
    result = register_series(frames, method='efficient_loftr', deep_options=options)
    np.testing.assert_allclose([frame.shift_xy for frame in result.frames],
                               [(0, 0), (-7, 5), (3, -4)], atol=.3)
    assert len(result.correspondence_diagnostics) == 3
    assert result.correspondence_diagnostics[0] is None
    assert all(diagnostic is not None for diagnostic in result.correspondence_diagnostics[1:])
    assert all(frame.quality_score is None for frame in result.frames[1:])
    for frame, original in zip(frames, before, strict=True):
        np.testing.assert_array_equal(frame.data, original)


def test_real_efficient_graph_uses_same_pair_estimator_and_unweighted_huber():
    import torch
    from stmviewer.graph_registration import register_graph
    from stmviewer.graph_application import apply_graph_to_movie
    from stmviewer.robust_graph import solve_robust_graph
    torch.set_num_threads(4)
    root = Path(os.environ['STMVIEWER_TEST_EFFICIENT_ROOT'])
    options = DeepMatcherOptions(root / 'weights/eloftr_outdoor.ckpt', 'cpu', root / 'source')
    frames = original_frames()
    trial = register_graph(frames, method='efficient_loftr', deep_options=options)
    np.testing.assert_allclose(trial.positions, [(0, 0), (-7, 5), (3, -4)], atol=.3)
    pair = estimate_pair(frames[0], frames[1], method='efficient_loftr', deep_options=options)
    np.testing.assert_allclose(trial.edges[0].shift_xy, pair.shift_xy, atol=1e-5)
    assert all(edge.quality_score is None for edge in trial.edges)
    assert all(edge.correspondence_diagnostics is not None for edge in trial.edges)
    robust = solve_robust_graph(trial)
    np.testing.assert_allclose(robust.positions, trial.positions, atol=.01)
    applied = apply_graph_to_movie(frames, trial)
    np.testing.assert_allclose([frame.shift_xy for frame in applied.frames], trial.positions)
    assert applied.graph_application.graph == trial
