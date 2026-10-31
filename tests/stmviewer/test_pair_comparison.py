"""Public pair comparison keeps geometry and brightness independent of the trial."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.io import open_stp
from stmviewer.pair_comparison import PairImages


def frame(values, index=0):
    template = open_stp(Path(__file__).parent / 'fixtures' / 'asymmetric.stp')
    return replace(template, data=np.asarray(values, dtype=np.float64), source_frame_index=index)


def test_shifted_pair_uses_fixed_reference_field_and_one_original_contrast():
    reference = frame([[0, 25, 50], [75, 100, 25]])
    moving = frame([[25, 50, 0], [100, 25, 75]], 1)
    pair = PairImages(reference, moving)

    shifted = pair.render((1, 0), layer='moving')
    overlay = pair.render((1, 0), layer='overlay')
    baseline = pair.render((0, 0), layer='reference')

    assert pair.contrast == (0.0, 100.0)
    assert shifted.rgba.shape == baseline.rgba.shape == (2, 3, 4)
    assert shifted.overlap_pixels == 4
    assert shifted.overlap_fraction == 4 / 6
    np.testing.assert_array_equal(shifted.rgba[:, 1:, 0], [[63, 127], [255, 63]])
    np.testing.assert_array_equal(overlay.rgba[:, 1:], baseline.rgba[:, 1:])
    assert not shifted.rgba[:, 0, 3].any()
    assert not overlay.rgba[:, 0, 3].any()
    np.testing.assert_array_equal(reference.data, [[0, 25, 50], [75, 100, 25]])


def test_pair_trial_estimates_only_the_selected_originals_and_has_no_image_arrays():
    from dataclasses import FrozenInstanceError, asdict
    import pytest
    from stmviewer.pair_comparison import estimate_pair

    reference = np.random.default_rng(12).normal(size=(32, 48))
    first = frame(reference, 19)
    second = frame(np.roll(reference, (2, -3), (0, 1)), 20)
    trial = estimate_pair(first, second)

    assert trial.shift_xy == (3.0, -2.0)
    assert trial.reference.source_frame_index == 19
    assert trial.moving.source_frame_index == 20
    assert trial.method == 'phase_correlation' and trial.label == 'Phase'
    assert trial.device == 'CPU' and trial.status == 'ok'
    assert 'normalization=phase' in trial.settings_text
    assert not any(isinstance(value, np.ndarray) for value in asdict(trial).values())
    with pytest.raises(FrozenInstanceError):
        trial.shift_xy = (0, 0)


def test_invalid_backend_output_or_pair_is_rejected_instead_of_becoming_a_trial():
    from types import SimpleNamespace
    import pytest
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import RegistrationError

    class Returned:
        def __init__(self, value):
            self.value = value

        def estimate(self, *args, **kwargs):
            return self.value

    valid = dict(frame_index=1, shift_xy=(1, -2), status='ok', quality_score=0.8)
    reference = frame(np.arange(12).reshape(3, 4))
    for result in [None, *[SimpleNamespace(**(valid | change)) for change in (
        {'frame_index': 2}, {'shift_xy': (float('nan'), 0)}, {'shift_xy': (1,)},
        {'status': 'failed'}, {'quality_score': float('nan')}, {'quality_score': -1},
    )]]:
        with pytest.raises(RegistrationError):
            estimate_pair(reference, reference, backend=Returned(result))
    for invalid in [frame([[1, 2]]), frame(np.full((3, 4), np.nan))]:
        with pytest.raises(RegistrationError):
            estimate_pair(reference, invalid, backend=Returned(SimpleNamespace(**valid)))


def test_invalid_display_parameters_do_not_produce_a_misleading_comparison():
    import pytest
    good = frame(np.arange(12).reshape(3, 4))
    for bad in [frame(np.ones((4, 3))), frame(np.empty((0, 4))), frame(np.ones(4))]:
        with pytest.raises(ValueError):
            PairImages(good, bad)
    pair = PairImages(good, good)
    for arguments in [{'gamma': 0}, {'gamma': float('nan')}, {'layer': 'invalid'},
                      {'shift_xy': (float('inf'), 0)}, {'shift_xy': (0,)}]:
        with pytest.raises(ValueError):
            pair.render(**arguments)


def test_subpixel_interpolation_precedes_gamma_and_keeps_reference_coordinates():
    pair = PairImages(frame(np.zeros((3, 3))), frame([[0, 2, 4], [6, 8, 10], [12, 14, 16]], 1))
    neutral = pair.render((-0.5, 0.5), layer='moving')
    bright = pair.render((-0.5, 0.5), gamma=2.0, layer='moving')

    assert pair.contrast == (0, 16)
    assert neutral.overlap_pixels == bright.overlap_pixels == 4
    np.testing.assert_array_equal(neutral.rgba[:, :, 3], [[0, 0, 0], [255, 255, 0], [255, 255, 0]])
    assert neutral.rgba[1, 0, 0] == 63  # Source midpoint is 4, in an original 0..16 range.
    assert bright.rgba[1, 0, 0] == 127  # sqrt(4/16), not interpolation of gamma-corrected endpoints.
    assert not bright.rgba.flags.writeable
    overlay = pair.render((-0.5, 0.5), gamma=2.0, layer='overlay')
    assert overlay.rgba[1, 0, 0] == 63  # Equal display contribution of reference 0 and moving 0.5.


def test_missing_samples_and_no_overlap_do_not_reset_contrast_or_look_valid():
    pair = PairImages(frame([[np.nan, 0, 10], [np.nan, 5, 10]]),
                      frame([[0, 5, 10], [0, 5, np.nan]], 1))
    original = pair.render(layer='reference')
    assert pair.contrast == (0, 10)
    assert original.overlap_pixels == 3
    assert original.rgba[1, 1, 0] == 127
    absent = pair.render((20, -20), layer='overlay')
    assert absent.overlap_pixels == 0 and absent.overlap_fraction == 0
    assert not absent.rgba[:, :, 3].any()
    assert pair.contrast == (0, 10)
    np.testing.assert_array_equal(pair.render((20, -20), layer='reference').rgba, original.rgba)


def test_cancellation_before_or_after_estimation_never_returns_a_completed_trial():
    from threading import Event
    import pytest
    from nanotrack.core import RegistrationFrameResult
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.registration import RegistrationCancelled

    cancelled = Event()
    reference = frame(np.arange(12).reshape(3, 4))
    cancelled.set()
    with pytest.raises(RegistrationCancelled):
        estimate_pair(reference, reference, cancelled=cancelled.is_set)
    cancelled.clear()

    class CancellingBackend:
        def estimate(self, *args, **kwargs):
            cancelled.set()
            return RegistrationFrameResult(1, (1, -2), 'external')

    with pytest.raises(RegistrationCancelled):
        estimate_pair(reference, reference, backend=CancellingBackend(), cancelled=cancelled.is_set)


def test_constant_or_entirely_missing_pair_has_an_explicit_validity_mask():
    constant = frame(np.full((2, 3), 7))
    raster = PairImages(constant, constant).render()
    assert np.all(raster.rgba[:, :, :3] == 127)
    assert np.all(raster.rgba[:, :, 3] == 255)
    missing = frame(np.full((2, 3), np.nan))
    empty = PairImages(missing, missing).render()
    assert empty.overlap_pixels == 0 and not empty.rgba[:, :, 3].any()


def test_shifted_missing_sample_invalidates_only_its_positive_weight_support():
    samples = np.array([[0, 1, 2, 3], [4, 5, np.nan, 7], [8, 9, 10, 11]], dtype=float)
    moving = frame(samples, 1)
    pair = PairImages(frame(np.zeros((3, 4))), moving)
    for xy, expected_valid in [
        ((1, 0), [[0, 1, 1, 1], [0, 1, 1, 0], [0, 1, 1, 1]]),
        ((-1, 0), [[1, 1, 1, 0], [1, 0, 1, 0], [1, 1, 1, 0]]),
        ((0.5, 0), [[0, 1, 1, 1], [0, 1, 0, 0], [0, 1, 1, 1]]),
        ((0.5, 0.25), [[0, 0, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0]]),
    ]:
        raster = pair.render(xy, layer='moving')
        np.testing.assert_array_equal(raster.rgba[:, :, 3], np.array(expected_valid) * 255)
        assert raster.overlap_pixels == sum(sum(row) for row in expected_valid)
    half = pair.render((0.5, 0), layer='moving')
    assert half.rgba[0, 2, 0] == 34  # Midpoint 1.5 in the original 0..11 display range.
    np.testing.assert_array_equal(moving.data, samples)
