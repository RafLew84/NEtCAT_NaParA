"""Geometry and evidence boundaries of the actual issue-21 predictor."""
import numpy as np

from stmdomains.experiments.controls import make_control
from stmdomains.experiments.training.predict import synthetic_rows, label_numbers


def test_resampled_controls_preserve_reference_grid_and_support():
    base, _, base_meta = make_control('single', 1701)
    doubled, _, doubled_meta = make_control('resample_2x', 1701)
    def rows(arrays, meta):
        return synthetic_rows(dict(sample_id='example', pixel_spacing_xy=meta['pixel_spacing_xy']), arrays)
    a, b = rows(base, base_meta), rows(doubled, doubled_meta)
    assert len(a) == len(b)
    for left, right in zip(a, b):
        assert left['element_id'] == right['element_id']
        assert left['available'] == right['available']
        assert left['scale_px'] == right['scale_px']
        np.testing.assert_allclose(np.array(left['raw_edge_xy'])*2, right['raw_edge_xy'])
        np.testing.assert_allclose(np.array(left['support_xyxy'])*2, right['support_xyxy'])


def test_grid_rows_are_unchanged_when_all_centers_are_removed():
    arrays, _, meta = make_control('single', 1701)
    record = dict(sample_id='example', pixel_spacing_xy=meta['pixel_spacing_xy'])
    before = [r for r in synthetic_rows(record, arrays) if r['sampler'] == 'grid']
    arrays = dict(arrays, centers_xy=np.empty((0, 2)), boxes_xyxy=np.empty((0, 4)), object_ids=np.array([], dtype='U1'))
    after = synthetic_rows(record, arrays)
    assert before == after


def test_component_encoding_keeps_refusals_and_partition_identity():
    result = label_numbers(['z', None, 'a', 'z', 'a'])
    assert result.tolist() == [2, 0, 1, 2, 1]


def test_small_field_keeps_all_planned_positions_as_unavailable():
    arrays = dict(image=np.zeros((20, 20)), measured=np.ones((20, 20), bool),
                  centers_xy=np.empty((0, 2)), boxes_xyxy=np.empty((0, 4)), object_ids=np.array([], dtype='U1'))
    rows = synthetic_rows(dict(sample_id='small', pixel_spacing_xy=[1., 1.]), arrays)
    assert len(rows) == 3
    assert not any(r['available'] for r in rows)
