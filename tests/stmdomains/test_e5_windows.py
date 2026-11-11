"""E5 extraction rows preserve graph anchors while recomputing true support."""
from copy import deepcopy

import numpy as np
import pytest

from stmdomains.experiments.e5_windows import patch_rows
from stmdomains.experiments.training.data import extract_patch, window_records
from stmdomains.experiments.training.predict import synthetic_rows


def fixture(centers=((56., 56.), (64., 64.), (20., 50.)), *, origin=(264., 0.)):
    xy = np.asarray(centers)
    yy, xx = np.mgrid[:128, :128]
    arrays = dict(image=(xx + 2 * yy).astype(np.float32), measured=np.ones((128, 128), bool),
                  centers_xy=xy, boxes_xyxy=np.column_stack((xy - 1, xy + 1)),
                  object_ids=np.asarray([f"m{i}" for i in range(len(xy))]))
    record = dict(sample_id="sample", frame_number=1, origin_in_expanded_xy=list(origin))
    rows = [r for r in window_records(record, arrays) if r["sampler"] == "centers" and r["scale_raw_px"] == 48]
    return record, arrays, rows


def test_exact_rows_preserve_original_preprocessing_and_do_not_mutate_inputs():
    record, arrays, rows = fixture()
    before = deepcopy(rows)
    changed = patch_rows(record, arrays, rows)
    assert rows == before
    for original, new in zip(rows, changed):
        for key in ("window_id", "element_id", "raw_edge_xy", "feature_support_xyxy",
                    "support_xyxy", "expanded_support_xyxy", "available", "transfer_split"):
            assert new[key] == original[key]
        if original["available"]:
            normalizer = dict(low=20., high=250.)
            np.testing.assert_array_equal(extract_patch(arrays, new, normalizer),
                                          extract_patch(arrays, original, normalizer))


def test_snap_and_shift_ties_preserve_nodes_and_recompute_support_membership():
    record, arrays, rows = fixture()
    snapped = patch_rows(record, arrays, rows, centering="snap")
    shifted = patch_rows(record, arrays, rows, centering="shifted")
    assert snapped[1]["raw_edge_xy"] == [56., 56.]
    assert shifted[0]["raw_edge_xy"] == [48., 48.]
    assert snapped[1]["node_raw_edge_xy"] == [64., 64.]
    assert snapped[1]["displacement_xy"] == [-8., -8.]
    assert snapped[1]["window_id"] == rows[1]["window_id"]
    # Original x64 support + origin264 starts301: both excluded here.
    assert snapped[1]["expanded_support_xyxy"] == [293., 29., 347., 83.]
    # Move the origin so exact fits guarded train, but snapped support crosses it.
    record["origin_in_expanded_xy"] = [292., 0.]
    exact = patch_rows(record, arrays, rows)
    snapped = patch_rows(record, arrays, rows, centering="snap")
    assert exact[1]["transfer_split"] == "train"
    assert snapped[1]["transfer_split"] is None
    assert snapped[1]["transfer_exclusion_reason"] == "spatial_holdout_or_guard"
    # New rows allow an 8px center movement without abusing extract_patch's ±2 shift.
    patch = extract_patch(arrays, snapped[1])
    assert patch.shape == (64, 64)
    assert patch.mean() == pytest.approx(166.5)


def test_smaller_scale_can_restore_support_but_holes_and_borders_never_pad():
    record, arrays, rows = fixture()
    assert not rows[2]["available"]
    smaller = patch_rows(record, arrays, rows, scale=32)
    assert smaller[2]["available"]
    assert smaller[2]["window_id"] == rows[2]["window_id"]
    assert smaller[2]["source_scale_raw_px"] == 48
    assert smaller[2]["scale_raw_px"] == 32
    arrays["measured"][40, 40] = False
    assert not patch_rows(record, arrays, rows)[0]["available"]
    record, arrays, rows = fixture(((1., 50.),))
    shifted = patch_rows(record, arrays, rows, centering="shifted")
    assert shifted[0]["raw_edge_xy"][0] == 0.
    assert not shifted[0]["available"]
    with pytest.raises(ValueError, match="incomplete"):
        extract_patch(arrays, shifted[0])


def test_empty_and_refused_ambiguous_variant_inputs():
    record, arrays, rows = fixture()
    assert patch_rows(record, arrays, []) == []
    with pytest.raises(ValueError, match="original"):
        patch_rows(record, arrays, patch_rows(record, arrays, rows))
    with pytest.raises(ValueError, match="unique"):
        patch_rows(record, arrays, rows + rows)
    with pytest.raises(ValueError, match="Unknown"):
        patch_rows(record, arrays, rows, scale=16)
    with pytest.raises(ValueError, match="same sample"):
        patch_rows(dict(record, sample_id="other"), arrays, rows)


def test_technically_resampled_control_preserves_reference_pixel_scale_and_grid():
    _, arrays, _ = fixture(((64., 64.),))
    record = dict(sample_id="resampled", kind="synthetic", pixel_spacing_xy=[.5, .5])
    rows = [r for r in synthetic_rows(record, arrays) if r['sampler'] == 'grid' and r['scale_px'] == 48]
    changed = patch_rows(record, arrays, rows)
    snapped = patch_rows(record, arrays, rows, centering='snap')
    for old, new, snap in zip(rows, changed, snapped):
        assert old['scale_raw_px'] == new['scale_raw_px'] == 96
        assert old['support_xyxy'] == new['support_xyxy']
        assert old['available'] == new['available']
        assert old['raw_edge_xy'] == snap['raw_edge_xy']
        if old['available']:
            np.testing.assert_array_equal(extract_patch(arrays, old), extract_patch(arrays, new))
    smaller = patch_rows(record, arrays, rows, scale=32)
    assert smaller[0]['scale_raw_px'] == 64
    shifted = patch_rows(record, arrays, rows, centering='shifted')
    assert shifted[0]['displacement_xy'] == [-16., -16.]
    assert shifted[0]['displacement_reference_xy'] == [-8., -8.]
