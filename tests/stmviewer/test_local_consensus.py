"""Public pair-to-local-evidence contract for REG-05."""

import numpy as np
from scipy.ndimage import gaussian_filter, shift

from stmviewer.local_consensus import estimate_local_consensus


def textured_images(xy=(13.25, -8.5), shape=(192, 256)):
    rng = np.random.default_rng(730)
    reference = gaussian_filter(rng.normal(size=shape), 1.25)
    moving = shift(reference, (-xy[1], -xy[0]), order=3, mode='constant', cval=0)
    return reference, moving


def test_local_search_recovers_subpixel_translation_from_inexact_deep_start():
    reference, moving = textured_images()
    originals = reference.copy(), moving.copy()
    result = estimate_local_consensus(reference, moving, (15.0, -7.0))

    np.testing.assert_allclose(result.final_shift_xy, (13.25, -8.5), atol=0.2)
    assert result.deep_shift_xy == (15.0, -7.0)
    assert result.status == 'manual_review'
    supported = [p for p in result.patches if p.status == 'inlier']
    assert len(supported) >= 4
    assert all(p.shift_xy is not None and p.moving_rect is not None for p in supported)
    for patch in supported:
        np.testing.assert_allclose(patch.shift_xy, (13.25, -8.5), atol=0.3)
    np.testing.assert_array_equal(reference, originals[0])
    np.testing.assert_array_equal(moving, originals[1])


def test_stationary_artifact_is_outvoted_by_spatially_separated_image_structures():
    reference, moving = textured_images((7.0, -5.0))
    rng = np.random.default_rng(99)
    artifact = gaussian_filter(rng.normal(size=(192, 40)), 0.8) * 40
    reference[:, 76:116] += artifact
    moving[:, 76:116] += artifact

    result = estimate_local_consensus(reference, moving, (8.0, -4.0))

    np.testing.assert_allclose(result.final_shift_xy, (7.0, -5.0), atol=0.2)
    rejected = [p for p in result.patches if p.status == 'outlier']
    assert len(rejected) >= 2
    assert all(p.shift_xy is not None and p.reason for p in rejected)
    supported = [p for p in result.patches if p.status == 'inlier']
    assert len({p.reference_rect[0] for p in supported}) >= 2
    assert len({p.reference_rect[1] for p in supported}) >= 2


def test_local_translation_does_not_depend_on_measurement_units_or_constant_offset():
    reference, moving = textured_images((-6.5, 9.25))
    result = estimate_local_consensus(reference * 1e-10 + 2e-8,
                                     moving * 1e-10 - 4e-8, (-7.0, 10.0))
    np.testing.assert_allclose(result.final_shift_xy, (-6.5, 9.25), atol=0.2)
    assert result.status == 'manual_review'


def test_periodic_image_reports_ambiguous_peaks_instead_of_claiming_one_translation():
    import pytest
    from stmviewer.local_consensus import LocalConsensusError

    y, x = np.mgrid[:192, :256]
    reference = np.cos(x * 2 * np.pi / 8) + np.sin(y * 2 * np.pi / 8)
    moving = np.roll(reference, (2, -3), axis=(0, 1))
    with pytest.raises(LocalConsensusError) as failure:
        estimate_local_consensus(reference, moving, (3.0, -2.0))
    evidence = failure.value.diagnostics
    assert evidence.final_shift_xy is None
    assert evidence.deep_shift_xy == (3.0, -2.0)
    assert evidence.patches and all(p.status == 'unmatched' for p in evidence.patches)
    assert any('Niejednoznaczne' in p.reason for p in evidence.patches)


def test_one_textured_scan_band_cannot_supply_global_spatial_support():
    import pytest
    from stmviewer.local_consensus import LocalConsensusError

    reference = np.zeros((192, 256))
    reference[56:88] = gaussian_filter(np.random.default_rng(41).normal(size=(32, 256)), 1)
    moving = shift(reference, (0, -7), order=3, mode='constant', cval=0)
    with pytest.raises(LocalConsensusError) as failure:
        estimate_local_consensus(reference, moving, (8.0, 1.0))
    diagnostics = failure.value.diagnostics
    assert diagnostics.final_shift_xy is None
    assert 'przestrzen' in diagnostics.reason
    assert any(p.shift_xy is not None for p in diagnostics.patches)


def test_two_spatial_motion_groups_remain_visible_and_the_global_result_is_uncertain():
    reference, _ = textured_images()
    upper = shift(reference, (2, -3), order=3, mode='constant', cval=0)
    lower = shift(reference, (-4, 5), order=3, mode='constant', cval=0)
    moving = upper.copy()
    moving[96:] = lower[96:]

    result = estimate_local_consensus(reference, moving, (0.0, 0.0))

    assert result.final_shift_xy is not None
    assert result.status == 'low_confidence'
    assert 'Konkurujące' in result.reason
    assert any(p.status == 'inlier' for p in result.patches)
    assert any(p.status == 'outlier' for p in result.patches)
    assert any(np.linalg.norm(np.asarray(result.final_shift_xy) - expected) < 0.2
               for expected in ((3, -2), (-5, 4)))


def test_patch_selection_finds_texture_away_from_cell_centers_without_overlapping_votes():
    reference = np.zeros((192, 256))
    rng = np.random.default_rng(113)
    for row in range(4):
        for column in range(4):
            y, x = row * 48 + 1, column * 64 + 1
            reference[y:y + 10, x:x + 10] = gaussian_filter(rng.normal(size=(10, 10)), 0.7)
    moving = shift(reference, (-2, -3), order=3, mode='constant', cval=0)
    result = estimate_local_consensus(reference, moving, (4.0, 1.0))
    np.testing.assert_allclose(result.final_shift_xy, (3, 2), atol=0.2)
    assert result.status == 'manual_review'
    patches = [p.reference_rect for p in result.patches]
    for i, (x, y, width, height) in enumerate(patches):
        for ox, oy, ow, oh in patches[i + 1:]:
            assert x + width <= ox or ox + ow <= x or y + height <= oy or oy + oh <= y


def test_missing_samples_are_refused_before_local_matching_and_are_never_filled():
    import pytest
    from stmviewer.local_consensus import LocalConsensusError

    reference, moving = textured_images()
    moving[0, 0] = np.nan
    with pytest.raises(LocalConsensusError, match='NaN/Inf') as failure:
        estimate_local_consensus(reference, moving, (15.0, -7.0))
    assert failure.value.diagnostics.final_shift_xy is None
    assert failure.value.diagnostics.patches == ()
    assert np.isnan(moving[0, 0])


def test_cancellation_from_last_progress_update_cannot_publish_a_result():
    import pytest
    from threading import Event
    from stmviewer.registration import RegistrationCancelled

    reference, moving = textured_images()
    stopped = Event()
    updates = []
    def progress(text):
        updates.append(text)
        if len(updates) == 16:
            stopped.set()
    with pytest.raises(RegistrationCancelled):
        estimate_local_consensus(reference, moving, (15.0, -7.0),
                                 progress=progress, cancelled=stopped.is_set)


def test_images_must_have_equal_dimensions_and_room_for_independent_patches():
    import pytest
    from stmviewer.local_consensus import LocalConsensusError

    for reference, moving, reason in (
        (np.zeros((128, 128)), np.zeros((128, 96)), 'wymiary'),
        (np.zeros((16, 16)), np.zeros((16, 16)), 'mały'),
    ):
        with pytest.raises(LocalConsensusError, match=reason) as failure:
            estimate_local_consensus(reference, moving, (0.0, 0.0))
        assert failure.value.diagnostics.final_shift_xy is None
        assert failure.value.diagnostics.patches == ()


def test_distinct_noisy_peaks_can_support_translation_below_large_absolute_correlation():
    from scipy.ndimage import map_coordinates

    rng = np.random.default_rng(202605)
    field = gaussian_filter(rng.normal(size=(320, 384)), 1.25)
    field /= field.std()
    y, x = np.mgrid[64:256, 64:320].astype(float)
    reference = map_coordinates(field, [y, x], order=3)
    moving = map_coordinates(field, [y - 5, x + 7], order=3)
    for frame in (reference, moving):
        noise = rng.normal(size=frame.shape)
        frame += noise / noise.std() * np.sqrt(1 / 0.3 - 1)

    result = estimate_local_consensus(reference, moving, (8.0, -4.0))

    np.testing.assert_allclose(result.final_shift_xy, (7.0, -5.0), atol=0.3)
    supported = [p for p in result.patches if p.status == 'inlier']
    assert len(supported) >= 4
    assert all(p.score < 0.45 for p in supported)
    assert all(p.peak_contrast is not None and p.peak_contrast >= 3.5 for p in supported)


def test_independent_noise_does_not_create_global_motion_after_relaxing_absolute_correlation():
    import pytest
    from stmviewer.local_consensus import LocalConsensusError

    for sigma in (0, 1):
        for seed in range(5):
            rng = np.random.default_rng(202605 + seed)
            frames = [rng.normal(size=(192, 256)) for _ in range(2)]
            if sigma:
                frames = [gaussian_filter(frame, sigma) for frame in frames]
            with pytest.raises(LocalConsensusError) as failure:
                estimate_local_consensus(*frames, (8.0, -4.0))
            assert failure.value.diagnostics.final_shift_xy is None
