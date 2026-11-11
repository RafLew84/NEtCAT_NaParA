"""E5 feature extraction, matched calibration and predictions before truth access."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from threadpoolctl import threadpool_limits

from .bundle import file_hash, write_json
from .e1_mechanics import gate_masks
from .e3_inference import encode_readouts
from .e3_pipeline import models_for
from .e5_catalog import PATCHES, runs
from .e5_features import encode_ae_readouts, equal_blocks, spatial_geometry
from .e5_fit import fit_adapters
from .e5_predict import generate_predictions
from .e5_windows import patch_rows
from .training.data import extract_patch, synthetic_in_normalizer_units, transfer_membership
from .training.texture import describe_patches

RTOL, ATOL, SCHEDULE_SEED = 1e-4, 1e-5, 20261112


def expand(values, indices, count):
    result = np.full((count,) + values.shape[1:], np.nan, dtype=values.dtype)
    result[indices] = values
    return result


def extraction_masks(record, rows, regime):
    """Geometric split membership is evaluated even for incomplete image support."""
    available = np.asarray([row['available'] for row in rows], bool)
    if record['kind'] == 'measurement' and regime == 'transfer':
        membership = [transfer_membership(record, np.asarray(row['support_xyxy']))[0] for row in rows]
        scope = np.asarray([value == 'test' for value in membership], bool)
        train = np.asarray([value == 'train' for value in membership], bool)
    else:
        scope = np.ones(len(rows), bool)
        train = np.full(len(rows), record['kind'] == 'measurement', bool)
    centers = np.asarray([row['raw_edge_xy'] for row in rows], float).reshape(-1, 2)
    return dict(available=available, scope=scope, train=train, centers=centers)


def check_baseline(actual, expected):
    """Require identical missingness and the declared fresh-CPU tolerance."""
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or not np.array_equal(np.isfinite(actual), np.isfinite(expected)):
        raise ValueError('Baseline feature shape or finite support changed')
    if not np.allclose(actual, expected, rtol=RTOL, atol=ATOL, equal_nan=True):
        raise ValueError('Fresh exact48 features exceeded the frozen baseline tolerance')
    finite = np.isfinite(actual) & np.isfinite(expected)
    return dict(max_abs_difference=float(np.max(np.abs(actual[finite] - expected[finite]))) if finite.any() else 0.,
                exact=bool(np.array_equal(actual, expected, equal_nan=True)),
                finite_rows=int(np.isfinite(actual).all(axis=1).sum()), rows=len(actual), dimensions=actual.shape[1])


def extract_group(bank, group, regime, models, check_budget):
    """Compute one group only; no full-map arrays are retained across groups."""
    original_rows = bank.inputs.rows(group)
    record, arrays = bank.inputs.sample(group)
    count = len(original_rows)
    normalizer = models[('ae', 20261101)].run_config['data']['normalizer']
    if any(model.run_config['data']['normalizer'] != normalizer for model in models.values()):
        raise ValueError('Frozen models disagree about regime normalization')
    source = synthetic_in_normalizer_units(arrays, normalizer) if record['kind'] == 'synthetic' else arrays
    values = {run['run_id']: {} for run in runs() if run['regime'] == regime}
    run_lookup = {(r['family'], r['seed']): r['run_id'] for r in runs() if r['regime'] == regime}
    shared, patch_replay = {}, None
    for patch_key, (scale, centering) in PATCHES.items():
        check_budget()
        rows = patch_rows(record, arrays, original_rows, scale=scale, centering=centering)
        masks = extraction_masks(record, rows, regime)
        shared.update({f'{patch_key}__{key}': value for key, value in masks.items()})
        indices = np.flatnonzero(masks['available'])
        patches = (np.stack([extract_patch(source, rows[int(i)], normalizer) for i in indices])
                   if len(indices) else np.empty((0, 64, 64), np.float32))
        if patch_key == 'exact48':
            cached = bank.inputs.load_npz(f"cache/{group['group_id']}/{regime}.npz")
            if not np.array_equal(indices, cached['available_indices']):
                raise ValueError('Exact48 extraction availability differs from source cache')
            if not np.array_equal(patches, cached['patches']):
                raise ValueError('Exact48 raw preprocessing differs from the frozen64 input cache')
            patch_replay = dict(available=len(indices), exact=True)
        native = (patches if scale == 64 else
                  (np.stack([extract_patch(source, rows[int(i)], normalizer, size=scale) for i in indices])
                   if len(indices) else np.empty((0, scale, scale), np.float32)))
        texture = describe_patches(native)
        values[run_lookup[('fft', None)]][patch_key] = expand(texture['features'], indices, count)
        for (family, seed), model in models.items():
            check_budget()
            if family == 'ae':
                encoded = encode_ae_readouts(model, patches) if patch_key == 'exact48' else encode_readouts(model, patches)
                values[run_lookup[('ae', seed)]][patch_key] = expand(encoded['ae'], indices, count)
                if patch_key == 'exact48':
                    values[run_lookup[('ae', seed)]]['map48'] = expand(encoded['ae_map'], indices, count)
            else:
                encoded = encode_readouts(model, patches)
                for name in ('rvae_full', 'rvae_content'):
                    values[run_lookup[(name, seed)]][patch_key] = expand(encoded[name], indices, count)
        if patch_key == 'exact48':
            baseline = bank.inputs.descriptor(group, regime)
            if not np.array_equal(baseline['available'], masks['available']):
                raise ValueError('Baseline E1 descriptor support changed')
            gates = gate_masks(baseline['available'], baseline['valid'], baseline['acf_score'],
                               baseline['second_direction_ratio'], baseline['energy'], bank.inputs.threshold)
            shared.update(baseline_available=baseline['available'], baseline_hard=gates['hard'],
                          baseline_full_gate=gates['hard'] & gates['acf'] & gates['spectral'],
                          baseline_acf=baseline['acf_score'], baseline_ratio=baseline['second_direction_ratio'],
                          baseline_energy=baseline['energy'])
    for item in values.values():
        item['multi'] = equal_blocks({scale: item[f'exact{scale}'] for scale in (32, 48, 64)})
        if group['sampler'] == 'grid' and not np.array_equal(item['exact48'], item['snap48'], equal_nan=True):
            raise ValueError('Grid snap8 did not preserve exact48 features')
    return values, shared, patch_replay


def _write_npz(out, relative, arrays, files):
    path = out / relative
    if path.exists():
        raise FileExistsError(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    files[relative] = file_hash(path)


def _generate(bank, e2: Path, out: Path, check_budget):
    if any((out / name).exists() for name in ('features', 'shared', 'adapters', 'predictions', 'prediction-freeze.json')):
        raise FileExistsError('E5 generation needs a new artifact tree')
    files, groups, drift = {}, [], []
    old_freeze = json.loads((e2 / 'prediction-freeze.json').read_text())
    if file_hash(e2 / 'prediction-index.json') != old_freeze['files']['prediction-index.json']:
        raise ValueError('E2 prediction index changed')
    lineage = dict(e2_root=str(e2.resolve()), e2_freeze_sha256=file_hash(e2 / 'prediction-freeze.json'),
                   e2_index_sha256=old_freeze['files']['prediction-index.json'],
                   baseline_feature_source='E2 FeatureBank readouts of verified issue21/E1 files',
                   model_source='E3 models_for, selected original checkpoints; no weight changes',
                   map_geometry=spatial_geometry(48), baseline_rtol=RTOL, baseline_atol=ATOL)
    write_json(out / 'feature-provenance.json', lineage)
    files['feature-provenance.json'] = file_hash(out / 'feature-provenance.json')
    templates = {e['cache_group']: e for e in bank.inputs.entries
                 if e['family'] == 'fft' and e['regime'] == 'transductive' and e['partition'] == 'fh4'}
    schedule = [(regime, key) for regime in ('transfer', 'transductive') for key in sorted(bank.inputs.groups)]
    order = np.random.default_rng(SCHEDULE_SEED).permutation(len(schedule))
    schedule = [schedule[i] for i in order]
    if len(schedule) != 420 or len(templates) != 210:
        raise ValueError('E5 requires the complete 105-image, two-sampler catalogue')
    write_json(out / 'schedule.json', dict(seed=SCHEDULE_SEED, groups=schedule))
    files['schedule.json'] = file_hash(out / 'schedule.json')
    models = {regime: models_for(bank, regime) for regime in ('transfer', 'transductive')}
    for number, (regime, group_key) in enumerate(schedule):
        check_budget()
        group = bank.inputs.groups[group_key]
        template = templates[group_key]
        values, shared, patch_replay = extract_group(bank, group, regime, models[regime], check_budget)
        original = bank.inputs.load_npz(f"{template['directory']}/{template['evaluation_input']}")
        shared['edges'] = original['edges']
        shared_relative = f'shared/input-{number:04d}.npz'
        _write_npz(out, shared_relative, shared, files)
        feature_paths = {}
        for run in [r for r in runs() if r['regime'] == regime]:
            rid = run['run_id']
            comparison = check_baseline(values[rid]['exact48'], bank.features(rid, group))
            drift.append(dict(run, cache_group=group_key, sampler=group['sampler'],
                              patch_cache_replay=patch_replay, **comparison))
            relative = f"features/input-{number:04d}/{run['family']}-{run['seed'] or 0}.npz"
            _write_npz(out, relative, values[rid], files)
            feature_paths[rid] = relative
        groups.append(dict(id=f'input-{number:04d}', regime=regime, cache_group=group_key,
                           sampler=group['sampler'], sample_id=group['record']['sample_id'],
                           kind=group['record']['kind'], pixel_spacing_xy=template['pixel_spacing_xy'],
                           shared=shared_relative, features=feature_paths))
        del values, shared
        if (number + 1) % 20 == 0:
            print(f'E5 feature groups: {number + 1}/420', flush=True)
    del models
    for relative, value in (('feature-group-index.json', groups), ('baseline-drift.json', drift)):
        write_json(out / relative, value)
        files[relative] = file_hash(out / relative)
    adapters = fit_adapters(bank, out, groups, files, check_budget)
    index = generate_predictions(bank, out, groups, adapters, files, check_budget)
    write_json(out / 'prediction-freeze.json', dict(
        schema='stmdomains-e5-prediction-freeze-v1', files=files, groups=len(groups),
        entries=len(index), adapters=len(adapters), baseline_feature_checks=len(drift),
        max_baseline_abs_difference=max(d['max_abs_difference'] for d in drift),
        truth_opened_for_this_run=False, historical_data_known=True,
        graph='original transductive FFT full-frame s48 graph, identical across both regimes',
        old_partitions_replayed=False, new_encoder_training=False))
    return index, files


def generate(bank, e2: Path, out: Path, check_budget=lambda: None):
    """Public truth-free pipeline; caller freezes protocol/code before calling."""
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):
        return _generate(bank, Path(e2), Path(out), check_budget)
