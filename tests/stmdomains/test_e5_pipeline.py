"""Miniature E5 calibration/prediction contracts; no scientific files or models."""
from types import SimpleNamespace

import numpy as np
import pytest

from stmdomains.experiments import e5_fit, e5_predict
from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.e5_catalog import conditions
from stmdomains.experiments.e5_generate import check_baseline, extraction_masks
from stmdomains.experiments.training.partition import fit_feature_adapter


def test_evaluation_membership_is_geometric_even_when_pixels_are_unavailable():
    record = dict(kind='measurement', frame_number=259, origin_in_expanded_xy=[0., 0.])
    rows = [dict(available=False, transfer_split=None, support_xyxy=[1., 1., 60., 60.], raw_edge_xy=[30., 30.]),
            dict(available=True, transfer_split='test', support_xyxy=[130., 1., 170., 60.], raw_edge_xy=[150., 30.])]
    result = extraction_masks(record, rows, 'transfer')
    assert result['scope'].tolist() == [True, False]
    assert result['available'].tolist() == [False, True]
    assert not result['train'].any()
    record['frame_number'], record['origin_in_expanded_xy'] = 1, [327., 0.]
    result = extraction_masks(record, rows, 'transfer')
    assert result['train'].tolist() == [True, False]
    result = extraction_masks(dict(kind='synthetic'), rows, 'transfer')
    assert result['scope'].all() and not result['train'].any()


def test_common_masks_are_contrast_local_and_do_not_hide_feature_missingness():
    shared = {}
    for key in ('exact32', 'exact48', 'exact64', 'snap48', 'shifted48'):
        shared[f'{key}__available'] = np.ones(4, bool)
        shared[f'{key}__scope'] = np.ones(4, bool)
    shared['exact64__available'][0] = False
    shared['shifted48__scope'][1] = False
    result = e5_predict.condition_masks(shared, conditions('ae'))
    assert result['map_base']['common']['available'].all()
    assert result['map_full']['common']['scope'].all()
    assert result['scale_base']['common']['available'].tolist() == [False, True, True, True]
    assert result['center_snap']['common']['scope'].tolist() == [True, False, True, True]
    assert result['scale32']['own']['available'].all()


def training_fixture(tmp_path):
    run = dict(run_id='transfer/ae/z32/seed-20261101', regime='transfer', family='ae', seed=20261101)
    rows = [dict(window_id=f'frame/centers/m{i}/s48', element_id=f'm{i}') for i in range(6)]
    ids = [r['window_id'] for r in rows]
    graph = dict(window_ids=ids, edges=np.array([[0, 1], [1, 4], [0, 4], [4, 5], [0, 5]]),
                 segments=[dict(group_id='frame/centers/s48', row_indices=np.arange(6), start=0, stop=6)],
                 training_ids_sha256='historical-only', membership_source='old-fit.json')
    bank = SimpleNamespace(inputs=SimpleNamespace(rows=lambda _group: rows), training_graph=lambda *_args: graph)
    base = np.array([[1., 0.], [1., 1.], [.2, 1.], [1., .3], [0., 1.], [-1., .2]])
    spatial = np.column_stack((base, np.ones(6)))
    spatial[1] = 0.
    np.savez(tmp_path / 'features.npz', exact48=base, map48=spatial)
    available, train = np.ones(6, bool), np.ones(6, bool)
    available[2], train[3] = False, False
    np.savez(tmp_path / 'shared.npz', exact48__available=available, exact48__train=train,
             exact48__scope=np.ones(6, bool), edges=graph['edges'], baseline_hard=np.ones(6, bool),
             baseline_full_gate=np.ones(6, bool))
    group = dict(regime='transfer', cache_group='frame/centers/s48', shared='shared.npz',
                 sampler='centers', sample_id='frame', kind='measurement', pixel_spacing_xy=[1., 1.],
                 features={run['run_id']: 'features.npz'})
    selected = [c for c in conditions('ae') if c['contrast'] == 'map']
    return bank, run, group, selected


def test_training_intersection_uses_all_features_and_geometry_without_new_edges(tmp_path):
    bank, run, group, selected = training_fixture(tmp_path)
    values, edges, ids, audit = e5_fit.matched_training(bank, tmp_path, [group], run, 'centers', selected)
    assert ids == ['frame/centers/m0/s48', 'frame/centers/m4/s48', 'frame/centers/m5/s48']
    np.testing.assert_array_equal(edges, [[0, 1], [1, 2], [0, 2]])
    assert values['map_base'].shape == (3, 2)
    assert values['map_full'].shape == (3, 3)
    assert audit['original_training_elements'] == 6 and audit['selected_training_elements'] == 3
    np.testing.assert_array_equal(e5_fit.filter_graph(bank.training_graph()['edges'], np.zeros(6, bool)), np.empty((0, 2), int))


def test_prediction_file_keeps_geometry_denominator_when_one_readout_is_missing(tmp_path, monkeypatch):
    bank, run, group, selected = training_fixture(tmp_path)
    values, edges, ids, _ = e5_fit.matched_training(bank, tmp_path, [group], run, 'centers', selected)
    adapters, files = {}, {}
    for condition in selected:
        ident = condition['id']
        adapter = fit_feature_adapter(values[ident], edges, ids, scope=dict(
            regime='transfer', sampler='centers', scale_px=48, feature_id=ident))
        path = f'{ident}.json'
        write_json(tmp_path / path, adapter)
        files[path] = file_hash(tmp_path / path)
        adapters[(run['run_id'], 'centers', ident)] = path
    monkeypatch.setattr(e5_predict, 'runs', lambda: [run])
    monkeypatch.setattr(e5_predict, 'conditions', lambda _family: selected)
    index = e5_predict.generate_predictions(bank, tmp_path, [group], adapters, files, lambda: None, expected_entries=1)
    assert len(index) == 1 and index[0]['adapters'] == {c['id']: f"{c['id']}.json" for c in selected}
    with np.load(tmp_path / index[0]['prediction'], allow_pickle=False) as result:
        assert result['map_full__common__available'].tolist() == [True, True, False, True, True, True]
        assert not result['map_full__common__valid'][1]
        assert result['map_base__common__valid'][1]
        assert result['map_full__common__fh4__before'][1] == 0
        assert result['map_base__common__fh4__before'][1] > 0
        # A minimum of8 leaves the unchanged six-node toy centers graph unassigned.
        assert not result['map_base__common__fh4__H_M1'].any()
        assert result['map_base__own__distance'].shape == (5,)
    assert file_hash(tmp_path / 'prediction-index.json') == files['prediction-index.json']


def test_missing_baseline48_gate_removes_own32_only_after_proposals():
    ids = list('abcd')
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    adapter = dict(available=True, q25=.5, q75=1.)
    result = e5_predict.partition_arrays(ids, edges, np.zeros(3), np.ones(4, bool), adapter,
                                         np.zeros(4, bool), np.zeros(4, bool), 4)
    assert (result['fh4__before'] > 0).all() and (result['mws__before'] > 0).all()
    assert not result['fh4__H_M1'].any() and not result['mws__A_fixed_M1'].any()


def test_baseline_drift_refuses_changed_support_and_excessive_differences():
    base = np.array([[1., 2.], [np.nan, np.nan]])
    assert check_baseline(base.copy(), base)['exact']
    assert check_baseline(base + 1e-6, base)['max_abs_difference'] == pytest.approx(1e-6)
    with pytest.raises(ValueError, match='tolerance'):
        check_baseline(base + .1, base)
    with pytest.raises(ValueError, match='finite support'):
        check_baseline(np.nan_to_num(base), base)


def test_extraction_integrates_random_models_and_resampled_synthetic_input():
    import torch
    from stmdomains.experiments.e5_generate import extract_group
    from stmdomains.experiments.training.data import extract_patch, synthetic_in_normalizer_units
    from stmdomains.experiments.training.models import Autoencoder, RotationalVAE
    from stmdomains.experiments.training.predict import synthetic_rows
    from stmdomains.experiments.training.texture import describe_patches

    torch.manual_seed(5)
    torch.set_num_threads(1)
    yy, xx = np.mgrid[:128, :128]
    xy = np.array([[64., 64.], [16., 16.]])
    arrays = dict(image=np.sin(xx / 4.) + np.sin(yy / 5.), measured=np.ones((128, 128), bool),
                  centers_xy=xy, boxes_xyxy=np.column_stack((xy - 1, xy + 1)), object_ids=np.array(['a', 'b']))
    record = dict(sample_id='toy', kind='synthetic', pixel_spacing_xy=[.5, .5])
    rows = [r for r in synthetic_rows(record, arrays) if r['sampler'] == 'centers' and r['scale_px'] == 48]
    group = dict(group_id='toy/centers/s48', sampler='centers', record=record)
    normalizer = dict(low=-2., high=2.)
    source = synthetic_in_normalizer_units(arrays, normalizer)
    cache = dict(available_indices=np.array([0]), patches=np.stack([extract_patch(source, rows[0], normalizer)]))
    native = describe_patches(np.stack([extract_patch(source, rows[0], normalizer, size=48)]))
    baseline = dict(available=np.array([True, False]), valid=np.array([True, False]),
                    **{k: np.r_[native[k], np.nan] for k in ('acf_score', 'second_direction_ratio', 'energy')})
    inputs = SimpleNamespace(rows=lambda _group: rows, sample=lambda _group: (record, arrays),
                             load_npz=lambda _path: cache, descriptor=lambda *_args: baseline, threshold=.1)
    ae, rvae = Autoencoder(32), RotationalVAE(32)
    for model in (ae, rvae):
        model.run_config = dict(data=dict(normalizer=normalizer))
    models = {(family, seed): model for seed in (20261101, 20261102, 20261103)
              for family, model in (('ae', ae), ('rvae', rvae))}
    values, shared, replay = extract_group(SimpleNamespace(inputs=inputs), group, 'transfer', models, lambda: None)
    assert replay == dict(available=1, exact=True)
    assert len(values) == 10
    assert shared['exact64__available'].tolist() == [False, False]
    assert shared['exact64__scope'].all()
    assert not shared['exact48__train'].any()
    for run_id, features in values.items():
        assert np.isnan(features['multi']).all()
        assert np.isfinite(features['exact48'][0]).all()
        assert np.isnan(features['exact48'][1]).all()
        if '/ae/' in run_id:
            assert features['map48'].shape == (2, 3136) and features['map48'].dtype == np.float32
