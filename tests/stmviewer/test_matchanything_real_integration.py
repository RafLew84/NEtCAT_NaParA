"""Opt-in MatchAnything with actual pinned resources, original-pixel boundaries."""
from dataclasses import replace
import os
from pathlib import Path
import socket
import sys
from types import ModuleType
import urllib.request

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_MATCHANYTHING_ROOT'),
                               reason='Requires explicitly prepared local MatchAnything resources')


def original_frames(shape=(256, 256)):
    import cv2
    from stmviewer.series import open_frame_series
    h, w = shape
    rng = np.random.default_rng(20261102)
    image = cv2.GaussianBlur(rng.normal(0, 1, shape).astype(np.float32), (0, 0), 1.2)
    for _ in range(45):
        x, y = rng.integers(16, w-16), rng.integers(16, h-16)
        cv2.circle(image, (int(x), int(y)), int(rng.integers(3, 12)), float(rng.uniform(-1, 1)), -1)
    image = (image - image.min()) / (image.max() - image.min())
    template = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])[0]
    return tuple(replace(template, source_frame_index=i, data=np.asarray(cv2.warpAffine(image,
        np.array([[1, 0, dx], [0, 1, dy]], np.float32), (w, h)), dtype=np.float64))
        for i, (dx, dy) in enumerate(((0, 0), (7, -5), (-3, 4))))


def options(device='cpu'):
    root = Path(os.environ['STMVIEWER_TEST_MATCHANYTHING_ROOT'])
    return DeepMatcherOptions(root/'weights/matchanything_eloftr.ckpt', device, root/'source')


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_real_model_recovers_xy_without_network_or_global_src_import(device, monkeypatch):
    import torch
    from stmviewer.matchanything_matcher import load_matchanything_backend
    if device == 'cuda' and not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    torch.set_num_threads(4)
    def forbidden(*args, **kwargs):
        pytest.fail('The model attempted network access')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(torch.hub, 'load', forbidden)
    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', forbidden)
    sentinel = ModuleType('src')
    monkeypatch.setitem(sys.modules, 'src', sentinel)
    backend = load_matchanything_backend(options(device))
    try:
        frames = original_frames()
        result = backend.estimate(frames[0].data, frames[1].data, moving_frame_index=1)
        np.testing.assert_allclose(result.shift_xy, [-7, 5], atol=.2)
        assert backend.device.startswith(device.upper())
        assert dict(backend.last_diagnostics.model_provenance)['model'] == 'MatchAnything-ELoFTR'
    finally:
        backend.close()
    assert sys.modules['src'] is sentinel


def test_real_graph_and_pair_share_estimator_and_keep_edge_evidence():
    import torch
    from stmviewer.graph_registration import register_graph
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.graph_application import apply_graph_to_movie
    torch.set_num_threads(4)
    frames = original_frames()
    graph = register_graph(frames, method='matchanything_eloftr', deep_options=options())
    np.testing.assert_allclose(graph.positions, [(0, 0), (-7, 5), (3, -4)], atol=.3)
    assert all(edge.correspondence_diagnostics is not None for edge in graph.edges)
    assert all(edge.quality_score is None for edge in graph.edges)
    pair = estimate_pair(frames[0], frames[1], method='matchanything_eloftr', deep_options=options())
    np.testing.assert_allclose(graph.edges[0].shift_xy, pair.shift_xy, atol=1e-5)
    robust = solve_robust_graph(graph)
    np.testing.assert_allclose(robust.positions, graph.positions, atol=.01)
    applied = apply_graph_to_movie(frames, graph)
    np.testing.assert_allclose([frame.shift_xy for frame in applied.frames], graph.positions)


@pytest.mark.parametrize('shape', [(80, 80), (137, 219), (128, 256)])
def test_real_author_resize_of_non_square_images_preserves_known_translation(shape):
    import torch
    from stmviewer.matchanything_matcher import load_matchanything_backend
    torch.set_num_threads(4)
    frames = original_frames(shape)
    backend = load_matchanything_backend(options())
    try:
        result = backend.estimate(frames[0].data, frames[1].data, moving_frame_index=1)
        np.testing.assert_allclose(result.shift_xy, [-7, 5], atol=.5)
        assert backend.last_diagnostics.preparation[0].original_shape == shape
        assert backend.last_diagnostics.preparation[0].model_shape == (640, 640)
    finally:
        backend.close()


def test_real_chain_keeps_original_pixels_and_one_translation_per_frame():
    import torch
    from stmviewer.registration import register_series
    torch.set_num_threads(4)
    frames = original_frames()
    originals = [frame.data.copy() for frame in frames]
    result = register_series(frames, method='matchanything_eloftr', deep_options=options())
    np.testing.assert_allclose([frame.shift_xy for frame in result.frames],
                               [(0, 0), (-7, 5), (3, -4)], atol=.3)
    assert result.method == 'MatchAnything-ELoFTR'
    assert len(result.correspondence_diagnostics) == 3
    assert result.correspondence_diagnostics[0] is None
    for frame, before in zip(frames, originals):
        np.testing.assert_array_equal(frame.data, before)
    assert all(frame.quality_score is None for frame in result.frames[1:])


@pytest.mark.parametrize('shape', [(1024, 384), (16, 48)])
def test_author_preset_supports_large_and_small_originals_at_fixed_model_size(shape):
    import torch
    from stmviewer.matchanything_matcher import load_matchanything_backend
    torch.set_num_threads(4)
    backend = load_matchanything_backend(options())
    try:
        image = np.random.default_rng(20261102).random(shape)
        result = backend.estimate(image, image, moving_frame_index=1)
        np.testing.assert_allclose(result.shift_xy, [0., 0.], atol=.05)
        assert backend.last_diagnostics.preparation[0].model_shape == (640, 640)
    finally:
        backend.close()
