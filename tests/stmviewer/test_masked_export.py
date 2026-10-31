"""Registration selections never erase measured pixels in saved movies."""

from dataclasses import replace

import numpy as np

from make_mask_fixtures import artefact_arrays
from make_registration_fixtures import frames_with_data
from stmviewer.mpp_export import save_aligned_mpp, save_original_mpp
from stmviewer.registration import register_series
from stmviewer.registration_masks import FrameMask, MaskRectangle
from stmviewer.series import open_frame_series


def masked_result():
    originals = tuple(replace(frame, size_x_nm=160, size_y_nm=192)
                      for frame in frames_with_data(*artefact_arrays()))
    omitted = FrameMask((MaskRectangle(0, 0, 80, 12, 'omit'),))
    result = register_series(originals, method='masked_correlation', masks=(omitted,) * 3)
    return originals, result


def test_masked_alignment_mpp_preserves_artifact_samples_and_geometry(tmp_path):
    originals, result = masked_result()
    assert [frame.shift_xy for frame in result.frames] == [(0, 0), (-4, 3), (-7, 1)]
    assert result.canvas_shape == (67, 87)
    aligned_path = save_aligned_mpp(tmp_path / 'masked.mpp', result, wsxm_compatible=True)
    restored = open_frame_series([aligned_path])
    for index, (source, aligned, saved, origin) in enumerate(zip(
            originals, result.frames, restored, [(7, 0), (3, 3), (0, 1)], strict=True)):
        x, y = origin
        # All input samples survive, especially the excluded 12-row bright/noisy band.
        np.testing.assert_array_equal(saved.data[y:y + 64, x:x + 80], source.data)
        np.testing.assert_array_equal(saved.data[y:y + 12, x:x + 80], artefact_arrays()[index][:12])
        np.testing.assert_array_equal(saved.data, aligned.image.data)
        np.testing.assert_array_equal(np.isfinite(saved.data), aligned.valid_mask)
        assert (saved.size_x_nm, saved.size_y_nm) == (174, 201)
        assert saved.measurement_time_s == (10, 20, 35)[index]
        assert saved.alignment.method == result.method
        assert 'maski włączone' in saved.alignment.method
        assert saved.alignment.shift_xy == [(0, 0), (-4, 3), (-7, 1)][index]
        assert saved.alignment.original_rect == (x, y, 80, 64)
        if index:
            assert saved.alignment.status == 'manual_review' and saved.alignment.quality_score is None
    input_path = save_original_mpp(tmp_path / 'original.mpp', originals)
    for source, saved in zip(originals, open_frame_series([input_path]), strict=True):
        np.testing.assert_array_equal(saved.data, source.data)
        assert saved.alignment is None


def test_masked_avi_retains_excluded_band_and_contains_no_colored_overlay(tmp_path):
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.avi_sources import aligned_movie_frames
    from test_avi_export import decode

    originals, result = masked_result()
    options = MoviePresentation(gamma=1.5, pixel_proportions=True, background=128)
    source_plan = prepare_avi(originals, fps=7, codec='FFV1', presentation=options)
    aligned_plan = prepare_avi(aligned_movie_frames(originals, result), fps=7, codec='FFV1',
                               presentation=options)
    source_fps, source_images = decode(save_avi(tmp_path / 'source.avi', source_plan))
    aligned_fps, aligned_images = decode(save_avi(tmp_path / 'aligned.avi', aligned_plan))
    assert source_fps == aligned_fps == 7
    assert len(source_images) == len(aligned_images) == 3
    for original, aligned, origin in zip(source_images, aligned_images,
                                         [(7, 0), (3, 3), (0, 1)], strict=True):
        assert aligned.shape == (68, 88, 3)
        x, y = origin
        np.testing.assert_array_equal(aligned[y:y + 64, x:x + 80], original)
        assert np.unique(aligned[y:y + 12, x:x + 80, 0]).size > 100
        np.testing.assert_array_equal(aligned[:, :, 0], aligned[:, :, 1])
        np.testing.assert_array_equal(aligned[:, :, 0], aligned[:, :, 2])
    for frame, source in zip(result.frames, originals, strict=True):
        np.testing.assert_array_equal(frame.original.data, source.data)
