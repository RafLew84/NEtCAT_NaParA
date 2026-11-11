"""Frozen-weight E3 prediction generation; evaluation references are never read."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .bundle import file_hash, write_json
from .e1_mechanics import apply_variant, gate_masks
from .e1_run import context, same_partition
from .e2_features import geometry_features, photometry_features
from .e2_pipeline import distances, spaces
from .e3_inference import encode_readouts
from .e3_transforms import CONDITIONS, fit_gradient, pixel_stats, transform
from .training.data import extract_patch, synthetic_in_normalizer_units
from .training.models import load_model
from .training.partition import fh_partition, mws_partition, relation_weights
from .training.predict import label_numbers
from .training.texture import describe_patches

STAGES = ('H_M1', 'A_fixed_M1', 'A_updated_M1')
SPACES = ('native', 'l2', 'adapted')


def expand(values, indices, count):
    values = np.asarray(values)
    result = np.full((count,) + values.shape[1:], np.nan, dtype=values.dtype)
    result[indices] = values
    return result


def load_adapters(bank, e2, out):
    frozen = json.loads((e2 / 'prediction-freeze.json').read_text())['files']
    result, hashes = {}, {}
    for run in bank.runs:
        for sampler in ('grid', 'centers'):
            name = f"adapters/{run['run_id']}/{sampler}.json"
            if file_hash(e2 / name) != frozen[name]:
                raise ValueError(f'E2 adapter changed: {name}')
            value = json.loads((e2 / name).read_text())
            result[(run['run_id'], sampler)] = value
            write_json(out / name, value)
            hashes[name] = file_hash(out / name)
    return result, hashes


def gradient_calibration(bank, out):
    results = {}
    for regime in ('transfer', 'transductive'):
        graph = bank.training_graph(regime, 'grid')
        pieces = []
        for segment in graph['segments']:
            cache = bank.inputs.load_npz(f"cache/{segment['group_id']}/{regime}.npz")
            lookup = {int(index): j for j, index in enumerate(cache['available_indices'])}
            pieces.append(cache['patches'][[lookup[int(i)] for i in segment['row_indices']]])
        results[regime] = dict(fit_gradient(np.concatenate(pieces)),
                               fit_window_ids=list(graph['window_ids']),
                               training_ids_sha256=graph['training_ids_sha256'])
    write_json(out / 'gradient-calibration.json', results)
    return results


def models_for(bank, regime):
    result = {}
    for run in bank.runs:
        if run['regime'] != regime or run['family'] not in ('ae', 'rvae_full'):
            continue
        family = 'ae' if run['family'] == 'ae' else 'rvae'
        result[(family, run['seed'])] = load_model(bank.inputs.source_root / 'training' / run['source_run_id'], 'cpu')
    return result


def native_patches(bank, group, rows, indices, normalizer):
    _, arrays = bank.inputs.sample(group)
    if group['record']['kind'] == 'synthetic':
        arrays = synthetic_in_normalizer_units(arrays, normalizer)
    return (np.stack([extract_patch(arrays, rows[i], normalizer, size=48) for i in indices])
            if len(indices) else np.empty((0, 48, 48), np.float32))


def descriptors(patches, indices, count):
    local = describe_patches(patches)
    result = {key: expand(value, indices, count) for key, value in local.items() if key != 'valid'}
    result['valid'] = np.zeros(count, bool)
    result['valid'][indices] = local['valid']
    result['available'] = np.zeros(count, bool)
    result['available'][indices] = True
    return result


def partition(ids, edges, distance, valid, adapter, masks, minimum):
    kinds, strengths = relation_weights(distance, adapter['q25'], adapter['q75'])
    result = {}
    for method in ('fh4', 'mws'):
        proposals = (fh_partition(ids, edges, distance, valid=valid, k=4.) if method == 'fh4' else
                     mws_partition(ids, edges, kinds, strengths, valid=valid)['component_ids'])
        result[f'{method}_before'] = label_numbers(proposals)
        for stage, mask in masks.items():
            result[f'{method}_{stage}'] = apply_variant(ids, edges, proposals, valid & mask, minimum)['after']
    return result


def baseline_check(actual, expected, label):
    if actual.shape != expected.shape or not np.allclose(actual, expected, atol=1e-5, rtol=1e-4, equal_nan=True):
        raise ValueError(f'Fresh identity differs beyond backend tolerance: {label}')
    mask = np.isfinite(actual) & np.isfinite(expected)
    return float(np.max(np.abs(actual[mask] - expected[mask]))) if mask.any() else 0.


def generate(bank, e2, out, check_budget):
    adapters, files = load_adapters(bank, e2, out)
    gradients = gradient_calibration(bank, out)
    files['gradient-calibration.json'] = file_hash(out / 'gradient-calibration.json')
    old_index = json.loads((e2 / 'prediction-index.json').read_text())
    old = {(e['run_id'], e['cache_group']): e for e in old_index}
    old_frozen = json.loads((e2 / 'prediction-freeze.json').read_text())['files']
    if file_hash(e2 / 'prediction-index.json') != old_frozen['prediction-index.json']:
        raise ValueError('E2 prediction index changed')
    templates = {(e['regime'], e['cache_group']): e for e in bank.inputs.entries if e['family'] == 'fft' and e['partition'] == 'fh4'}
    schedule = [(regime, key) for regime in ('transfer', 'transductive') for key in sorted(bank.inputs.groups)]
    order = np.random.default_rng(20261111).permutation(len(schedule))
    schedule = [schedule[i] for i in order]
    write_json(out / 'schedule.json', schedule)
    files['schedule.json'] = file_hash(out / 'schedule.json')
    models = {regime: models_for(bank, regime) for regime in ('transfer', 'transductive')}
    drift, index = [], []
    for group_number, (regime, group_key) in enumerate(schedule):
        check_budget()
        group = bank.inputs.groups[group_key]
        template = templates[(regime, group_key)]
        rows, ids, desc, scope, gates, hard, minimum = context(bank.inputs, template)
        count = len(rows)
        cache = bank.inputs.load_npz(f'cache/{group_key}/{regime}.npz')
        indices, patches64 = cache['available_indices'], cache['patches']
        window_ids = [rows[i]['window_id'] for i in indices]
        normalizer = models[regime][('ae', 20261101)].run_config['data']['normalizer']
        patches48 = native_patches(bank, group, rows, indices, normalizer)
        source = bank.inputs.load_npz(f"{template['directory']}/{template['evaluation_input']}")
        edges = source['edges']
        condition_values, condition_desc, pixel_values = [], [], []
        pose_values = []
        preview_row = next((int(i) for i in indices if scope[i]), None)
        preview_slot = list(indices).index(preview_row) if preview_row is not None else None
        preview_paths = []
        for condition in CONDITIONS:
            x64 = transform(patches64, condition, gradients[regime]['value'], window_ids)
            x48 = transform(patches48, condition, gradients[regime]['value'], window_ids)
            d = descriptors(x48, indices, count)
            if condition == 'identity':
                for key in ('acf_score', 'second_direction_ratio', 'energy', 'basis_vectors'):
                    if not np.allclose(d[key], desc[key], rtol=1e-12, atol=1e-14, equal_nan=True):
                        raise ValueError(f'Native identity descriptor changed: {key}')
                for key in ('valid', 'available'):
                    if not np.array_equal(d[key], desc[key]): raise ValueError('Native validity changed')
                new_pass = d['valid'] & (d['acf_score'] > bank.inputs.threshold) & (d['second_direction_ratio'] >= .25) & (d['energy'] > 0)
                if not np.array_equal(new_pass, desc['order_pass']): raise ValueError('Native identity gate changed')
            condition_desc.append(d)
            pixel_values.append({k: expand(v, indices, count) for k, v in pixel_stats(patches64, x64).items()})
            feats = {('fft', None): d['features'], ('geometry', None): geometry_features(d),
                     ('photometry', None): photometry_features(dict(available_indices=indices, patches=x64), count)}
            poses = {}
            for (family, seed), model in models[regime].items():
                encoded = encode_readouts(model, x64)
                for name, value in encoded.items():
                    if not name.startswith('_'):
                        feats[(name, seed)] = expand(value, indices, count)
                poses[seed] = poses.get(seed, {})
                if family == 'rvae':
                    poses[seed] = {key: expand(encoded[key], indices, count) for key in ('_angle', '_translation')}
            condition_values.append(feats)
            pose_values.append(poses)
            preview_path = None
            if preview_slot is not None:
                preview_path = f'previews/group-{group_number:04d}-{condition}.png'
                p = out / preview_path; p.parent.mkdir(exist_ok=True)
                Image.fromarray(np.uint8(255 * np.clip(x64[preview_slot], 0, 1))).save(p)
                files[preview_path] = file_hash(p)
            preview_paths.append(preview_path)
        runs = [r for r in bank.runs if r['regime'] == regime]
        coordinates, validities = {}, {}
        for run in runs:
            adapter = adapters[(run['run_id'], group['sampler'])]
            if not adapter['available']:
                raise ValueError('E3 expected the 60 available E2 adapters')
            prepared = [spaces(values[(run['family'], run['seed'])], adapter, scope) for values in condition_values]
            coordinates[run['run_id']] = [v[0] for v in prepared]
            validities[run['run_id']] = np.asarray([v[1] for v in prepared])
        common = np.logical_and.reduce(list(validities.values())) & scope & desc['available']
        shared_path = f'groups/group-{group_number:04d}.npz'
        shared = dict(edges=edges, scope=scope, available=desc['available'], common=common)
        for key in ('acf_score', 'second_direction_ratio', 'energy', 'valid'):
            shared[key] = np.stack([d[key] for d in condition_desc])
        for key in pixel_values[0]:
            shared['pixels_' + key] = np.stack([v[key] for v in pixel_values])
        shared['hard'] = np.stack([gate_masks(d['available'], d['valid'], d['acf_score'], d['second_direction_ratio'], d['energy'], bank.inputs.threshold)['hard'] & scope for d in condition_desc])
        shared['full_gate'] = np.stack([shared['hard'][i] & (d['acf_score'] > bank.inputs.threshold) & (d['second_direction_ratio'] >= .25) for i, d in enumerate(condition_desc)])
        p = out / shared_path; p.parent.mkdir(exist_ok=True); np.savez_compressed(p, **shared)
        files[shared_path] = file_hash(p)
        for run in runs:
            adapter = adapters[(run['run_id'], group['sampler'])]
            coords, valid = coordinates[run['run_id']], validities[run['run_id']]
            values = np.stack([v[(run['family'], run['seed'])] for v in condition_values])
            old_values = bank.features(run, group)
            max_error = baseline_check(values[0], old_values, f"{run['run_id']}/{group_key}")
            arrays = dict(features=values, valid=valid)
            edge_distances, outcomes = [], []
            absolute, relative = [], []
            feature_norms = []
            for ci, coordinate in enumerate(coords):
                dist = np.stack([distances(v, edges, valid[ci], adapter['edge_median'] if si == 2 else 1.) for si, v in enumerate(coordinate)])
                edge_distances.append(dist)
                masks = dict(H_M1=shared['hard'][0], A_fixed_M1=shared['full_gate'][0], A_updated_M1=shared['full_gate'][ci])
                outcomes.append(partition(ids, edges, dist[2], valid[ci], adapter, masks, minimum))
                paired = valid[ci] & valid[0]
                shift, rel = [], []
                for si, current in enumerate(coordinate):
                    movement = np.linalg.norm(current - coords[0][si], axis=1)
                    norms = np.linalg.norm(coords[0][si], axis=1)
                    movement[~paired] = np.nan
                    ratio = np.full(count, np.nan)
                    np.divide(movement, norms, out=ratio, where=paired & (norms > 0))
                    if si == 2:
                        movement = movement / adapter['edge_median']
                    shift.append(movement); rel.append(ratio)
                absolute.append(shift); relative.append(rel)
                feature_norms.append([np.where(valid[ci], np.linalg.norm(v, axis=1) /
                    (adapter['edge_median'] if si == 2 else 1.), np.nan) for si, v in enumerate(coordinate)])
            arrays['distances'] = np.stack(edge_distances)
            arrays['shift_absolute'] = np.asarray(absolute)
            arrays['shift_relative'] = np.asarray(relative)
            arrays['feature_norms'] = np.asarray(feature_norms)
            for key in outcomes[0]: arrays[key] = np.stack([o[key] for o in outcomes])
            if run['family'].startswith('rvae'):
                angles = np.stack([v[run['seed']]['_angle'] for v in pose_values])
                translations = np.stack([v[run['seed']]['_translation'] for v in pose_values])
                arrays['angle_shift'] = np.abs(np.arctan2(np.sin(angles - angles[0]), np.cos(angles - angles[0])))
                arrays['translation_shift'] = np.linalg.norm(translations - translations[0], axis=2)
            previous = old[(run['run_id'], group_key)]
            old_path = previous['prediction']
            if file_hash(e2 / old_path) != old_frozen[old_path]: raise ValueError('E2 prediction changed')
            historical_coords, historical_valid = spaces(old_values, adapter, scope)
            historical_distance = distances(historical_coords[2], edges, historical_valid, adapter['edge_median'])
            historical = partition(ids, edges, historical_distance, historical_valid, adapter,
                dict(H_M1=hard, A_fixed_M1=hard & gates['acf'] & gates['spectral']), minimum)
            with np.load(e2 / old_path, allow_pickle=False) as z:
                assert np.array_equal(z['edges'], edges)
                changes = {}
                for method in ('fh4', 'mws'):
                    for stage, old_stage in (('before', 'before'), ('H_M1', 'H_M1'), ('A_fixed_M1', 'A1S1M1')):
                        previous_labels = z[f'actual_{method}_{old_stage}']
                        if not np.array_equal(historical[f'{method}_{stage}'], previous_labels):
                            raise ValueError('Historical E2 partition did not replay exactly')
                        changes[f'{method}_{stage}'] = not same_partition(arrays[f'{method}_{stage}'][0], previous_labels)
            drift.append(dict(run_id=run['run_id'], group=group_key, max_abs_feature_error=max_error,
                              historical_exact_partitions=6, partition_changed=changes))
            ident = f'entry-{len(index):05d}'
            relative_path = f'predictions/{ident}.npz'
            p = out / relative_path; p.parent.mkdir(exist_ok=True); np.savez_compressed(p, **arrays)
            files[relative_path] = file_hash(p)
            index.append(dict(template, **{k: run[k] for k in ('run_id', 'family', 'seed')}, id=ident,
                              prediction=relative_path, shared=shared_path, preview_row_index=preview_row,
                              preview_images=preview_paths, adapter=f"adapters/{run['run_id']}/{group['sampler']}.json"))
        if group_number % 20 == 0:
            print(f'E3 prediction groups {group_number + 1}/{len(schedule)}', flush=True)
    write_json(out / 'backend-drift.json', dict(records=drift))
    write_json(out / 'prediction-index.json', index)
    for name in ('backend-drift.json', 'prediction-index.json'): files[name] = file_hash(out / name)
    return index, files, gradients
