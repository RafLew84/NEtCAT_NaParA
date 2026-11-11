"""E3 post-freeze quality, paired stability and offline viewer payloads."""
from __future__ import annotations

from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_run import compact, context, make_samples, write_js
from .e2_metrics import edge_reference, pair_summary
from .e3_metrics import assignment_stability, distance_change
from .e3_pipeline import SPACES, STAGES
from .e3_transforms import CONDITIONS
from .training.evaluate import _truth_bundle, aggregate_samples, evaluate_sample

REPO = Path(__file__).resolve().parents[2]


def stats(values):
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if not len(values): return dict(count=0, mean=None, q25=None, median=None, q75=None)
    q = np.quantile(values, [.25, .5, .75])
    return dict(count=len(values), mean=float(values.mean()), q25=float(q[0]), median=float(q[1]), q75=float(q[2]))


def change_flags(base, after, edges, scope, common):
    assignment = scope & ((base > 0) != (after > 0))
    both = scope & common & (base > 0) & (after > 0)
    u, v = edges.T
    changed = both[u] & both[v] & ((base[u] == base[v]) != (after[u] == after[v]))
    relation = np.zeros(len(base), bool)
    relation[edges[changed].ravel()] = True
    return assignment, relation


def evaluate(bank, out, index, frozen, gradients, check_budget):
    for name, expected in frozen.items():
        if file_hash(out / name) != expected: raise ValueError(f'Frozen E3 artifact changed: {name}')
    truths, hashes = {}, {}
    for field, directory in (('controls', REPO / '.scratch/training-20/controls/evaluation'),
                             ('references', REPO / '.scratch/unsupervised-input/evaluation')):
        manifest, truths[field] = _truth_bundle(directory, field)
        hashes[str(directory / 'manifest.json')] = file_hash(directory / 'manifest.json')
        hashes.update({str(directory / r['file']): r['sha256'] for r in manifest[field]})
    write_json(out / 'truth-audit.json', dict(files=hashes))
    samples = make_samples(bank.inputs, truths['controls'], truths['references'], out)
    gallery, quality_summary = [], []
    pairs, domain_batch = defaultdict(list), defaultdict(list)
    shared_cache, last_shared, last_batch, meta = None, None, None, None
    counts = defaultdict(int)
    with gzip.open(out / 'paired-sample-metrics.jsonl.gz', 'wt') as paired_stream, \
            gzip.open(out / 'edge-summary.jsonl.gz', 'wt') as edge_stream, \
            gzip.open(out / 'domain-sample-metrics.jsonl.gz', 'wt') as domain_stream, \
            (out / 'paired-metrics.csv').open('w', newline='') as csv_stream:
        writer = None

        def flush():
            for (case, ci, si, support), pieces in pairs.items():
                current, baseline, same, eligible = [np.concatenate([p[i] for p in pieces]) for i in range(4)]
                metric = pair_summary(current, same, eligible, max_curve_points=2)
                baseline_metric = pair_summary(baseline, same, eligible, max_curve_points=2)
                for value in (metric, baseline_metric): value.pop('roc'); value.pop('pr')
                edge_stream.write(compact(dict(meta, case=case, condition=CONDITIONS[ci], space=SPACES[si],
                    support=support, summary=metric, paired_identity=baseline_metric)) + '\n')
                counts['edge_aggregates'] += 1
            for (case, ci, method, stage), pieces in domain_batch.items():
                quality_summary.append(dict(meta, case=case, condition=CONDITIONS[ci], partition=method,
                                            variant=stage, metrics=aggregate_samples(pieces)))
            pairs.clear(); domain_batch.clear()

        for number, entry in enumerate(sorted(index, key=lambda e: (e['run_id'], e['sampler'], e['sample_id']))):
            check_budget()
            batch = (entry['run_id'], entry['sampler'])
            if last_batch is not None and batch != last_batch: flush()
            last_batch = batch
            meta = {key: entry[key] for key in ('run_id', 'regime', 'family', 'seed', 'sampler')}
            rows, ids, desc, scope, gates, hard, minimum = context(bank.inputs, entry)
            if last_shared != entry['shared']:
                with np.load(out / entry['shared'], allow_pickle=False) as z: shared_cache = dict(z)
                last_shared = entry['shared']
            shared = shared_cache
            with np.load(out / entry['prediction'], allow_pickle=False) as z: data = dict(z)
            adapter = json.loads((out / entry['adapter']).read_text())
            edges = shared['edges']
            truth_meta, truth = truths['controls' if entry['kind'] == 'synthetic' else 'references'].get(entry['sample_id'], ({}, {}))
            case = truth_meta.get('case') if entry['kind'] == 'synthetic' else 'measurement'
            reference = edge_reference(rows, edges, truth, entry['kind'], entry['regime'])
            labels = truth.get('domain_labels' if entry['kind'] == 'synthetic' else 'region_instances')
            payloads = {method: dict(id=f"{entry['id']}-{method}", scope=scope, available=desc['available'],
                         edges=edges, min_size=minimum, threshold=bank.inputs.threshold,
                         preview_row_index=entry['preview_row_index'], conditions={}) for method in ('fh4', 'mws')}
            for ci, condition in enumerate(CONDITIONS):
                own = data['valid'][0] & data['valid'][ci] & scope & desc['available']
                common = shared['common'][0] & shared['common'][ci]
                for support, nodes in (('own', own), ('common', common)):
                    supported_edges = nodes[edges].all(axis=1)
                    eligible = reference['valid'] & supported_edges
                    for si, space in enumerate(SPACES):
                        distances = data['distances'][ci, si]
                        original = data['distances'][0, si]
                        paired = distance_change(original, distances, edges, supported_edges,
                            adapter['q25'] if si == 2 else None, adapter['q75'] if si == 2 else None)
                        movement = stats(data['shift_absolute'][ci, si, nodes])
                        relative = stats(data['shift_relative'][ci, si, nodes])
                        norm_delta = stats(data['feature_norms'][ci, si, nodes] - data['feature_norms'][0, si, nodes])
                        pixel = stats(shared['pixels_post_outside_fraction'][ci, nodes])
                        angle = stats(data['angle_shift'][ci, nodes]) if 'angle_shift' in data else stats([])
                        translation = stats(data['translation_shift'][ci, nodes]) if 'translation_shift' in data else stats([])
                        item = dict(meta, sample_id=entry['sample_id'], case=case, condition=condition,
                            space=space, support=support, feature_absolute=movement, feature_relative=relative,
                            distances=paired, feature_norm_change=norm_delta,
                            base_norm=stats(data['feature_norms'][0, si, nodes]),
                            changed_norm=stats(data['feature_norms'][ci, si, nodes]),
                            input_rmse=stats(shared['pixels_input_rmse'][ci, nodes]),
                            post_outside_fraction=pixel, baseline_saturation=stats(shared['pixels_baseline_saturation_fraction'][ci, nodes]),
                            angle_radians=angle, translation_normalized=translation)
                        paired_stream.write(compact(item) + '\n')
                        row = dict(meta, sample_id=entry['sample_id'], case=case, condition=condition, space=space,
                            support=support, nodes=movement['count'], edges=paired['counts']['compared_pairs'],
                            feature_absolute_median=movement['median'], feature_relative_median=relative['median'],
                            feature_norm_change_median=norm_delta['median'],
                            distance_rmse=paired['rmse'], distance_spearman=paired['spearman'],
                            relation_changed=paired['relation_changed_pairs'], relation_change_fraction=paired['relation_change_fraction'],
                            outside_mean=pixel['mean'], angle_median=angle['median'], translation_median=translation['median'])
                        if writer is None:
                            writer = csv.DictWriter(csv_stream, fieldnames=list(row)); writer.writeheader()
                        writer.writerow(row)
                        pairs[(case, ci, si, support)].append((distances, original, reference['same'], eligible))
                        counts['paired_sample_evaluations'] += 1
                for method in ('fh4', 'mws'):
                    before = data[f'{method}_before'][ci]
                    variants = {}
                    for stage in STAGES:
                        after = data[f'{method}_{stage}'][ci]
                        baseline = data[f'{method}_{stage}'][0]
                        states = np.where(~scope, 'not_evaluated', np.where(~desc['available'], 'insufficient_data',
                                          np.where(after > 0, 'ordered_untyped', 'ambiguous')))
                        metric = evaluate_sample(rows, labels, before, after, edges,
                            evaluation_valid=truth.get('evaluation_valid'), orientation_labels=truth.get('orientation_groups'),
                            truth_raster=truth.get('domain_labels') if entry['sampler'] == 'grid' else None,
                            pixel_spacing_xy=entry['pixel_spacing_xy'], regime=entry['regime'], kind=entry['kind'],
                            case=case if entry['kind'] == 'synthetic' else None, states=states)
                        stability = assignment_stability(baseline, after, edges, scope & desc['available'])
                        domain_batch[(case, ci, method, stage)].append(metric)
                        domain_stream.write(compact(dict(meta, sample_id=entry['sample_id'], case=case,
                            condition=condition, partition=method, variant=stage, metrics=metric, stability=stability)) + '\n')
                        changed, neighbor_changed = change_flags(baseline, after, edges, scope, own)
                        value = metric['after']
                        variants[stage] = dict(labels=after, coverage=value['positive_reference_coverage'],
                            merge_rate=value['pairs']['merge_rate'], split_rate=value['pairs']['split_rate'],
                            assigned=value['assigned_full_support_elements'], domain_count=value['domain_count_in_scope'],
                            stability=stability, assignment_changed=changed, neighbor_relation_changed=neighbor_changed,
                            common_available=own)
                        counts['domain_sample_evaluations'] += 1
                    payload = dict(before=before, variants=variants, hard=shared['hard'][ci], acf=shared['acf_score'][ci],
                        ratio=shared['second_direction_ratio'][ci], energy=shared['energy'][ci], full_gate=shared['full_gate'][ci],
                        preview_image=entry['preview_images'][ci])
                    for key in ('input_rmse', 'post_outside_fraction', 'baseline_saturation_fraction'):
                        payload[key] = shared['pixels_' + key][ci]
                    for si, space in enumerate(SPACES): payload['feature_shift_' + space] = data['shift_absolute'][ci, si]
                    payloads[method]['conditions'][condition] = payload
            for method, payload in payloads.items():
                path = f"runs/{payload['id']}.js"
                write_js(out / path, 'E3_RUN_DATA', payload)
                gallery.append(dict(meta, id=payload['id'], sample_id=entry['sample_id'], partition=method, path=path))
            if number % 200 == 0: print(f'E3 evaluation {number + 1}/{len(index)}', flush=True)
        flush()
    with gzip.open(out / 'domain-summary.json.gz', 'wt') as f: f.write(compact(dict(records=quality_summary)))
    write_js(out / 'gallery-data.js', 'E3_DATA', dict(samples=samples, runs=gallery, conditions=CONDITIONS,
             variants=STAGES, gradient={k: v['value'] for k, v in gradients.items()}))
    from .e3_gallery import write_gallery
    write_gallery(out / 'index.html')
    return dict(counts, domain_aggregates=len(quality_summary), gallery_runs=len(gallery), samples=len(samples))
