"""Truth-free E7 learned and historical-distance predictions on fixed graphs."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np

from .bundle import file_hash, write_json
from .e2_pipeline import distances
from .e5_predict import partition_arrays
from .e7_probe import common_nodes, load_features, pair_features, predict_same, specs
from .training.partition import transform_features


def frozen_adapters(e2, out):
    """Verify every old E2 adapter against its prediction freeze; never refit."""
    e2, out = Path(e2), Path(out)
    freeze = json.loads((e2 / 'prediction-freeze.json').read_text())
    adapters, paths, files = {}, {}, {}
    for spec in specs():
        family, seed = spec['baseline_family'], spec['seed']
        run = f'transfer/{family}' + (f'/z32/seed-{seed}' if seed is not None else '')
        relative = f'adapters/{run}/centers.json'
        if relative not in freeze['files'] or file_hash(e2 / relative) != freeze['files'][relative]:
            raise ValueError('Historical E2 adapter differs from prediction freeze')
        adapter = json.loads((e2 / relative).read_text())
        target = f'historical-adapters/{spec["id"]}.json'
        (out / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(e2 / relative, out / target)
        adapters[spec['id']], paths[spec['id']] = adapter, target
        files[target] = file_hash(out / target)
    return adapters, paths, files


def prediction_arrays(features, rows, model, historical):
    common = common_nodes(features)
    edges = np.asarray(features['edges'], dtype=np.int64)
    ids = [row['element_id'] for row in rows]
    if len(ids) != len(common):
        raise ValueError('Prediction rows differ from feature nodes')
    usable = common[edges].all(axis=1)
    score = np.full(len(edges), np.nan)
    pair = pair_features(features, edges[usable], model['spec']['blocks'])
    score[usable] = predict_same(model, pair)
    calibration = model['calibration']
    learned_distance = np.full(len(edges), np.nan)
    learned_valid = common & bool(calibration['available'])
    if calibration['available']:
        learned_distance[usable] = (1. - score[usable]) / calibration['edge_median']
    spec = model['spec']
    name = ('geometry' if spec['baseline_family'] == 'geometry' else 'photometry'
            if spec['baseline_family'] == 'photometry' else
            f'ae_{spec["seed"]}' if spec['baseline_family'] == 'ae' else f'rvae_{spec["seed"]}')
    coordinates, valid = transform_features(features[name], historical)
    historical_valid = common & valid
    scale = historical['edge_median'] if historical['available'] else 1.
    distance = distances(coordinates, edges, historical_valid, scale=scale)
    arrays = dict(edges=edges, available=np.asarray(features['available'], bool),
                  common_valid=common, learned_score=score, learned_distance=learned_distance,
                  learned_valid=learned_valid, historical_distance=distance, historical_valid=historical_valid,
                  hard=np.asarray(features['hard'], bool), full_gate=np.asarray(features['full_gate'], bool))
    for name, d, v, adapter in (('learned', learned_distance, learned_valid, calibration),
                                ('historical', distance, historical_valid, historical)):
        result = partition_arrays(ids, edges, d, v, adapter, arrays['hard'], arrays['full_gate'], 8)
        arrays.update({f'{name}__{key}': value for key, value in result.items()})
    return arrays


def predict_all(bank, e2, out, entries, models, check_budget=lambda: None):
    """Predict validation/STM only; their truth files are never opened here."""
    out = Path(out)
    adapters, adapter_paths, files = frozen_adapters(e2, out)
    index = []
    for entry in entries:
        if entry['role'] == 'train':
            continue
        if entry['role'] not in ('validation', 'stm_development'):
            raise ValueError('Unknown E7 prediction role')
        check_budget()
        features = load_features(out, entry)
        rows = json.loads((out / entry['rows_file']).read_text())
        for spec in specs():
            check_budget()
            ident = spec['id']
            if models[ident]['spec'] != spec:
                raise ValueError('Probe specification differs from fixed E7 design')
            arrays = prediction_arrays(features, rows, models[ident], adapters[ident])
            relative = f'predictions/entry-{len(index):05d}.npz'
            (out / relative).parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(out / relative, **arrays)
            files[relative] = file_hash(out / relative)
            index.append(dict(entry, id=f'entry-{len(index):05d}', model_id=ident,
                              family=spec['family'], seed=spec['seed'], sampler='centers',
                              scale_px=48, regime='transfer', prediction_file=relative,
                              model_file=f'probes/{ident}.json', adapter_file=adapter_paths[ident],
                              baseline_family=spec['baseline_family'],
                              common_nodes=int(arrays['common_valid'].sum()),
                              historical_invalid_common_nodes=int((arrays['common_valid'] & ~arrays['historical_valid']).sum()),
                              learned_calibration_available=bool(models[ident]['calibration']['available'])))
    write_json(out / 'prediction-index.json', index)
    files['prediction-index.json'] = file_hash(out / 'prediction-index.json')
    return index, files
