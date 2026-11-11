"""Post-freeze E7a domain evaluation with paired E7 baselines and an offline gallery."""
from __future__ import annotations

from collections import defaultdict
import gzip
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_run import compact, write_js
from .e2_metrics import edge_reference
from .e5_evaluate import valid_reference
from .e5_metrics import graph_boundary_metrics
from .e5_readout import write_csv
from .e7_evaluate import model_label, prepare_samples
from .e7_probe import specs
from .e7a_predict import archive, RULES
from .training.evaluate import _truth_bundle, aggregate_samples, evaluate_sample

REPO = Path(__file__).resolve().parents[2]
GATES = ('H_M1', 'A_fixed_M1')


def evaluate(source, out, index, check_budget=lambda: None):
    source, out = Path(source), Path(out)
    truths = {r['sample_id']: r for r in json.loads((source / 'truths/index.json').read_text())}
    entries = json.loads((source / 'data-index.json').read_text())
    for entry in entries:
        for key in ('source_file', 'rows_file'):
            entry[key] = str(source / entry[key])
    samples = prepare_samples(out, entries, truths)
    sample_by_id = {s['id']: s for s in samples}
    ref_dir = REPO / '.scratch/unsupervised-input/evaluation'
    ref_manifest, references = _truth_bundle(ref_dir, 'references')
    write_json(out / 'truth-audit.json', dict(
        e7_truth_index_sha256=file_hash(source / 'truths/index.json'),
        stm_manifest_sha256=file_hash(ref_dir / 'manifest.json'),
        stm_files={r['file']: r['sha256'] for r in ref_manifest['references']},
        stm_role='known partial development reference, not independent test'))
    with gzip.open(source / 'domain-metrics.jsonl.gz', 'rt') as stream:
        previous = {(r['sample_id'], r['model_id'], r['partition'], r['variant']): r['metrics']
                    for r in map(json.loads, stream) if r['head'] == 'learned'}
    by_sample = defaultdict(list)
    for entry in index:
        by_sample[entry['sample_id']].append(entry)
    metrics, graph_rows, runs, groups = [], [], [], defaultdict(list)
    baseline_checks = 0
    for number, (ident, rows_index) in enumerate(sorted(by_sample.items())):
        check_budget()
        entry = rows_index[0]
        rows = json.loads((source / entry['rows_file']).read_text())
        truth = (archive(source / entry['truth_file']) if entry['kind'] == 'synthetic'
                 else references.get(ident, ({}, {}))[1])
        labels = truth.get('domain_labels', truth.get('region_instances'))
        ref_valid, case = valid_reference(truth), sample_by_id[ident]['case']
        if len(rows_index) != 8 or {r['model_id'] for r in rows_index} != {s['id'] for s in specs()}:
            raise ValueError('Incomplete E7a model matrix')
        common_graph = None
        for entry in rows_index:
            data = archive(out / entry['prediction_file'])
            if common_graph is None:
                common_graph = data
            for key in ('edges', 'available', 'common_valid', 'hard', 'full_gate'):
                if not np.array_equal(data[key], common_graph[key]):
                    raise ValueError('E7a model matrix changed common graph or gates')
            edges, available = data['edges'], data['available']
            reference = edge_reference(rows, edges, truth, entry['kind'], 'transductive')
            head_stats = {}
            for rule in RULES:
                rule_id = rule['id']
                head_stats[rule_id] = {}
                for gate in GATES:
                    after = data[f'{rule_id}__{gate}']
                    states = np.where(~available, 'insufficient_data',
                                      np.where(after > 0, 'ordered_untyped', 'ambiguous'))
                    metric = evaluate_sample(rows, labels, data[f'{rule_id}__before'], after, edges,
                        evaluation_valid=ref_valid, orientation_labels=truth.get('orientation_groups'),
                        pixel_spacing_xy=entry['record'].get('pixel_spacing_xy', [1., 1.]),
                        regime='transductive', kind=entry['kind'],
                        case=case if entry['kind'] == 'synthetic' else None, states=states)
                    if rule_id in ('e7_fh', 'e7_mws'):
                        old_method = 'fh4' if rule_id == 'e7_fh' else 'mws'
                        if metric != previous[(ident, entry['model_id'], old_method, gate)]:
                            raise ValueError('Baseline quality metrics differ from E7')
                        baseline_checks += 1
                    meta = {k: entry[k] for k in ('sample_id', 'model_id', 'family', 'seed', 'role', 'group_id')}
                    meta.update(case=case, rule=rule_id, gate=gate)
                    metrics.append(dict(meta, metrics=metric))
                    graph_rows.append(dict(meta, metrics=graph_boundary_metrics(reference['labels'], after,
                        edges, available, reference_valid=reference['node_valid'])))
                    cases = (case, 'all_synthetic') if entry['kind'] == 'synthetic' else (case,)
                    for group_case in cases:
                        for group in (entry['group_id'], 'all_groups'):
                            groups[(entry['role'], group_case, group, entry['model_id'], rule_id, gate)].append(metric)
                    a = metric['after']
                    head_stats[rule_id][gate] = dict(coverage=a['positive_reference_coverage'],
                        merge_rate=a['pairs']['merge_rate'], split_rate=a['pairs']['split_rate'],
                        assigned=a['assigned_full_support_elements'], domain_count=a['domain_count_in_scope'])
            def head(rule_id):
                return dict(valid=data['learned_valid'], stats=head_stats[rule_id],
                    **{stage: data[f'{rule_id}__{stage}'] for stage in ('before', *GATES)})
            for rule in RULES:
                run_id = f"{ident}--{entry['model_id']}--{rule['id']}"
                payload = {key: data[key] for key in
                           ('available', 'common_valid', 'hard', 'full_gate', 'edges', 'learned_score')}
                # These compatibility keys mean E7 FH and E7 MWS, never different feature sets.
                payload.update(id=run_id, learned=head(rule['id']), geometry=head('e7_fh'),
                               historical=head('e7_mws'), score_kind='p_same')
                relative = f'runs/{run_id}.js'
                write_js(out / relative, 'E7_RUN_DATA', payload)
                runs.append(dict(id=run_id, sample_id=ident, model_id=entry['model_id'],
                    family=entry['family'], seed=entry['seed'], partition=rule['id'], path=relative))
        if number % 20 == 0:
            print(f'E7a evaluation: {number + 1}/{len(by_sample)}', flush=True)
    summary = [dict(role=k[0], case=k[1], group_id=k[2], model_id=k[3], rule=k[4], gate=k[5],
                    metrics=aggregate_samples(values)) for k, values in groups.items()]
    for name, records in (('domain-metrics', metrics), ('graph-metrics', graph_rows)):
        with gzip.open(out / f'{name}.jsonl.gz', 'wt') as stream:
            for record in records:
                stream.write(compact(record) + '\n')
    write_json(out / 'domain-summary.json', dict(records=summary))
    write_csv(out / 'domain-summary.csv', summary)
    write_js(out / 'gallery-data.js', 'E7_DATA', dict(samples=samples, runs=runs,
        models=[dict(s, label=model_label(s)) for s in specs()], rules=RULES,
        default_model_id='geometry_rvae_seed20261101', score_kind='p_same',
        stm_independent_test=False, fitting=False, encoder_inference=False))
    from .e7a_gallery import write_gallery
    write_gallery(out / 'index.html')
    return dict(samples=len(samples), gallery_runs=len(runs), domain_evaluations=len(metrics),
                aggregates=len(summary), baseline_metric_replays=baseline_checks)
