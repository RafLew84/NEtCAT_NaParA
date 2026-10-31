"""Manual source rectangles select evidence without changing measurement samples."""

import numpy as np

from stmviewer.registration_masks import FrameMask, MaskRectangle


def test_use_union_minus_omit_clips_to_source_and_excludes_missing_samples():
    values = np.arange(24, dtype=float).reshape(4, 6)
    values[0, 0] = np.nan
    mask = FrameMask((MaskRectangle(0, 0, 4, 3, 'use'),
                      MaskRectangle(4, 2, 7, 5, 'use'),
                      MaskRectangle(1, 1, 3, 4, 'omit')))
    actual = mask.raster(values)
    np.testing.assert_array_equal(actual, [
        [False, True, True, True, False, False],
        [True, False, False, True, False, False],
        [True, False, False, True, True, True],
        [False, False, False, False, True, True],
    ])
    assert not actual.flags.writeable
    assert np.isnan(values[0, 0]) and values[3, 5] == 23


def test_source_keyed_snapshot_is_unchanged_by_edit_removal_or_clear():
    from stmviewer.registration_masks import FrameMasks
    from make_registration_fixtures import frames_with_data

    first, second, third = frames_with_data(*(np.ones((8, 10)) for _ in range(3)))
    store = FrameMasks()
    selected = FrameMask((MaskRectangle(1, 2, 4, 5, 'omit'),))
    store.set(second, selected)
    snapshot = store.snapshot((first, second, third))
    assert snapshot == (FrameMask(), selected, FrameMask())
    assert store.marked_count == 1
    store.remove(first)
    assert store.snapshot((third, second)) == (FrameMask(), selected)
    store.set(second, FrameMask((MaskRectangle(0, 0, 10, 8, 'use'),)))
    assert snapshot[1].raster(second.data).sum() == 71
    store.remove(second)
    assert store.get(second) == FrameMask() and store.marked_count == 0
    store.set(third, selected)
    store.clear()
    assert store.get(third) == FrameMask() and store.marked_count == 0
    assert snapshot[1] == selected


def test_masked_ncc_recovers_sample_translation_when_stationary_band_wins_unmasked():
    from stmviewer.pair_comparison import estimate_pair
    from make_mask_fixtures import artefact_arrays
    from make_registration_fixtures import frames_with_data

    first, second, _ = frames_with_data(*artefact_arrays())
    omitted = FrameMask((MaskRectangle(0, 0, 80, 12, 'omit'),))
    unmasked = estimate_pair(first, second, method='masked_correlation',
                             reference_mask=omitted, moving_mask=omitted, use_masks=False)
    masked = estimate_pair(first, second, method='masked_correlation',
                           reference_mask=omitted, moving_mask=omitted)
    assert unmasked.shift_xy == (0, 0)
    assert masked.shift_xy == (-4, 3)
    assert masked.quality_score is None and masked.status == 'manual_review'
    assert 'wyłączone' in unmasked.label and 'włączone' in masked.label
    assert 'omit' in masked.settings_text and '80' in masked.settings_text


def test_each_mask_can_refuse_the_pair_without_using_unmasked_pixels():
    import pytest
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import RegistrationError
    from make_mask_fixtures import artefact_arrays
    from make_registration_fixtures import frames_with_data

    first, second, _ = frames_with_data(*artefact_arrays())
    empty = FrameMask((MaskRectangle(0, 0, 80, 64, 'omit'),))
    narrow = FrameMask((MaskRectangle(0, 0, 1, 64, 'use'),))
    for masks, reason in [({'reference_mask': empty}, 'bazowa.*za mało danych'),
                           ({'moving_mask': empty}, 'przesuwana.*za mało danych'),
                           ({'moving_mask': narrow}, 'rozpiętość')]:
        with pytest.raises(RegistrationError, match=reason):
            estimate_pair(first, second, method='masked_correlation', **masks)
    assert estimate_pair(first, second, method='masked_correlation',
                         reference_mask=empty, moving_mask=empty, use_masks=False).shift_xy == (0, 0)


def test_flat_selected_region_and_no_supported_overlap_are_rejected():
    import pytest
    from dataclasses import replace
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import RegistrationError
    from make_registration_fixtures import frames_with_data

    rng = np.random.default_rng(8)
    first, second = frames_with_data(rng.normal(size=(64, 80)), rng.normal(size=(64, 80)))
    changed = first.data.copy()
    changed[:20] = 6
    first = replace(first, data=changed)
    with pytest.raises(RegistrationError, match='za mało tekstury'):
        estimate_pair(first, second, method='masked_correlation',
                      reference_mask=FrameMask((MaskRectangle(0, 0, 80, 20, 'use'),)))
    masks = []
    for _ in range(2):
        points = rng.choice(64 * 80, 64, replace=False)
        masks.append(FrameMask(tuple(MaskRectangle(int(p % 80), int(p // 80),
                                                   int(p % 80) + 1, int(p // 80) + 1, 'use') for p in points)))
    with pytest.raises(RegistrationError, match='wspólnych'):
        estimate_pair(first, second, method='masked_correlation', reference_mask=masks[0], moving_mask=masks[1])


def test_masked_ncc_uses_only_finite_available_samples_and_leaves_originals_unchanged():
    import pytest
    from dataclasses import replace
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import RegistrationError
    from make_mask_fixtures import artefact_arrays
    from make_registration_fixtures import frames_with_data

    first, second, _ = frames_with_data(*artefact_arrays())
    inputs = []
    for frame in (first, second):
        values = frame.data.copy()
        values[:12] = np.nan
        inputs.append(replace(frame, data=values))
    snapshots = [frame.data.copy() for frame in inputs]
    result = estimate_pair(*inputs, method='masked_correlation')
    assert result.shift_xy == (-4, 3)
    for frame, before in zip(inputs, snapshots):
        np.testing.assert_array_equal(frame.data, before)
    with pytest.raises(RegistrationError, match='NaN/Inf'):
        estimate_pair(*inputs, method='phase_correlation')


def test_full_series_uses_captured_per_source_masks_after_live_edits_and_can_cancel():
    import pytest
    from stmviewer.registration import register_series, RegistrationCancelled, RegistrationError
    from stmviewer.registration_masks import FrameMasks
    from make_mask_fixtures import artefact_arrays
    from make_registration_fixtures import frames_with_data

    originals = frames_with_data(*artefact_arrays())
    store = FrameMasks()
    omitted = FrameMask((MaskRectangle(0, 0, 80, 12, 'omit'),))
    for frame in originals:
        store.set(frame, omitted)
    snapshot = store.snapshot(originals)
    result = register_series(originals, method='masked_correlation', masks=snapshot,
                             progress=lambda *args: store.clear())
    assert [frame.shift_xy for frame in result.frames] == [(0, 0), (-4, 3), (-7, 1)]
    assert store.marked_count == 0
    assert [frame.quality_score for frame in result.frames] == [1.0, None, None]
    assert 'włączone' in result.method
    without = register_series(originals, method='masked_correlation', masks=snapshot, use_masks=False)
    assert [frame.shift_xy for frame in without.frames] == [(0, 0), (0, 0), (0, 0)]
    assert 'wyłączone' in without.method
    stopped = False
    def stop_after_pair(done, total, text):
        nonlocal stopped
        stopped = done >= 2
    with pytest.raises(RegistrationCancelled):
        register_series(originals, method='masked_correlation', masks=snapshot,
                        progress=stop_after_pair, cancelled=lambda: stopped)
    with pytest.raises(RegistrationError, match='wszystkim klatkom'):
        register_series(originals, method='masked_correlation', masks=snapshot[:1])
    with pytest.raises(RegistrationError, match='za mało danych'):
        register_series(originals[:1], method='masked_correlation',
                        masks=(FrameMask((MaskRectangle(0, 0, 80, 64, 'omit'),)),))


def test_integer_masked_alignment_preserves_every_measured_sample_next_to_nan(tmp_path):
    from make_mask_fixtures import artefact_arrays
    from make_registration_fixtures import frames_with_data
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.registration import register_series
    from stmviewer.series import open_frame_series

    first, second, _ = artefact_arrays()
    first[30, 30] = second[30, 30] = np.nan
    omitted = FrameMask((MaskRectangle(0, 0, 80, 12, 'omit'),))
    for moving, expected_shift in ((first.copy(), (0, 0)), (second, (-4, 3))):
        originals = frames_with_data(first, moving)
        before = [frame.data.copy() for frame in originals]
        result = register_series(originals, method='masked_correlation', masks=(omitted, omitted))
        assert result.frames[1].shift_xy == expected_shift
        exported = save_aligned_mpp(tmp_path / f'shift-{expected_shift[0]}.mpp', result,
                                    wsxm_compatible=True)
        restored = open_frame_series([exported])
        for aligned, original, saved in zip(result.frames, before, restored):
            x, y = map(int, aligned.origin_xy)
            assert aligned.valid_mask.sum() == np.isfinite(saved.data).sum() == 5119
            np.testing.assert_array_equal(aligned.image.data[y:y + 64, x:x + 80], original)
            np.testing.assert_array_equal(saved.data, aligned.image.data)
            assert np.isnan(saved.data[y + 30, x + 30])
            np.testing.assert_array_equal(aligned.original.data, original)
            assert np.isnan(aligned.image.data[~aligned.valid_mask]).all()


def test_fractional_alignment_requires_every_positive_weight_sample_without_spreading_gaps():
    from dataclasses import replace
    from make_mask_fixtures import artefact_arrays
    from make_registration_fixtures import frames_with_data
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.registration import register_series

    samples = artefact_arrays()[0]
    samples[28:33, 28:34] = [
        [0, 2, 4, 6, 8, 10],
        [12, 14, 16, 18, 20, 22],
        [24, 26, np.nan, 30, 32, 34],
        [36, 38, 40, 42, 44, 46],
        [48, 50, 52, 54, 56, 58],
    ]
    originals = frames_with_data(samples, samples.copy())
    base = register_series(originals, method='masked_correlation')
    for xy, valid_count, expected in [
        ((0.5, 0), 5054, [[13, 15, 17, 19], [25, np.nan, np.nan, 31], [37, 39, 41, 43]]),
        ((0.5, 0.25), 4973, [[10, 12, 14, 16], [22, np.nan, np.nan, 28],
                            [34, np.nan, np.nan, 40], [46, 48, 50, 52]]),
    ]:
        start = replace(movie_pair_trial(base, 1), shift_xy=xy)
        trial = ManualPairDraft(*originals, start).apply()
        aligned = apply_movie_correction(base, trial).frames[1]
        assert aligned.valid_mask.sum() == valid_count
        np.testing.assert_array_equal(aligned.image.data[29:29 + len(expected), 29:33], expected)
        assert np.isnan(aligned.image.data[~aligned.valid_mask]).all()
        np.testing.assert_array_equal(aligned.original.data, samples)
