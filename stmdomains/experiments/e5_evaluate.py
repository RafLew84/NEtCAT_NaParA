"""Post-freeze E5 scoring and paired gallery on original graph coordinates."""
from __future__ import annotations

from collections import defaultdict
import gzip
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_run import compact, make_samples, write_js
from .e2_metrics import edge_reference
from .e3_metrics import assignment_stability
from .e5_catalog import CONDITIONS, CONTEXTS, PATCHES, STAGES, conditions, patch_keys
from .e5_metrics import graph_boundary_metrics
from .training.evaluate import _truth_bundle, aggregate_samples, evaluate_sample

REPO = Path(__file__).resolve().parents[2]


def evaluation_rows(original, available, scope):
    """Preserve graph anchors; only the declared denominator/split changes."""
    if len(original) != len(available) or len(scope) != len(original):
        raise ValueError('Evaluation masks must align with original graph rows')
    return [dict(row, available=bool(available[i]),
                 transfer_split='test' if scope[i] else None)
            for i, row in enumerate(original)]


def valid_reference(truth):
    labels = truth.get('domain_labels', truth.get('region_instances'))
    if labels is None: return None
    valid = np.asarray(truth.get('evaluation_valid', np.ones_like(labels, bool)), bool).copy()
    for name in ('boundary_uncertain', 'boundary_unscored'):
        if name in truth: valid &= ~np.asarray(truth[name], bool)
    return valid


def gallery_stage(metric, labels, stability):
    value = metric['after']
    return dict(labels=labels, coverage=value['positive_reference_coverage'],
                merge_rate=value['pairs']['merge_rate'], split_rate=value['pairs']['split_rate'],
                assigned=value['assigned_full_support_elements'],
                domain_count=value['domain_count_in_scope'], stability=stability,
                positive_reference_elements=metric['positive_reference_elements'],
                before_coverage=metric['before']['positive_reference_coverage'])


def evaluate(bank, out, index, frozen, check_budget):
    for name, expected in frozen.items():
        if file_hash(out / name) != expected: raise ValueError(f'Frozen E5 artifact changed: {name}')
    truths, hashes = {}, {}
    for field, directory in (('controls', REPO / '.scratch/training-20/controls/evaluation'),
                             ('references', REPO / '.scratch/unsupervised-input/evaluation')):
        manifest, truths[field] = _truth_bundle(directory, field)
        hashes[str(directory / 'manifest.json')] = file_hash(directory / 'manifest.json')
        hashes.update({str(directory / r['file']): r['sha256'] for r in manifest[field]})
    write_json(out / 'truth-audit.json', dict(files=hashes))
    from .e5_context_audit import audit_context
    context_count = audit_context(bank, out, index, truths, check_budget)
    samples = make_samples(bank.inputs, truths['controls'], truths['references'], out)
    gallery, summary, batch_rows = [], [], defaultdict(list)
    last_batch, meta, counts = None, None, defaultdict(int)
    with gzip.open(out / 'metrics.jsonl.gz', 'wt') as stream, \
            (out / 'support-summary.jsonl').open('w') as support_stream:

        def flush():
            for (case, condition, contrast, context, method, stage), pieces in batch_rows.items():
                summary.append(dict(meta, case=case, condition=condition, contrast=contrast,
                                    context=context, partition=method, variant=stage,
                                    metrics=aggregate_samples(pieces)))
            batch_rows.clear()

        for number, entry in enumerate(sorted(index, key=lambda e: (e['run_id'], e['sampler'], e['sample_id']))):
            check_budget()
            batch = (entry['run_id'], entry['sampler'])
            if last_batch is not None and batch != last_batch: flush()
            last_batch = batch
            meta = {key: entry[key] for key in ('run_id', 'regime', 'family', 'seed', 'sampler')}
            original = bank.inputs.rows(entry)
            with np.load(out / entry['shared'], allow_pickle=False) as z: shared = dict(z)
            with np.load(out / entry['prediction'], allow_pickle=False) as z: data = dict(z)
            truth_meta, truth = truths['controls' if entry['kind'] == 'synthetic' else 'references'].get(entry['sample_id'], ({}, {}))
            case = truth_meta.get('case') if entry['kind'] == 'synthetic' else 'measurement'
            labels = truth.get('domain_labels', truth.get('region_instances'))
            reference_valid = valid_reference(truth)
            edges = shared['edges']
            configs = conditions(entry['family'])
            union_scope = np.logical_or.reduce([data[f"{c['id']}__own__scope"] for c in configs])
            payloads = {method: dict(id=f"{entry['id']}-{method}", scope=union_scope,
                edges=edges, pixel_spacing_xy=entry['pixel_spacing_xy'],
                min_size=4 if entry['sampler'] == 'grid' else 8,
                threshold=bank.inputs.threshold, gate_source=dict(condition_id='exact48',
                    available=shared['baseline_available'], hard=shared['baseline_hard'],
                    full_gate=shared['baseline_full_gate'], acf=shared['baseline_acf'],
                    ratio=shared['baseline_ratio'], energy=shared['baseline_energy']),
                conditions={}) for method in ('fh4', 'mws')}
            for config in configs:
                condition, contrast = config['id'], config['contrast']
                patch = patch_keys(config)[-1]
                for method in payloads:
                    payloads[method]['conditions'][condition] = dict(
                        patch_centers_xy=shared[f'{patch}__centers'],
                        support_by_scale=({str(s): shared[f'exact{s}__available'] for s in (32, 48, 64)}
                            if config['centering'] == 'exact' else {'48': shared[f'{patch}__available']}),
                        available=data[f'{condition}__own__available'], contexts={})
                for context in CONTEXTS:
                    prefix = f'{condition}__{context}'
                    scope, available, valid = [data[f'{prefix}__{k}'] for k in ('scope', 'available', 'valid')]
                    eligible = scope & available
                    rows = evaluation_rows(original, available, scope)
                    reference = edge_reference(rows, edges, truth, entry['kind'], entry['regime'])
                    common = data[f'{condition}__common__scope'] & data[f'{condition}__common__available']
                    row_meta = dict(meta, sample_id=entry['sample_id'], case=case,
                                    condition=condition, contrast=contrast, context=context)
                    support_stream.write(compact(dict(row_meta, counts=dict(
                        planned_nodes=len(rows), scope_nodes=int(scope.sum()),
                        available_nodes=int(eligible.sum()), feature_valid_nodes=int(valid.sum()),
                        missing_baseline48_gate_nodes=int((eligible & ~shared['baseline_available']).sum()),
                        common_lost_nodes=int((eligible & ~common).sum())))) + '\n')
                    counts['support_records'] += 1
                    for method in ('fh4', 'mws'):
                        before = data[f'{prefix}__{method}__before']
                        values = {}
                        for stage in STAGES:
                            after = data[f'{prefix}__{method}__{stage}']
                            baseline = data[f"{config['baseline_id']}__{context}__{method}__{stage}"]
                            states = np.where(~scope, 'not_evaluated', np.where(~available, 'insufficient_data',
                                np.where(~shared['baseline_available'], 'no_baseline48_gate',
                                np.where(after > 0, 'ordered_untyped', 'ambiguous'))))
                            metric = evaluate_sample(rows, labels, before, after, edges,
                                evaluation_valid=reference_valid, orientation_labels=truth.get('orientation_groups'),
                                truth_raster=truth.get('domain_labels') if entry['sampler'] == 'grid' else None,
                                pixel_spacing_xy=entry['pixel_spacing_xy'], regime=entry['regime'],
                                kind=entry['kind'], case=case if entry['kind'] == 'synthetic' else None, states=states)
                            graph = graph_boundary_metrics(reference['labels'], after, edges, eligible,
                                                           reference_valid=reference['node_valid'])
                            locality = dict(graph_cuts=graph, raster_boundary=metric['after']['boundary'],
                                            reference_counts=reference['counts'], reference_scope=reference['reference_scope'])
                            base_scope = data[f"{config['baseline_id']}__{context}__scope"]
                            base_available = data[f"{config['baseline_id']}__{context}__available"]
                            stability = assignment_stability(baseline, after, edges,
                                                             eligible & base_scope & base_available)
                            stream.write(compact(dict(row_meta, partition=method, variant=stage,
                                                      metrics=metric, locality=locality, stability=stability)) + '\n')
                            batch_rows[(case, condition, contrast, context, method, stage)].append(metric)
                            values[stage] = gallery_stage(metric, after, stability)
                            counts['domain_sample_evaluations'] += 1
                        payloads[method]['conditions'][condition]['contexts'][context] = dict(
                            scope=scope, comparison_available=available, feature_valid=valid,
                            before=before, variants=values)
            for method, payload in payloads.items():
                for config in configs:
                    for context in CONTEXTS:
                        target = payload['conditions'][config['id']]['contexts'][context]
                        base = payload['conditions'][config['baseline_id']]['contexts'][context]
                        target['baseline'] = {key: base[key] for key in ('scope', 'comparison_available', 'feature_valid', 'before', 'variants')}
                path = f"runs/{payload['id']}.js"
                write_js(out / path, 'E5_RUN_DATA', payload)
                gallery.append(dict(meta, id=payload['id'], sample_id=entry['sample_id'], partition=method, path=path))
            if number % 200 == 0: print(f'E5 evaluation {number + 1}/{len(index)}', flush=True)
        flush()
    with gzip.open(out / 'domain-summary.json.gz', 'wt') as f: f.write(compact(dict(records=summary)))
    write_js(out / 'gallery-data.js', 'E5_DATA', dict(samples=samples, runs=gallery,
        conditions=list(CONDITIONS), contexts=CONTEXTS, variants=STAGES))
    from .e5_gallery import write_gallery
    write_gallery(out / 'index.html')
    return dict(counts, context_audit_records=context_count, domain_aggregates=len(summary),
                gallery_runs=len(gallery), samples=len(samples))
