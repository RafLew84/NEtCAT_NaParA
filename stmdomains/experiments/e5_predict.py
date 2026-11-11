"""E5 fixed-graph predictions with separate support and representation validity."""
from __future__ import annotations

import json

import numpy as np

from .bundle import file_hash, write_json
from .e1_mechanics import apply_variant
from .e2_pipeline import distances
from .e5_catalog import CONTEXTS, conditions, patch_keys, runs
from .training.partition import fh_partition, mws_partition, relation_weights, transform_features
from .training.predict import label_numbers


def condition_masks(shared, selected):
    """Common depends on geometry/split only, never on feature validity."""
    own = {}
    for condition in selected:
        keys = patch_keys(condition)
        own[condition['id']] = dict(
            available=np.logical_and.reduce([shared[f'{key}__available'] for key in keys]),
            scope=np.logical_and.reduce([shared[f'{key}__scope'] for key in keys]))
    common = {}
    for contrast in dict.fromkeys(c['contrast'] for c in selected):
        members = [own[c['id']] for c in selected if c['contrast'] == contrast]
        common[contrast] = {key: np.logical_and.reduce([m[key] for m in members])
                            for key in ('available', 'scope')}
    return {c['id']: dict(own=own[c['id']], common=common[c['contrast']]) for c in selected}


def partition_arrays(ids, edges, distance, valid, adapter, hard, full_gate, minimum):
    if adapter['available']:
        kinds, strengths = relation_weights(distance, adapter['q25'], adapter['q75'])
    else:
        kinds = np.full(len(edges), 'unavailable', dtype='U11')
        strengths = np.full(len(edges), np.nan)
    result = {}
    for method in ('fh4', 'mws'):
        proposals = (fh_partition(ids, edges, distance, valid=valid, k=4.) if method == 'fh4' else
                     mws_partition(ids, edges, kinds, strengths, valid=valid)['component_ids'])
        result[f'{method}__before'] = label_numbers(proposals).astype(np.int32)
        for stage, mask in (('H_M1', hard), ('A_fixed_M1', full_gate)):
            labels = apply_variant(ids, edges, proposals, valid & mask, minimum)['after']
            result[f'{method}__{stage}'] = labels.astype(np.int32)
    return result


def generate_predictions(bank, out, groups, adapters, files, check_budget, *, expected_entries=4200):
    index, adapter_cache = [], {}
    for group in groups:
        check_budget()
        with np.load(out / group['shared'], allow_pickle=False) as archive:
            shared = {key: archive[key] for key in archive.files}
        edges = shared['edges']
        rows = bank.inputs.rows(group['cache_group'])
        ids = [row['element_id'] for row in rows]
        minimum = 4 if group['sampler'] == 'grid' else 8
        for run in [r for r in runs() if r['regime'] == group['regime']]:
            check_budget()
            selected = conditions(run['family'])
            masks = condition_masks(shared, selected)
            saved, adapter_paths = {}, {}
            with np.load(out / group['features'][run['run_id']], allow_pickle=False) as features:
                for condition in selected:
                    ident = condition['id']
                    relative = adapters[(run['run_id'], group['sampler'], ident)]
                    if relative not in adapter_cache:
                        if file_hash(out / relative) != files[relative]:
                            raise ValueError('New adapter changed before prediction')
                        adapter_cache[relative] = json.loads((out / relative).read_text())
                    adapter = adapter_cache[relative]
                    adapter_paths[ident] = relative
                    coordinates, feature_valid = transform_features(features[condition['feature']], adapter)
                    for context in CONTEXTS:
                        prefix = f'{ident}__{context}__'
                        scope = masks[ident][context]['scope']
                        available = masks[ident][context]['available']
                        valid = feature_valid & scope & available
                        scale = adapter['edge_median'] if adapter['available'] else 1.
                        distance = distances(coordinates, edges, valid, scale=scale)
                        saved.update({prefix + 'scope': scope, prefix + 'available': available,
                                      prefix + 'valid': valid, prefix + 'distance': distance})
                        predictions = partition_arrays(ids, edges, distance, valid, adapter,
                                                       shared['baseline_hard'], shared['baseline_full_gate'], minimum)
                        saved.update({prefix + key: value for key, value in predictions.items()})
            ident = f'entry-{len(index):05d}'
            relative = f'predictions/{ident}.npz'
            path = out / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, **saved)
            files[relative] = file_hash(path)
            index.append(dict(run, id=ident, sampler=group['sampler'], sample_id=group['sample_id'],
                              kind=group['kind'], pixel_spacing_xy=group['pixel_spacing_xy'],
                              cache_group=group['cache_group'], shared=group['shared'],
                              features=group['features'][run['run_id']], prediction=relative,
                              adapters=adapter_paths))
        if len(index) % 300 == 0:
            print(f'E5 predictions: {len(index)}/4200 entries', flush=True)
    if len(index) != expected_entries:
        raise ValueError('Incomplete E5 prediction matrix')
    write_json(out / 'prediction-index.json', index)
    files['prediction-index.json'] = file_hash(out / 'prediction-index.json')
    return index
