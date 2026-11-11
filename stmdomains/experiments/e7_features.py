"""Frozen E7 centers48 features: new synthetic encodes, cached STM readouts."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from .bundle import arrays_hash, file_hash, validate_input, write_json
from .e1_mechanics import gate_masks
from .e2_features import geometry_features, photometry_features
from .e3_inference import encode_readouts
from .e3_pipeline import models_for
from .training.data import extract_patch, synthetic_in_normalizer_units
from .training.partition import neighbor_edges
from .training.texture import describe_patches

SEEDS = (20261101, 20261102, 20261103)
SCHEDULE_SEED = 20261117


def _expand(values, indices, count):
    result = np.full((count,) + values.shape[1:], np.nan, dtype=values.dtype)
    result[indices] = values
    return result


def _source(out, entry):
    path = (out / entry['source_file']).resolve()
    if not path.is_relative_to(out.resolve()) or file_hash(path) != entry['record']['sha256']:
        raise ValueError('Published E7 analysis input path/hash mismatch')
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    validate_input(arrays)
    if arrays_hash(arrays) != entry['record']['content_sha256']:
        raise ValueError('Published E7 analysis array content changed')
    return arrays


def synthetic_features(arrays, rows, normalizer, models):
    """No truth accepted: six frozen forward encodes supply all learned blocks."""
    count = len(rows)
    available = np.asarray([row['available'] for row in rows], bool)
    indices = np.flatnonzero(available)
    source = synthetic_in_normalizer_units(arrays, normalizer)
    patches = (np.stack([extract_patch(source, rows[int(i)], normalizer) for i in indices])
               if len(indices) else np.empty((0, 64, 64), np.float32))
    native = (np.stack([extract_patch(source, rows[int(i)], normalizer, size=48) for i in indices])
              if len(indices) else np.empty((0, 48, 48), np.float32))
    local = describe_patches(native)
    desc = {key: _expand(local[key], indices, count)
            for key in ('acf_score', 'second_direction_ratio', 'energy', 'basis_vectors')}
    desc.update(available=available, valid=np.zeros(count, bool))
    desc['valid'][indices] = local['valid']
    features = dict(geometry=geometry_features(desc),
                    photometry=photometry_features(dict(available_indices=indices, patches=patches), count))
    for (family, seed), model in models.items():
        encoded = encode_readouts(model, patches)
        key = 'ae' if family == 'ae' else 'rvae_full'
        features[f'{family}_{seed}'] = _expand(encoded[key], indices, count)
    return features, desc


def cached_stm_features(bank, entry, rows):
    """Read transfer-only source arrays; this branch never calls any encoder."""
    group = bank.inputs.group(entry['cache_group'])
    if rows != bank.inputs.rows(group):
        raise ValueError('Published STM rows differ from frozen anchor rows')
    features = {family: bank.features(f'transfer/{family}', group) for family in ('geometry', 'photometry')}
    for family in ('ae', 'rvae'):
        readout = 'ae' if family == 'ae' else 'rvae_full'
        for seed in SEEDS:
            features[f'{family}_{seed}'] = bank.features(f'transfer/{readout}/z32/seed-{seed}', group)
    return features, bank.inputs.descriptor(group, 'transfer')


def prepare_features(bank, out: Path, entries, check_budget=lambda: None):
    """Write finite/missing blocks and full fixed graphs; never open truth files."""
    out = Path(out)
    if not entries:
        raise ValueError('No E7 entries supplied')
    if (out / 'features').exists() or (out / 'feature-index.json').exists():
        raise FileExistsError('E7 features require a fresh destination')
    entries = list(entries)
    if len({entry['sample_id'] for entry in entries}) != len(entries):
        raise ValueError('Repeated E7 feature sample ID')
    entries = [entries[i] for i in np.random.default_rng(SCHEDULE_SEED).permutation(len(entries))]
    write_json(out / 'feature-schedule.json', dict(seed=SCHEDULE_SEED,
               sample_ids=[entry['sample_id'] for entry in entries]))
    torch.set_num_threads(1)
    models = models_for(bank, 'transfer')
    expected = {(family, seed) for family in ('ae', 'rvae') for seed in SEEDS}
    if set(models) != expected:
        raise ValueError('E7 requires all six frozen transfer AE/rVAE z32 models')
    normalizer = models[('ae', SEEDS[0])].run_config['data']['normalizer']
    if any(model.run_config['data']['normalizer'] != normalizer for model in models.values()):
        raise ValueError('Transfer model normalizers disagree')
    files, result = {'feature-schedule.json': file_hash(out / 'feature-schedule.json')}, []
    for number, entry in enumerate(entries):
        check_budget()
        arrays = _source(out, entry)
        rows_path = (out / entry['rows_file']).resolve()
        if not rows_path.is_relative_to(out.resolve()):
            raise ValueError('Row path escapes E7 output')
        if file_hash(rows_path) != entry['rows_sha256']:
            raise ValueError('Published E7 row hash changed')
        rows = json.loads(rows_path.read_text())
        if any(row['sampler'] != 'centers' or row.get('scale_px', row['scale_raw_px']) != 48 for row in rows):
            raise ValueError('E7 uses only source centers at reference scale48')
        if entry['kind'] == 'measurement':
            features, desc = cached_stm_features(bank, entry, rows)
        elif entry['kind'] == 'synthetic':
            features, desc = synthetic_features(arrays, rows, normalizer, models)
        else:
            raise ValueError('Unknown E7 sample kind')
        available = np.asarray([row['available'] for row in rows], bool)
        if not np.array_equal(available, desc['available']):
            raise ValueError('Row support differs from descriptor availability')
        spacing = np.asarray(entry['record']['pixel_spacing_xy'], float)
        xy = np.asarray([row['raw_edge_xy'] for row in rows], float).reshape(-1, 2)
        ids = [row['element_id'] for row in rows]
        edges = neighbor_edges(xy * spacing, ids, mode='centers', stride=16.)
        gates = gate_masks(available, desc['valid'], desc['acf_score'], desc['second_direction_ratio'],
                           desc['energy'], bank.inputs.threshold)
        features = dict(features, edges=edges, available=available, hard=gates['hard'],
                        full_gate=gates['hard'] & gates['acf'] & gates['spectral'],
                        acf=desc['acf_score'], ratio=desc['second_direction_ratio'], energy=desc['energy'])
        expected_dimensions = dict(geometry=8, photometry=3,
            **{f'{family}_{seed}': 32 if family == 'ae' else 34 for family, seed in expected})
        for name, dimension in expected_dimensions.items():
            if features[name].shape != (len(rows), dimension):
                raise ValueError(f'E7 feature alignment changed: {name}')
        relative = f"features/{entry['sample_id']}.npz"
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **features)
        files[relative] = file_hash(path)
        result.append(dict(entry, features_file=relative))
        if (number + 1) % 20 == 0 or number + 1 == len(entries):
            print(f'E7 features: {number + 1}/{len(entries)}', flush=True)
    lineage = bank.audit()['checkpoint_lineage']
    provenance = dict(schema='stmdomains-e7-features-v1',
        checkpoints={key: value for key, value in lineage['runs'].items() if key.startswith('transfer/')},
        normalization_path=lineage['normalization_path'], normalization_sha256=lineage['normalization_sha256'],
        normalizer=normalizer, feature_blocks=expected_dimensions, sampler='centers', scale_reference_px=48,
        synthetic_encoder_inference=True, stm_encoder_inference=False, encoder_training=False,
        stm_features='verified E2 FeatureBank transfer AE/full-rVAE/geometry/photometry',
        model_input='frozen real normalizer; synthetic bridge .5+.4*renderer; raw bilinear sampling to64 then clip',
        geometry='native48 ACF descriptors, unchanged eight-dimensional unordered-axis readout',
        graph='full source centers in reference pixels, neighbor_edges; descriptor availability applied later',
        threshold=bank.inputs.threshold, truth_files_opened=False)
    for relative, value in (('feature-index.json', result), ('feature-provenance.json', provenance)):
        write_json(out / relative, value)
        files[relative] = file_hash(out / relative)
    return result, files
