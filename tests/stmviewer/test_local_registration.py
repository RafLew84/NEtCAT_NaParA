"""Local registration through public pair and movie APIs."""

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.pair_comparison import estimate_pair
from deep_ecc_fixture import controlled_loftr as model_fixture, textured_pair

controlled_loftr = model_fixture
METHOD = 'deep_local_consensus'


def test_pair_keeps_exact_deep_start_and_reports_spatially_supported_translation(controlled_loftr):
    control, weights = controlled_loftr
    frames = textured_pair()
    originals = [frame.data.copy() for frame in frames]

    trial = estimate_pair(*frames, method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'))

    np.testing.assert_allclose(trial.shift_xy, (18.25, -12.5), atol=0.35)
    assert trial.local.deep_shift_xy == (19.0, -12.0)
    assert trial.local.final_shift_xy == trial.shift_xy
    assert trial.status == 'manual_review' and trial.quality_score is None
    assert sum(patch.status == 'inlier' for patch in trial.local.patches) >= 4
    assert trial.local.actual_device == 'CPU'
    assert str(weights) in trial.settings_text
    assert control.loaded == 1 and control.calls == 1
    for frame, original in zip(frames, originals):
        np.testing.assert_array_equal(frame.data, original)


def test_series_uses_local_pair_results_and_keeps_evidence_when_removing_a_frame(controlled_loftr):
    from stmviewer.registration import register_series
    from make_registration_fixtures import frames_with_data

    control, weights = controlled_loftr
    first, second = textured_pair()
    _, third = textured_pair((-6.75, 8.5))
    frames = frames_with_data(first.data, second.data, third.data)
    control.shifts = [(19, -12), (-24.5, 21.6)]
    progress = []
    result = register_series(frames, method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'),
                             progress=lambda *args: progress.append(args))

    np.testing.assert_allclose([frame.shift_xy for frame in result.frames],
                               [(0, 0), (18.25, -12.5), (-6.75, 8.5)], atol=0.4)
    assert result.method == 'Deep Matcher + lokalne fragmenty (v1)'
    assert result.device == 'CPU'
    assert control.loaded == 1 and control.calls == 2
    assert result.local_diagnostics[0] is None
    assert result.local_diagnostics[1].deep_shift_xy == (19, -12)
    assert result.local_diagnostics[1].final_shift_xy == result.frames[1].shift_xy
    assert all(frame.status == 'manual_review' and frame.quality_score is None for frame in result.frames[1:])
    assert all(np.isnan(frame.image.data[~frame.valid_mask]).all() for frame in result.frames)
    assert any('Fragmenty' in description for _, _, description in progress)
    surviving = result.without_frame(1)
    assert surviving.local_diagnostics == (None, result.local_diagnostics[2])
    assert surviving.frames[-1].image is result.frames[-1].image


def test_manual_correction_keeps_local_evidence_and_exports_only_measurement_images(controlled_loftr, tmp_path):
    import cv2
    from stmviewer.registration import register_series
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial, remove_movie_correction
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.series import open_frame_series
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.avi_sources import aligned_movie_frames

    _, weights = controlled_loftr
    frames = textured_pair()
    automatic = register_series(frames, method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'))
    draft = ManualPairDraft(*frames, start=movie_pair_trial(automatic, 1))
    draft.nudge(1, 0)
    corrected = apply_movie_correction(automatic, draft.apply())

    assert corrected.local_diagnostics is automatic.local_diagnostics
    np.testing.assert_allclose(corrected.frames[1].shift_xy, (19.25, -12.5), atol=0.35)
    assert corrected.local_diagnostics[1].final_shift_xy == automatic.frames[1].shift_xy
    assert corrected.frames[1].quality_score is None
    restored = remove_movie_correction(corrected, 1)
    assert restored.local_diagnostics is automatic.local_diagnostics
    np.testing.assert_array_equal(restored.frames[1].image.data, automatic.frames[1].image.data)

    path = save_aligned_mpp(tmp_path / 'local.mpp', corrected)
    reopened = open_frame_series([path])
    for actual, expected in zip(reopened, corrected.frames):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        np.testing.assert_array_equal(np.isfinite(actual.data), expected.valid_mask)
        assert actual.alignment.method == corrected.method
        assert actual.alignment.shift_xy == expected.shift_xy
    assert len(reopened[1].alignment.manual_movie.corrections) == 1

    source = aligned_movie_frames(frames, corrected)
    assert source[1].data is corrected.frames[1].image.data
    plan = prepare_avi(source, fps=7, codec='FFV1',
                       presentation=MoviePresentation(pixel_proportions=True, background=255))
    movie = save_avi(tmp_path / 'local.avi', plan)
    reader = cv2.VideoCapture(str(movie))
    try:
        assert reader.isOpened() and reader.get(cv2.CAP_PROP_FPS) == 7
        for index, frame in enumerate(corrected.frames):
            ok, raster = reader.read()
            assert ok
            np.testing.assert_array_equal(raster, plan.render_frame(index))
            np.testing.assert_array_equal(raster[..., 0], raster[..., 1])
            np.testing.assert_array_equal(raster[..., 1], raster[..., 2])
            height, width = frame.valid_mask.shape
            assert np.all(raster[:height, :width][~frame.valid_mask] == 255)
            assert np.all(raster[height:, :] == 255)
            assert np.all(raster[:, width:] == 255)
        assert not reader.read()[0]
    finally:
        reader.release()
