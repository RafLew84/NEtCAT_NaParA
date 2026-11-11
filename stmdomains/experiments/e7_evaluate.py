"""Post-freeze E7 scoring and paired images; STM is development-only."""
from __future__ import annotations

from collections import defaultdict
import gzip
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .bundle import file_hash, write_json
from .e1_run import compact, write_js
from .e2_metrics import edge_reference
from .e5_evaluate import valid_reference
from .e5_metrics import graph_boundary_metrics
from .e5_readout import write_csv
from .e7_metrics import relation_metrics
from .e7_probe import specs
from .training.evaluate import _truth_bundle, aggregate_samples, evaluate_sample

REPO = Path(__file__).resolve().parents[2]
STAGES = ('H_M1', 'A_fixed_M1')
METHODS = ('fh4', 'mws')


def archive(path):
    with np.load(path, allow_pickle=False) as z: return dict(z)


def model_label(spec):
    labels = dict(geometry='Geometria', geometry_photometry='Geometria + fotometria',
                  geometry_ae='Geometria + AE', geometry_rvae='Geometria + rVAE')
    return labels[spec['family']] + (f" · {spec['seed']}" if spec['seed'] is not None else '')


def prepare_samples(out, entries, truth_index):
    samples = []
    for entry in entries:
        if entry['role'] == 'train': continue
        arrays = archive(out / entry['source_file'])
        rows = json.loads((out / entry['rows_file']).read_text())
        pixels = arrays['image']
        selected = pixels[arrays['measured'] & np.isfinite(pixels)]
        low, high = np.quantile(selected, [.02, .98]) if len(selected) else (0., 1.)
        gray = np.uint8(np.clip((pixels - low) / max(high - low, 1e-12), 0, 1) * 255)
        relative = f"images/{entry['sample_id']}.png"
        (out / relative).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(gray).save(out / relative)
        case = truth_index[entry['sample_id']]['case'] if entry['kind'] == 'synthetic' else 'measurement'
        title = (f"{case} · grupa {entry['group_id']}" if entry['kind'] == 'synthetic'
                 else f"TTMAPP · klatka {entry['record']['frame_number']}")
        samples.append(dict(id=entry['sample_id'], title=title, kind=entry['kind'], case=case,
            role=entry['role'], image=relative, width=pixels.shape[1], height=pixels.shape[0],
            xy=[row['raw_edge_xy'] for row in rows], element_ids=[row['element_id'] for row in rows],
            pixel_spacing_xy=entry['record'].get('pixel_spacing_xy', [1., 1.])))
    return sorted(samples, key=lambda s: (s['kind'] != 'measurement', s['id']))


def head_payload(data, head, method, stats):
    result = {stage: data[f'{head}__{method}__{stage}'] for stage in ('before', *STAGES)}
    result.update(valid=data[f'{head}_valid'], stats=stats)
    return result


def evaluate(out, entries, index, frozen, check_budget):
    for name, expected in frozen.items():
        if file_hash(out / name) != expected: raise ValueError(f'Frozen E7 artifact changed: {name}')
    truth_index = {r['sample_id']: r for r in json.loads((out / 'truths/index.json').read_text())}
    ref_dir = REPO / '.scratch/unsupervised-input/evaluation'
    ref_manifest, references = _truth_bundle(ref_dir, 'references')
    write_json(out / 'truth-audit.json', dict(
        real_reference_manifest_sha256=file_hash(ref_dir / 'manifest.json'),
        real_files={r['file']: r['sha256'] for r in ref_manifest['references']},
        new_truth_index_sha256=file_hash(out / 'truths/index.json'),
        roles=dict(validation='new realizations of known synthetic geometries',
                   stm_development='known partial interiors, no independent test')))
    samples = prepare_samples(out, entries, truth_index)
    sample_lookup = {s['id']: s for s in samples}
    by_sample = defaultdict(list)
    for item in index: by_sample[item['sample_id']].append(item)
    domains, pairs, graph_rows, gallery = [], [], [], []
    domain_groups, pair_groups = defaultdict(list), defaultdict(list)
    for number, (ident, sample_entries) in enumerate(sorted(by_sample.items())):
        check_budget()
        source = sample_entries[0]
        rows = json.loads((out / source['rows_file']).read_text())
        if source['kind'] == 'synthetic':
            truth = archive(out / source['truth_file'])
            expected = truth_index[ident]['sha256']
            if file_hash(out / source['truth_file']) != expected: raise ValueError('Truth changed')
        else:
            _, truth = references.get(ident, ({}, {}))
        case = sample_lookup[ident]['case']
        labels = truth.get('domain_labels', truth.get('region_instances'))
        ref_valid = valid_reference(truth)
        data_by_model = {r['model_id']: archive(out / r['prediction_file']) for r in sample_entries}
        if len(sample_entries) != len(specs()) or set(data_by_model) != {s['id'] for s in specs()}:
            raise ValueError('Incomplete or repeated E7 model matrix')
        geometric = data_by_model['geometry']
        for data in data_by_model.values():
            for key in ('edges', 'available', 'common_valid'):
                if not np.array_equal(data[key], geometric[key]):
                    raise ValueError('E7 comparisons changed their graph or common support')
        all_learned_finite = np.logical_and.reduce([np.isfinite(d['learned_score']) for d in data_by_model.values()])
        stats_by_model = {}
        for entry in sample_entries:
            model_id = entry['model_id']
            data = data_by_model[model_id]
            edges, available = data['edges'], data['available']
            # 'transductive' here is the historical scorer's full-frame scope flag.
            # Encoders remain transfer-pretrained; this is NOT an independent test.
            reference = edge_reference(rows, edges, truth, source['kind'], 'transductive')
            common_pairs = reference['valid'] & data['common_valid'][edges].all(1) & all_learned_finite
            paired_edges = common_pairs & data['historical_valid'][edges].all(1)
            paired_edges &= np.isfinite(data['historical_distance'])
            meta = {k: entry[k] for k in ('sample_id', 'model_id', 'family', 'seed', 'role', 'group_id')}
            meta['case'] = case
            for head in ('learned', 'historical'):
                score = 1 - data['learned_score'] if head == 'learned' else data['historical_distance']
                cases = (case, 'all_synthetic') if source['kind'] == 'synthetic' else (case,)
                masks = [('historical_matched', paired_edges)]
                if head == 'learned': masks.insert(0, ('learned_common', common_pairs))
                for comparison, eligible in masks:
                    pair = relation_metrics(score, reference['same'], eligible, classifier=head == 'learned')
                    pair.update(reference_counts=reference['counts'],
                                own_finite_reference_edges=int((reference['valid'] & np.isfinite(score)).sum()),
                                comparison_scope=comparison)
                    pairs.append(dict(meta, head=head, comparison=comparison, metrics=pair))
                    for group_case in cases:
                        for group_id in (entry['group_id'], 'all_groups'):
                            pair_groups[(entry['role'], group_case, group_id, model_id, head, comparison)].append(
                                (score[eligible], reference['same'][eligible]))
                stats_by_model[(model_id, head)] = {}
                for method in METHODS:
                    statistics = {}
                    before = data[f'{head}__{method}__before']
                    for stage in STAGES:
                        after = data[f'{head}__{method}__{stage}']
                        states = np.where(~available, 'insufficient_data',
                            np.where(after > 0, 'ordered_untyped', 'ambiguous'))
                        metric = evaluate_sample(rows, labels, before, after, edges,
                            evaluation_valid=ref_valid, orientation_labels=truth.get('orientation_groups'),
                            pixel_spacing_xy=source['record'].get('pixel_spacing_xy', [1., 1.]),
                            regime='transductive', kind=source['kind'],
                            case=case if source['kind'] == 'synthetic' else None, states=states)
                        domains.append(dict(meta, head=head, partition=method, variant=stage, metrics=metric))
                        graph_rows.append(dict(meta, head=head, partition=method, variant=stage,
                            metrics=graph_boundary_metrics(reference['labels'], after, edges, available,
                                                           reference_valid=reference['node_valid'])))
                        for group_case in cases:
                            for group_id in (entry['group_id'], 'all_groups'):
                                domain_groups[(entry['role'], group_case, group_id, model_id, head, method, stage)].append(metric)
                        value = metric['after']
                        statistics[stage] = dict(coverage=value['positive_reference_coverage'],
                            merge_rate=value['pairs']['merge_rate'], split_rate=value['pairs']['split_rate'],
                            assigned=value['assigned_full_support_elements'], domain_count=value['domain_count_in_scope'])
                    stats_by_model[(model_id, head)][method] = statistics
        for entry in sample_entries:
            model_id = entry['model_id']
            data, geo = data_by_model[model_id], data_by_model['geometry']
            for method in METHODS:
                run_id = f"{ident}--{model_id}--{method}"
                payload = dict(id=run_id, available=data['available'], common_valid=data['common_valid'],
                    hard=data['hard'], full_gate=data['full_gate'], edges=data['edges'],
                    learned_score=data['learned_score'], score_kind='p_same',
                    learned=head_payload(data, 'learned', method, stats_by_model[(model_id, 'learned')][method]),
                    historical=head_payload(data, 'historical', method, stats_by_model[(model_id, 'historical')][method]),
                    geometry=head_payload(geo, 'learned', method, stats_by_model[('geometry', 'learned')][method]))
                relative = f'runs/{run_id}.js'
                write_js(out / relative, 'E7_RUN_DATA', payload)
                gallery.append(dict(id=run_id, sample_id=ident, model_id=model_id,
                    family=entry['family'], seed=entry['seed'], partition=method, path=relative))
        if number % 20 == 0: print(f'E7 evaluation: {number + 1}/{len(by_sample)} images', flush=True)
    model_lookup = {s['id']: s for s in specs()}
    domain_summary = [dict(role=k[0], case=k[1], group_id=k[2], model_id=k[3], family=model_lookup[k[3]]['family'],
        seed=model_lookup[k[3]]['seed'], head=k[4], partition=k[5], variant=k[6], metrics=aggregate_samples(v))
        for k, v in domain_groups.items()]
    pair_summary = []
    for (role, case, group_id, model_id, head, comparison), pieces in pair_groups.items():
        scores = np.concatenate([p[0] for p in pieces])
        same = np.concatenate([p[1] for p in pieces])
        pair_summary.append(dict(role=role, case=case, group_id=group_id, model_id=model_id, comparison=comparison,
            family=model_lookup[model_id]['family'], seed=model_lookup[model_id]['seed'], head=head,
            samples=len(pieces), metrics=relation_metrics(scores, same, np.ones(len(scores), bool),
                                                        classifier=head == 'learned')))
    for name, records in (('domain-metrics', domains), ('pair-metrics', pairs), ('graph-metrics', graph_rows)):
        with gzip.open(out / f'{name}.jsonl.gz', 'wt') as stream:
            for row in records: stream.write(compact(row) + '\n')
    for name, records in (('domain-summary', domain_summary), ('pair-summary', pair_summary)):
        write_json(out / f'{name}.json', dict(records=records))
        write_csv(out / f'{name}.csv', records)
    write_js(out / 'gallery-data.js', 'E7_DATA', dict(samples=samples, runs=gallery,
        models=[dict(s, label=model_label(s)) for s in specs()], default_model_id='geometry_rvae_seed20261101',
        score_kind='p_same', stm_independent_test=False, encoder_training=False))
    from .e7_gallery import write_gallery
    write_gallery(out / 'index.html')
    return dict(samples=len(samples), gallery_runs=len(gallery), domain_sample_evaluations=len(domains),
                pair_sample_evaluations=len(pairs), domain_aggregates=len(domain_summary),
                pair_aggregates=len(pair_summary))
