"""Truth-free prediction and frozen historical-adapter contracts."""
import json

import numpy as np
import pytest

from stmdomains.experiments import e7_predict, e7_probe
from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.e5_predict import partition_arrays
from stmdomains.experiments.training.partition import fit_feature_adapter


def fixture():
    n = 12
    rng = np.random.default_rng(51)
    f = {name: rng.normal(size=(n, dim)) for name, dim in e7_probe.BLOCK_DIMENSIONS.items()}
    edges = np.array([(i, i + 1) for i in range(n - 1)])
    f.update(edges=edges, available=np.ones(n, bool), hard=np.ones(n, bool), full_gate=np.zeros(n, bool))
    rows = [dict(element_id=f'n{i}') for i in range(n)]
    spec = e7_probe.specs()[0]
    model = dict(spec=spec, mean=[0.] * 16, scale=[1.] * 16, coefficients=[0.] * 16,
                 intercept=0., calibration=e7_probe.calibrate_distances([.2, .3, .5, .7, .8]))
    adapter = fit_feature_adapter(f['geometry'], edges, [r['element_id'] for r in rows],
                                  scope=dict(regime='transfer', sampler='centers', scale_px=48, feature_id='geometry'))
    return f, rows, model, adapter


def test_partition_replay_uses_same_graph_and_post_partition_gate():
    f, rows, model, adapter = fixture()
    result = e7_predict.prediction_arrays(f, rows, model, adapter)
    np.testing.assert_array_equal(result['edges'], f['edges'])
    np.testing.assert_allclose(result['learned_score'], .5)
    np.testing.assert_allclose(result['learned_distance'], 1.)
    expected = partition_arrays([r['element_id'] for r in rows], f['edges'],
                                result['learned_distance'], result['common_valid'], model['calibration'],
                                f['hard'], f['full_gate'], 8)
    for key, value in expected.items():
        np.testing.assert_array_equal(result[f'learned__{key}'], value)
    assert (result['learned__fh4__before'] > 0).all()
    assert (result['learned__fh4__H_M1'] > 0).all()
    assert not result['learned__fh4__A_fixed_M1'].any()


def test_zero_legacy_raw_vector_remains_in_common_but_legacy_validity_is_explicit():
    f, rows, model, adapter = fixture()
    f['geometry'][0] = 0.
    f['rvae_20261103'][3] = np.nan
    result = e7_predict.prediction_arrays(f, rows, model, adapter)
    assert result['common_valid'][0] and not result['historical_valid'][0]
    assert not result['common_valid'][3] and result['available'][3]
    assert np.isfinite(result['learned_score'][0])
    assert np.isnan(result['historical_distance'][0])
    assert result['learned__fh4__before'][0] > 0
    assert result['historical__fh4__before'][0] == 0


def test_unavailable_learned_calibration_refuses_partitions_but_retains_pair_scores():
    f, rows, model, adapter = fixture()
    model['calibration'] = e7_probe.calibrate_distances([0., 0.])
    result = e7_predict.prediction_arrays(f, rows, model, adapter)
    assert np.isfinite(result['learned_score']).all()
    assert not result['learned_valid'].any()
    assert not result['learned__fh4__before'].any()
    assert not result['learned__mws__H_M1'].any()


def test_historical_copy_checks_e2_freeze_and_prediction_never_opens_truth(tmp_path, monkeypatch):
    f, rows, model, adapter = fixture()
    e2, out = tmp_path / 'e2', tmp_path / 'out'
    out.mkdir()
    spec = model['spec']
    monkeypatch.setattr(e7_predict, 'specs', lambda: [spec])
    relative = 'adapters/transfer/geometry/centers.json'
    write_json(e2 / relative, adapter)
    write_json(e2 / 'prediction-freeze.json', dict(files={relative: file_hash(e2 / relative)}))
    np.savez(out / 'f.npz', **f)
    write_json(out / 'r.json', rows)
    entry = dict(sample_id='validation', kind='synthetic', role='validation', group_id='new-seed',
                 features_file='f.npz', rows_file='r.json', truth_file='never-open-this-missing-file.npz')
    index, files = e7_predict.predict_all(None, e2, out, [entry], {spec['id']: model})
    assert len(index) == 1 and index[0]['model_id'] == 'geometry'
    assert file_hash(out / index[0]['adapter_file']) == file_hash(e2 / relative)
    assert index[0]['prediction_file'] in files
    assert index[0]['historical_invalid_common_nodes'] == 0
    changed = json.loads((e2 / relative).read_text())
    changed['edge_median'] *= 2
    write_json(e2 / relative, changed)
    with pytest.raises(ValueError, match='prediction freeze'):
        e7_predict.frozen_adapters(e2, out)
