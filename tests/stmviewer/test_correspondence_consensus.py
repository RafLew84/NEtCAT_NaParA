"""Known correspondences exercise the public global-translation boundary."""
import numpy as np

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


def test_narrow_band_cannot_supply_global_two_dimensional_support():
    import pytest
    from stmviewer.correspondence_types import CorrespondenceRefusal

    reference = np.column_stack((np.linspace(20, 230, 40), np.linspace(60, 65, 40)))
    with pytest.raises(CorrespondenceRefusal) as failure:
        estimate_correspondence_translation(reference, reference - (2.5, -4.), (151, 259), (151, 259))
    evidence = failure.value.diagnostics
    assert evidence.final_shift_xy is None
    assert evidence.inlier_count == 40
    assert evidence.reference_span_xy[1] < .05
    assert 'przestrzen' in evidence.reason


def test_insufficient_or_ambiguous_matches_leave_no_global_shift():
    import pytest
    from stmviewer.correspondence_types import CorrespondenceRefusal

    points = np.array([(x, y) for y in (20., 55., 90., 120.) for x in (25., 90., 160., 220.)])
    cases = [
        (np.empty((0, 2)), np.empty((0, 2)), 'mało'),
        (points[:3], points[:3] + 3, 'mało'),
        (np.vstack((points, points)), np.vstack((points + [5., 0.], points - [5., 0.])), 'Niejednoznaczne'),
    ]
    for reference, moving, message in cases:
        with pytest.raises(CorrespondenceRefusal) as failure:
            estimate_correspondence_translation(reference, moving, (151, 259), (151, 259))
        evidence = failure.value.diagnostics
        assert evidence.final_shift_xy is None
        assert message in evidence.reason
        assert len(evidence.reference_support) == 16


def test_diagonal_strip_is_not_mistaken_for_two_dimensional_spatial_support():
    import pytest
    from stmviewer.correspondence_types import CorrespondenceRefusal

    reference = np.column_stack((np.linspace(20, 230, 40), np.linspace(15, 130, 40)))
    with pytest.raises(CorrespondenceRefusal, match='przestrzen'):
        estimate_correspondence_translation(reference, reference - (2.5, -4.), (151, 259), (151, 259))


def test_two_grid_rows_or_columns_are_local_support_even_when_span_exceeds_quarter():
    import pytest
    from stmviewer.correspondence_types import CorrespondenceRefusal

    points = np.array([(x, y) for y in (58., 76., 96., 116.) for x in (20., 80., 160., 230.)])
    for reference, shape, xy in ((points, (192, 256), (2., -3.)),
                                 (points[:, ::-1], (256, 192), (-3., 2.))):
        with pytest.raises(CorrespondenceRefusal) as failure:
            estimate_correspondence_translation(reference, reference - xy, shape, shape)
        assert failure.value.diagnostics.final_shift_xy is None
        assert 'przestrzen' in failure.value.diagnostics.reason
