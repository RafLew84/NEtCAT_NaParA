"""Run the fixed twelve-fit matrix; never retry or replace a failed fit."""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import subprocess
import sys

from ...bundle import file_hash, write_json
from .common import read_json
from .prepare import verify_plan


def run(output, device):
    output = Path(output).resolve()
    plan = verify_plan(output)
    target = output/'training/registry.json'
    if (output/'training').exists():
        raise FileExistsError('Preserve previous fit attempts; no implicit suite restart')
    registry = dict(schema='stmdomains-masked-ae25-suite-v1', plan_sha256=file_hash(output/'plan.json'), runs=[], skipped=[])
    for regime in ('transfer', 'transductive'):
        for family in ('mask25', 'mask50'):
            steps = 2000
            if regime == 'transductive':
                prior = [r for r in registry['runs'] if r['regime']=='transfer' and r['family']==family]
                if len(prior)!=3 or any(r['status']!='completed' for r in prior):
                    registry['skipped'].append(dict(regime=regime, family=family, reason='Missing three successful transfers'))
                    write_json(target, registry)
                    continue
                steps = int(statistics.median(r['selected_step'] for r in prior))
            for seed in (20261101,20261102,20261103):
                directory = output/f'training/{regime}/{family}/z32/seed-{seed}'
                command = [sys.executable,'-m','stmdomains.experiments.training.masked_ae.fit','run',
                           '--data',plan['data_root'],'--output',str(output),'--regime',regime,
                           '--family',family,'--seed',str(seed),'--steps',str(steps),'--device',device]
                result = subprocess.run(command, check=False)
                if not (directory/'run.json').exists():
                    registry['worker_failure'] = dict(directory=str(directory), returncode=result.returncode)
                    write_json(target, registry)
                    raise RuntimeError('Fit worker did not record an outcome')
                data = read_json(directory/'run.json')
                registry['runs'].append({k:data[k] for k in ('run_id','family','regime','seed','status','completed_steps','selected_step','seconds','selected_checkpoint_sha256')} | dict(directory=str(directory), run_sha256=file_hash(directory/'run.json')))
                registry['total_fit_seconds'] = sum(r['seconds'] for r in registry['runs'])
                write_json(target, registry)
    registry['completed'] = sum(r['status']=='completed' for r in registry['runs'])
    write_json(target, registry)
    print({'completed':registry['completed'], 'total_fit_seconds':registry['total_fit_seconds']}, flush=True)
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', choices=('cpu','cuda'), default='cuda')
    args = parser.parse_args()
    run(args.output, args.device)


if __name__ == '__main__':
    main()
