"""Small versionable evidence manifest; large measurements/models stay local."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..bundle import file_hash, write_json
from .predict import read_json


def summarize(output, destination):
    registry = read_json(output/'training/registry.json')
    aggregate = read_json(output/'evaluation/aggregates.json')
    main = []
    for row in aggregate:
        metadata, metric = row['metadata'], row['metrics']
        if metadata['kind'] != 'measurement' or metadata['sampler'] != 'grid' or metadata['scale_px'] != 48:
            continue
        value = dict(metadata=metadata, reference_elements=metric['evaluated_elements'],
                     full_support_elements=metric['full_support_elements'])
        for stage in ('before', 'after'):
            item = metric[stage]
            value[stage] = dict(coverage=item['coverage'], merge_rate=item['pairs']['merge_rate'],
                                split_rate=item['pairs']['split_rate'],
                                assigned_elements=item['assigned_evaluated_elements'],
                                per_orientation_group=item['per_orientation_group'])
        main.append(value)
    artifacts = [
        'training/architecture.json', 'training/registry.json',
        'training-resume/resume-report.json', 'frozen-predictions.json',
        'export-contract-audit.json', 'inference-configuration.json',
        'cache/order-thresholds.json', 'predictions/index.json',
        'evaluation/evaluation-evidence.json', 'evaluation/aggregates.json',
        'evaluation/continuation.json', 'evaluation/ablations.json',
        'evaluation/stability.json', 'evaluation/benefits.json',
        'feature-diagnostics.json', 'index.html',
        'gallery/scenario-map.json', 'gallery/scenario-source.json',
        'figures/validation-curves.png', 'figures/reconstruction-examples.png',
    ]
    for optional in ('training/training-audit.json', 'training-resume/reference-blind.json', 'gallery/browser-check.json'):
        if (output/optional).exists():
            artifacts.append(optional)
    hashes = {name: file_hash(output/name) for name in artifacts}
    sources = {}
    for path in sorted(Path(__file__).parent.glob('*.py')):
        key = path.relative_to(Path.cwd()) if path.is_absolute() else path
        sources[str(key)] = file_hash(path)
    for path in sorted(Path('tests/stmdomains').glob('test_training*.py')):
        sources[str(path)] = file_hash(path)
    runs = []
    for row in registry['runs']:
        run = read_json(Path(row['directory'])/'run.json')
        runs.append({key: run[key] for key in ('family', 'latent_dim', 'seed', 'regime', 'status',
                    'selected_step', 'selected_checkpoint_sha256', 'completed_steps', 'seconds',
                    'best_validation_loss', 'parameter_count', 'cuda_peak_allocated_bytes', 'peak_rss_bytes')})
    continuation = [{key: row[key] for key in ('metadata', 'continuation', 'claim_scope',
                    'full_three_group_ttmapp_benefit', 'stability', 'benefit')}
                    | {'synthetic_control_conditions_qualified': row['synthetic_controls']['qualified']}
                    for row in read_json(output/'evaluation/continuation.json')]
    value = dict(schema='stmdomains-autoencoder-domain-evidence-v1', issue=21,
                 experiment_root=str(output), plan_sha256=file_hash(Path(__file__).with_name('experiment-plan.json')),
                 fits=runs, total_fit_seconds=registry['total_fit_seconds'],
                 checkpoint_bytes=registry['checkpoint_bytes'],
                 ttmapp_grid48=main, continuation=continuation,
                 resources={p.name: read_json(p) for p in sorted(output.glob('*-resources.json'))},
                 code_sha256=sources, artifacts_sha256=hashes,
                 limitations=['single correlated acquisition', 'saved registration is often low-confidence',
                              'partial references only', 'no application or native GUI acceptance'])
    write_json(destination, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--manifest', type=Path, default=Path('.scratch/autoencoder-21/evidence.json'))
    args = parser.parse_args()
    value = summarize(args.output, args.manifest)
    print(f"Manifest: {args.manifest}; {len(value['fits'])} fits; {len(value['ttmapp_grid48'])} main STM entries")


if __name__ == '__main__':
    main()
