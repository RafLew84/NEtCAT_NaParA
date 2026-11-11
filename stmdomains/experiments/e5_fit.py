"""Matched E5 adapters fitted only to filtered historical label-free fit IDs."""
from __future__ import annotations

import hashlib
import json

import numpy as np

from .bundle import file_hash, write_json
from .e5_catalog import conditions, patch_keys, runs
from .training.partition import _unit_features, fit_feature_adapter


def feature_dimension(run, condition):
    if condition['feature'] == 'map48':
        return 3136
    base = dict(ae=32, rvae_full=34, rvae_content=32, fft=216)[run['family']]
    return base * (3 if condition['feature'] == 'multi' else 1)


def filter_graph(edges, keep):
    """Filter original edges and remap endpoints; never infer new neighbors."""
    edges, keep = np.asarray(edges), np.asarray(keep)
    if keep.ndim != 1 or keep.dtype.kind != 'b':
        raise ValueError('Training selection must be a boolean vector')
    if edges.ndim != 2 or edges.shape[1] != 2 or edges.dtype.kind not in 'iu':
        raise ValueError('Training edges must be integer E-by-2')
    if np.any(edges < 0) or np.any(edges >= len(keep)):
        raise ValueError('Training endpoint outside original membership')
    lookup = np.full(len(keep), -1, np.int64)
    lookup[keep] = np.arange(int(keep.sum()))
    return lookup[edges[keep[edges].all(axis=1)]]


def matched_training(bank, out, groups, run, sampler, selected):
    """Materialize one contrast only, preserving old segment and ID order."""
    graph = bank.training_graph(run['regime'], sampler)
    lookup = {(g['regime'], g['cache_group']): g for g in groups}
    chunks = {c['id']: [] for c in selected}
    masks, observed_ids = [], []
    for segment in graph['segments']:
        group = lookup[(run['regime'], segment['group_id'])]
        indices = segment['row_indices']
        rows = bank.inputs.rows(segment['group_id'])
        observed_ids.extend(rows[int(i)]['window_id'] for i in indices)
        if segment['start'] != len(observed_ids) - len(indices) or segment['stop'] != len(observed_ids):
            raise ValueError('Historical graph segment order changed')
        keep = np.ones(len(indices), bool)
        with np.load(out / group['shared'], allow_pickle=False) as shared, np.load(
                out / group['features'][run['run_id']], allow_pickle=False) as features:
            for condition in selected:
                values = features[condition['feature']][indices]
                _, valid = _unit_features(values)
                keep &= valid
                for key in patch_keys(condition):
                    keep &= shared[f'{key}__available'][indices] & shared[f'{key}__train'][indices]
                chunks[condition['id']].append(values)
        masks.append(keep)
    if observed_ids != list(graph['window_ids']):
        raise ValueError('Training rows no longer match original fit IDs')
    keep = np.concatenate(masks) if masks else np.empty(0, bool)
    features = {}
    for condition in selected:
        values = (np.concatenate(chunks[condition['id']]) if chunks[condition['id']] else
                  np.empty((0, feature_dimension(run, condition))))
        features[condition['id']] = values[keep]
    ids = [ident for ident, valid in zip(graph['window_ids'], keep) if valid]
    edges = filter_graph(graph['edges'], keep)
    audit = dict(original_training_elements=len(keep), selected_training_elements=len(ids),
                 original_training_edges=len(graph['edges']), selected_training_edges=len(edges),
                 source_training_ids_sha256=graph['training_ids_sha256'],
                 source_membership=graph['membership_source'],
                 selection='intersection of all contrast inputs, geometric train membership and nonzero finite features',
                 fit_window_ids=ids, filtered_edges_sha256=hashlib.sha256(edges.tobytes()).hexdigest())
    return features, edges, ids, audit


def fit_adapters(bank, out, groups, files, check_budget):
    """Return paths keyed by (run_id,sampler,condition_id), writing new fits only."""
    paths, audit = {}, []
    for run in runs():
        selected = conditions(run['family'])
        for sampler in ('grid', 'centers'):
            for contrast in dict.fromkeys(c['contrast'] for c in selected):
                check_budget()
                subset = [c for c in selected if c['contrast'] == contrast]
                features, edges, ids, match = matched_training(bank, out, groups, run, sampler, subset)
                matched_hash = hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()
                for condition in subset:
                    check_budget()
                    feature_id = f"{run['run_id']}/{condition['id']}"
                    adapter = fit_feature_adapter(features[condition['id']], edges, ids, scope=dict(
                        regime=run['regime'], sampler=sampler, scale_px=condition['scales'],
                        feature_id=feature_id, contrast=contrast, condition=condition['id']))
                    if adapter['training_ids_sha256'] != matched_hash:
                        raise ValueError('Adapter did not retain matched training IDs')
                    adapter.update(fit_window_ids=ids, e5_fit_provenance=match)
                    relative = f"adapters/{feature_id}/{sampler}.json"
                    if (out / relative).exists():
                        raise FileExistsError(relative)
                    write_json(out / relative, adapter)
                    files[relative] = file_hash(out / relative)
                    paths[(run['run_id'], sampler, condition['id'])] = relative
                    audit.append(dict(run, sampler=sampler, contrast=contrast, condition=condition['id'],
                                      path=relative, training_ids_sha256=matched_hash,
                                      training_elements=adapter['training_elements'],
                                      valid_training_elements=adapter['valid_training_elements'],
                                      valid_training_edges=adapter['valid_training_edges'],
                                      available=adapter['available'], reason=adapter['reason'],
                                      input_dimension=adapter['input_dimension'],
                                      output_dimension=len(adapter['components'] or [])))
                del features
        print(f"E5 adapters: {run['run_id']} ({len(paths)} fits)", flush=True)
    write_json(out / 'adapter-audit.json', audit)
    files['adapter-audit.json'] = file_hash(out / 'adapter-audit.json')
    return paths
