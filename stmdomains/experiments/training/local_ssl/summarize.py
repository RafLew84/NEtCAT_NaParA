"""Compact evidence manifest for the bounded issue22 research experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...bundle import file_hash, write_json


def read(path):
    return json.loads(Path(path).read_text())


def main_results(output: Path):
    """Expose the fixed primary comparison without choosing a winning seed."""
    measurement, controls = [], {}
    for row in read(output / 'evaluation/aggregates.json'):
        meta, metrics = row['metadata'], row['metrics']
        if meta['scale_px'] != 48 or meta['sampler'] != 'grid':
            continue
        if meta['kind'] == 'measurement':
            stages = {}
            for stage in ('before', 'after'):
                value = metrics[stage]
                stages[stage] = {key: value[key] for key in
                                 ('coverage', 'assigned_evaluated_elements', 'pairs', 'local_pairs')}
            measurement.append(dict(metadata=meta, evaluated_elements=metrics['evaluated_elements'],
                                    **stages))
        else:
            keys = ('regime', 'family', 'latent', 'partition', 'case')
            key = tuple(meta[name] for name in keys)
            item = controls.setdefault(key, dict(metadata={name: meta[name] for name in keys},
                                                  assessments=0, passed=0, unavailable=0))
            # Aggregate criteria refer to all three realizations for this seed.
            passed = metrics['criteria']['passed']
            item['assessments'] += 1
            item['passed'] += passed is True
            item['unavailable'] += passed is None
    result = dict(schema='stmdomains-ssl22-main-result-summary-v1',
                  primary='grid48; z32 primary, z16 diagnostic; every seed retained',
                  measurement=measurement, control_seed_groups=list(controls.values()),
                  control_counting='Each assessment aggregates all three control realizations for one model seed; FFT has one nonlearned seed group.')
    write_json(output / 'main-result-summary.json', result)
    return result


def build(output: Path, destination: Path):
    output = output.resolve()
    main_results(output)
    runs = []
    for path in sorted((output / 'training').glob('*/*/z*/seed-*/run.json')):
        value = read(path)
        keys = ('status', 'stop_reason', 'family', 'latent_dim', 'seed', 'regime',
                'completed_steps', 'selected_step', 'selected_checkpoint_sha256',
                'seconds', 'parameter_count', 'peak_rss_bytes',
                'cuda_peak_allocated_bytes', 'config_hash', 'best_validation_loss')
        selected = next((row for row in value.get('validation_history', [])
                         if row['step'] == value.get('selected_step')), None)
        runs.append({key: value.get(key) for key in keys} | dict(
            run_id=str(path.parent.relative_to(output)), selected_validation=selected))
    if not 1 <= len(runs) <= 9:
        raise ValueError('Expected at most nine bounded SSL run records')
    names = [str(p.relative_to(output)) for p in sorted(output.glob('*.json'))
             if p.resolve() != destination.resolve() and not p.name.endswith('.resources.json')]
    names += [str(p.relative_to(output)) for p in sorted(output.glob('*-audit.py'))]
    names += ['training/registry.json', 'training/training-audit.json',
              'evaluation/evaluation-evidence.json', 'evaluation/summary.json',
              'evaluation/metrics.csv', 'evaluation/aggregates.json',
              'evaluation/continuation.json', 'evaluation/ablations.json',
              'evaluation/paired-model-comparisons.json', 'index.html']
    names += [str(p.relative_to(output)) for folder in ('figures', 'gallery')
              for p in sorted((output / folder).glob('*')) if p.is_file()]
    artifacts = {name: file_hash(output / name) for name in sorted(set(names))
                 if (output / name).is_file()}
    resources = {p.name: read(p) for p in sorted(output.glob('*.resources.json'))}
    continuation = read(output / 'evaluation/continuation.json')
    criteria = [{key: value.get(key) for key in
                 ('metadata', 'continuation', 'benefit', 'stability', 'claim_scope')}
                for value in continuation]
    source = Path(__file__).parent
    code = {str(p.relative_to(Path.cwd())): file_hash(p) for p in sorted(source.glob('*'))
            if p.is_file() and p.suffix in ('.py', '.json', '.sh')}
    result = dict(
        schema='stmdomains-local-ssl22-evidence-v1', output=str(output),
        scope='Transfer and transduction separately; grid48 primary; grid32/64 and centers diagnostic. Known controls and one correlated acquisition.',
        plan_sha256=file_hash(output / 'plan.json'), runs=runs,
        training_seconds=sum(r.get('seconds') or 0. for r in runs),
        completed_steps=sum(r.get('completed_steps') or 0 for r in runs),
        postprocess_cpu_seconds=sum(r['cpu_seconds'] for r in resources.values()),
        resources=resources, continuation=criteria, artifacts_sha256=artifacts,
        source_sha256=code, evaluation=read(output / 'evaluation/evaluation-evidence.json'),
        training_audit=read(output / 'training/training-audit.json'),
        application_detector_adopted=False,
    )
    write_json(destination, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output, args.manifest)
    print(json.dumps({key: result[key] for key in
                      ('completed_steps', 'training_seconds', 'postprocess_cpu_seconds')}))


if __name__ == '__main__':
    main()
