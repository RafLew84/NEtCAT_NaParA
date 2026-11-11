"""Bounded E7 fit contracts; no existing scientific input or checkpoints."""
import json

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning
import warnings

from stmdomains.experiments import e7_probe as probe
from stmdomains.experiments.bundle import write_json


def features(n=10):
    rng = np.random.default_rng(27)
    result = {name: rng.normal(size=(n, dimension))
              for name, dimension in probe.BLOCK_DIMENSIONS.items()}
    result.update(available=np.ones(n, bool), hard=np.ones(n, bool), full_gate=np.zeros(n, bool),
                  edges=np.array([(a, b) for a in range(n) for b in range(a + 1, n)], dtype=int))
    return result


def test_common_preserves_zeros_and_pair_features_are_symmetric():
    f = features(3)
    for name in probe.BLOCK_DIMENSIONS:
        f[name][0] = 0.
    assert probe.common_nodes(f).all()
    f['rvae_20261103'][2, 1] = np.nan
    assert probe.common_nodes(f).tolist() == [True, True, False]
    edges = np.array([[0, 1], [1, 0]])
    x = probe.pair_features(f, edges, ['geometry', 'ae_20261101'])
    np.testing.assert_array_equal(x[0], x[1])
    assert x.shape == (2, 80)
    assert probe.pair_features(f, np.empty((0, 2), int), ['geometry']).shape == (0, 16)


def test_group_class_weights_equal_cells_not_raw_class_sizes():
    groups = ['a'] * 5 + ['b'] * 4
    target = [0, 0, 0, 1, 1, 0, 1, 1, 1]
    w, cells = probe.group_class_weights(groups, target)
    assert w.mean() == pytest.approx(1.)
    np.testing.assert_allclose([r['weight_sum'] for r in cells], len(w) / 4)
    with pytest.raises(ValueError, match='Both relation classes'):
        probe.group_class_weights(['a', 'b'], [1, 1])
    with pytest.raises(ValueError, match='Every training group'):
        probe.group_class_weights(['a', 'b'], [0, 1])


def test_json_probe_matches_weighted_sklearn_probability():
    rng = np.random.default_rng(18)
    x = rng.normal(size=(40, 5))
    x[:, -1] = 0.
    y = np.array([0] * 13 + [1] * 7 + [0] * 9 + [1] * 11)
    groups = ['a'] * 20 + ['b'] * 20
    w, _ = probe.group_class_weights(groups, y)
    scaler = StandardScaler().fit(x, sample_weight=w)
    expected = LogisticRegression(C=1., penalty='l2', solver='lbfgs', max_iter=2000,
                                  tol=1e-8).fit(scaler.transform(x), y, sample_weight=w)
    model = json.loads(json.dumps(probe.fit_model(x, y, groups), allow_nan=False))
    np.testing.assert_allclose(model['mean'], scaler.mean_)
    np.testing.assert_allclose(probe.predict_same(model, x), expected.predict_proba(scaler.transform(x))[:, 1], atol=1e-12)
    assert model['scale'][-1] == 1.


def test_fit_reads_train_only_and_calibration_includes_unlabeled_edges(tmp_path):
    f = features()
    f['ae_20261103'][9] = np.nan
    np.savez(tmp_path / 'features.npz', **f)
    rows = [dict(element_id=f'n{i}', available=True, raw_edge_xy=[float(i), 0.]) for i in range(10)]
    write_json(tmp_path / 'rows.json', rows)
    np.savez(tmp_path / 'truth.npz', domain_labels=np.array([1, 1, 1, 2, 2, 2, 0, 0, 3, 3]),
             evaluation_valid=np.ones(10, bool), boundary_uncertain=np.array([False] * 8 + [True, False]))
    entry = dict(sample_id='train', group_id='seed-a', kind='synthetic', role='train',
                 features_file='features.npz', rows_file='rows.json', truth_file='truth.npz')
    unseen = dict(sample_id='validation', group_id='other', kind='synthetic', role='validation',
                  features_file='must-not-open.npz', rows_file='must-not-open.json', truth_file='must-not-open-truth.npz')
    models, files = probe.fit_probes(tmp_path, [entry, unseen])
    assert len(models) == 8 and len(files) == 11
    order = json.loads((tmp_path / 'probe-fit-order.json').read_text())
    assert list(models) == order['order']
    expected = np.random.default_rng(20261117).permutation(8)
    assert order['order'] == [probe.specs()[i]['id'] for i in expected]
    audit = json.loads((tmp_path / 'probe-fit-audit.json').read_text())
    assert audit['samples'] == [dict(sample_id='train', group_id='seed-a', usable_train_edges=36,
                                      selected_same=6, selected_different=9)]
    assert not audit['case_metadata_read']
    for model in models.values():
        assert model['training_pairs'] == 15
        assert model['same_pairs'] == 6 and model['different_pairs'] == 9
        assert model['calibration']['training_edges'] == 36
        assert model['training_samples'] == ['train']
        assert not model['validation_labels_accessed']
        assert 'must-not-open-truth.npz' not in model['input_sha256']


def test_degenerate_calibration_is_explicit_and_ties_remain_ties():
    assert probe.calibrate_distances([])['reason'] == 'no_training_edges'
    assert probe.calibrate_distances([0., 0.])['reason'] == 'all_training_distances_zero'
    result = probe.calibrate_distances([.5, .5])
    assert result['available'] and result['collapsed_quantiles']
    assert result['edge_median'] == .5 and result['q25'] == result['q75'] == 1.
    result = probe.calibrate_distances([0., .2, .4])
    assert result['zero_training_edges'] == 1 and result['edge_median'] == pytest.approx(.3)
    result = probe.calibrate_distances([0., 1e-12, 3e-12])
    assert result['raw_positive_median'] == pytest.approx(2e-12)
    assert result['edge_median'] == result['median_floor'] == 1e-10
    np.testing.assert_allclose([result['q25'], result['q75']], [.005, .02])
    with pytest.raises(ValueError, match='finite'):
        probe.calibrate_distances([np.nan])


def test_convergence_warning_stops_fixed_budget_probe(monkeypatch):
    def failed_fit(*args, **kwargs):
        warnings.warn('iteration budget exhausted', ConvergenceWarning)
    monkeypatch.setattr(probe.LogisticRegression, 'fit', failed_fit)
    with pytest.raises(RuntimeError, match='failed to converge'):
        probe.fit_model(np.arange(8).reshape(4, 2), [0, 1, 0, 1], ['a'] * 4)
