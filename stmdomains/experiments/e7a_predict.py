"""Fixed E7a partition rules over already frozen E7 pair scores; no fitting."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_mechanics import apply_variant
from .e5_predict import partition_arrays
from .training.partition import fh_partition, mws_partition, relation_weights
from .training.predict import label_numbers

STAGES = ('before', 'H_M1', 'A_fixed_M1')
RULES = (
    dict(id='e7_fh', label='E7 · FH / mediana, k=4', baseline='e7_fh'),
    dict(id='e7_mws', label='E7 · MWS / kwantyle', baseline='e7_mws'),
    dict(id='fh_raw', label='FH · surowe 1−p, k=4', baseline='e7_fh'),
    dict(id='mws_t050', label='MWS · próg 0,50 (główny)', threshold=.5, baseline='e7_mws'),
    dict(id='mws_t025', label='MWS · próg 0,25', threshold=.25, baseline='e7_mws'),
    dict(id='mws_t075', label='MWS · próg 0,75', threshold=.75, baseline='e7_mws'),
)


def archive(path):
    with np.load(path, allow_pickle=False) as data:
        return dict(data)


def signed_relations(score, threshold):
    """Piecewise linear evidence, bounded in [0,1]; exact threshold neutral."""
    score = np.asarray(score, float)
    if score.ndim != 1 or not 0 < threshold < 1:
        raise ValueError('Expected score vector and threshold strictly inside (0,1)')
    finite = np.isfinite(score)
    if np.isinf(score).any() or np.any((score[finite] < 0) | (score[finite] > 1)):
        raise ValueError('Scores must lie in [0,1] or be missing NaN')
    kinds = np.full(len(score), 'none', dtype='U11')
    weights = np.zeros(len(score))
    kinds[~finite], weights[~finite] = 'unavailable', np.nan
    attractive, repulsive = finite & (score > threshold), finite & (score < threshold)
    kinds[attractive], kinds[repulsive] = 'attractive', 'repulsive'
    weights[attractive] = (score[attractive] - threshold) / (1 - threshold)
    weights[repulsive] = (threshold - score[repulsive]) / threshold
    return kinds, weights


def predict(data, rows, calibration):
    ids = [row['element_id'] for row in rows]
    valid, edges = data['learned_valid'], data['edges']
    if len(ids) != len(valid) or not np.array_equal(valid, data['common_valid']):
        raise ValueError('E7a requires the original common mask and available calibration')
    score = np.asarray(data['learned_score'])
    signed_relations(score, .5)  # Validate even when only replay is requested.
    usable = valid[edges].all(axis=1)
    if not np.isfinite(score[usable]).all() or not calibration['available']:
        raise ValueError('Missing score on usable edge or unavailable E7 calibration')
    if not np.array_equal(data['available'], np.array([r['available'] for r in rows])):
        raise ValueError('Physical support differs from frozen source rows')
    replay = partition_arrays(ids, edges, data['learned_distance'], valid, calibration,
                              data['hard'], data['full_gate'], 8)
    result = {key: data[key].copy() for key in
              ('available', 'common_valid', 'learned_valid', 'edges', 'hard', 'full_gate', 'learned_score')}
    for rule, method in (('e7_fh', 'fh4'), ('e7_mws', 'mws')):
        for stage in STAGES:
            value = replay[f'{method}__{stage}']
            if not np.array_equal(value, data[f'learned__{method}__{stage}']):
                raise ValueError('E7 baseline partition replay changed')
            result[f'{rule}__{stage}'] = value
    raw = 1. - score
    scaled = label_numbers(fh_partition(ids, edges, raw, valid=valid,
                                       k=4 * calibration['edge_median']))
    if not np.array_equal(scaled, result['e7_fh__before']):
        raise ValueError('FH rescaled-k identity changed')
    audit = dict(baseline_arrays_exact=6, fh_scaled_k_identity=True, rules={})
    for rule in RULES[2:]:
        ident = rule['id']
        if 'threshold' in rule:
            kinds, strengths = signed_relations(score, rule['threshold'])
            partition = mws_partition(ids, edges, kinds, strengths, valid=valid)
            proposals = partition['component_ids']
            audit['rules'][ident] = dict(partition['stats'],
                **{f'{kind}_edges': int((usable & (kinds == kind)).sum())
                   for kind in ('attractive', 'repulsive', 'none')})
        else:
            proposals = fh_partition(ids, edges, raw, valid=valid, k=4.)
        result[f'{ident}__before'] = label_numbers(proposals).astype(np.int32)
        for stage, mask in (('H_M1', data['hard']), ('A_fixed_M1', data['full_gate'])):
            result[f'{ident}__{stage}'] = apply_variant(ids, edges, proposals, valid & mask, 8)['after']
    old_kinds, _ = relation_weights(data['learned_distance'], calibration['q25'], calibration['q75'])
    audit['e7_mws_edges'] = {kind: int((usable & (old_kinds == kind)).sum())
                             for kind in ('attractive', 'repulsive', 'none')}
    return result, audit


def predict_all(source, out, source_index, check_budget=lambda: None):
    source, out = Path(source), Path(out)
    index, audits, files = [], [], {}
    (out / 'predictions').mkdir()
    for number, entry in enumerate(source_index):
        check_budget()
        rows = json.loads((source / entry['rows_file']).read_text())
        data = archive(source / entry['prediction_file'])
        model = json.loads((source / entry['model_file']).read_text())
        arrays, audit = predict(data, rows, model['calibration'])
        relative = f'predictions/entry-{number:05d}.npz'
        np.savez_compressed(out / relative, **arrays)
        files[relative] = file_hash(out / relative)
        index.append(dict(entry, anchor_prediction_file=entry['prediction_file'], prediction_file=relative))
        audits.append(dict(sample_id=entry['sample_id'], model_id=entry['model_id'], **audit))
        if number % 200 == 0:
            print(f'E7a partitions: {number + 1}/{len(source_index)}', flush=True)
    for name, value in (('prediction-index.json', index), ('replay-audit.json', audits)):
        write_json(out / name, value)
        files[name] = file_hash(out / name)
    return index, files
