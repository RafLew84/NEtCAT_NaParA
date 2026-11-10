"""Label-free issue-21 inference, calibrated graph comparison and frozen outputs.

This is a research runner, not a detector integrated into the application.
The process denies evaluation/reference paths. Evaluation is a separate process
and consumes only completed, hashed predictions; it never calls this predictor.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import json
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np

from ..bundle import arrays_hash, file_hash, load_sample, write_json
from ..results import validate_result
from .data import (SCALES, STRIDE, extract_patch, read_windows, support_available,
                   synthetic_in_normalizer_units)

_CPU_STARTED = time.process_time()
_CPU_PREVIOUS = 0.


def check_postprocess_budget():
    if time.process_time()-_CPU_STARTED+_CPU_PREVIOUS > 7200:
        raise RuntimeError('Frozen two-hour CPU postprocessing budget exceeded')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > 12*1024**3:
        raise RuntimeError('Frozen 12 GiB RSS budget exceeded')


def read_json(path):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def write_gzip(path, value, *, compresslevel=9):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=compresslevel) as compressed:
            compressed.write(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                        separators=(',', ':')).encode())


def deny_evaluation_paths():
    def audit(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.fsdecode(args[0]).replace('\\', '/')
        if '/evaluation/' in path or '/references/' in path or 'manual_domain' in path:
            raise PermissionError(f'Evaluation data denied to predictor: {path}')
    sys.addaudithook(audit)


def synthetic_rows(record, arrays):
    """Grid and support in reference pixels, stored in raw edge coordinates.

    The supplied technical resampling calibration is used before extraction.
    No case name, domain truth or renderer parameters are needed here.
    """
    spacing = np.asarray(record['pixel_spacing_xy'], float)
    if spacing.shape != (2,) or not np.allclose(spacing, spacing[0]) or spacing[0] <= 0:
        raise ValueError('Pilot requires finite isotropic reference-pixel calibration')
    factor = float(spacing[0])
    height, width = arrays['image'].shape
    positions = [('grid', f'g-{x:g}-{y:g}', [x/factor, y/factor])
                 for y in np.arange(STRIDE/2, height*factor, STRIDE)
                 for x in np.arange(STRIDE/2, width*factor, STRIDE)]
    positions += [('centers', str(ident), xy.tolist())
                  for ident, xy in zip(arrays['object_ids'], arrays['centers_xy'])]
    rows = []
    for sampler, ident, xy in positions:
        for scale in SCALES:
            center = np.asarray(xy)
            box = np.r_[center-scale/(2*factor), center+scale/(2*factor)]
            support = box + np.array([-3, -3, 3, 3])/factor
            available = support_available(support, arrays['measured'])
            rows.append(dict(window_id=f"{record['sample_id']}/{sampler}/{ident}/s{scale}",
                             sample_id=record['sample_id'], element_id=ident, sampler=sampler,
                             raw_edge_xy=list(map(float, xy)), position_unit='raw_px',
                             pixel_spacing_xy=spacing.tolist(), scale_px=scale,
                             scale_raw_px=scale/factor, feature_support_xyxy=box.tolist(),
                             support_xyxy=support.tolist(), available=available,
                             unavailable_reason=None if available else 'incomplete_measured_support',
                             transfer_split=None, transductive_split=None))
    return rows


def make_groups(prepared, controls):
    manifest = read_json(prepared/'data/analysis/manifest.json')
    heldout = read_json(controls/'analysis/manifest.json')
    measurement_rows = defaultdict(list)
    for row in read_windows(prepared/'data/windows.jsonl'):
        row = dict(row, scale_px=row['scale_raw_px'], pixel_spacing_xy=[1., 1.])
        measurement_rows[row['sample_id']].append(row)
    groups = []
    for analysis, records in ((prepared/'data/analysis', manifest['samples']),
                              (controls/'analysis', heldout['samples'])):
        for record in records:
            _, arrays = load_sample(analysis, record['sample_id'])
            rows = (measurement_rows[record['sample_id']] if record['kind'] == 'measurement'
                    else synthetic_rows(record, arrays))
            for scale in SCALES:
                for sampler in ('grid', 'centers'):
                    selected = [r for r in rows if r['scale_px'] == scale and r['sampler'] == sampler]
                    groups.append(dict(group_id=f"{record['sample_id']}/{sampler}/s{scale}",
                                       record=record, analysis=str(analysis.resolve()),
                                       rows=selected, scale_px=scale, sampler=sampler))
    return groups


def cache_inputs(prepared, controls, output):
    from .texture import describe_patches, calibrate_order_thresholds, order_mask
    target = output/'cache'
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    manifest = read_json(prepared/'data/manifest.json')
    for name in ('windows', 'split', 'normalization'):
        if file_hash(prepared/'data'/manifest[name+'_file']) != manifest[name+'_sha256']:
            raise ValueError('Prepared data changed: '+name)
    write_json(output/'inference-configuration.json', dict(
        schema='stmdomains-issue21-inference-v1',
        plan_sha256=file_hash(Path(__file__).with_name('experiment-plan.json')),
        prepared_manifest_sha256=file_hash(prepared/'data/manifest.json'),
        scales=list(SCALES), main_scale=48, samplers=['grid', 'centers'],
        graph_context=dict(full_fields='visualization and transductive inference',
                           transfer_measurement_metrics='eligible test nodes and edges only'),
        synthetic_units='use supplied pixel_spacing_xy; preserve reference-pixel supports and stride',
        orientation='raw rVAE angle diagnostic only; unvalidated lattice angles stay null',
        catalogue='type_id null; structural-type validation not claimed',
        checkpoint_selection='frozen training protocol only; no domain-reference selection'))
    normalizers = read_json(prepared/'data/normalization.json')
    thresholds = calibrate_order_thresholds()
    write_json(target/'order-thresholds.json', thresholds)
    groups = make_groups(prepared, controls)
    index = []
    current_sample = None
    arrays = None
    for n, group in enumerate(groups):
        check_postprocess_budget()
        record, rows = group['record'], group['rows']
        if current_sample != record['sample_id']:
            _, arrays = load_sample(Path(group['analysis']), record['sample_id'])
            current_sample = record['sample_id']
        relative = Path(group['group_id'])
        write_gzip(target/relative/'rows.json.gz', rows)
        available = np.array([i for i, row in enumerate(rows) if row['available']], dtype=np.int64)
        for regime in ('transfer', 'transductive'):
            source = (arrays if record['kind'] == 'measurement'
                      else synthetic_in_normalizer_units(arrays, normalizers[regime]))
            normalized = normalizers[regime]
            native = np.stack([extract_patch(source, rows[i], normalized, size=group['scale_px'])
                               for i in available]) if len(available) else np.empty((0, group['scale_px'], group['scale_px']))
            patches = np.stack([extract_patch(source, rows[i], normalized) for i in available]) \
                if len(available) else np.empty((0, 64, 64), np.float32)
            description = describe_patches(native)
            # The calibrator records a scalar for each scale, used by every feature family.
            threshold = thresholds['scales'][str(group['scale_px'])]['threshold']
            passed = order_mask(description, threshold)
            cached = dict(available_indices=available, patches=patches,
                          order_pass=np.zeros(len(rows), bool),
                          acf_score=np.full(len(rows), np.nan),
                          fft=np.full((len(rows), 216), np.nan))
            cached['order_pass'][available] = passed
            cached['acf_score'][available] = description['acf_score']
            cached['fft'][available] = description['features']
            np.savez_compressed(target/relative/f'{regime}.npz', **cached)
        index.append({k: v for k, v in group.items() if k != 'rows'})
        if n % 60 == 0:
            print(f'cache {n+1}/{len(groups)}', flush=True)
    write_json(target/'index.json', index)
    return index


def model_runs(training):
    runs = []
    for path in sorted(training.glob('*/*/z*/seed-*/run.json')):
        config = read_json(path)
        if config['status'] != 'completed' or not config.get('selected_checkpoint'):
            continue
        regime, family, latent, seed = path.parent.relative_to(training).parts
        runs.append(dict(run_id='/'.join((regime, family, latent, seed)), regime=regime,
                         family=family, latent=int(latent[1:]), seed=int(seed[5:]),
                         directory=str(path.parent.resolve()), run_metadata=config))
    return runs


def encode_models(output, device='cuda'):
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    import torch
    from .models import load_model
    target = output/'features'
    target.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    groups = read_json(output/'cache/index.json')
    completed = []
    for run in model_runs(output/'training'):
        run_target = target/run['run_id']
        if (run_target/'complete.json').exists():
            completed.append(read_json(run_target/'complete.json'))
            continue
        model = load_model(Path(run['directory']), device=device)
        model.eval()
        started = time.monotonic()
        if device == 'cuda':
            torch.cuda.reset_peak_memory_stats()
        for group in groups:
            check_postprocess_budget()
            cache_path = output/'cache'/group['group_id']
            rows = read_json(cache_path/'rows.json.gz')
            with np.load(cache_path/f"{run['regime']}.npz", allow_pickle=False) as data:
                indices, patches = data['available_indices'], data['patches']
            content = np.full((len(rows), run['latent']), np.nan, np.float32)
            angle = np.full(len(rows), np.nan, np.float32)
            reconstruction_mse = np.full(len(rows), np.nan, np.float32)
            with torch.inference_mode():
                for start in range(0, len(indices), 128):
                    idx = indices[start:start+128]
                    tensor = torch.from_numpy(patches[start:start+128, None]).to(device)
                    encoded = model.encode(tensor)
                    content[idx] = encoded['content'].cpu().numpy()
                    if encoded['angle_radians'] is not None:
                        angle[idx] = encoded['angle_radians'].cpu().numpy()
                    reconstruction = model.predict(tensor)
                    reconstruction_mse[idx] = (reconstruction-tensor).square().mean((1, 2, 3)).cpu().numpy()
            if run['family'] == 'rvae':
                norm = np.linalg.norm(content, axis=1, keepdims=True)
                with np.errstate(divide='ignore', invalid='ignore'):
                    full = np.concatenate((content/norm, np.cos(angle)[:, None], np.sin(angle)[:, None]), axis=1)/np.sqrt(2)
            else:
                full = content
            path = run_target/group['group_id']
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path.with_suffix('.npz'), features=full, content=content,
                                angle_radians=angle, reconstruction_mse=reconstruction_mse)
        if device == 'cuda':
            torch.cuda.synchronize()
        summary = dict(run, inference_seconds=time.monotonic()-started,
                       peak_gpu_bytes=int(torch.cuda.max_memory_allocated()) if device == 'cuda' else 0)
        write_json(run_target/'complete.json', summary)
        completed.append(summary)
        print(f"encoded {run['run_id']} {summary['inference_seconds']:.1f}s", flush=True)
        del model
    write_json(target/'index.json', completed)
    return completed


def load_features(output, run, group):
    if run['family'] == 'fft':
        path = output/'cache'/group['group_id']/f"{run['regime']}.npz"
        key = 'fft'
    else:
        path = (output/'features'/run['run_id']/group['group_id']).with_suffix('.npz')
        key = 'features'
    with np.load(path, allow_pickle=False) as data:
        return data[key]


def label_numbers(components):
    keys = sorted({str(c) for c in components if c is not None})
    mapping = {key: i+1 for i, key in enumerate(keys)}
    return np.array([mapping[str(c)] if c is not None else 0 for c in components], np.int32)


def relation_records(rows, edges, result):
    records = []
    for i, (u, v) in enumerate(edges):
        a, b = rows[u], rows[v]
        aa, bb = np.asarray(a['support_xyxy']), np.asarray(b['support_xyxy'])
        spacing = np.asarray(a['pixel_spacing_xy'])
        intersection = float(np.maximum(0, np.minimum(aa[2:], bb[2:])-np.maximum(aa[:2], bb[:2])).prod()*spacing.prod())
        union = float((np.prod(aa[2:]-aa[:2])+np.prod(bb[2:]-bb[:2]))*spacing.prod()-intersection)
        distance = result['edge_distances'][i]
        available = bool(np.isfinite(distance))
        relation = dict(kind=str(result['relation_kinds'][i]),
                        strength=float(result['relation_strengths'][i]) if available else None)
        records.append(dict(edge_id=f"{a['element_id']}:{b['element_id']}", u=a['element_id'], v=b['element_id'],
                            neighbor_rule='grid8-stride16' if a['sampler'] == 'grid' else 'local-centers',
                            distance_px=float(np.linalg.norm((np.array(a['raw_edge_xy'])-b['raw_edge_xy'])*spacing)),
                            support_intersection_area_px2=intersection, support_iou=intersection/union if union else 0.,
                            appearance_distance=float(distance) if available else None,
                            structure_spacing=dict(value=None, reason='not_separated_from_orientation'),
                            orientation=dict(value_deg=None, reason='no_validated_lattice_angle'),
                            translation_jump=dict(value=None, reason='not_measured'),
                            availability='available' if available else 'unavailable',
                            missing_reasons=[] if available else ['unavailable_feature_or_adapter'],
                            solver_relation=relation))
    return records


def result_envelope(group, rows, run, method, result, acf, threshold, hashes, relation_artifact):
    before, after = result['proposal_component_ids'], result['final_component_ids']
    assignments, evidence, proposals = [], [], []
    for i, row in enumerate(rows):
        reason = result['reasons'][i]
        if not row['available']:
            reason, state = 'incomplete_measured_support', 'insufficient_data'
        elif reason == 'outside_transfer_test':
            state = 'not_evaluated'
        elif after[i] is not None:
            state, reason = 'ordered_untyped', None
        else:
            state = 'ambiguous'
        assignments.append(dict(element_id=row['element_id'], xy=row['raw_edge_xy'],
                                support_xyxy=row['feature_support_xyxy'], state=state, reason=reason,
                                type_id=None, domain_id=after[i], orientation_deg=None))
        proposals.append(dict(element_id=row['element_id'], component_id=before[i],
                              reason=None if before[i] is not None else (reason or 'unavailable_feature')))
        score = float(acf[i]) if np.isfinite(acf[i]) else None
        evidence.append(dict(element_id=row['element_id'], order=dict(score=score, threshold=threshold, method='windowed_acf'),
                             orientation=dict(degrees=None, equivalent_degrees=[], reason='no_validated_lattice_angle'),
                             reliability=dict(score=score, calibrated_probability=False),
                             material=dict(state='unknown', score=None, reason='no_material_model'),
                             refusal_reasons=[] if reason is None else [reason]))
    payload = dict(schema='stmdomains-result-v1', sample_id=group['record']['sample_id'],
                   input_content_sha256=group['record']['content_sha256'], run_id=run['run_id']+'/'+method,
                   catalogue_id=None, assignments=assignments,
                   extensions=dict(training_v1=dict(protocol_id='stmdomains-training-plan-v1', **hashes,
                       regime=run['regime'], feature_id=run['run_id'], partition_id=method,
                       elements=rows, proposals=proposals, evidence=evidence,
                       relations_artifact=relation_artifact,
                       conflict_counts=result.get('stats', {}))))
    validate_result(payload)
    return payload


def partition_all(prepared, output):
    from .partition import neighbor_edges, fit_feature_adapter, partition_graph
    target = output/'predictions'
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    groups = read_json(output/'cache/index.json')
    thresholds = read_json(output/'cache/order-thresholds.json')
    runs = read_json(output/'features/index.json')
    runs += [dict(run_id=regime+'/fft', regime=regime, family='fft', latent=None, seed=None)
             for regime in ('transfer', 'transductive')]
    plan = Path(__file__).with_name('experiment-plan.json')
    hashes = dict(plan_sha256=file_hash(plan), split_sha256=file_hash(prepared/'data/split.json'))
    index = []
    for run in runs:
        for scale in SCALES:
            for sampler in ('grid', 'centers'):
                selected = [g for g in groups if g['scale_px'] == scale and g['sampler'] == sampler]
                train_features, train_edges, train_ids, fit_windows = [], [], [], []
                offset = 0
                for group in selected:
                    if group['record']['kind'] != 'measurement':
                        continue
                    rows = read_json(output/'cache'/group['group_id']/'rows.json.gz')
                    take = [i for i, r in enumerate(rows) if r['available'] and
                            (run['regime'] == 'transductive' or r['transfer_split'] == 'train')]
                    if not take:
                        continue
                    feature = load_features(output, run, group)[take]
                    ids = [rows[i]['window_id'] for i in take]
                    xy = np.array([rows[i]['raw_edge_xy'] for i in take])
                    edges = neighbor_edges(xy, ids, mode=sampler, stride=STRIDE)
                    train_features.append(feature)
                    train_edges.extend((edges+offset).tolist())
                    train_ids.extend(ids)
                    fit_windows.extend(ids)
                    offset += len(take)
                if not train_features:
                    raise ValueError('No eligible adapter training data')
                adapter = fit_feature_adapter(np.concatenate(train_features), np.array(train_edges, dtype=int).reshape(-1, 2),
                                              train_ids, scope=dict(regime=run['regime'], scale_px=scale,
                                              sampler=sampler, feature_id=run['run_id']))
                adapter['fit_window_ids'] = fit_windows
                adapter_path = target/run['run_id']/sampler/f's{scale}'/'adapter.json'
                write_json(adapter_path, adapter)
                adapter_hash = file_hash(adapter_path)
                checkpoint = None
                if run['family'] != 'fft':
                    checkpoint = run['run_metadata'].get('selected_checkpoint_sha256')
                for group in selected:
                    check_postprocess_budget()
                    rows = read_json(output/'cache'/group['group_id']/'rows.json.gz')
                    ids = [r['element_id'] for r in rows]
                    xy = np.array([np.array(r['raw_edge_xy'])*r['pixel_spacing_xy'] for r in rows]).reshape(-1, 2)
                    edges = neighbor_edges(xy, ids, mode=sampler, stride=STRIDE)
                    features = load_features(output, run, group)
                    with np.load(output/'cache'/group['group_id']/f"{run['regime']}.npz", allow_pickle=False) as cache:
                        order_pass, acf = cache['order_pass'], cache['acf_score']
                    threshold = thresholds['scales'][str(scale)]['threshold']
                    for method in ('fh4', 'mws'):
                        result = partition_graph(ids, edges, features, adapter, method=method,
                                                 order_pass=order_pass, min_size=4 if sampler == 'grid' else 8)
                        folder = target/run['run_id']/sampler/f's{scale}'/group['record']['sample_id']/method
                        relations_path = folder/'relations.json.gz'
                        write_gzip(relations_path, relation_records(rows, edges, result), compresslevel=1)
                        payload = result_envelope(group, rows, run, method, result, acf, threshold,
                            dict(hashes, checkpoint_sha256=checkpoint, adapter_sha256=adapter_hash),
                            dict(path='relations.json.gz', sha256=file_hash(relations_path)))
                        write_gzip(folder/'result.json.gz', payload, compresslevel=1)
                        before = label_numbers(result['proposal_component_ids'])
                        after = label_numbers(result['final_component_ids'])
                        np.savez_compressed(folder/'metrics-input.npz', before=before, after=after,
                                            edges=edges, acf_score=acf,
                                            available=np.array([r['available'] for r in rows], bool))
                        evaluation_input = 'metrics-input.npz'
                        if run['regime'] == 'transfer' and group['record']['kind'] == 'measurement':
                            eligible = np.array([r['transfer_split'] == 'test' for r in rows], bool)
                            heldout_features = features.copy()
                            heldout_features[~eligible] = np.nan
                            selected_indices = np.flatnonzero(eligible)
                            heldout_edges = selected_indices[neighbor_edges(xy[eligible],
                                [ids[i] for i in selected_indices], mode=sampler, stride=STRIDE)]
                            heldout = partition_graph(ids, heldout_edges, heldout_features, adapter, method=method,
                                                     order_pass=order_pass & eligible,
                                                     min_size=4 if sampler == 'grid' else 8)
                            for i in np.flatnonzero(~eligible):
                                heldout['reasons'][i] = 'outside_transfer_test'
                            rel_path = folder/'heldout-relations.json.gz'
                            write_gzip(rel_path, relation_records(rows, heldout_edges, heldout), compresslevel=1)
                            heldout_payload = result_envelope(group, rows, run, method, heldout, acf, threshold,
                                dict(hashes, checkpoint_sha256=checkpoint, adapter_sha256=adapter_hash),
                                dict(path='heldout-relations.json.gz', sha256=file_hash(rel_path)))
                            heldout_payload['extensions']['training_v1']['graph_context'] = 'eligible_transfer_test_only'
                            write_gzip(folder/'heldout-result.json.gz', heldout_payload, compresslevel=1)
                            np.savez_compressed(folder/'heldout-metrics-input.npz',
                                before=label_numbers(heldout['proposal_component_ids']),
                                after=label_numbers(heldout['final_component_ids']),
                                edges=heldout_edges, acf_score=acf,
                                available=np.array([r['available'] for r in rows], bool))
                            evaluation_input = 'heldout-metrics-input.npz'
                        index.append(dict(run_id=run['run_id'], regime=run['regime'], family=run['family'],
                                          latent=run['latent'], seed=run['seed'], scale_px=scale, sampler=sampler,
                                          sample_id=group['record']['sample_id'], kind=group['record']['kind'],
                                          pixel_spacing_xy=group['record']['pixel_spacing_xy'],
                                          partition=method, directory=str(folder.relative_to(output)),
                                          evaluation_input=evaluation_input,
                                          cache_group=group['group_id']))
                print(f"partition {run['run_id']} {sampler} s{scale}", flush=True)
    write_json(target/'index.json', index)
    return index


def freeze(output):
    if (output/'frozen-predictions.json').exists():
        raise FileExistsError('Predictions are already frozen')
    from .export_contract import finalize
    finalize(output)
    files = {}
    for directory in ('predictions', 'features', 'cache'):
        for path in sorted((output/directory).rglob('*')):
            if path.is_file():
                files[str(path.relative_to(output))] = file_hash(path)
    for path in (output/'training').rglob('*.json'):
        files[str(path.relative_to(output))] = file_hash(path)
    for run in model_runs(output/'training'):
        path = Path(run['directory'])/run['run_metadata']['selected_checkpoint']
        files[str(path.relative_to(output.resolve()))] = file_hash(path)
    configuration = output/'inference-configuration.json'
    files[str(configuration.relative_to(output))] = file_hash(configuration)
    contract_audit = output/'export-contract-audit.json'
    files[str(contract_audit.relative_to(output))] = file_hash(contract_audit)
    code = {str(p): file_hash(p) for name in ('predict.py', 'texture.py', 'partition.py', 'models.py', 'fit.py', 'data.py', 'export_contract.py')
            if (p := Path(__file__).with_name(name)).exists()}
    value = dict(schema='stmdomains-frozen-predictions-v1', evaluation_opened=False,
                 files=files, code_sha256=code,
                 policy='No manual reference or final control truth used in fitting or prediction')
    write_json(output/'frozen-predictions.json', value)
    print(f'frozen {len(files)} artifacts', flush=True)


def main():
    global _CPU_STARTED, _CPU_PREVIOUS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['cache', 'encode', 'partition', 'freeze'])
    parser.add_argument('--prepared', type=Path, default=Path('.scratch/training-20'))
    parser.add_argument('--output', type=Path, default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--device', default='cuda')
    args = parser.parse_args()
    deny_evaluation_paths()
    _CPU_STARTED = time.process_time()
    _CPU_PREVIOUS = sum(read_json(path)['cpu_seconds'] for path in args.output.glob('*-resources.json'))
    started, cpu = time.monotonic(), time.process_time()
    if args.stage == 'cache':
        cache_inputs(args.prepared, args.prepared/'controls', args.output)
    elif args.stage == 'encode':
        encode_models(args.output, args.device)
    elif args.stage == 'partition':
        partition_all(args.prepared, args.output)
    else:
        freeze(args.output)
    write_json(args.output/f'{args.stage}-resources.json', dict(wall_seconds=time.monotonic()-started,
               cpu_seconds=time.process_time()-cpu, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


if __name__ == '__main__':
    main()
