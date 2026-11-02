"""Known correspondences exercise the public global-translation boundary."""
import numpy as np
import pytest

from stmviewer.correspondence_consensus import estimate_correspondence_translation


def test_spread_correspondences_return_subpixel_shift_moving_onto_reference():
    reference = np.array([(x, y) for y in (20., 55., 90., 120.)
                          for x in (25., 90., 160., 220.)])
    moving = reference - (6.25, -3.5)
    result = estimate_correspondence_translation(reference, moving, (151, 259), (151, 259))
    np.testing.assert_allclose(result.final_shift_xy, (6.25, -3.5), atol=1e-12)
    assert result.inlier_count == 16
    assert result.valid_count == 16
    assert sum(result.reference_support) == 16
    assert result.status == 'manual_review'


def test_outliers_and_padding_points_do_not_count_as_translation_support():
    reference = np.array([(x, y) for y in (20., 55., 90., 120.)
                          for x in (25., 90., 160., 220.)])
    moving = reference - (6.25, -3.5)
    # Six inconsistent vectors and two model-padding correspondences.
    p0 = np.vstack((reference, reference[:6], [[260., 20.], [20., 155.]]))
    p1 = np.vstack((moving, reference[:6] + [35., -12.], [[254., 23.], [14., 158.]]))
    result = estimate_correspondence_translation(p0, p1, (151, 259), (151, 259))
    np.testing.assert_allclose(result.final_shift_xy, (6.25, -3.5), atol=1e-12)
    assert result.input_count == 24
    assert result.valid_count == 22
    assert result.inlier_count == 16
    assert sum(result.reference_support) == 16


def test_narrow_band_returns_candidate_with_spatial_warning():
    reference = np.column_stack((np.linspace(20, 230, 40), np.linspace(60, 65, 40)))
    evidence = estimate_correspondence_translation(
        reference, reference - (2.5, -4.), (151, 259), (151, 259))
    np.testing.assert_allclose(evidence.final_shift_xy, (2.5, -4.))
    assert evidence.status == 'low_confidence'
    assert evidence.inlier_count == 40
    assert evidence.reference_span_xy[1] < .05
    assert 'przestrzen' in evidence.reason


def test_insufficient_matches_still_leave_no_global_shift():
    from stmviewer.correspondence_types import CorrespondenceRefusal

    points = np.array([(x, y) for y in (20., 55., 90., 120.) for x in (25., 90., 160., 220.)])
    # Not enough valid correspondences, or ten valid points with only three agreeing.
    mixed_moving = points[:10].copy() - np.array([(3., 2.)] * 3 + [(10. * i, 0.) for i in range(7)])
    cases = [(np.empty((0, 2)), np.empty((0, 2))),
             (points[:3], points[:3] + 3),
             (points[:7], points[:7] + 3), (points[:10], mixed_moving)]
    for reference, moving in cases:
        with pytest.raises(CorrespondenceRefusal) as failure:
            estimate_correspondence_translation(reference, moving, (151, 259), (151, 259))
        evidence = failure.value.diagnostics
        assert evidence.final_shift_xy is None
        assert 'mało' in evidence.reason
        assert len(evidence.reference_support) == 16


def test_competing_groups_return_explicitly_ambiguous_candidate():
    points = np.array([(x, y) for y in (20., 55., 90., 120.) for x in (25., 90., 160., 220.)])
    evidence = estimate_correspondence_translation(
        np.vstack((points, points)), np.vstack((points + [5., 0.], points - [5., 0.])),
        (151, 259), (151, 259))
    assert evidence.final_shift_xy in ((-5., 0.), (5., 0.))
    assert evidence.status == 'low_confidence'
    assert 'konkurencyjne' in evidence.reason
    assert '16' in evidence.reason


def test_diagonal_strip_retains_warning_about_limited_spatial_support():
    reference = np.column_stack((np.linspace(20, 230, 40), np.linspace(15, 130, 40)))
    evidence = estimate_correspondence_translation(
        reference, reference - (2.5, -4.), (151, 259), (151, 259))
    assert evidence.status == 'low_confidence'
    assert 'przestrzen' in evidence.reason


def test_two_grid_rows_or_columns_warn_even_when_span_exceeds_quarter():
    points = np.array([(x, y) for y in (58., 76., 96., 116.) for x in (20., 80., 160., 230.)])
    for reference, shape, xy in ((points, (192, 256), (2., -3.)),
                                 (points[:, ::-1], (256, 192), (-3., 2.))):
        evidence = estimate_correspondence_translation(reference, reference - xy, shape, shape)
        np.testing.assert_allclose(evidence.final_shift_xy, xy)
        assert evidence.status == 'low_confidence'
        assert 'przestrzen' in evidence.reason


@pytest.mark.parametrize('count', [4, 7, 9])
def test_small_consistent_group_is_available_for_review_without_false_certainty(count):
    rng = np.random.default_rng(431)
    reference = rng.uniform(50., 450., (100, 2))
    moving = rng.uniform(10., 490., (100, 2))
    moving[:count] = reference[:count] - (6.25, -3.5)
    result = estimate_correspondence_translation(reference, moving, (512, 512), (512, 512))
    np.testing.assert_allclose(result.final_shift_xy, (6.25, -3.5), atol=1e-12)
    assert result.inlier_count == count
    assert result.inlier_fraction == count / 100
    assert result.status == 'low_confidence'
    assert f'{count}/100' in result.reason
    assert result.settings_version == 2
