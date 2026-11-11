"""Small weighted synthetic relation probes; no validation-label access."""
from __future__ import annotations

import json
from pathlib import Path
import warnings
from collections import Counter

import numpy as np
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .bundle import file_hash, write_json
from .e2_metrics import edge_reference

SEEDS = (20261101, 20261102, 20261103)
FIT_ORDER_SEED = 20261117
BLOCK_DIMENSIONS = dict(geometry=8, photometry=3,
                        **{f'ae_{seed}': 32 for seed in SEEDS},
                        **{f'rvae_{seed}': 34 for seed in SEEDS})


def specs():
    result = [dict(id='geometry', family='geometry', seed=None, blocks=['geometry'],
                   baseline_family='geometry'),
              dict(id='geometry_photometry', family='geometry_photometry', seed=None,
                   blocks=['geometry', 'photometry'], baseline_family='photometry')]
    for family in ('ae', 'rvae'):
        for seed in SEEDS:
            result.append(dict(id=f'geometry_{family}_seed{seed}', family=f'geometry_{family}',
                               seed=seed, blocks=['geometry', f'{family}_{seed}'],
                               baseline_family='ae' if family == 'ae' else 'rvae_full'))
    return result


def load_features(out, entry):
    with np.load(Path(out) / entry['features_file'], allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def common_nodes(features):
    """Finite all-readout intersection, retaining finite zero vectors."""
    available = np.asarray(features['available'], dtype=bool)
    if available.ndim != 1:
        raise ValueError('Availability must be a node vector')
    result = available.copy()
    for name, dimension in BLOCK_DIMENSIONS.items():
        values = np.asarray(features[name], dtype=float)
        if values.shape != (len(available), dimension):
            raise ValueError(f'Unexpected feature shape: {name}')
        result &= np.isfinite(values).all(axis=1)
    return result


def pair_features(features, edges, blocks):
    """Symmetric endpoint difference and mean; no IDs or coordinates added."""
    values = np.concatenate([np.asarray(features[name], float) for name in blocks], axis=1)
    pairs = np.asarray(edges)
    if pairs.size == 0:
        pairs = np.empty((0, 2), dtype=np.int64)
    if (pairs.ndim != 2 or pairs.shape[1] != 2 or pairs.dtype.kind not in 'iu'
            or np.any(pairs < 0) or np.any(pairs >= len(values))):
        raise ValueError('Invalid pair endpoints')
    a, b = values[pairs[:, 0]], values[pairs[:, 1]]
    return np.concatenate((np.abs(a - b), (a + b) / 2), axis=1)


def group_class_weights(groups, target):
    """Each observed group/class cell gets equal total weight; mean weight one."""
    groups, target = np.asarray(groups), np.asarray(target)
    if groups.ndim != 1 or target.shape != groups.shape or not len(groups):
        raise ValueError('Training groups and targets must be aligned nonempty vectors')
    if set(np.unique(target)) != {0, 1}:
        raise ValueError('Both relation classes are required for the fixed probe')
    for group in np.unique(groups):
        if set(target[groups == group]) != {0, 1}:
            raise ValueError('Every training group must contain both relation classes')
    keys = [(str(group), int(label)) for group, label in zip(groups, target)]
    counts = Counter(keys)
    weights = np.asarray([1. / counts[key] for key in keys])
    weights /= weights.mean()
    audit = [dict(group_id=group, same=bool(label), pairs=count,
                  weight_sum=float(weights[[key == (group, label) for key in keys]].sum()))
             for (group, label), count in sorted(counts.items())]
    return weights, audit


def fit_model(values, target, groups):
    values, target = np.asarray(values, float), np.asarray(target, dtype=int)
    if values.ndim != 2 or len(values) != len(target) or not np.isfinite(values).all():
        raise ValueError('Probe fit requires finite labeled training pairs')
    weights, cells = group_class_weights(groups, target)
    scaler = StandardScaler().fit(values, sample_weight=weights)
    classifier = LogisticRegression(C=1., penalty='l2', solver='lbfgs', max_iter=2000,
                                    tol=1e-8, class_weight=None)
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        try:
            classifier.fit(scaler.transform(values), target, sample_weight=weights)
        except ConvergenceWarning as exc:
            raise RuntimeError('Fixed relation probe failed to converge') from exc
    if classifier.classes_.tolist() != [0, 1]:
        raise AssertionError('Probability convention changed')
    return dict(schema='stmdomains-e7-logistic-probe-v1', available=True,
                mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist(),
                coefficients=classifier.coef_[0].tolist(), intercept=float(classifier.intercept_[0]),
                target='1=same positive domain, 0=different positive domains',
                settings=dict(C=1., penalty='l2', solver='lbfgs', max_iter=2000, tol=1e-8),
                iterations=int(classifier.n_iter_[0]), training_pairs=len(target),
                same_pairs=int(target.sum()), different_pairs=int((target == 0).sum()),
                weighting='1/n(group,class), normalized to mean1; no additional class_weight',
                weight_cells=cells, weighted_mean=True)


def predict_same(model, values):
    values = np.asarray(values, float)
    mean, scale = np.asarray(model['mean']), np.asarray(model['scale'])
    coefficients = np.asarray(model['coefficients'])
    if values.ndim != 2 or values.shape[1:] != mean.shape or scale.shape != mean.shape:
        raise ValueError('Pair dimension differs from frozen probe')
    return expit(((values - mean) / scale) @ coefficients + model['intercept'])


def calibrate_distances(distance):
    """Calibrate all usable TRAIN edges, without consulting relation labels."""
    values = np.asarray(distance, float)
    if values.ndim != 1 or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError('Calibration requires finite nonnegative distances')
    positive = values[values > 0]
    result = dict(available=False, reason=None, edge_median=None, raw_positive_median=None,
                  median_floor=1e-10, q25=None, q75=None,
                  training_edges=len(values), positive_training_edges=len(positive),
                  zero_training_edges=int((values == 0).sum()), collapsed_quantiles=None,
                  policy='all common-node training graph edges; no reference eligibility filter')
    if not len(positive):
        result['reason'] = 'no_training_edges' if not len(values) else 'all_training_distances_zero'
        return result
    raw_median = float(np.median(positive))
    median = max(raw_median, result['median_floor'])
    q25, q75 = np.quantile(values / median, [.25, .75], method='linear')
    result.update(available=True, edge_median=median, raw_positive_median=raw_median,
                  q25=float(q25), q75=float(q75),
                  collapsed_quantiles=bool(q25 == q75))
    return result


def fit_probes(out, entries, check_budget=lambda: None):
    """Fit eight fixed probes using only role=train synthetic references."""
    out = Path(out)
    training = [entry for entry in entries if entry['role'] == 'train']
    if not training or any(entry['kind'] != 'synthetic' for entry in training):
        raise ValueError('E7 probe training is restricted to synthetic train entries')
    prepared, input_hashes, sample_audit = [], {}, []
    for entry in training:
        check_budget()
        features = load_features(out, entry)
        rows = json.loads((out / entry['rows_file']).read_text())
        with np.load(out / entry['truth_file'], allow_pickle=False) as archive:
            truth = {key: archive[key] for key in archive.files}
        common = common_nodes(features)
        edges = features['edges']
        if len(rows) != len(common):
            raise ValueError('Rows differ from feature nodes')
        reference = edge_reference(rows, edges, truth, 'synthetic', 'transfer')
        usable = common[edges].all(axis=1)
        labeled = usable & reference['valid']
        prepared.append((entry, features, usable, labeled, reference['same']))
        sample_audit.append(dict(sample_id=entry['sample_id'], group_id=entry['group_id'],
                                 usable_train_edges=int(usable.sum()),
                                 selected_same=int((labeled & reference['same']).sum()),
                                 selected_different=int((labeled & ~reference['same']).sum())))
        for field in ('features_file', 'rows_file', 'truth_file'):
            input_hashes[entry[field]] = file_hash(out / entry[field])
    group_counts = {entry['group_id']: [0, 0] for entry in training}
    for entry, features, usable, labeled, same in prepared:
        group_counts[entry['group_id']][0] += int((labeled & ~same).sum())
        group_counts[entry['group_id']][1] += int((labeled & same).sum())
    if any(not all(counts) for counts in group_counts.values()):
        raise ValueError('Every training group must contain both relation classes')
    models, files = {}, {}
    selected = specs()
    order = np.random.default_rng(FIT_ORDER_SEED).permutation(len(selected))
    fit_order = [selected[i]['id'] for i in order]
    write_json(out / 'probe-fit-order.json', dict(seed=FIT_ORDER_SEED, order=fit_order,
                                                input_sample_order=[e['sample_id'] for e in training]))
    files['probe-fit-order.json'] = file_hash(out / 'probe-fit-order.json')
    write_json(out / 'probe-fit-audit.json', dict(samples=sample_audit,
        scope='same all-feature common nodes and labeled pairs for all eight probes',
        case_metadata_read=False, validation_labels_accessed=False, stm_labels_accessed=False))
    files['probe-fit-audit.json'] = file_hash(out / 'probe-fit-audit.json')
    for position, number in enumerate(order):
        spec = selected[number]
        check_budget()
        chunks, targets, groups = [], [], []
        for entry, features, usable, labeled, same in prepared:
            x = pair_features(features, features['edges'], spec['blocks'])
            chunks.append(x[labeled])
            targets.append(same[labeled].astype(int))
            groups.extend([entry['group_id']] * int(labeled.sum()))
        model = fit_model(np.concatenate(chunks), np.concatenate(targets), groups)
        calibration = []
        for entry, features, usable, labeled, same in prepared:
            x = pair_features(features, features['edges'][usable], spec['blocks'])
            calibration.append(1. - predict_same(model, x))
        model.update(spec=spec, calibration=calibrate_distances(np.concatenate(calibration)),
                     input_sha256=input_hashes, training_samples=[e['sample_id'] for e in training],
                     fit_order_seed=FIT_ORDER_SEED, fit_order_index=position,
                     validation_labels_accessed=False, stm_labels_accessed=False)
        relative = f'probes/{spec["id"]}.json'
        write_json(out / relative, model)
        models[spec['id']] = model
        files[relative] = file_hash(out / relative)
    write_json(out / 'probe-index.json', {key: f'probes/{key}.json' for key in models})
    files['probe-index.json'] = file_hash(out / 'probe-index.json')
    return models, files
