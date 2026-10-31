"""Hybrid aligned survives manual edits and the public MPP/AVI export boundaries."""

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial, remove_movie_correction
from stmviewer.manual_pair import ManualPairDraft
from stmviewer.registration import register_series
from deep_ecc_fixture import controlled_loftr as external_loftr, textured_pair
from make_registration_fixtures import frames_with_data

controlled_loftr = external_loftr
LABEL = 'Deep Matcher + ECC (v1)'


def hybrid_movie(controlled_loftr):
    control, weights = controlled_loftr
    first, second = textured_pair()
    _, third = textured_pair((-6.75, 8.5))
    originals = frames_with_data(first.data, second.data, third.data)
    control.shifts = [(19, -12), (-24.5, 21.6)]
    result = register_series(originals, method='deep_matcher_ecc',
                             deep_options=DeepMatcherOptions(weights, 'cpu'))
    return originals, result


def test_manual_movie_corrections_preserve_hybrid_diagnostics_as_history(controlled_loftr, tmp_path):
    originals, automatic = hybrid_movie(controlled_loftr)
    before = [f.data.tobytes() for f in originals]
    first = ManualPairDraft(*originals[:2], start=movie_pair_trial(automatic, 1))
    first.nudge(1, 0)
    corrected = apply_movie_correction(automatic, first.apply())
    second = ManualPairDraft(*originals[1:], start=movie_pair_trial(corrected, 2))
    second.nudge(0, -1)
    corrected = apply_movie_correction(corrected, second.apply())

    np.testing.assert_allclose([f.shift_xy for f in corrected.frames],
                               [(0, 0), (19.25, -12.5), (-5.75, 7.5)], atol=0.2)
    assert corrected.pair_diagnostics is automatic.pair_diagnostics
    assert corrected.pair_diagnostics[1].deep_shift_xy == (19, -12)
    assert corrected.pair_diagnostics[1].final_shift_xy == automatic.frames[1].shift_xy
    assert corrected.baseline is automatic.baseline
    assert corrected.method == LABEL and corrected.settings_version == 1
    assert [f.original is original for f, original in zip(corrected.frames, originals)] == [True] * 3
    assert [f.data.tobytes() for f in originals] == before
    assert all(f.status == 'manual_review' and f.quality_score is None for f in corrected.frames[1:])

    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.series import open_frame_series

    reopened = open_frame_series([save_aligned_mpp(tmp_path / 'corrected-hybrid.mpp', corrected)])
    history = reopened[-1].alignment.manual_movie
    assert len(history.corrections) == 2 and history.settings_version == 1
    assert [f.quality_score for f in history.baseline] == [1, None, None]
    assert history.corrections[0].source_label.startswith(LABEL)
    assert reopened[-1].alignment.method == LABEL
    assert reopened[-1].alignment.shift_xy == corrected.frames[-1].shift_xy
    assert reopened[-1].data.tobytes() == corrected.frames[-1].image.data.tobytes()

    restored = remove_movie_correction(remove_movie_correction(corrected, 2), 1)
    assert restored.pair_diagnostics is automatic.pair_diagnostics
    for actual, expected in zip(restored.frames, automatic.frames):
        assert actual.shift_xy == expected.shift_xy
        np.testing.assert_array_equal(actual.image.data, expected.image.data)


def test_hybrid_mpp_roundtrip_retains_samples_geometry_uncertainty_and_sources(controlled_loftr, tmp_path):
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.series import open_frame_series

    originals, result = hybrid_movie(controlled_loftr)
    for finite_fill in (False, True):
        path = save_aligned_mpp(tmp_path / f'hybrid-{finite_fill}.mpp', result,
                                wsxm_compatible=finite_fill)
        restored = open_frame_series([path])
        assert len(restored) == 3
        assert [f.measurement_time_s for f in restored] == [10, 20, 35]
        assert [f.provenance.source_frame_index for f in restored] == [0, 1, 2]
        assert [f.alignment.status for f in restored] == ['ok', 'manual_review', 'manual_review']
        assert [f.alignment.quality_score for f in restored] == [1, None, None]
        for actual, expected, original in zip(restored, result.frames, originals):
            np.testing.assert_array_equal(actual.data, expected.image.data)
            np.testing.assert_array_equal(np.isfinite(actual.data), expected.valid_mask)
            assert actual.data.shape == (150, 218)
            assert actual.alignment.method == LABEL and actual.alignment.device == 'CPU'
            assert actual.alignment.original_shape == (128, 192)
            assert actual.alignment.original_size_nm == (8, 9)
            assert actual.alignment.original_offset_nm == (2, -1)
            assert actual.alignment.shift_xy == expected.shift_xy
            assert actual.alignment.origin_xy == expected.origin_xy
            assert actual.alignment.reference.source_frame_index == 0
            assert actual.provenance.source == str(original.source)
            np.testing.assert_allclose((actual.size_x_nm, actual.size_y_nm), (218 / 24, 150 * 9 / 128))

    surviving = result.without_frame(1)
    reopened = open_frame_series([save_aligned_mpp(tmp_path / 'without-middle.mpp', surviving)])
    assert [f.measurement_time_s for f in reopened] == [10, 35]
    assert [f.provenance.source_frame_index for f in reopened] == [0, 2]
    assert reopened[-1].alignment.shift_xy == result.frames[-1].shift_xy
    assert reopened[-1].data.tobytes() == result.frames[-1].image.data.tobytes()


def test_hybrid_avi_encodes_aligned_once_with_same_frame_order_and_background(controlled_loftr, tmp_path):
    import cv2
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.avi_sources import aligned_movie_frames

    originals, result = hybrid_movie(controlled_loftr)
    data_before = [f.image.data.tobytes() for f in result.frames]
    source = aligned_movie_frames(originals, result)
    assert all(f.data is aligned.image.data for f, aligned in zip(source, result.frames))
    plan = prepare_avi(source, fps=7, codec='FFV1',
                       presentation=MoviePresentation(pixel_proportions=True, background=255))
    expected = [plan.render_frame(i) for i in range(3)]
    path = save_avi(tmp_path / 'hybrid.avi', plan)
    reader = cv2.VideoCapture(str(path))
    try:
        assert reader.isOpened()
        assert reader.get(cv2.CAP_PROP_FPS) == 7
        for raster, aligned in zip(expected, result.frames):
            ok, actual = reader.read()
            assert ok and actual.shape == (150, 218, 3)
            np.testing.assert_array_equal(actual, raster)
            assert np.all(actual[~aligned.valid_mask] == 255)
            assert np.ptp(actual[aligned.valid_mask]) == 255
        assert not reader.read()[0]
    finally:
        reader.release()
    assert [f.image.data.tobytes() for f in result.frames] == data_before
