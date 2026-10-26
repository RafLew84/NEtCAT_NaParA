"""Movie rasters checked against small, independently worked patterns."""
from dataclasses import replace
from pathlib import Path

import numpy as np

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
