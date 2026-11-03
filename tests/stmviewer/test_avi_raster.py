"""Movie rasters checked against small, independently worked patterns."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from stmviewer.frame import ImageFrame
from stmviewer.avi_raster import MoviePresentation, movie_geometry, render_movie_frame


def frame(data, **metadata):
    return ImageFrame(Path('source.stp'), np.array(data, dtype=np.float64), {},
                      None, None, metadata.get('size_x_nm'), metadata.get('size_y_nm'),
                      None, None, None, None, None)


def test_gamma_missing_constant_and_empty_frames_keep_samples_and_edges():
    source = frame([[0, 1, 4], [np.nan, np.inf, -np.inf], [4, 1, 0]])
    options = MoviePresentation(gamma=2)
    geometry = movie_geometry((source,), options)
    raster = render_movie_frame(source, options, geometry)
    expected = np.array([[0, 127, 255, 0], [0, 0, 0, 0],
                         [255, 127, 0, 0], [0, 0, 0, 0]], dtype=np.uint8)
    assert raster.dtype == np.uint8 and raster.shape == (4, 4, 3)
    np.testing.assert_array_equal(raster, np.repeat(expected[:, :, None], 3, axis=2))
    constant = replace(source, data=np.full((3, 3), 7.0))
    assert np.all(render_movie_frame(constant, options, geometry)[:3, :3] == 180)
    empty = replace(source, data=np.full((3, 3), np.nan))
    assert not render_movie_frame(empty, options, geometry).any()
    assert np.isnan(source.data[1, 0])


def test_shared_physical_scale_expands_pixels_and_mask_without_cropping():
    source = frame([[0, np.nan, 4], [4, 1, 0]], size_x_nm=6, size_y_nm=2)
    options = MoviePresentation()
    geometry = movie_geometry((source, source), options)
    assert geometry.image_size == (6, 2) and geometry.physical
    expected = np.array([[0, 0, 0, 0, 255, 255], [255, 255, 63, 63, 0, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(render_movie_frame(source, options, geometry)[:, :, 0], expected)
    for other in (replace(source, size_x_nm=3), replace(source, size_y_nm=None)):
        fallback = movie_geometry((source, other), options)
        assert fallback.image_size == (3, 2) and not fallback.physical
    pixels = movie_geometry((source,), MoviePresentation(pixel_proportions=True))
    assert pixels.image_size == (3, 2) and not pixels.physical
    vertical = replace(source, size_x_nm=3, size_y_nm=4)
    assert movie_geometry((vertical,), options).image_size == (3, 4)


@pytest.mark.parametrize('background', [0, 128, 255])
@pytest.mark.parametrize('gamma, middle', [(1, 63), (2, 127)])
def test_selected_background_is_unchanged_by_gamma_and_fills_padding(background, gamma, middle):
    source = frame([[0, 1, 4], [np.nan, np.inf, -np.inf], [4, 1, 0]],
                   size_x_nm=6, size_y_nm=3)
    options = MoviePresentation(gamma=gamma, background=background)
    geometry = movie_geometry((source,), options)
    expected = np.array([[0, 0, middle, middle, 255, 255],
                         [background] * 6,
                         [255, 255, middle, middle, 0, 0],
                         [background] * 6], dtype=np.uint8)
    raster = render_movie_frame(source, options, geometry)
    np.testing.assert_array_equal(raster, np.repeat(expected[:, :, None], 3, axis=2))
    empty = replace(source, data=np.full((3, 3), np.nan))
    assert np.all(render_movie_frame(empty, options, geometry) == background)
    assert np.isnan(source.data[1, 0])


def test_movie_contrast_uses_only_selected_finite_measurements():
    from stmviewer.avi_export import prepare_avi
    from stmviewer.avi_raster import movie_contrast_levels
    images = (frame([[-1000, 1000, np.nan]]), frame([[100, 125, np.nan]]),
              frame([[125, 200, np.inf]]), frame([[np.nan, -np.inf, np.nan]]))
    options = MoviePresentation(contrast='movie', background=128)
    plan = prepare_avi(images, start=2, end=4, presentation=options)
    levels = movie_contrast_levels(plan.frames)
    assert levels == (100, 200)
    expected = (np.array([[0, 63, 128, 128], [128] * 4], dtype=np.uint8),
                np.array([[63, 255, 128, 128], [128] * 4], dtype=np.uint8),
                np.full((2, 4), 128, dtype=np.uint8))
    for image, wanted in zip(plan.frames, expected, strict=True):
        actual = render_movie_frame(image, options, plan.geometry, contrast_limits=levels)
        np.testing.assert_array_equal(actual[:, :, 0], wanted)
    per_frame = MoviePresentation(background=128)
    assert render_movie_frame(images[1], per_frame, plan.geometry)[0, 1, 0] == 255
    assert render_movie_frame(images[2], per_frame, plan.geometry)[0, 0, 0] == 0


@pytest.mark.parametrize('contrast', ['per_frame', 'movie'])
def test_constant_and_missing_movie_has_defined_levels(contrast):
    from stmviewer.avi_raster import movie_contrast_levels
    images = (frame([[7, np.nan, 7]]), frame([[np.nan, np.inf, -np.inf]]))
    options = MoviePresentation(gamma=2, background=255, contrast=contrast)
    geometry = movie_geometry(images, options)
    levels = movie_contrast_levels(images)
    assert levels == (7, 7)
    first = render_movie_frame(images[0], options, geometry, contrast_limits=levels)
    np.testing.assert_array_equal(first[:, :, 0], [[180, 255, 180, 255], [255] * 4])
    assert np.all(render_movie_frame(images[1], options, geometry, contrast_limits=levels) == 255)
    empty_levels = movie_contrast_levels((images[1],))
    assert empty_levels is None
    assert np.all(render_movie_frame(images[1], options, geometry, contrast_limits=empty_levels) == 255)


def test_shared_contrast_handles_finite_float_extremes():
    from stmviewer.avi_raster import movie_contrast_levels
    largest = np.finfo(np.float64).max
    image = frame([[-largest, 0, largest]])
    options = MoviePresentation(gamma=2, contrast='movie')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        raster = render_movie_frame(image, options, movie_geometry((image,), options),
                                    contrast_limits=movie_contrast_levels((image,)))
    np.testing.assert_array_equal(raster[0, :, 0], [0, 180, 255, 0])
