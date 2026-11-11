import numpy as np
import pytest

from stmdomains.experiments.e5_predict import partition_arrays
from stmdomains.experiments.e7a_predict import predict, signed_relations
from stmdomains.experiments.training.partition import mws_partition


def test_signed_evidence_endpoints_neutral_and_missing():
    kinds, weights = signed_relations([0, .1, .5, .8, 1, np.nan], .5)
    assert kinds.tolist() == ['repulsive', 'repulsive', 'none', 'attractive', 'attractive', 'unavailable']
    np.testing.assert_allclose(weights, [1, .8, 0, .6, 1, np.nan])
    for threshold in (.25, .75):
        k, w = signed_relations([0, threshold, 1], threshold)
        assert k.tolist() == ['repulsive', 'none', 'attractive']
        np.testing.assert_equal(w, [1, 0, 1])


@pytest.mark.parametrize('score,threshold', [([1.01], .5), ([-.01], .5), ([np.inf], .5), ([.3], 0), ([.3], 1)])
def test_invalid_probability_inputs_fail(score, threshold):
    with pytest.raises(ValueError):
        signed_relations(score, threshold)


def test_mutex_prevents_strong_conflict_and_reports_late_weak_conflict():
    edges = np.array([[0, 1], [1, 2], [0, 2]])
    kinds, weights = signed_relations([.95, .8, .01], .5)
    result = mws_partition(['a', 'b', 'c'], edges, kinds, weights)
    assert result['component_ids'] == ['a', 'a', 'c']
    assert result['stats']['blocked_attractions'] == 1
    kinds, weights = signed_relations([.95, .9, .4], .5)
    result = mws_partition(['a', 'b', 'c'], edges, kinds, weights)
    assert result['component_ids'] == ['a', 'a', 'a']
    assert result['stats']['late_repulsive_conflicts'] == 1


def test_row_order_and_edge_direction_do_not_change_domains():
    ids = ['c', 'a', 'b']
    edges = np.array([[0, 1], [1, 2], [0, 2]])
    kinds, weights = signed_relations([.1, .9, .8], .5)
    original = mws_partition(ids, edges, kinds, weights)['component_ids']
    order = np.array([2, 0, 1])
    inverse = np.argsort(order)
    result = mws_partition([ids[i] for i in order], inverse[edges[::-1, ::-1]],
                           kinds[::-1], weights[::-1])['component_ids']
    assert dict(zip(ids, original)) == dict(zip([ids[i] for i in order], result))


def fixture_data(n=10):
    rows = [dict(element_id=f'p{i:02d}', available=True, raw_edge_xy=[10.+i, 20.]) for i in range(n)]
    edges = np.array([[i, i+1] for i in range(n-1)], int).reshape(-1, 2)
    valid = np.arange(n) < n-1
    score = np.where(valid[edges].all(axis=1), .9, np.nan)
    calibration = dict(available=True, edge_median=.1, q25=.5, q75=1.5)
    data = dict(edges=edges, learned_valid=valid, common_valid=valid,
                available=np.ones(n, bool), hard=np.ones(n, bool), full_gate=np.zeros(n, bool),
                learned_score=score, learned_distance=(1-score)/.1)
    replay = partition_arrays([r['element_id'] for r in rows], edges, data['learned_distance'], valid,
                              calibration, data['hard'], data['full_gate'], 8)
    data.update({f'learned__{k}': v for k, v in replay.items()})
    return rows, data, calibration


def test_replay_and_refusals_keep_missing_feature_in_physical_denominator():
    rows, data, calibration = fixture_data()
    actual, audit = predict(data, rows, calibration)
    assert audit['baseline_arrays_exact'] == 6 and audit['fh_scaled_k_identity']
    assert actual['available'].sum() == 10
    assert (actual['mws_t050__H_M1'] > 0).sum() == 9
    assert (actual['mws_t050__A_fixed_M1'] > 0).sum() == 0
    assert actual['mws_t050__before'][-1] == 0
    np.testing.assert_equal(actual['learned_score'], data['learned_score'])
    data['learned__mws__before'][0] = 999
    with pytest.raises(ValueError, match='replay'):
        predict(data, rows, calibration)


def test_no_nodes_is_valid_empty_result():
    rows, data, calibration = fixture_data(0)
    actual, _ = predict(data, rows, calibration)
    assert all(not len(values) for values in actual.values())
