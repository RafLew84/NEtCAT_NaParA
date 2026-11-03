"""Raw correlation estimates remain distinct from phase-based confidence."""

import numpy as np

from stmviewer.pair_comparison import estimate_pair
from make_registration_fixtures import frames_with_data

METHOD = 'phase_no_normalization'
LABEL = 'Korelacja bez normalizacji (v1)'


def test_raw_correlation_finds_pair_shift_without_phase_confidence():
    original = np.random.default_rng(42).normal(size=(32, 48))
    frames = frames_with_data(original, np.roll(original, (2, -3), (0, 1)))
    before = [frame.data.copy() for frame in frames]

    trial = estimate_pair(*frames, method=METHOD)

    np.testing.assert_allclose(trial.shift_xy, (3, -2), atol=0.05)
    assert trial.method == METHOD and trial.label == LABEL
    assert trial.status == 'manual_review' and trial.quality_score is None
    assert 'normalization=None' in trial.settings_text
    for frame, expected in zip(frames, before):
        np.testing.assert_array_equal(frame.data, expected)


def test_raw_correlation_series_matches_pairs_and_preserves_missing_confidence():
    from stmviewer.registration import register_series

    original = np.random.default_rng(42).normal(size=(32, 48))
    second = np.roll(original, (2, -3), (0, 1))
    third = np.roll(second, (-1, 5), (0, 1))
    frames = frames_with_data(original, second, third)
    progress = []
    result = register_series(frames, method=METHOD, progress=lambda *args: progress.append(args))

    assert result.method == LABEL
    assert result.canvas_shape == (34, 53)
    assert result.padding_ltrb == (2, 2, 3, 0)
    assert [f.shift_xy for f in result.frames] == [(0, 0), (3, -2), (-2, -1)]
    assert [f.status for f in result.frames] == ['ok', 'manual_review', 'manual_review']
    assert [f.quality_score for f in result.frames] == [1, None, None]
    assert result.frames[2].inherited_uncertainty
    pair = estimate_pair(frames[1], frames[2], method=METHOD)
    assert pair.shift_xy == (-5, 1)
    assert result.frames[1].original is frames[1]
    for frame in result.frames:
        assert frame.valid_mask.sum() == 32 * 48
        assert np.isnan(frame.image.data[~frame.valid_mask]).all()
    np.testing.assert_allclose(result.frames[1].image.data[2:32, 5:50], original[:30, 3:48])
    assert [p[:2] for p in progress] == [(i, 6) for i in range(1, 7)]


def test_raw_correlation_rejects_textureless_pairs_and_series():
    import pytest
    from stmviewer.registration import RegistrationError, register_series

    frames = frames_with_data(np.ones((32, 48)), np.ones((32, 48)))
    with pytest.raises(RegistrationError, match='za mało tekstury'):
        estimate_pair(*frames, method=METHOD)
    with pytest.raises(RegistrationError, match='za mało tekstury'):
        register_series(frames, method=METHOD)
