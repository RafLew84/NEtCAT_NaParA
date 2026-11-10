"""Frozen issue22 local-map inference; reused FFT/cache, unchanged gate and solvers.

All three scales and both samplers use the same prepared inputs as issue21.
The six random controls load saved step-zero states; they perform no training.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import time

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from .. import predict as original
from ..data import SCALES, STRIDE
from ..predict import (read_json, write_gzip, model_runs, load_features,
                       label_numbers, relation_records, result_envelope)

SEEDS = (20261101, 20261102, 20261103)
_BUDGET = None
_BASELINE_FREEZES = {}


def check_postprocess_budget():
    if _BUDGET is not None:
        _BUDGET.check()


def baseline_source(baseline: Path, relative: str | Path) -> Path:
    """Read only a baseline artifact whose original freeze contains its hash."""
    baseline = baseline.resolve()
    relative = Path(relative)
    source = (baseline/relative).resolve()
    if relative.is_absolute() or not source.is_relative_to(baseline):
        raise ValueError('Baseline artifact escapes its root')
    if str(baseline) not in _BASELINE_FREEZES:
        manifest = baseline/'frozen-predictions.json'
        _BASELINE_FREEZES[str(baseline)] = (file_hash(manifest), read_json(manifest))
    _, freeze = _BASELINE_FREEZES[str(baseline)]
    expected = freeze['files'].get(str(relative))
    if expected is None or file_hash(source) != expected:
        raise ValueError('Missing or changed baseline artifact: '+str(relative))
    return source


def trial_runs(output: Path, baseline: Path | None = None) -> list[dict]:
    """Completed trained runs plus their preserved z32 initialization controls."""
    trained = model_runs(output/'training')
    planned = {(regime, latent, seed) for regime in ('transfer', 'transductive')
               for latent in ((16, 32) if regime == 'transfer' else (32,)) for seed in SEEDS}
    attempted = list((output/'training').glob('*/*/z*/seed-*/run.json'))
    for run in trained:
        key = (run['regime'], run['latent'], run['seed'])
        if run['family'] != 'local_ssl' or key not in planned:
            raise ValueError('Unexpected issue22 fit')
    # A skipped transductive refit is recorded by the trainer, not replaced.
    transfer = [p for p in attempted if p.relative_to(output/'training').parts[0] == 'transfer']
    if len(transfer) != 6:
        raise ValueError('All six planned transfer fits need a recorded outcome')
    untrained = []
    for run in trained:
        if run['latent'] != 32:
            continue
        metadata = dict(run['run_metadata'])
        initial = metadata.get('initial_checkpoint')
        expected = metadata.get('initial_checkpoint_sha256')
        if not initial or not expected or file_hash(Path(run['directory'])/initial) != expected:
            raise ValueError('Saved initialization is absent or changed')
        metadata.update(selected_checkpoint=initial, selected_checkpoint_sha256=expected,
                        selected_step=0, control='same encoder before any optimization')
        untrained.append(dict(run, run_id=run['run_id'].replace('/local_ssl/', '/local_ssl_untrained/'),
                              family='local_ssl_untrained', initial=True, run_metadata=metadata))
    return sorted([dict(run, initial=False) for run in trained]+untrained, key=lambda r:r['run_id'])


def cache_inputs(prepared: Path, output: Path, baseline: Path):
    """Reuse authenticated original inputs exactly; never recalibrate the gate."""
    if (output/'cache').exists():
        raise FileExistsError(output/'cache')
    from .fit import verified_plan
    verified_plan(prepared, baseline, output)
    manifest = read_json(prepared/'data/manifest.json')
    old_config = read_json(baseline_source(baseline, 'inference-configuration.json'))
    if old_config['prepared_manifest_sha256'] != file_hash(prepared/'data/manifest.json'):
        raise ValueError('The prepared data differ from the original cache identity')
    for name in ('windows', 'split', 'normalization'):
        if file_hash(prepared/'data'/manifest[name+'_file']) != manifest[name+'_sha256']:
            raise ValueError('Prepared data changed: '+name)
    groups = read_json(baseline_source(baseline, 'cache/index.json'))
    expected_controls = (prepared/'controls/analysis').resolve()
    expected_measurements = (prepared/'data/analysis').resolve()
    for group in groups:
        wanted = expected_measurements if group['record']['kind'] == 'measurement' else expected_controls
        if Path(group['analysis']).resolve() != wanted:
            raise ValueError('Cached source differs from the original prepared input')
        record = group['record']
        loaded, _ = load_sample(wanted, record['sample_id'])
        if loaded != record:
            raise ValueError('Cached source content or metadata changed')
    cache_files = sorted(k for k in _BASELINE_FREEZES[str(baseline.resolve())][1]['files']
                         if k.startswith('cache/'))
    for relative in cache_files:
        check_postprocess_budget()
        source = baseline_source(baseline, relative)
        target = output/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    write_json(output/'inference-configuration.json', dict(
        schema='stmdomains-issue22-inference-v1', plan_sha256=file_hash(output/'plan.json'),
        prepared_manifest_sha256=file_hash(prepared/'data/manifest.json'),
        controls_analysis_sha256=file_hash(expected_controls/'manifest.json'),
        baseline_freeze_sha256=file_hash(baseline/'frozen-predictions.json'),
        cache_reused_files=len(cache_files), scales=list(SCALES), main_scale=48,
        samplers=['grid', 'centers'], regimes=['transfer', 'transductive'],
        descriptor='flatten z by 7 by 7 local map in fixed spatial order; no pooling',
        graph_context=dict(full_fields='visualization and transductive inference',
                           transfer_measurement_metrics='eligible test nodes and edges only'),
        baseline_adapters='exact frozen FFT bytes; no refitting or gate recalibration',
        orientation='not separately measured by SSL; ACF order evidence is external geometry',
        catalogue='type_id null',
        controls_scope='original81 realizations already seen in21; development assessment',
        checkpoint_selection='unlabelled validation; no domain-reference selection'))
    return groups


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
    for run in trial_runs(output):
        run_target = target/run['run_id']
        if (run_target/'complete.json').exists():
            completed.append(read_json(run_target/'complete.json'))
            continue
        model = load_model(Path(run['directory']), device=device, initial=run['initial'])
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
            content = np.full((len(rows), run['latent']*49), np.nan, np.float32)
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
            if device == 'cuda' and torch.cuda.max_memory_allocated() > 8*1024**3:
                raise RuntimeError('Frozen8GiB GPU tensor budget exceeded')
            full = content
            path = run_target/group['group_id']
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path.with_suffix('.npz'), features=full,
                                angle_radians=angle, reconstruction_mse=reconstruction_mse)
        if device == 'cuda':
            torch.cuda.synchronize()
        summary = dict(run, inference_seconds=time.monotonic()-started,
                       peak_gpu_bytes=int(torch.cuda.max_memory_allocated()) if device == 'cuda' else 0,
                       descriptor_dimension=run['latent']*49, local_map_shape=[run['latent'],7,7],
                       feature_archive_layout='features stores flattened content once; no duplicate content array',
                       reconstruction_mse_reason='no decoder in local SSL',
                       angle_reason='no separate lattice angle estimator')
        write_json(run_target/'complete.json', summary)
        completed.append(summary)
        print(f"encoded {run['run_id']} {summary['inference_seconds']:.1f}s", flush=True)
        del model
    write_json(target/'index.json', completed)
    return completed


def fit_new_adapter(output: Path, run: dict, groups: list[dict], scale: int, sampler: str) -> dict:
    from ..partition import neighbor_edges, fit_feature_adapter
    features, edges, ids = [], [], []
    offset = 0
    for group in groups:
        check_postprocess_budget()
        if group['record']['kind'] != 'measurement':
            continue
        rows = read_json(output/'cache'/group['group_id']/'rows.json.gz')
        take = [i for i,row in enumerate(rows) if row['available'] and
                (run['regime'] == 'transductive' or row['transfer_split'] == 'train')]
        if not take:
            continue
        feature = load_features(output, run, group)[take]
        group_ids = [rows[i]['window_id'] for i in take]
        xy = np.array([rows[i]['raw_edge_xy'] for i in take])
        edge = neighbor_edges(xy, group_ids, mode=sampler, stride=STRIDE)
        features.append(feature)
        edges.extend((edge+offset).tolist())
        ids.extend(group_ids)
        offset += len(take)
    if not features:
        raise ValueError('No eligible adapter training data')
    adapter = fit_feature_adapter(np.concatenate(features), np.array(edges,dtype=int).reshape(-1,2), ids,
        scope=dict(regime=run['regime'], scale_px=scale, sampler=sampler, feature_id=run['run_id']))
    adapter['fit_window_ids'] = ids
    return adapter


def audit_baseline_predictions(output: Path, baseline: Path, index: list[dict]) -> dict:
    """Every FFT output, including controls/centers/scales, preserves original numbers."""
    comparisons = 0
    for item in index:
        if item['family'] != 'fft':
            continue
        check_postprocess_budget()
        names = ['metrics-input.npz']
        if item['regime'] == 'transfer' and item['kind'] == 'measurement':
            names.append('heldout-metrics-input.npz')
        for name in names:
            relative = Path(item['directory'])/name
            source = baseline_source(baseline, relative)
            with np.load(source, allow_pickle=False) as old, np.load(output/relative, allow_pickle=False) as new:
                if old.files != new.files or any(not np.array_equal(old[k],new[k],equal_nan=True) for k in old.files):
                    raise ValueError('Frozen FFT result changed: '+str(relative))
            comparisons += 1
    result = dict(schema='stmdomains-issue22-baseline-reuse-v1', passed=True,
                  compared_prediction_archives=comparisons,
                  scope='both regimes, three scales, grid/centers, all measurements and original controls')
    write_json(output/'baseline-reuse-audit.json',result)
    return result


def partition_all(prepared, output, baseline):
    from ..partition import neighbor_edges, partition_graph
    target = output/'predictions'
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    groups = read_json(output/'cache/index.json')
    thresholds = read_json(output/'cache/order-thresholds.json')
    runs = read_json(output/'features/index.json')
    runs += [dict(run_id=regime+'/fft', regime=regime, family='fft', latent=None, seed=None)
             for regime in ('transfer', 'transductive')]
    plan = output/'plan.json'
    hashes = dict(plan_sha256=file_hash(plan), split_sha256=file_hash(prepared/'data/split.json'))
    index = []
    for run in runs:
        for scale in SCALES:
            for sampler in ('grid', 'centers'):
                selected = [g for g in groups if g['scale_px'] == scale and g['sampler'] == sampler]
                adapter_path = target/run['run_id']/sampler/f's{scale}'/'adapter.json'
                if run['family'] == 'fft':
                    source = baseline_source(baseline, adapter_path.relative_to(output))
                    adapter_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, adapter_path)
                    adapter = read_json(adapter_path)
                    expected = dict(regime=run['regime'], scale_px=scale,
                                    sampler=sampler, feature_id=run['run_id'])
                    if adapter['scope'] != expected:
                        raise ValueError('Baseline adapter scope mismatch')
                else:
                    adapter = fit_new_adapter(output, run, selected, scale, sampler)
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
    audit_baseline_predictions(output, baseline, index)
    return index


def freeze(output: Path, baseline: Path):
    from ..export_contract import finalize
    if (output/'frozen-predictions.json').exists():
        raise FileExistsError('Predictions already frozen')
    finalize(output)
    files, external = {}, {}
    def include(path):
        path = Path(path).resolve()
        target = files if path.is_relative_to(output.resolve()) else external
        key = str(path.relative_to(output.resolve())) if target is files else str(path)
        target[key] = file_hash(path)
    for directory in ('predictions','features','cache','training'):
        for path in sorted((output/directory).rglob('*')):
            check_postprocess_budget()
            if path.is_file():
                include(path)
    for group in read_json(output/'cache/index.json'):
        analysis = Path(group['analysis'])
        for name in ('manifest.json',group['record']['file']):
            include(analysis/name)
    for name in ('plan.json','inference-configuration.json','export-contract-audit.json',
                 'baseline-reuse-audit.json','baseline-audit.json','prior-budget.json'):
        include(output/name)
    include(baseline/'frozen-predictions.json')
    for entry in read_json(output/'prior-budget.json')['postprocessing_reports']:
        include(entry['path'])
    code = {}
    source_dir = Path(__file__).parent
    for path in source_dir.glob('*.py'):
        code[str(path.resolve())] = file_hash(path)
    for module_dir,names in ((source_dir.parent,('predict.py','texture.py','partition.py','models.py',
                            'fit.py','data.py','checkpoint.py','evaluate.py','export_contract.py',
                            'diagnostics.py','gallery.py','controls.py','experiment-plan.json')),
                            (source_dir.parent.parent,('bundle.py','results.py','controls.py'))):
        for name in names:
            path = module_dir/name
            code[str(path.resolve())] = file_hash(path)
    value = dict(schema='stmdomains-frozen-predictions-v1', evaluation_opened=False, files=files,
                 external_files=external, code_sha256=code,
                 policy='No manual reference or synthetic truth in fitting/prediction; original controls are development evidence')
    write_json(output/'frozen-predictions.json',value)
    print(f'frozen {len(files)} local and {len(external)} external artifacts',flush=True)
    return value


def main():
    global _BUDGET
    from .evaluate import PostprocessBudget
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['cache','encode','partition','freeze'])
    parser.add_argument('--prepared',type=Path,default=Path('.scratch/training-20'))
    parser.add_argument('--output',type=Path,default=Path('.scratch/local-ssl-22'))
    parser.add_argument('--baseline',type=Path,default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--device',default='cuda')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.baseline = args.baseline.resolve()
    args.prepared = args.prepared.resolve()
    original.deny_evaluation_paths()
    resource_path = args.output/f'{args.stage}.resources.json'
    if resource_path.exists():
        raise FileExistsError(resource_path)
    _BUDGET = PostprocessBudget(args.output, baseline=args.baseline)
    original.check_postprocess_budget = check_postprocess_budget
    status = 'failed'
    try:
        _BUDGET.check()
        if args.stage == 'cache':
            cache_inputs(args.prepared,args.output,args.baseline)
        elif args.stage == 'encode':
            encode_models(args.output,args.device)
        elif args.stage == 'partition':
            partition_all(args.prepared,args.output,args.baseline)
        else:
            freeze(args.output,args.baseline)
        _BUDGET.check()
        status = 'completed'
    finally:
        write_json(resource_path,dict(status=status,**_BUDGET.measurements()))


if __name__ == '__main__':
    main()
