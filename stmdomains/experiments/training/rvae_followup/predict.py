"""Isolated issue-21a inference; original models, gate and solvers stay frozen.

Only the primary grid48 comparison is run. Truth paths are denied until the
completed prediction tree has been hashed; baseline adapters are copied exactly.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import time

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from .. import predict as original
from ..data import STRIDE, extract_patch, synthetic_in_normalizer_units
from ..predict import (read_json, write_gzip, make_groups, model_runs, load_features,
                       label_numbers, relation_records, result_envelope)

NEW_FAMILIES = ('rvae_lowkl', 'rvae_fourier', 'rvae_fourier_lowkl')
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


def trial_runs(output: Path, baseline: Path) -> list[dict]:
    base = [dict(run, baseline=True) for run in model_runs(baseline/'training')
            if run['regime'] == 'transfer' and run['latent'] == 32 and run['family'] in ('ae', 'rvae')]
    if len(base) != 6:
        raise ValueError('Six completed original transfer z32 models required')
    for run in base:
        directory = Path(run['directory'])
        for filename in ('run.json', 'config.json', run['run_metadata']['selected_checkpoint']):
            baseline_source(baseline, (directory/filename).relative_to(baseline.resolve()))
    new = [dict(run, baseline=False) for run in model_runs(output/'training')]
    planned = {(family, seed) for family in NEW_FAMILIES for seed in SEEDS}
    if any(run['regime'] != 'transfer' or run['latent'] != 32 or (run['family'],run['seed']) not in planned for run in new):
        raise ValueError('Unexpected issue-21a fit')
    # Failed/stopped fits remain in training reports and are not silently replaced.
    attempted = list((output/'training').glob('transfer/*/z32/seed-*/run.json'))
    if len(attempted) != 9:
        raise ValueError('All nine planned fits must have an outcome before inference')
    return sorted(base+new, key=lambda run:run['run_id'])


def cache_inputs(prepared: Path, output: Path, baseline: Path):
    from ..texture import describe_patches, order_mask
    target = output/'cache'
    if target.exists():
        raise FileExistsError(target)
    if not (output/'plan.json').is_file():
        raise ValueError('Freeze issue-21a plan before prediction')
    manifest = read_json(prepared/'data/manifest.json')
    for name in ('windows', 'split', 'normalization'):
        if file_hash(prepared/'data'/manifest[name+'_file']) != manifest[name+'_sha256']:
            raise ValueError('Prepared data changed: '+name)
    target.mkdir(parents=True)
    thresholds_path = baseline_source(baseline, 'cache/order-thresholds.json')
    shutil.copyfile(thresholds_path, target/'order-thresholds.json')
    thresholds = read_json(target/'order-thresholds.json')
    controls = output/'controls'
    write_json(output/'inference-configuration.json', dict(
        schema='stmdomains-issue21a-inference-v1', plan_sha256=file_hash(output/'plan.json'),
        prepared_manifest_sha256=file_hash(prepared/'data/manifest.json'),
        controls_analysis_sha256=file_hash(controls/'analysis/manifest.json'),
        baseline_freeze_sha256=file_hash(baseline/'frozen-predictions.json'),
        order_calibration_sha256=file_hash(thresholds_path), scales=[48], main_scale=48,
        samplers=['grid'], regimes=['transfer'],
        graph_context=dict(full_fields='exploratory visualization',
                           transfer_measurement_metrics='eligible test nodes and edges only'),
        baseline_adapters='exact frozen bytes, no refitting',
        orientation='raw angle diagnostic only; unvalidated lattice angles stay null',
        catalogue='type_id null',
        checkpoint_selection='unlabelled validation; no reference-based model selection'))
    normalizer = read_json(prepared/'data/normalization.json')['transfer']
    groups = [group for group in make_groups(prepared, controls)
              if group['scale_px'] == 48 and group['sampler'] == 'grid']
    index=[]
    for n, group in enumerate(groups):
        check_postprocess_budget()
        record, rows = group['record'], group['rows']
        _, arrays = load_sample(Path(group['analysis']), record['sample_id'])
        path = target/group['group_id']
        write_gzip(path/'rows.json.gz', rows)
        available = np.array([i for i,row in enumerate(rows) if row['available']],dtype=np.int64)
        source = arrays if record['kind']=='measurement' else synthetic_in_normalizer_units(arrays, normalizer)
        native = np.stack([extract_patch(source,rows[i],normalizer,size=48) for i in available]) if len(available) else np.empty((0,48,48))
        patches = np.stack([extract_patch(source,rows[i],normalizer) for i in available]) if len(available) else np.empty((0,64,64),np.float32)
        description=describe_patches(native)
        threshold=thresholds['scales']['48']['threshold']
        cached=dict(available_indices=available,patches=patches,order_pass=np.zeros(len(rows),bool),
                    acf_score=np.full(len(rows),np.nan),fft=np.full((len(rows),216),np.nan))
        cached['order_pass'][available]=order_mask(description,threshold)
        cached['acf_score'][available]=description['acf_score']
        cached['fft'][available]=description['features']
        np.savez_compressed(path/'transfer.npz',**cached)
        index.append({k:v for k,v in group.items() if k!='rows'})
        if n%20==0: print(f'cache {n+1}/{len(groups)}',flush=True)
    write_json(target/'index.json',index)
    return index


def fit_new_adapter(output: Path, run: dict, groups: list[dict]) -> dict:
    from ..partition import neighbor_edges, fit_feature_adapter
    features, edges, ids=[],[],[]
    offset=0
    for group in groups:
        if group['record']['kind'] != 'measurement': continue
        rows=read_json(output/'cache'/group['group_id']/'rows.json.gz')
        take=[i for i,row in enumerate(rows) if row['available'] and row['transfer_split']=='train']
        if not take: continue
        feature=load_features(output,run,group)[take]
        group_ids=[rows[i]['window_id'] for i in take]
        xy=np.array([rows[i]['raw_edge_xy'] for i in take])
        edge=neighbor_edges(xy,group_ids,mode='grid',stride=STRIDE)
        features.append(feature);edges.extend((edge+offset).tolist());ids.extend(group_ids)
        offset+=len(take)
    if not features: raise ValueError('No eligible adapter training data')
    adapter=fit_feature_adapter(np.concatenate(features),np.array(edges,dtype=int).reshape(-1,2),ids,
         scope=dict(regime='transfer',scale_px=48,sampler='grid',feature_id=run['run_id']))
    adapter['fit_window_ids']=ids
    return adapter


def audit_baseline_predictions(output: Path, baseline: Path, index: list[dict]) -> dict:
    """Unchanged measurements must reproduce the frozen original baseline arrays."""
    comparisons = 0
    for item in index:
        check_postprocess_budget()
        if item['kind'] != 'measurement' or item['family'] not in ('ae', 'rvae', 'fft'):
            continue
        for name in ('metrics-input.npz', 'heldout-metrics-input.npz'):
            relative = Path(item['directory'])/name
            source = baseline_source(baseline, relative)
            with np.load(source, allow_pickle=False) as before, np.load(output/relative, allow_pickle=False) as after:
                if before.files != after.files or any(not np.array_equal(before[key], after[key], equal_nan=True)
                                                     for key in before.files):
                    raise ValueError('Baseline prediction changed on an unchanged measurement: '+str(relative))
            comparisons += 1
    report = dict(passed=True, compared_arrays=comparisons,
                  scope='AE/rVAE/FFT transferz32 grid48, full and heldout measurement graphs',
                  policy='Exact equality of all stored numerical arrays; fresh controls have no prior predictions')
    write_json(output/'baseline-reuse-audit.json', report)
    return report

def encode_models(output, baseline, device='cuda'):
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
    for run in trial_runs(output, baseline):
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
            if run['family'].startswith('rvae'):
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


def partition_all(prepared, output, baseline):
    from ..partition import neighbor_edges, partition_graph
    target = output/'predictions'
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    groups = read_json(output/'cache/index.json')
    thresholds = read_json(output/'cache/order-thresholds.json')
    runs = read_json(output/'features/index.json')
    runs += [dict(run_id='transfer/fft', regime='transfer', family='fft', latent=None, seed=None,
                  baseline=True)]
    hashes = dict(plan_sha256=file_hash(output/'plan.json'),
                  split_sha256=file_hash(prepared/'data/split.json'))
    index = []
    for run in runs:
        for scale in (48,):
            for sampler in ('grid',):
                selected = [g for g in groups if g['scale_px'] == scale and g['sampler'] == sampler]
                adapter_path = target/run['run_id']/sampler/f's{scale}'/'adapter.json'
                if run.get('baseline', False):
                    source = baseline_source(baseline, Path('predictions')/run['run_id']/sampler/f's{scale}'/'adapter.json')
                    adapter_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, adapter_path)
                    adapter = read_json(adapter_path)
                    expected = dict(regime='transfer', scale_px=48, sampler='grid', feature_id=run['run_id'])
                    if adapter['scope'] != expected:
                        raise ValueError('Baseline adapter scope mismatch')
                else:
                    adapter = fit_new_adapter(output, run, selected)
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


def checkpoint_evidence(directory: Path, metadata: dict) -> list[Path]:
    """Authenticate selected and fixed-step checkpoints before freezing reports."""
    directory = directory.resolve()
    wanted = {entry['file']: entry['sha256'] for entry in metadata.get('checkpoints', [])
              if entry['step'] == 2000}
    selected = metadata.get('selected_checkpoint')
    if selected:
        wanted[selected] = metadata['selected_checkpoint_sha256']
    paths = []
    for name, expected in sorted(wanted.items()):
        path = (directory/name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(directory):
            raise ValueError('Checkpoint evidence escapes its run directory')
        if file_hash(path) != expected:
            raise ValueError('Selected/fixed-step checkpoint evidence changed: '+str(path))
        paths.append(path)
    return paths


def freeze(output: Path, baseline: Path):
    from ..export_contract import finalize
    if (output/'frozen-predictions.json').exists():
        raise FileExistsError('Predictions already frozen')
    finalize(output)
    baseline_source(baseline, 'cache/order-thresholds.json')
    if file_hash(baseline/'frozen-predictions.json') != _BASELINE_FREEZES[str(baseline.resolve())][0]:
        raise ValueError('Original baseline manifest changed during prediction')
    files={}
    for directory in ('predictions','features','cache','training','diagnostic','controls/analysis'):
        for path in sorted((output/directory).rglob('*')):
            if path.is_file() and path.suffix!='.pt':
                files[str(path.relative_to(output))]=file_hash(path)
    external={}
    def include(path):
        path = Path(path).resolve()
        if path.is_relative_to(output.resolve()):
            files[str(path.relative_to(output.resolve()))] = file_hash(path)
        else:
            external[str(path)] = file_hash(path)
    for run in trial_runs(output,baseline):
        directory=Path(run['directory'])
        for filename in ('run.json','config.json'):
            include(directory/filename)
        for path in checkpoint_evidence(directory, run['run_metadata']):
            include(path)
    for path in sorted((output/'diagnostic').glob('*/run.json')):
        for checkpoint in checkpoint_evidence(path.parent, read_json(path)):
            include(checkpoint)
    for group in read_json(output/'cache/index.json'):
        analysis=Path(group['analysis'])
        # Freeze exact source array plus its manifest; input references stay external.
        record=group['record']
        for name in ('manifest.json',record['file']):
            path=analysis/name
            if path.is_relative_to(output.resolve()):
                files[str(path.relative_to(output.resolve()))]=file_hash(path)
            else: external[str(path)]=file_hash(path)
    for name in ('plan.json','protocol.json','inference-configuration.json','export-contract-audit.json',
                 'baseline-reuse-audit.json','baseline-audit.json','diagnostic-inputs.npz',
                 'training/training-audit.json'):
        files[name]=file_hash(output/name)
    external[str((baseline/'frozen-predictions.json').resolve())]=file_hash(baseline/'frozen-predictions.json')
    code={}
    source_dir = Path(__file__).parent
    for path in source_dir.glob('*.py'):
        code[str(path.resolve())] = file_hash(path)
    for module_dir,names in ((source_dir.parent,('predict.py','texture.py','partition.py','models.py',
                             'fit.py','data.py','checkpoint.py','evaluate.py','export_contract.py',
                             'diagnostics.py','gallery.py','controls.py')),
                            (source_dir.parent.parent,('bundle.py','results.py','controls.py'))):
        for name in names:
            path=module_dir/name
            code[str(path.resolve())]=file_hash(path)
    value=dict(schema='stmdomains-frozen-predictions-v1',evaluation_opened=False,files=files,
               external_files=external,code_sha256=code,
               policy='No manual reference or fresh synthetic truth in fitting or prediction; grid48 transfer only')
    write_json(output/'frozen-predictions.json',value)
    print(f'frozen {len(files)} local and {len(external)} external artifacts',flush=True)
    return value


def main():
    global _BUDGET
    from .evaluate import PostprocessBudget
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['cache','encode','partition','freeze'])
    parser.add_argument('--prepared',type=Path,default=Path('.scratch/training-20'))
    parser.add_argument('--output',type=Path,default=Path('.scratch/rvae-21a'))
    parser.add_argument('--baseline',type=Path,default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--device',default='cuda')
    args=parser.parse_args()
    args.output=args.output.resolve();args.baseline=args.baseline.resolve();args.prepared=args.prepared.resolve()
    original.deny_evaluation_paths()
    resource_path=args.output/f'{args.stage}.resources.json'
    if resource_path.exists(): raise FileExistsError(resource_path)
    _BUDGET=PostprocessBudget(args.output)
    status='failed'
    try:
        _BUDGET.check()
        if args.stage=='cache': cache_inputs(args.prepared,args.output,args.baseline)
        elif args.stage=='encode': encode_models(args.output,args.baseline,args.device)
        elif args.stage=='partition': partition_all(args.prepared,args.output,args.baseline)
        else: freeze(args.output,args.baseline)
        _BUDGET.check();status='completed'
    finally:
        write_json(resource_path,dict(status=status,**_BUDGET.measurements()))


if __name__=='__main__': main()
