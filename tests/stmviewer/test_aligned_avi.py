"""Existing aligned samples, masks and geometry survive AVI export unchanged."""
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series
from test_avi_export import decode
from test_mpp_export_window import FIXTURES


@pytest.mark.parametrize('codec', ['MJPG', 'FFV1'])
@pytest.mark.parametrize('scale', ['common', 'unknown', 'pixel-override'])
def test_export_uses_frozen_aligned_samples_and_scale_after_deletion(tmp_path, codec, scale):
    originals = tuple(replace(f, size_x_nm=96, size_y_nm=32) for f in open_frame_series(
        [FIXTURES / 'registration/integer.mpp']))
    if scale == 'unknown':
        originals = tuple(replace(f, size_x_nm=None) for f in originals)
    result = register_series(originals)
    before = [(f.image.data.tobytes(), f.valid_mask.tobytes(), f.original.data.tobytes()) for f in result.frames]
    surviving = result.without_frame(0)
    frames = tuple(f.image for f in surviving.frames)
    plan = prepare_avi(frames, start=2, end=2, fps=11, codec=codec, presentation=MoviePresentation(
        gamma=2, background=255, contrast='movie', pixel_proportions=scale == 'pixel-override'))
    # A later registration has its own canvas. The pending movie keeps the old one.
    newer = register_series(originals[1:])
    assert newer.canvas_shape != result.canvas_shape
    path = save_avi(tmp_path / 'aligned.avi', plan)
    fps, images = decode(path)
    assert fps == 11 and len(images) == 1
    expected = np.full((34, 53), 255, dtype=np.uint8)
    data = originals[2].data
    expected[1:33, :48] = (np.sqrt((data - data.min()) / (data.max() - data.min())) * 255).astype(np.uint8)
    if scale == 'common':
        expected = np.repeat(expected, 2, axis=1)
        assert plan.geometry.physical
    else:
        expected = np.pad(expected, ((0, 0), (0, 1)), constant_values=255)
        assert not plan.geometry.physical
    actual = images[0]
    assert actual.shape == (*expected.shape, 3)
    difference = np.abs(actual[:, :, 0].astype(int) - expected)
    assert (difference.max() <= 1) if codec == 'FFV1' else (difference.mean() < 5)
    assert [(f.image.data.tobytes(), f.valid_mask.tobytes(), f.original.data.tobytes())
            for f in result.frames] == before
    assert result.canvas_shape == (34, 53)
    assert result.frames[2].origin_xy == (0, 1)


def test_subpixel_aligned_is_rendered_without_resampling_measurements(tmp_path):
    result = register_series(open_frame_series([FIXTURES / 'registration/subpixel.mpp']))
    aligned = result.frames[1]
    assert any(abs(v - round(v)) > 0.01 for v in aligned.shift_xy)
    before = aligned.image.data.tobytes()
    plan = prepare_avi((aligned.image,), codec='FFV1', presentation=MoviePresentation(
        pixel_proportions=True, background=128))
    _, images = decode(save_avi(tmp_path / 'subpixel.avi', plan))
    actual = images[0][:, :, 0]
    h, w = aligned.image.data.shape
    assert actual.shape == (h + h % 2, w + w % 2)
    assert np.all(actual[:h, :w][~aligned.valid_mask] == 128)
    if h % 2:
        assert np.all(actual[h:] == 128)
    if w % 2:
        assert np.all(actual[:, w:] == 128)
    values = aligned.image.data[aligned.valid_mask]
    expected = (255 * (values - values.min()) / (values.max() - values.min())).astype(np.uint8)
    assert np.max(np.abs(actual[:h, :w][aligned.valid_mask].astype(int) - expected)) <= 1
    assert aligned.image.data.tobytes() == before
