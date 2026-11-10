"""Audit immutable issue21 artifacts and the shared original21/22 resource budget."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...bundle import file_hash, write_json
from ..predict import read_json
from .evaluate import PostprocessBudget


def prior_budget(baseline: Path) -> dict:
    reports = []
    for path in sorted(baseline.glob('*-resources.json')):
        data = read_json(path)
        seconds = float(data['cpu_seconds'])
        if not 0 <= seconds < float('inf'):
            raise ValueError('Invalid original CPU record')
        reports.append(dict(path=str(path.resolve()), sha256=file_hash(path), cpu_seconds=seconds))
    if not reports:
        raise ValueError('Original21 postprocessing resource records required')
    runs = [dict(path=str(path.resolve()), **read_json(path))
            for path in sorted((baseline/'training').glob('*/*/z*/seed-*/run.json'))]
    if len(runs) != 18:
        raise ValueError('Exactly18 original21 fits required for shared budget')
    checkpoints = list((baseline/'training').rglob('*.pt'))
    return dict(schema='stmdomains-issue22-prior-budget-v1',
                baseline=str(baseline.resolve()), postprocessing_reports=reports,
                prior_postprocessing_cpu_seconds=sum(r['cpu_seconds'] for r in reports),
                prior_fit_count=len(runs), prior_fit_seconds=sum(r['seconds'] for r in runs),
                prior_checkpoint_count=len(checkpoints),
                prior_checkpoint_bytes=sum(p.stat().st_size for p in checkpoints),
                limits=dict(fits=27, fit_seconds=24300, checkpoint_bytes=10*1024**3,
                            postprocessing_cpu_seconds=7200),
                remaining_fits=9, excluded='Issue21a has a separately authorized budget')


def audit_baseline(baseline: Path, output: Path, budget: PostprocessBudget) -> dict:
    if (output/'baseline-audit.json').exists():
        raise FileExistsError('Baseline audit already exists')
    frozen_path = baseline/'frozen-predictions.json'
    frozen = read_json(frozen_path)
    for index,(relative,expected) in enumerate(frozen['files'].items(),1):
        if index%100 == 0:
            budget.check()
        path = (baseline/relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(baseline.resolve()) or file_hash(path) != expected:
            raise ValueError('Frozen issue21 artifact changed: '+relative)
        if index%20000 == 0:
            print(f'checked baseline {index}/{len(frozen["files"])}',flush=True)
    for relative,expected in frozen.get('code_sha256',{}).items():
        path = Path(__file__).parent.parent/relative
        if file_hash(path) != expected:
            raise ValueError('Frozen issue21 source changed: '+relative)
    result = dict(schema='stmdomains-issue22-baseline-audit-v1',
                  baseline=str(baseline.resolve()), checked_artifacts=len(frozen['files']),
                  frozen_manifest_sha256=file_hash(frozen_path),
                  code_sha256=frozen.get('code_sha256',{}), all_matched=True)
    write_json(output/'baseline-audit.json',result)
    ledger = prior_budget(baseline)
    write_json(output/'prior-budget.json',ledger)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('audit-baseline','plan','audit-training'))
    parser.add_argument('--output',type=Path,default=Path('.scratch/local-ssl-22'))
    parser.add_argument('--baseline',type=Path,default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--prepared',type=Path,default=Path('.scratch/training-20'))
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.baseline = args.baseline.resolve()
    args.prepared = args.prepared.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    resource_path = args.output/f'{args.stage}.resources.json'
    if resource_path.exists():
        raise FileExistsError(resource_path)
    budget = PostprocessBudget(args.output,baseline=args.baseline)
    status = 'failed'
    try:
        budget.check()
        if args.stage == 'audit-baseline':
            result = audit_baseline(args.baseline,args.output,budget)
        else:
            from . import fit
            operation = fit.prepare_plan if args.stage == 'plan' else fit.audit
            value = operation(args.prepared,args.baseline,args.output)
            result = dict(stage=args.stage,completed=True,run_count=len(value.get('runs',[])))
        budget.check()
        status = 'completed'
        print(json.dumps(result,indent=2))
    finally:
        write_json(resource_path,dict(status=status,**budget.measurements()))


if __name__ == '__main__':
    main()
