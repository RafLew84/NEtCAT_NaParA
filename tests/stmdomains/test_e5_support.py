import numpy as np
import pytest

from stmdomains.experiments.e5_support import (
    footprint_context, snap_to_grid, support_masks, window_support,
)


def test_snap_preserves_nodes_and_uses_lower_tie_without_clipping():
    xy = np.array([[16., 0.], [15., 1.], [17., 17.], [255., 255.]])
    original = xy.copy()
    snapped = snap_to_grid(xy)
    np.testing.assert_array_equal(snapped, [[8., -8.], [8., 8.], [24., 24.], [248., 248.]])
    np.testing.assert_array_equal(snap_to_grid([[7., 8.], [9., 8.]]), [[8., 8.], [8., 8.]])
    np.testing.assert_array_equal(snap_to_grid([[8., 24.]], origin=16), [[0., 16.]])
    np.testing.assert_array_equal(xy, original)


def test_support_detects_measured_holes_and_image_border():
    measured = np.ones((20, 20), bool)
    measured[12, 12] = False
    result = window_support([[5., 5.], [12., 12.], [18., 10.]], 4, measured)
    np.testing.assert_array_equal(result["available"], [True, False, False])
    np.testing.assert_array_equal(result["nominal_boxes"][0], [3., 3., 7., 7.])
    np.testing.assert_array_equal(result["support_boxes"][0], [0., 0., 10., 10.])
    margin_hole = measured.copy()
    margin_hole[9, 9] = False
    assert not window_support([[5., 5.]], 4, margin_hole)["available"][0]


def test_comparison_masks_keep_own_denominators_and_fixed_edges():
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    scope = np.array([True, True, True, False])
    masks = dict(base=np.ones(4, bool), changed=np.array([True, True, False, True]))
    result = support_masks(masks, scope, edges)
    np.testing.assert_array_equal(result["common"], [True, True, False, False])
    assert result["counts"]["own"]["base"] == dict(nodes=3, edges=2, lost_to_common_nodes=1)
    assert result["counts"]["common_edges"] == 1
    assert masks["base"].all()  # no in-place narrowing of another contrast
    with pytest.raises(ValueError, match="Repeated"):
        support_masks(masks, scope, [[0, 1], [1, 0]])


def test_synthetic_purity_uses_original_anchor_not_snapped_context_label():
    labels = np.ones((12, 12), int)
    labels[:, 6:] = 2
    truth = dict(domain_labels=labels)
    result = footprint_context([[4., 6.], [6., 6.], [8., 6.]], 4, truth, "synthetic")
    np.testing.assert_array_equal(result["pure_synthetic"], [True, False, True])
    np.testing.assert_allclose(result["anchor_domain_fraction"], [1., .5, 1.])
    np.testing.assert_array_equal(result["positive_instance_count"], [1, 2, 1])
    moved = footprint_context([[8., 6.]], 4, truth, "synthetic", anchor_xy=[[4., 6.]])
    assert moved["anchor_labels"][0] == 1
    assert moved["anchor_domain_fraction"][0] == 0
    assert not moved["pure_synthetic"][0]


def test_uncertainty_and_outside_footprint_never_become_pure():
    uncertain = np.zeros((12, 12), bool)
    uncertain[4:6, 4:6] = True
    result = footprint_context([[6., 6.], [1., 1.]], 4,
        dict(domain_labels=np.ones((12, 12), int), boundary_unscored=uncertain), "synthetic")
    assert result["reference_known_fraction"][0] == .75
    assert not result["pure_synthetic"].any()
    assert np.isnan(result["reference_known_fraction"][1])
    assert result["positive_instance_count"][1] == -1


def test_real_roi_containment_is_not_domain_purity_and_margin_is_explicit():
    roi = dict(id="B", bbox_raw_xyxy=[218, 58, 250, 126])
    empty = footprint_context([[234., 94.]], 32, {}, "measurement", rois=[roi])
    assert empty["pure_synthetic"] is None
    assert not empty["known_interior_contained"].any()
    assert empty["roi_contained"]["B"].all()
    assert empty["unavailable_reason"] == "missing_reference_raster"
    guarded = footprint_context([[234., 94.]], 32, {}, "measurement", rois=[roi], margin=3)
    assert not guarded["roi_contained"]["B"].any()
    truth = dict(region_instances=np.ones((256, 256), int))
    known = footprint_context([[234., 94.]], 32, truth, "measurement")
    assert known["known_interior_contained"].all()
    assert known["pure_synthetic"] is None


def test_empty_support_and_invalid_inputs():
    measured = np.ones((10, 10), bool)
    assert window_support([], 4, measured)["available"].shape == (0,)
    assert support_masks(dict(a=np.zeros(0, bool)), np.zeros(0, bool), [])["counts"]["common_nodes"] == 0
    with pytest.raises(ValueError):
        snap_to_grid([[np.nan, 0]])
    with pytest.raises(ValueError):
        window_support([[5, 5]], 4, measured, margin=-1)
    with pytest.raises(ValueError):
        footprint_context([[5, 5]], 4, dict(domain_labels=np.ones(10, int)), "synthetic")
