"""Small evidence manifest for the completed bounded21a experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...bundle import file_hash, write_json


def read(path):
    return json.loads(Path(path).read_text())


def build(output: Path, destination: Path):
    output = output.resolve()
    plan = read(output/'plan.json')
    runs = []
    for spec in plan['runs']:
        result = read(output/spec['run_id']/'run.json')
        selected = next((row for row in result.get('validation_history', [])
                         if row['step'] == result.get('selected_step')), None)
        last = next((row for row in result.get('validation_history', []) if row['step'] == 2000), None)
        keys = ('status', 'stop_reason', 'family', 'seed', 'diagnostic', 'completed_steps',
                'selected_step', 'selected_checkpoint_sha256', 'seconds', 'parameter_count',
                'peak_rss_bytes', 'cuda_peak_allocated_bytes', 'config_hash')
        runs.append({key: result.get(key) for key in keys} |
                    dict(run_id=spec['run_id'], selected_validation=selected, step2000_validation=last))
    files = ['plan.json', 'protocol.json', 'baseline-audit.json', 'controls/audit.json',
             'training/training-audit.json', 'baseline-reuse-audit.json',
             'frozen-predictions.json', 'evaluation/evaluation-evidence.json',
             'evaluation/summary.json', 'evaluation/metrics.csv', 'evaluation/aggregates.json',
             'evaluation/continuation.json', 'evaluation/ablations.json',
             'evaluation/paired-model-comparisons.json', 'feature-diagnostics.json', 'index.html']
    files += [str(p.relative_to(output)) for p in sorted((output/'figures').glob('*')) if p.is_file()]
    files += [str(p.relative_to(output)) for p in sorted((output/'gallery').glob('*')) if p.is_file()]
    artifacts = {name: file_hash(output/name) for name in files if (output/name).is_file()}
    resources = {p.name: read(p) for p in sorted(output.glob('*.resources.json'))}
    continuation = read(output/'evaluation/continuation.json')
    criteria = [{key: value.get(key) for key in ('metadata', 'continuation', 'benefit', 'stability', 'claim_scope')}
                for value in continuation]
    source = Path(__file__).parent
    code = {str(p.relative_to(Path.cwd())): file_hash(p)
            for p in sorted(source.glob('*')) if p.is_file() and p.suffix in ('.py', '.json', '.sh')}
    result = dict(schema='stmdomains-rvae21a-evidence-v1', output=str(output),
                  scope='transfer z32, grid48; previously viewed TTMAPP plus fresh realizations of known synthetic families',
                  plan_sha256=file_hash(output/'plan.json'), runs=runs,
                  training_seconds=sum(r.get('seconds') or 0. for r in runs),
                  completed_steps=sum(r.get('completed_steps') or 0 for r in runs),
                  postprocess_cpu_seconds=sum(r['cpu_seconds'] for r in resources.values()),
                  resources=resources, continuation=criteria,
                  artifacts_sha256=artifacts, source_sha256=code,
                  evaluation=read(output/'evaluation/evaluation-evidence.json'),
                  original21_unchanged=read(output/'baseline-audit.json'),
                  baseline_predictions=read(output/'baseline-reuse-audit.json'),
                  application_detector_adopted=False)
    write_json(destination, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output, args.manifest)
    print(json.dumps({key: result[key] for key in ('completed_steps', 'training_seconds', 'postprocess_cpu_seconds')}))


if __name__ == '__main__':
    main()
