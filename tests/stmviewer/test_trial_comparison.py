"""Two saved full trials -> one shared field rendered from original pixels."""

import numpy as np

from make_registration_fixtures import frames_with_data
from stmviewer.trial_comparison import FullTrialComparison


def test_full_trials_use_one_common_canvas_when_switching_between_results():
    original = np.arange(12).reshape(3, 4)
    frames = frames_with_data(original, original + 20)
    comparison = FullTrialComparison(frames, ((0, 0), (2, -1)), ((0, 0), (-1, 1)))

    assert comparison.canvas_shape == (5, 7)
    assert comparison.origin_xy == (1, 1)
    assert comparison.original_rect(0, 'A') == (1, 1, 4, 3)
    assert comparison.original_rect(0, 'B') == (1, 1, 4, 3)
    assert comparison.original_rect(1, 'A') == (3, 0, 4, 3)
    assert comparison.original_rect(1, 'B') == (0, 2, 4, 3)
    first = comparison.render(0, 'A')
    second = comparison.render(1, 'B')
    np.testing.assert_array_equal(first.data[1:4, 1:5], original)
    np.testing.assert_array_equal(second.data[2:5, :4], original + 20)
    assert np.isnan(first.data[0]).all()
    assert np.isnan(second.data[:2]).all()
    assert not first.data.flags.writeable
    assert second.source == frames[1].source
    assert second.source_frame_index == frames[1].source_frame_index


def test_different_historical_origins_are_normalized_without_losing_subpixel_values():
    original = np.arange(12).reshape(3, 4)
    frames = frames_with_data(original, original)
    comparison = FullTrialComparison(frames, ((9, -5), (9.5, -5.25)),
                                     ((-8, 12), (-8, 12)))

    assert comparison.canvas_shape == (4, 5)
    assert comparison.original_rect(0, 'A') == comparison.original_rect(0, 'B') == (0, 1, 4, 3)
    assert comparison.original_rect(1, 'A') == (0.5, 0.75, 4, 3)
    image = comparison.render(1, 'A')
    np.testing.assert_array_equal(image.data[1:3, 1:4], [[1.5, 2.5, 3.5], [5.5, 6.5, 7.5]])
    assert np.isnan(image.data[0]).all() and np.isnan(image.data[-1]).all()
    assert np.isnan(image.data[:, 0]).all() and np.isnan(image.data[:, -1]).all()


def test_shared_canvas_keeps_physical_scale_only_when_all_originals_agree():
    from dataclasses import replace

    originals = frames_with_data(np.ones((3, 4)), np.ones((3, 4)))
    frames = tuple(replace(frame, size_x_nm=24, size_y_nm=12) for frame in originals)
    comparison = FullTrialComparison(frames, ((0, 0), (2, -1)), ((0, 0), (-1, 1)))
    image = comparison.render(1, 'A')
    assert comparison.pixel_size_nm == (6, 4)
    assert (image.size_x_nm, image.size_y_nm) == (42, 20)
    assert (frames[1].size_x_nm, frames[1].size_y_nm) == (24, 12)

    mixed = (frames[0], replace(frames[1], size_x_nm=12))
    comparison = FullTrialComparison(mixed, ((0, 0), (2, -1)), ((0, 0), (-1, 1)))
    image = comparison.render(1, 'A')
    assert comparison.pixel_size_nm is None
    assert (image.size_x_nm, image.size_y_nm) == (None, None)


def test_partial_trial_cannot_be_opened_as_a_complete_movie():
    import pytest

    frames = frames_with_data(np.ones((3, 4)), np.ones((3, 4)))
    with pytest.raises(ValueError, match='kompletn'):
        FullTrialComparison(frames, ((0, 0),), ((0, 0), (1, 1)))
    with pytest.raises(ValueError, match='kompletn'):
        FullTrialComparison((), (), ())
    with pytest.raises(ValueError, match='XY'):
        FullTrialComparison(frames, ((0, 0), (np.nan, 1)), ((0, 0), (1, 1)))
    with pytest.raises(ValueError, match='wymiar'):
        FullTrialComparison(frames_with_data(np.ones((3, 4)), np.ones((2, 4))),
                            ((0, 0), (1, 1)), ((0, 0), (1, 1)))


def test_excessive_canvas_is_rejected_before_allocating_an_image():
    import pytest

    frames = frames_with_data(np.ones((3, 4)), np.ones((3, 4)))
    with pytest.raises(ValueError, match='pamię'):
        FullTrialComparison(frames, ((0, 0), (100_000, 100_000)), ((0, 0), (0, 0)))
    with pytest.raises(ValueError, match='XY'):
        FullTrialComparison(frames, ((-1e308, 0), (1e308, 0)), ((0, 0), (0, 0)))


def test_navigation_never_wraps_invalid_indices_or_selects_an_unknown_trial():
    import pytest

    comparison = FullTrialComparison(frames_with_data(np.ones((3, 4))), ((0, 0),), ((0, 0),))
    for index in (-1, 1):
        with pytest.raises(IndexError):
            comparison.render(index, 'A')
    with pytest.raises(ValueError, match='prób'):
        comparison.render(0, 'C')


def test_browsing_long_trials_keeps_only_current_images_in_memory():
    import gc
    import tracemalloc

    original = np.arange(256 * 256).reshape(256, 256)
    # Caller-owned originals exist before measuring the comparison's overhead.
    frames = frames_with_data(*(original for _ in range(200)))
    shifts = tuple((float(i % 3), float(i % 5)) for i in range(200))
    tracemalloc.start()
    try:
        comparison = FullTrialComparison(frames, shifts, tuple((0., 0.) for _ in frames))
        for index in range(200):
            image = comparison.render(index, 'A' if index % 2 else 'B')
            assert image.data.shape == (260, 258)
            del image
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # Two retained movie copies would exceed 200 MiB. The measured budget allows
    # temporary interpolation allocations and lightweight records, independent
    # of frame count, with ample headroom across supported Python versions.
    assert peak < 8 * 1024 * 1024
    assert current < 2 * 1024 * 1024
