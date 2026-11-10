"""Audit the frozen baseline and reserve new issue21a controls without inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import time

from ...bundle import file_hash, write_json
from .. import controls

PROTOCOL = Path(__file__).with_name('protocol.json')


def prior_cpu(output: Path) -> float:
    return sum(float(json.loads(p.read_text()).get('cpu_seconds', 0.))
               for p in output.glob('*.resources.json'))


def record_resources(output: Path, name: str, started: float, cpu: float) -> None:
    measured = dict(cpu_seconds=time.process_time()-cpu,
                    wall_seconds=time.perf_counter()-started,
                    max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    measured['previous_cpu_seconds'] = prior_cpu(output)
    write_json(output/f'{name}.resources.json', measured)
    if measured['previous_cpu_seconds']+measured['cpu_seconds'] > 7200:
        raise RuntimeError('Issue21a two-hour CPU budget exceeded')
    if measured['max_rss_bytes'] > 12*1024**3:
        raise RuntimeError('Issue21a 12GiB RSS budget exceeded')


def audit_baseline(baseline: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    if (output/'baseline-audit.json').exists():
        raise FileExistsError('Baseline audit already exists')
    started, cpu = time.perf_counter(), time.process_time()
    frozen_path = baseline/'frozen-predictions.json'
    frozen = json.loads(frozen_path.read_text())
    for index, (relative, expected) in enumerate(frozen['files'].items(), 1):
        path = (baseline/relative).resolve()
        if not path.is_relative_to(baseline.resolve()) or file_hash(path) != expected:
            raise ValueError(f'Frozen issue21 artifact changed: {relative}')
        if index % 20000 == 0:
            print(f'checked baseline {index}/{len(frozen["files"])}', flush=True)
            if prior_cpu(output)+time.process_time()-cpu > 7200:
                raise RuntimeError('Issue21a CPU budget exceeded during baseline audit')
    # Old frozen code keys are names relative to training/.
    for relative, expected in frozen.get('code_sha256', {}).items():
        path = Path(__file__).parent.parent/relative
        if file_hash(path) != expected:
            raise ValueError(f'Frozen issue21 source changed: {relative}')
    audit = dict(schema='stmdomains-rvae21a-baseline-audit-v1',
                 baseline=str(baseline.resolve()), checked_artifacts=len(frozen['files']),
                 frozen_manifest_sha256=file_hash(frozen_path),
                 code_sha256=frozen.get('code_sha256', {}), all_matched=True)
    write_json(output/'baseline-audit.json', audit)
    record_resources(output, 'baseline-audit', started, cpu)
    return audit


def reserve_controls(prepared: Path, output: Path) -> dict:
    started, cpu = time.perf_counter(), time.process_time()
    plan = json.loads((output/'plan.json').read_text())
    protocol_path = output/'protocol.json'
    if file_hash(PROTOCOL) != file_hash(protocol_path) or plan['protocol_sha256'] != file_hash(PROTOCOL):
        raise ValueError('Protocol changed after plan freeze')
    protocol = json.loads(protocol_path.read_text())
    seeds = tuple(protocol['control_seeds'])
    old_audit_path = prepared/'controls/audit.json'
    old_audit = json.loads(old_audit_path.read_text())
    if set(seeds) & set(old_audit['seeds']) or len(set(seeds)) != 3:
        raise ValueError('Controls must have three new distinct seeds')
    previous = controls.FINAL_SEEDS
    try:
        controls.FINAL_SEEDS = seeds
        result = controls.prepare(output/'controls')
    finally:
        controls.FINAL_SEEDS = previous
    # Generation owns truth; no image analysis or fitting is performed here.
    manifest_path = output/'controls/evaluation/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.update(role='Reserved fresh issue21a realizations; exclude from training and selection',
                    development='Known issue14-21 cases and realizations',
                    novelty='New noise and random phases; same families, not new STM acquisitions')
    write_json(manifest_path, manifest)
    result.update(schema='stmdomains-rvae21a-controls-v1',
                  evaluation_manifest_sha256=file_hash(manifest_path),
                  protocol_sha256=file_hash(protocol_path), plan_sha256=file_hash(output/'plan.json'),
                  previous_controls_audit_sha256=file_hash(old_audit_path),
                  wrapper_sha256=file_hash(Path(__file__)))
    write_json(output/'controls/audit.json', result)
    record_resources(output, 'controls', started, cpu)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('audit-baseline', 'plan', 'controls', 'audit-training'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--prepared', type=Path, default=Path('.scratch/training-20'))
    args = parser.parse_args()
    if args.stage == 'audit-baseline':
        result = audit_baseline(args.baseline, args.output)
    elif args.stage == 'controls':
        result = reserve_controls(args.prepared, args.output)
    else:
        from . import fit
        started, cpu = time.perf_counter(), time.process_time()
        try:
            operation = fit.prepare_plan if args.stage == 'plan' else fit.audit
            value = operation(args.prepared, args.baseline, args.output)
            result = {'stage': args.stage, 'completed': True,
                      'run_count': len(value.get('runs', []))}
        finally:
            record_resources(args.output, args.stage, started, cpu)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
