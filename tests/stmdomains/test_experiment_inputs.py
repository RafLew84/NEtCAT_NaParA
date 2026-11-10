"""Geometry, ablation, isolation and scoring contracts for research inputs."""

import copy

import numpy as np
import pytest

from stmdomains.experiments.bundle import arrays_hash, load_sample, validate_input, write_arrays, write_json
from stmdomains.experiments.controls import CASES, make_control
from stmdomains.experiments.real_input import convert_detections
from stmdomains.experiments.results import pair_scores, validate_result


@pytest.mark.parametrize('case', CASES)
def test_controls_have_finite_label_free_inputs_and_separate_truth(case):
    arrays, truth, meta = make_control(case, 1701)
    validate_input(arrays)
    assert set(arrays) == {'image', 'measured', 'centers_xy', 'boxes_xyxy', 'object_ids'}
    assert truth['domain_labels'].shape == arrays['image'].shape
    assert np.array_equal(truth['evaluation_valid'], ~truth['boundary_uncertain'])
    assert len(set(truth['domain_labels'].ravel()) - {0}) == meta['expected_domain_count']
    assert np.isfinite(truth['orientation_deg'][truth['type_labels'] == 1]).all()


@pytest.mark.parametrize('case', ['missing_10', 'missing_30', 'missing_50', 'missing_local'])
def test_detection_ablations_do_not_change_image_or_truth(case):
    base, truth, _ = make_control('single', 1701)
    missing, changed_truth, _ = make_control(case, 1701)
    assert np.array_equal(missing['image'], base['image'])
    assert arrays_hash(truth) == arrays_hash(changed_truth)
    assert 0 < len(missing['object_ids']) < len(base['object_ids'])
    by_id = dict(zip(base['object_ids'], base['centers_xy']))
    assert all(np.array_equal(by_id[i], p) for i, p in zip(missing['object_ids'], missing['centers_xy']))


def test_resampling_and_crop_preserve_physical_positions_and_spacing():
    base, _, _ = make_control('single', 1701)
    scaled, truth, meta = make_control('resample_2x', 1701)
    np.testing.assert_allclose(scaled['centers_xy'] * meta['pixel_spacing_xy'], base['centers_xy'])
    assert np.all(truth['spacing_reference_px'] == 12)
    cropped, _, meta = make_control('crop', 1701)
    by_id = dict(zip(base['object_ids'], base['centers_xy']))
    expected = np.array([by_id[i] for i in cropped['object_ids']])
    np.testing.assert_allclose(cropped['centers_xy'] + meta['offset_in_base_xy'], expected)
    _, wider_truth, _ = make_control('larger_spacing', 1701)
    assert np.all(wider_truth['spacing_reference_px'] == 16)


def test_type_orientation_and_domain_are_separate():
    _, truth, meta = make_control('two_orientations', 1701)
    assert meta['expected_domain_count'] == 2
    assert np.unique(truth['type_labels']).tolist() == [1]
    assert np.unique(truth['orientation_deg']).tolist() == [0., 27.]
    _, truth, meta = make_control('phase_boundary', 1701)
    assert meta['expected_domain_count'] == 2
    assert np.unique(truth['type_labels']).tolist() == [1]
    assert np.unique(truth['orientation_deg']).tolist() == [0.]
    _, truth, meta = make_control('single_defect', 1701)
    assert meta['expected_domain_count'] == 1
    assert truth['domain_labels'].min() == 1


def detection(ident, box, view='expanded_aligned'):
    return dict(frame_index=0, detection_id=ident, bbox_xyxy=box, source_view=view,
                original_bbox_xyxy=[999]*4, domain_id='forbidden_legacy')


def test_current_boxes_transform_without_clipping_and_filter_by_center():
    origins = np.array([[10.25, 20.5]])
    rows = [detection('a', [9.25, 19.5, 15.25, 25.5]),
            detection('b', [0., 0., 1., 1.]),
            detection('c', [9., 2., 11., 4.], 'raw')]
    frames, excluded = convert_detections(rows, origins, (10, 10))
    assert [i for i, _ in frames[0]] == ['a']
    np.testing.assert_allclose(frames[0][0][1], [-1, -1, 5, 5])
    assert {e['object_id'] for e in excluded} == {'b', 'c'}
    np.testing.assert_allclose(frames[0][0][1] + np.tile(origins[0], 2), rows[0]['bbox_xyxy'])


@pytest.mark.parametrize('box', [[0, 0, 0, 1], [0, np.nan, 2, 2]])
def test_invalid_boxes_fail_instead_of_becoming_missing_data(box):
    with pytest.raises(ValueError):
        convert_detections([detection('a', box)], np.zeros((1, 2)), (10, 10))


def test_repeatability_and_sample_hashes(tmp_path):
    first, _, _ = make_control('random_minsep', 1702)
    second, _, _ = make_control('random_minsep', 1702)
    assert arrays_hash(first) == arrays_hash(second)
    different, _, _ = make_control('random_minsep', 2702)
    assert arrays_hash(first) != arrays_hash(different)
    directory = tmp_path/'analysis'
    hashes = write_arrays(directory/'samples/example.npz', first)
    write_json(directory/'manifest.json', dict(schema='stmdomains-input-v1', samples=[dict(sample_id='example', file='samples/example.npz', **hashes)]))
    _, loaded = load_sample(directory, 'example')
    assert arrays_hash(loaded) == arrays_hash(first)
    # Any changes in a separate evaluation tree are irrelevant to the loader.
    write_json(tmp_path/'evaluation/manifest.json', dict(labels=[1, 2, 3]))
    assert arrays_hash(load_sample(directory, 'example')[1]) == arrays_hash(first)
    (tmp_path/'evaluation/manifest.json').unlink()
    assert arrays_hash(load_sample(directory, 'example')[1]) == arrays_hash(first)
    first['image'][0, 0] += 1
    write_arrays(directory/'samples/example.npz', first)
    with pytest.raises(ValueError, match='hash mismatch'):
        load_sample(directory, 'example')


def test_analysis_rejects_labels_and_centers_in_padding():
    arrays, _, _ = make_control('single', 1701)
    bad = dict(arrays, domain_labels=np.ones_like(arrays['image']))
    with pytest.raises(ValueError, match='fields'):
        validate_input(bad)
    x, y = np.floor(arrays['centers_xy'][0]).astype(int)
    arrays['measured'][y, x] = False
    with pytest.raises(ValueError, match='measured pixels'):
        validate_input(arrays)


def test_pair_metrics_distinguish_merging_splitting_and_refusal():
    ref = [1, 1, 2, 2, 0]
    perfect = pair_scores(ref, [8, 8, 9, 9, 99])
    assert perfect['merge_rate'] == perfect['split_rate'] == 0
    assert perfect['assignment_fraction'] == 1
    assert pair_scores(ref, [1, 1, 1, 1, 0])['merge_rate'] == 1
    assert pair_scores(ref, [1, 2, 3, 4, 0])['split_rate'] == 1
    refusal = pair_scores(ref, [-1, -1, -1, -1, 0])
    assert refusal['assignment_fraction'] == 0
    assert refusal['merge_rate'] is refusal['split_rate'] is None


def test_result_contract_preserves_unknown_states():
    result = dict(schema='stmdomains-result-v1', sample_id='s1', input_content_sha256='abc',
                  run_id='run1', catalogue_id='cat1', assignments=[
                      dict(element_id='p1', xy=[1., 1.], support_xyxy=[0, 0, 2, 2],
                           state='insufficient_data', reason='too_few_repeats',
                           type_id=None, domain_id=None, orientation_deg=None)])
    validate_result(result)
    bad = copy.deepcopy(result); bad['assignments'][0]['domain_id'] = 'D1'
    with pytest.raises(ValueError): validate_result(bad)
    bad = copy.deepcopy(result); bad['assignments'][0]['state'] = 'recognized'
    with pytest.raises(ValueError): validate_result(bad)
