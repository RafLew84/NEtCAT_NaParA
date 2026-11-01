"""Bounded input-intervention prototype 24a; no training or calibration fits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import time

import numpy as np
import torch

from ...bundle import file_hash, write_arrays, write_json
from ..graph_ssl.data import iter_prepared
from ..graph_ssl.fit import deny_evaluation_paths, load_encoder
from ..graph_ssl.predict import runs as old_runs, partition_features, export
from .representation import MODES, build_inputs, dependency_audit


CPU_CAP = 1800.
RSS_CAP = 4 * 1024**3
SEEDS = (20261101, 20261102, 20261103)


def read(path):
    return json.loads(Path(path).read_text())


def arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def budget(root, started):
    used = sum(read(p)['cpu_seconds'] for p in root.glob('*.resources.json'))
    if used + time.process_time() - started > CPU_CAP:
        raise RuntimeError('24a CPU budget exceeded')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > RSS_CAP:
        raise MemoryError('24a RSS budget exceeded')


def verify_plan(root):
    plan = read(root / 'plan.json')
    for field in ('code_sha256', 'source_files'):
        for name, expected in plan[field].items():
            if file_hash(Path(name)) != expected:
                raise ValueError('Changed pinned source: ' + name)
    if file_hash(Path(plan['protocol'])) != plan['protocol_sha256']:
        raise ValueError('Changed predeclared protocol')
    return plan


def plan(root, source):
    if (root / 'plan.json').exists() or (root / 'predictions').exists():
        raise FileExistsError('Plan must precede the intervention')
    frozen = read(source / 'frozen-predictions.json')
    source_files = {str(source / name): digest for name, digest in frozen['files'].items()}
    source_files.update(frozen['external_files'])
    source_files[str(source / 'frozen-predictions.json')] = file_hash(source / 'frozen-predictions.json')
    for name, digest in source_files.items():
        if file_hash(Path(name)) != digest:
            raise ValueError('Changed issue24 artifact: ' + name)
    base_runs = [r for r in old_runs(source) if r['regime'] == 'transfer' and
                 r['family'] in ('geometry', 'graph_sce_scale', 'graph_untrained')]
    variants = []
    for base in base_runs:
        for mode in ('root57',) if base['family'] == 'geometry' else MODES:
            variants.append(dict(base, base_variant_id=base['variant_id'], mode=mode,
                                 variant_id=mode + '--' + base['variant_id']))
    assert len(variants) == 19
    own = Path(__file__).parent
    code = {str(p): file_hash(p) for p in (own / name for name in
            ('__init__.py', 'representation.py', 'trial.py', 'evaluation.py', 'audit.py'))}
    protocol = Path('docs/stmdomains/graph-context-boundary-protocol.md')
    result = dict(schema='stmdomains-graph24a-plan-v1', source_root=str(source),
                  frozen_at_utc=datetime.now(timezone.utc).isoformat(), parent_commit='32525dc',
                  protocol=str(protocol), protocol_sha256=file_hash(protocol),
                  code_sha256=code, source_files=source_files,
                  initial_source_freeze_sha256=file_hash(source / 'frozen-predictions.json'),
                  variants=variants, expected_predictions=3534, expected_controls=93,
                  expected_available_roots=8350, expected_single_roots=121,
                  optimizer_steps=0, calibration_fits=0, cpu_cap_seconds=CPU_CAP,
                  process_rss_cap_bytes=RSS_CAP, device='cpu',
                  adapter_policy='Fixed original24 per representation, no refit',
                  root_scope='All original S24 roots; dependency certificate never filters output',
                  controls_policy='Known issue24 controls; diagnostic, not held-out',
                  primary_mode='halfopen72', ablation_mode='root_only')
    write_json(root / 'plan.json', result)
    return dict(variants=len(variants), predictions=3534, plan_sha256=file_hash(root / 'plan.json'))


def disable_optimizer_steps():
    def forbidden(*args, **kwargs):
        raise RuntimeError('Optimizer steps forbidden in diagnostic24a')
    for kind in (torch.optim.Adam, torch.optim.AdamW, torch.optim.SGD):
        kind.step = forbidden


@torch.inference_mode()
def encode(model, inputs, eligible):
    result = np.full((len(eligible), 32), np.nan, dtype=np.float32)
    chosen = np.flatnonzero(eligible)
    for begin in range(0, len(chosen), 64):
        indices = chosen[begin:begin + 64]
        width = int(inputs['valid'][indices].sum(axis=1).max())
        x = torch.from_numpy(inputs['x'][indices, :width])
        adj = torch.from_numpy(inputs['adj'][indices, :width, :width])
        valid = torch.from_numpy(inputs['valid'][indices, :width])
        result[indices] = model.encode(x, adj, valid)[:, 0].numpy()
    return result


def predict(root):
    started = time.process_time()
    config = verify_plan(root)
    source = Path(config['source_root'])
    if (root / 'predictions').exists() or (root / 'prepared').exists():
        raise FileExistsError('Prediction attempt already exists; no implicit replay')
    disable_optimizer_steps()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    variants = config['variants']
    models, adapters = {}, {}
    for run in variants:
        base = run['base_variant_id']
        if run['family'] != 'geometry' and base not in models:
            model = load_encoder(Path(run['checkpoint']), 'cpu')[0]
            model.requires_grad_(False)
            models[base] = model
        adapter_path = source / 'adapters' / (base + '.json')
        adapters[base] = read(adapter_path)
        target = root / 'adapters' / (run['variant_id'] + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(adapter_path, target)
    source_entries = {(r['variant_id'], r['partition'], r['sample_id']): r
                      for r in read(source / 'predictions/index.json')}
    source_manifest = read(source / 'prepared/manifest.json')
    selected_samples = [s for s in source_manifest['samples'] if s['kind'] == 'synthetic']
    for sample_row in selected_samples:
        for field in ('rows_file', 'cache_file'):
            destination = root / 'prepared' / sample_row[field]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / 'prepared' / sample_row[field], destination)
    write_json(root / 'prepared/manifest.json', dict(source_manifest, samples=selected_samples,
               total_samples=93, counts={'synthetic/anchors': 19629, 'synthetic/eligible': 8350}))
    entries, dependency_counts = [], []
    for sample in iter_prepared(source, kind='synthetic'):
        budget(root, started)
        sid = sample['sample_id']
        inputs_by_mode = {}
        for mode in MODES:
            inputs = build_inputs(sample, mode)
            inputs_by_mode[mode] = inputs
            write_arrays(root / 'representations' / mode / (sid + '.npz'), inputs)
            dep = dependency_audit(sample, inputs)
            write_arrays(root / 'dependency' / mode / (sid + '.npz'), dep)
            dependency_counts.append(dict(sample_id=sid, mode=mode,
                available_roots=int(sample['eligible'].sum()),
                complete_receptive_context=int(dep['complete_inside_ego72'].sum()),
                root_context_nodes=inputs['valid'].sum(axis=1).tolist()))
        geom_path = source / 'geometry' / (sid + '.npz')
        target = root / 'geometry' / geom_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(geom_path, target)
        geom = arrays(geom_path)
        for run in variants:
            base, mode, variant = run['base_variant_id'], run['mode'], run['variant_id']
            source_feature = source / 'features' / base / (sid + '.npz')
            target = root / 'features' / variant / (sid + '.npz')
            target.parent.mkdir(parents=True, exist_ok=True)
            if mode in ('closed72', 'root57'):
                shutil.copy2(source_feature, target)
                feature = arrays(source_feature)['features']
            else:
                feature = encode(models[base], inputs_by_mode[mode], sample['eligible'])
                write_arrays(target, dict(features=feature))
            for method in ('fh4', 'mws'):
                metadata = {key: value for key, value in run.items() if key != 'checkpoint'}
                metadata.update(sample_id=sid, kind='synthetic', partition=method,
                                scale_px=72, sampler='centers', feature_id=variant)
                old = source_entries[base, method, sid]
                if mode in ('closed72', 'root57'):
                    pred = arrays(source / old['file'])
                else:
                    pred = partition_features(sample, feature, adapters[base], geom, method,
                                              np.ones(len(sample['ids']), dtype=bool))
                filename = f'predictions/{variant}/{method}/{sid}.npz'
                export(root, sample, metadata, pred, filename)
                if mode in ('closed72', 'root57'):
                    shutil.copy2(source / old['file'], root / filename)
                entries.append(dict(metadata, file=filename))
        print('saved', sid, flush=True)
    assert len(entries) == 3534
    write_json(root / 'predictions/index.json', entries)
    write_json(root / 'dependency/summary.json', dependency_counts)
    write_json(root / 'execution.json', dict(optimizer_steps=0, calibration_fits=0,
        optimizer_steps_forbidden=True, inference_mode=True, weights_require_grad=False,
        controls=93, prediction_entries=len(entries), device='cpu', reference_access=False))


def freeze(root):
    config = verify_plan(root)
    if (root / 'frozen-predictions.json').exists():
        raise FileExistsError('Predictions already frozen')
    if len(read(root / 'predictions/index.json')) != 3534:
        raise ValueError('Incomplete predictions')
    files = {str(p.relative_to(root)): file_hash(p) for p in sorted(root.rglob('*'))
             if p.is_file() and 'evaluation' not in p.relative_to(root).parts}
    external = dict(config['source_files'])
    external.update({str(Path(name).resolve()): digest for name, digest in config['code_sha256'].items()})
    write_json(root / 'frozen-predictions.json', dict(schema='stmdomains-frozen-predictions-v1',
        evaluation_opened=False, files=files, external_files=external,
        code_sha256=config['code_sha256'], prediction_count=3534,
        plan_sha256=file_hash(root / 'plan.json')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('plan', 'predict', 'freeze'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('.scratch/graph-ssl-24'))
    args = parser.parse_args()
    root, source = args.output.resolve(), args.source.resolve()
    if root == source:
        raise ValueError('Intervention must use a separate output directory')
    root.mkdir(parents=True, exist_ok=True)
    deny_evaluation_paths()
    resource_path = root / (args.stage + '.resources.json')
    if resource_path.exists():
        raise FileExistsError('Stage already attempted')
    started, wall = time.process_time(), time.perf_counter()
    status = 'failed'
    try:
        budget(root, started)
        result = plan(root, source) if args.stage == 'plan' else {'predict': predict, 'freeze': freeze}[args.stage](root)
        budget(root, started)
        status = 'completed'
        if result is not None:
            print(json.dumps(result))
    finally:
        write_json(resource_path, dict(status=status, cpu_seconds=time.process_time() - started,
            wall_seconds=time.perf_counter() - wall,
            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024))


if __name__ == '__main__':
    main()
