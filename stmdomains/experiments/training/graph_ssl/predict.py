"""Frozen, label-free geometry/graph comparison for research trial 24."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import resource
import time

import numpy as np
from scipy.spatial import cKDTree
from sklearn.cluster import HDBSCAN
import torch

from ...bundle import file_hash, write_arrays, write_json
from ...results import validate_result
from .. import partition as common
from .data import iter_prepared
from .legacy_geometry import compute_sample_geometry, legacy_join
from .fit import load_encoder, deny_evaluation_paths, verified_plan


def read(path):
    return json.loads(Path(path).read_text())


def stage_budget(root, started):
    used = sum(read(p)['cpu_seconds'] for p in root.glob('*resources.json'))
    if used + time.process_time() - started > 7200:
        raise RuntimeError('Graph24 postprocess CPU budget exhausted')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > 12 * 1024**3:
        raise MemoryError('Graph24 RSS budget exceeded')


def graph_edges(xy, ids):
    """Center graph, positive-NN radius, canonical ties, duplicates retained."""
    xy = np.asarray(xy, float)
    if len(xy) < 2:
        return np.empty((0, 2), dtype=np.int64)
    distance = np.linalg.norm(xy[:, None] - xy[None, :], axis=2)
    nearest = np.where(distance > 1e-10, distance, np.inf).min(axis=1)
    finite = nearest[np.isfinite(nearest)]
    radius = min(24., 1.65 * float(np.median(finite))) if len(finite) else 24.
    a, b = np.where(np.triu(distance <= radius + 1e-10, 1))
    pairs = [(int(u), int(v)) if str(ids[u]) < str(ids[v]) else (int(v), int(u)) for u, v in zip(a, b)]
    return np.asarray(sorted(pairs, key=lambda p: (str(ids[p[0]]), str(ids[p[1]]))), np.int64).reshape(-1, 2)


def runs(root):
    result = []
    for regime in ('transfer', 'transductive'):
        result.append(dict(variant_id=f'{regime}-geometry', family='geometry', regime=regime, seed=None, latent=None))
        for seed in (20261101, 20261102, 20261103):
            for loss in (('sce_scale', 'sce') if regime == 'transfer' else ('sce_scale',)):
                directory = root / 'training' / regime / loss / f'seed-{seed}'
                record = read(directory / 'run.json')
                if record.get('status') != 'completed':
                    continue
                checkpoint = record.get('selected_checkpoint')
                if checkpoint is None:
                    checkpoint = record.get('checkpoint')
                if checkpoint is None:
                    raise ValueError('Completed fit lacks selected checkpoint')
                path = Path(checkpoint)
                if not path.is_absolute():
                    path = directory / path
                if file_hash(path) != record['selected_checkpoint_sha256']:
                    raise ValueError('Selected checkpoint differs from the completed run')
                result.append(dict(variant_id=f'{regime}-graph_{loss}-{seed}', family=f'graph_{loss}',
                                   regime=regime, seed=seed, latent=32, checkpoint=str(path)))
                if loss == 'sce_scale':
                    initial = directory / record['initial_checkpoint']
                    if file_hash(initial) != record['initial_checkpoint_sha256']:
                        raise ValueError('Initial checkpoint differs from the completed run')
                    result.append(dict(variant_id=f'{regime}-graph_untrained-{seed}', family='graph_untrained',
                                       regime=regime, seed=seed, latent=32,
                                       checkpoint=str(initial)))
    return result


def geometry(root):
    started=time.process_time()
    output = root / 'geometry'
    if output.exists():
        raise FileExistsError(output)
    output.mkdir()
    records = []
    for sample in iter_prepared(root):
        stage_budget(root,started)
        h, w = sample['arrays']['image'].shape
        sx, sy = sample['record']['pixel_spacing_xy']
        features = compute_sample_geometry(sample['xyref'], (w*sx, h*sy), sample['eligible'],
                                            node_indices=sample['node_indices'])
        path = output / (sample['sample_id'] + '.npz')
        hashes = write_arrays(path, features)
        records.append(dict(sample_id=sample['sample_id'], file=str(path.relative_to(root)), **hashes))
    write_json(output / 'manifest.json', records)


@torch.inference_mode()
def encode(root, device):
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started=time.process_time()
    variants = runs(root)
    for run in variants:
        folder = root / 'features' / run['variant_id']
        if folder.exists():
            raise FileExistsError(folder)
        folder.mkdir(parents=True)
        model = None if run['family'] == 'geometry' else load_encoder(run['checkpoint'], device)[0]
        for sample in iter_prepared(root):
            stage_budget(root,started)
            n = len(sample['ids'])
            features = np.full((n, 57 if model is None else 32), np.nan, np.float32)
            chosen = np.flatnonzero(sample['eligible'])
            if model is None:
                features[chosen] = sample['x'][chosen, 0]
            else:
                for begin in range(0, len(chosen), 64):
                    indices = chosen[begin:begin+64]
                    width = int(sample['valid'][indices].sum(axis=1).max())
                    x = torch.from_numpy(sample['x'][indices, :width]).to(device)
                    adj = torch.from_numpy(sample['adj'][indices, :width, :width]).to(device)
                    valid = torch.from_numpy(sample['valid'][indices, :width]).to(device)
                    features[indices] = model.encode(x, adj, valid)[:, 0].cpu().numpy()
            write_arrays(folder / (sample['sample_id']+'.npz'), dict(features=features))
        print('encoded', run['variant_id'], flush=True)
    write_json(root / 'features/runs.json', variants)


def transform(features, adapter):
    finite = np.isfinite(features).all(axis=1)
    out = np.full((len(features), len(adapter['components'])), np.nan)
    if adapter['available']:
        out[finite] = ((features[finite]-adapter['mean'])/adapter['std']-adapter['pca_mean']) @ np.asarray(adapter['components']).T
    else:
        finite[:] = False
    return out, finite


def fit_adapter(root, run):
    features, edges, identifiers, offset = [], [], [], 0
    for sample in iter_prepared(root, kind='measurement'):
        selected = sample['eligible'] & ((sample['split'] == 'train') if run['regime'] == 'transfer' else True)
        indices = np.flatnonzero(selected)
        with np.load(root / 'features' / run['variant_id'] / (sample['sample_id']+'.npz')) as archive:
            values = archive['features'][indices]
        ids = [str(sample['ids'][i]) for i in indices]
        edges.append(graph_edges(sample['xyref'][indices], ids)+offset)
        features.append(values)
        identifiers.extend(sample['sample_id']+'/'+ident for ident in ids)
        offset += len(indices)
    x = np.concatenate(features)
    edge = np.concatenate(edges)
    result = dict(available=False, input_dimension=x.shape[1], training_elements=len(x),
                  training_ids=identifiers, regime=run['regime'], feature_id=run['variant_id'],
                  mean=[], std=[], pca_mean=[], components=[], reason=None)
    if len(x) < 2 or not np.isfinite(x).all() or not len(edge):
        result['reason'] = 'insufficient_training_geometry'
        return result
    result['mean'] = x.mean(axis=0).tolist()
    result['std'] = np.maximum(x.std(axis=0), 1e-6).tolist()
    standardized = (x-result['mean'])/result['std']
    center = standardized.mean(axis=0)
    _, singular, components = np.linalg.svd(standardized-center, full_matrices=False)
    components = components[:min(24, x.shape[1], len(x)-1)]
    for vector in components:
        vector *= 1 if vector[np.argmax(abs(vector))] >= 0 else -1
    projected = (standardized-center) @ components.T
    distances = np.linalg.norm(projected[edge[:, 0]]-projected[edge[:, 1]], axis=1)
    positive = distances[distances > 1e-10]
    if not len(positive):
        result['reason'] = 'degenerate_training_geometry'
        return result
    median = float(np.median(positive))
    q25, q75 = np.quantile(distances/median, [.25, .75])
    result.update(available=True, pca_mean=center.tolist(), components=components.tolist(),
                  singular_values=singular.tolist(), edge_median=median, q25=float(q25), q75=float(q75))
    # Shared descriptor groups are diagnostic, never physical structural types.
    labels = HDBSCAN(min_cluster_size=8, min_samples=4, allow_single_cluster=True).fit_predict(projected)
    groups = []
    for label in sorted(set(labels)-{-1}):
        member = projected[labels == label]
        centroid = member.mean(axis=0)
        radius = float(np.quantile(np.linalg.norm(member-centroid, axis=1), .95))
        groups.append(dict(id=int(label)+1, centroid=centroid.tolist(), radius=radius, training_members=len(member)))
    result['catalogue'] = dict(meaning='descriptor_similarity_only_not_structural_type', groups=groups,
                               assignment='nearest centroid within its training95% radius; otherwise null')
    return result


def integer_labels(labels):
    unique = sorted(set(v for v in labels if v is not None))
    mapping = {value: i+1 for i, value in enumerate(unique)}
    return np.asarray([0 if v is None else mapping[v] for v in labels], np.int32)


def descriptor_groups(projected, adapter):
    labels = np.zeros(len(projected), np.int32)
    groups = adapter.get('catalogue', {}).get('groups', [])
    if not groups or not len(projected):
        return labels
    valid = np.isfinite(projected).all(axis=1)
    selected = np.flatnonzero(valid)
    if not len(selected):
        return labels
    centers = np.asarray([group['centroid'] for group in groups])
    distance = np.linalg.norm(projected[selected, None] - centers, axis=2)
    chosen = np.argmin(distance, axis=1)
    for index, group in enumerate(groups):
        accepted = (chosen == index) & (distance[:, index] <= group['radius'])
        labels[selected[accepted]] = group['id']
    return labels


def partition_features(sample, values, adapter, geometry_values, method, scope):
    n = len(sample['ids'])
    indices = np.flatnonzero(scope)
    ids = sample['ids'][indices].tolist()
    local_edges = graph_edges(sample['xyref'][indices], ids)
    edges = indices[local_edges]
    projected, valid = transform(values[indices], adapter)
    valid &= sample['eligible'][indices]
    distances = np.full(len(local_edges), np.nan)
    active = valid[local_edges].all(axis=1)
    if adapter['available']:
        distances[active] = np.linalg.norm(projected[local_edges[active, 0]]-projected[local_edges[active, 1]], axis=1)/adapter['edge_median']
        kinds, strengths = common.relation_weights(distances, adapter['q25'], adapter['q75'])
    else:
        kinds, strengths = np.full(len(distances), 'unavailable'), np.full(len(distances), np.nan)
    if method == 'fh4':
        proposal = common.fh_partition(ids, local_edges, distances, valid=valid)
    else:
        proposal = common.mws_partition(ids, local_edges, kinds, strengths, valid=valid)['component_ids']
    final, reasons = common.apply_refusals(ids, local_edges, proposal,
                                          valid & geometry_values['gate'][indices], min_size=8)
    before, after = np.zeros(n, np.int32), np.zeros(n, np.int32)
    before[indices], after[indices] = integer_labels(proposal), integer_labels(final)
    states = np.full(n, 'not_evaluated', dtype='U24')
    states[indices] = np.where(after[indices] > 0, 'ordered_untyped', 'ambiguous')
    states[scope & ~sample['eligible']] = 'insufficient_data'
    refusal = np.full(n, 'not_test_scope', dtype='U96')
    refusal[indices] = ['' if value is None else value for value in reasons]
    for index in np.flatnonzero(scope & ~sample['eligible']):
        refusal[index] = sample['rows'][index]['unavailable_reason']
    groups = np.zeros(n, np.int32)
    groups[indices] = descriptor_groups(projected, adapter)
    return dict(before=before, after=after, edges=edges, states=states, reasons=refusal,
                score=geometry_values['score'], edge_distances=distances,
                relation_kinds=kinds, relation_strengths=strengths,
                descriptor_group=groups)


def export(root, sample, metadata, arrays, filename):
    path = root / filename
    write_arrays(path, arrays)
    assignments = []
    for i, row in enumerate(sample['rows']):
        state = str(arrays['states'][i])
        domain = int(arrays['after'][i]) or None
        assignments.append(dict(element_id=row['element_id'], xy=row['raw_edge_xy'],
                                support_xyxy=row['support_xyxy'], state=state,
                                reason=None if domain else str(arrays['reasons'][i]),
                                type_id=None, domain_id=domain, orientation_deg=None))
    payload = dict(schema='stmdomains-result-v1', sample_id=sample['sample_id'],
                   input_content_sha256=sample['record']['content_sha256'],
                   run_id=metadata['variant_id']+'-'+metadata['partition'], catalogue_id=None,
                   assignments=assignments, extensions=dict(graph24=dict(
                       elements=sample['rows'], metadata=metadata, material=None,
                       descriptor_catalogue='adapters/'+metadata['variant_id']+'.json' if metadata['family']!='legacy15' else None)))
    validate_result(payload)
    with gzip.open(path.with_suffix('.json.gz'), 'wt', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)


def partition_all(root):
    started=time.process_time()
    variants = read(root / 'features/runs.json')
    adapters = {}
    for run in variants:
        stage_budget(root,started)
        adapter = fit_adapter(root, run)
        write_json(root / 'adapters' / (run['variant_id']+'.json'), adapter)
        adapters[run['variant_id']] = adapter
    entries = []
    for sample in iter_prepared(root):
        stage_budget(root,started)
        with np.load(root / 'geometry' / (sample['sample_id']+'.npz')) as archive:
            geom = {key: archive[key] for key in archive.files}
        for run in variants:
            with np.load(root / 'features' / run['variant_id'] / (sample['sample_id']+'.npz')) as archive:
                values = archive['features']
            for method in ('fh4', 'mws'):
                meta = dict(run, feature_id=run['variant_id'], sample_id=sample['sample_id'],
                            kind=sample['kind'], case=sample['record'].get('case'),
                            control_seed=sample['record'].get('seed'), partition=method, scale_px=72, sampler='centers')
                meta.pop('checkpoint', None)
                filename = f"predictions/{run['variant_id']}/{method}/{sample['sample_id']}.npz"
                arrays = partition_features(sample, values, adapters[run['variant_id']], geom, method,
                                            np.ones(len(sample['ids']), bool))
                export(root, sample, meta, arrays, filename)
                meta['file'] = filename
                if sample['kind']=='measurement' and run['regime']=='transfer':
                    meta['heldout_file'] = filename.replace('.npz', '-heldout.npz')
                    heldout = partition_features(sample, values, adapters[run['variant_id']], geom, method, sample['split']=='test')
                    export(root, sample, meta, heldout, meta['heldout_file'])
                entries.append(meta)
        for regime in ('transfer', 'transductive'):
            meta = dict(sample_id=sample['sample_id'], kind=sample['kind'], case=sample['record'].get('case'),
                        control_seed=sample['record'].get('seed'), variant_id=regime+'-legacy15', feature_id='legacy15',
                        family='legacy15', regime=regime, seed=None, latent=None, partition='legacy15', scale_px=72,
                        sampler='centers', before_stage_interpretation='complete_legacy15_procedure_no_separate_unfiltered_partition')
            filename=f'predictions/{regime}-legacy15/{sample["sample_id"]}.npz'
            for heldout in (False, True) if regime=='transfer' and sample['kind']=='measurement' else (False,):
                scope=(sample['split']=='test') if heldout else np.ones(len(sample['ids']), bool)
                available=scope & sample['eligible']
                canonical=np.argsort(sample['ids'],kind='stable')
                labels=np.zeros(len(canonical),np.int32)
                labels[canonical]=legacy_join(sample['xyref'][canonical],
                                               {key:value[canonical] for key,value in geom.items()},available[canonical])
                chosen=np.flatnonzero(scope)
                reasons=np.where(~scope,'not_test_scope',np.where(labels>0,'','legacy_cell_order_phase_or_size')).astype('U96')
                for index in np.flatnonzero(scope & ~sample['eligible']):
                    reasons[index]=sample['rows'][index]['unavailable_reason']
                arrays=dict(before=labels, after=labels, edges=chosen[graph_edges(sample['xyref'][chosen],sample['ids'][chosen])],
                            states=np.where(~scope, 'not_evaluated', np.where(~sample['eligible'], 'insufficient_data',
                                            np.where(labels>0,'ordered_untyped','ambiguous'))), score=geom['score'],reasons=reasons)
                key='heldout_file' if heldout else 'file'
                meta[key]=filename.replace('.npz','-heldout.npz') if heldout else filename
                export(root,sample,meta,arrays,meta[key])
            entries.append(meta)
        print('partitioned',sample['sample_id'],flush=True)
    write_json(root/'predictions/index.json',entries)


def freeze(root):
    target=root/'frozen-predictions.json'
    if target.exists():
        raise FileExistsError(target)
    plan=read(root/'plan.json')
    files={str(p.relative_to(root)):file_hash(p) for p in sorted(root.rglob('*')) if p.is_file()
           and not any(part.startswith('.') for part in p.relative_to(root).parts)
           and 'evaluation' not in p.relative_to(root).parts and p.name!='frozen-predictions.json'}
    for name, expected in plan['code_sha256'].items():
        if file_hash(Path(name))!=expected:
            raise ValueError('Frozen numerical source changed: '+name)
    external={str(Path(name).resolve()):expected for name,expected in plan['code_sha256'].items()}
    manifest=read(root/'prepared/manifest.json')
    for row in manifest['samples']:
        base=Path(row['source_analysis'])
        for path in (base/'manifest.json',base/row['record']['file']):
            external[str(path.resolve())]=file_hash(path)
    write_json(target,dict(schema='stmdomains-frozen-predictions-v1',evaluation_opened=False,
                           files=files,code_sha256=plan['code_sha256'],external_files=external,
                           plan_sha256=file_hash(root/'plan.json'),prediction_count=len(read(root/'predictions/index.json'))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('geometry','encode','partition','freeze'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device',default='cuda')
    args=parser.parse_args(); root=args.output.resolve()
    verified_plan(root,root)
    deny_evaluation_paths()
    started,wall=time.process_time(),time.perf_counter()
    target=root/(args.stage+'.resources.json')
    if target.exists():
        raise FileExistsError(target)
    status='failed'
    try:
        stage_budget(root,started)
        {'geometry':geometry,'encode':lambda r:encode(r,args.device),'partition':partition_all,'freeze':freeze}[args.stage](root)
        stage_budget(root,started)
        status='completed'
    finally:
        write_json(target,dict(status=status,cpu_seconds=time.process_time()-started,
                               wall_seconds=time.perf_counter()-wall,
                               max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))


if __name__=='__main__':
    main()
