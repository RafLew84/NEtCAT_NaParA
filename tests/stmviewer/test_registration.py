"""Original frames -> complete registration, with independent geometric expectations."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.io import open_stp
from stmviewer.registration import register_series

FIXTURES = Path(__file__).parent / 'fixtures'


def frames_with_data(*arrays):
    template = open_stp(FIXTURES / 'asymmetric.stp')
    return tuple(replace(template, data=np.asarray(a, dtype=np.float64),
                         source_frame_index=i, measurement_time_s=(10, 20, 35)[i % 3])
                 for i, a in enumerate(arrays))


def test_phase_accumulates_adjacent_xy_and_keeps_whole_original_fields():
    original = np.random.default_rng(42).normal(size=(32, 48))
    second = np.roll(original, (2, -3), (0, 1))
    third = np.roll(second, (-1, 5), (0, 1))
    frames = frames_with_data(original, second, third)
    before = [f.data.copy() for f in frames]

    result = register_series(frames)

    assert result.canvas_shape == (34, 53)
    assert result.padding_ltrb == (2, 2, 3, 0)
    assert result.reference.source == frames[0].source
    assert result.reference.source_frame_index == 0
    assert [f.shift_xy for f in result.frames] == [(0, 0), (3, -2), (-2, -1)]
    assert [f.origin_xy for f in result.frames] == [(2, 2), (5, 0), (0, 1)]
    for i, aligned in enumerate(result.frames):
        assert aligned.original is frames[i]
        assert aligned.original_rect[2:] == (48, 32)
        assert aligned.status == 'ok'
        np.testing.assert_array_equal(frames[i].data, before[i])
        assert not np.shares_memory(frames[i].data, aligned.image.data)
        assert aligned.valid_mask.sum() == 32 * 48
        assert np.isnan(aligned.image.data[~aligned.valid_mask]).all()
    np.testing.assert_array_equal(result.frames[0].image.data[2:34, 2:50], original)
    np.testing.assert_allclose(result.frames[1].image.data[2:32, 5:50], original[:30, 3:48])


def test_subpixel_field_keeps_original_size_even_when_valid_mask_is_smaller():
    from nanotrack.core import RegistrationFrameResult

    class HalfPixelBackend:
        def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
            return RegistrationFrameResult(moving_frame_index, (0.5, -0.25), 'controlled')

    frames = frames_with_data(np.arange(12).reshape(3, 4), np.arange(12).reshape(3, 4))
    result = register_series(frames, backend=HalfPixelBackend())

    assert result.canvas_shape == (4, 5)
    frame = result.frames[1]
    assert frame.original_rect == (0.5, 0.75, 4, 3)
    assert frame.valid_mask.sum() == 6
    np.testing.assert_array_equal(frame.image.data[1:3, 1:4], [[1.5, 2.5, 3.5], [5.5, 6.5, 7.5]])
    assert np.isnan(frame.image.data[0]).all() and np.isnan(frame.image.data[-1]).all()


def test_cancellation_during_aligned_discards_incomplete_result():
    from threading import Event
    import pytest
    from stmviewer.registration import RegistrationCancelled

    frame = np.random.default_rng(2).normal(size=(20, 24))
    cancelled = Event()
    progress = []

    def on_progress(done, total, description):
        progress.append((done, total))
        if done == 3:  # Two estimates, then the first materialized image.
            cancelled.set()

    with pytest.raises(RegistrationCancelled):
        register_series(frames_with_data(frame, frame), progress=on_progress, cancelled=cancelled.is_set)
    assert progress == [(1, 4), (2, 4), (3, 4)]


def test_invalid_inputs_and_failed_or_missing_estimates_reject_the_entire_attempt():
    import pytest
    from nanotrack.core import RegistrationFrameResult
    from stmviewer.registration import RegistrationError

    for frames, reason in [
        ((), 'pusta'),
        (frames_with_data(np.full((3, 4), np.nan)), 'NaN'),
        (frames_with_data(np.ones((3, 4)), np.ones((4, 4))), 'wymiar'),
        (frames_with_data(np.ones((3, 4)), np.ones((3, 4))), 'tekstur'),
    ]:
        with pytest.raises(RegistrationError, match=reason):
            register_series(frames)

    class BrokenBackend:
        def __init__(self, output):
            self.output = output

        def estimate(self, *args, **kwargs):
            return self.output

    invalid_shift = RegistrationFrameResult(1, (0, 0), 'controlled')
    invalid_shift.shift_xy = (np.inf, 0)
    frames = frames_with_data(np.arange(12).reshape(3, 4), np.arange(12).reshape(3, 4))
    for result in [None, invalid_shift, RegistrationFrameResult(1, (0, 0), 'controlled', status='failed'),
                   RegistrationFrameResult(7, (0, 0), 'controlled')]:
        with pytest.raises(RegistrationError, match='1 → 2'):
            register_series(frames, backend=BrokenBackend(result))


def test_deleting_reference_or_uncertain_frame_keeps_geometry_and_inherited_quality():
    from nanotrack.core import RegistrationFrameResult

    class UncertainBackend:
        def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
            return RegistrationFrameResult(
                moving_frame_index, (2, -1), 'controlled', quality_score=0.2 if moving_frame_index == 1 else 0.9,
                status='manual_review' if moving_frame_index == 1 else 'ok',
            )

    frame = np.arange(20).reshape(4, 5)
    originals = frames_with_data(frame, frame, frame)
    result = register_series(originals, backend=UncertainBackend())
    assert [f.status for f in result.frames] == ['ok', 'manual_review', 'manual_review']
    assert [f.quality_score for f in result.frames] == [1, 0.2, 0.2]
    assert result.frames[2].inherited_uncertainty

    remaining = result.without_frame(0).without_frame(0)

    assert len(remaining.frames) == 1 and remaining.frames[0] is result.frames[2]
    assert remaining.reference == result.reference
    assert remaining.canvas_shape == result.canvas_shape == (6, 9)
    assert remaining.frames[0].origin_xy == (4, 0)
    assert remaining.frames[0].status == 'manual_review'
    assert remaining.without_frame(0) is None
    again = register_series((originals[2],))
    assert again.frames[0].shift_xy == (0, 0) and again.canvas_shape == (4, 5)
    assert again.reference.source_frame_index == 2


def test_aligned_uses_only_common_positive_finite_pixel_scale_without_changing_source_metadata():
    frame = np.random.default_rng(4).normal(size=(8, 12))
    first, second = frames_with_data(frame, np.roll(frame, (1, -2), (0, 1)))
    first = replace(first, size_x_nm=24, size_y_nm=32)
    second = replace(second, size_x_nm=24, size_y_nm=32, channel='Other', signal_unit='a.u.')
    result = register_series((first, second))
    assert result.pixel_size_nm == (2, 4)
    assert (result.frames[0].image.size_x_nm, result.frames[0].image.size_y_nm) == (28, 36)
    assert result.frames[1].original is second
    assert result.frames[1].image.channel == 'Other'
    for scale in (None, 12, 0, np.nan, np.inf):
        changed = replace(second, size_x_nm=scale)
        result = register_series((first, changed))
        assert result.pixel_size_nm is None
        assert all(f.image.size_x_nm is None and f.image.size_y_nm is None for f in result.frames)
        assert result.frames[1].original is changed
        assert result.without_frame(1).pixel_size_nm is None


def test_real_phase_subpixels_and_default_quality_match_nanotrack():
    from scipy.ndimage import fourier_shift
    from nanotrack.registration import run_adjacent_phase_registration

    first = np.random.default_rng(42).normal(size=(64, 64))
    second = np.fft.ifftn(fourier_shift(np.fft.fftn(first), shift=(2.4, -3.25))).real
    originals = frames_with_data(first, second)
    result = register_series(originals)
    np.testing.assert_allclose(result.frames[1].shift_xy, (3.25, -2.4), atol=0.1)
    baseline = run_adjacent_phase_registration(np.stack([first, second]))
    for index, frame in enumerate(result.frames):
        reference = baseline.get_result(index)
        assert frame.shift_xy == reference.shift_xy
        assert frame.quality_score == reference.quality_score
        assert frame.status == reference.status


def test_real_phase_repeated_pattern_is_complete_but_low_confidence():
    y, x = np.mgrid[:48, :48]
    pattern = (((x // 4) + (y // 4)) % 2).astype(float)
    result = register_series(frames_with_data(pattern, np.roll(pattern, (4, 4), (0, 1)), pattern))
    assert [frame.status for frame in result.frames] == ['ok', 'low_confidence', 'low_confidence']
    assert result.frames[2].inherited_uncertainty
    assert all(frame.valid_mask.any() for frame in result.frames)
    assert result.frames[1].quality_score < 0.5


def test_cancellation_at_last_progress_cannot_publish_a_result():
    from threading import Event
    import pytest
    from stmviewer.registration import RegistrationCancelled

    cancelled = Event()
    def progress(done, total, text):
        if done == total:
            cancelled.set()
    with pytest.raises(RegistrationCancelled):
        register_series(frames_with_data(np.ones((3, 4))), progress=progress, cancelled=cancelled.is_set)
