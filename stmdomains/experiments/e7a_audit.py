"""Post-freeze audit with explicit pair enumeration and grouped count sums."""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e7a_predict import archive, RULES
from .training.evaluate import _truth_bundle

REPO = Path(__file__).resolve().parents[2]
COUNT_PATHS = ('positive_reference_elements', 'known_zero_elements', 'full_support_elements',
               'after.pairs.assigned_elements', 'after.pairs.same_reference_pairs',
               'after.pairs.different_reference_pairs', 'after.pairs.merged_pairs', 'after.pairs.split_pairs',
               'after.false_known_zero_assignments', 'after.assigned_full_support_elements')


def get(value, path):
    for part in path.split('.'):
        value = value[part]
    return value


def equal_ratio(actual, numerator, denominator):
    if not denominator:
        assert actual is None
    else:
        assert actual is not None and abs(actual-numerator/denominator) < 1e-12


def audit(out):
    out = Path(out)
    run = json.loads((out / 'manifest.json').read_text())
    assert run['status'] == 'completed'
    source = Path(run['source'])
    frozen = json.loads((out / 'prediction-freeze.json').read_text())
    assert not frozen['reference_guard']['blocked'] and frozen['reference_guard']['protected']
    for name, digest in frozen['files'].items():
        assert file_hash(out / name) == digest
    for name, digest in run['code_sha256'].items():
        assert file_hash(REPO / name) == digest == file_hash(out / 'code' / name)
    assert file_hash(out / 'protocol.md') == run['protocol_sha256']
    index = json.loads((out / 'prediction-index.json').read_text())
    with gzip.open(out / 'domain-metrics.jsonl.gz', 'rt') as stream:
        records = list(map(json.loads, stream))
    lookup = {(r['sample_id'], r['model_id'], r['rule'], r['gate']): r for r in records}
    assert len(lookup) == len(records) == 10080
    _, references = _truth_bundle(REPO / '.scratch/unsupervised-input/evaluation', 'references')
    counts = dict(frozen_files=len(frozen['files']), unchanged_score_arrays=0,
                  unchanged_graph_and_mask_arrays=0, domain_count_recomputations=0,
                  aggregate_field_checks=0, refusal_invariants=0)
    truth_cache = {}
    for entry in index:
        data = archive(out / entry['prediction_file'])
        old = archive(source / entry['anchor_prediction_file'])
        np.testing.assert_equal(data['learned_score'], old['learned_score'])
        counts['unchanged_score_arrays'] += 1
        for key in ('edges', 'available', 'common_valid', 'learned_valid', 'hard', 'full_gate'):
            np.testing.assert_equal(data[key], old[key])
            counts['unchanged_graph_and_mask_arrays'] += 1
        ident = entry['sample_id']
        if ident not in truth_cache:
            rows = json.loads((source / entry['rows_file']).read_text())
            truth = (archive(source / entry['truth_file']) if entry['kind'] == 'synthetic'
                     else references.get(ident, ({}, {}))[1])
            labels = truth.get('domain_labels', truth.get('region_instances'))
            if labels is None:
                ref = np.zeros(len(rows), int); eligible = np.zeros(len(rows), bool)
            else:
                xy = np.floor([r['raw_edge_xy'] for r in rows]).astype(int).reshape(-1, 2)
                x, y = xy.T
                ref = labels[y, x]
                eligible = np.asarray(truth.get('evaluation_valid', np.ones_like(labels, bool)))[y, x].copy()
                for key in ('boundary_uncertain', 'boundary_unscored'):
                    if key in truth: eligible &= ~truth[key][y, x]
            available = np.asarray([r['available'] for r in rows], bool)
            positive = eligible & available & (ref > 0)
            zero = eligible & available & (ref == 0) & (entry['kind'] == 'synthetic')
            truth_cache[ident] = ref, positive, zero, available
        ref, positive, zero, available = truth_cache[ident]
        u, v = np.triu_indices(len(ref), 1)
        eligible_pair = positive[u] & positive[v]
        same = ref[u] == ref[v]
        for rule in RULES:
            before = data[f"{rule['id']}__before"]
            for gate, mask_name in (('H_M1', 'hard'), ('A_fixed_M1', 'full_gate')):
                pred = data[f"{rule['id']}__{gate}"]
                assigned = pred > 0
                assert not np.any(assigned & ~(data['learned_valid'] & data[mask_name]))
                for label in np.unique(pred[assigned]):
                    chosen = np.flatnonzero(pred == label)
                    assert len(chosen) >= 8 and len(np.unique(before[chosen])) == 1
                    # Check connectivity separately by flood fill in the immutable graph.
                    allowed, visited = set(chosen.tolist()), {int(chosen[0])}
                    while True:
                        expanded = visited | {int(b) for a, b in data['edges'] if int(a) in visited and int(b) in allowed}
                        expanded |= {int(a) for a, b in data['edges'] if int(b) in visited and int(a) in allowed}
                        if expanded == visited: break
                        visited = expanded
                    assert visited == allowed
                counts['refusal_invariants'] += 1
                m = lookup[(ident, entry['model_id'], rule['id'], gate)]['metrics']
                a = m['after']; pair = a['pairs']
                active = eligible_pair & assigned[u] & assigned[v]
                split = int(np.count_nonzero(active & same & (pred[u] != pred[v])))
                merged = int(np.count_nonzero(active & ~same & (pred[u] == pred[v])))
                n_same, n_diff = int((active & same).sum()), int((active & ~same).sum())
                assert m['positive_reference_elements'] == int(positive.sum())
                assert m['known_zero_elements'] == int(zero.sum())
                assert pair['assigned_elements'] == int((assigned & positive).sum())
                assert (pair['same_reference_pairs'], pair['different_reference_pairs'], pair['split_pairs'], pair['merged_pairs']) == (n_same, n_diff, split, merged)
                assert a['false_known_zero_assignments'] == int((assigned & zero).sum())
                equal_ratio(a['positive_reference_coverage'], (assigned & positive).sum(), positive.sum())
                equal_ratio(pair['merge_rate'], merged, n_diff)
                equal_ratio(pair['split_rate'], split, n_same)
                equal_ratio(a['false_known_zero_fraction'], (assigned & zero).sum(), zero.sum())
                counts['domain_count_recomputations'] += 1
    totals = defaultdict(lambda: np.zeros(len(COUNT_PATHS), np.int64))
    for r in records:
        cases = (r['case'], 'all_synthetic') if r['role'] == 'validation' else (r['case'],)
        for case in cases:
            for group in (r['group_id'], 'all_groups'):
                totals[(r['role'], case, group, r['model_id'], r['rule'], r['gate'])] += [get(r['metrics'], p) for p in COUNT_PATHS]
    summary = json.loads((out / 'domain-summary.json').read_text())['records']
    assert len(totals) == len(summary) == 10944
    for r in summary:
        key = tuple(r[k] for k in ('role', 'case', 'group_id', 'model_id', 'rule', 'gate'))
        assert np.array_equal(totals[key], [get(r['metrics'], p) for p in COUNT_PATHS])
        counts['aggregate_field_checks'] += len(COUNT_PATHS)
    report = dict(status='PASS', script_sha256=file_hash(Path(__file__)), checks=counts,
        method='Explicit unordered pair enumeration; independent flood-fill and count summation',
        source_prediction_freeze_sha256=file_hash(source / 'prediction-freeze.json'),
        input_sha256={n: file_hash(out/n) for n in ('prediction-freeze.json', 'domain-metrics.jsonl.gz', 'domain-summary.json')},
        fitting=False, encoder_inference=False, independent_reviewer=False)
    write_json(out / 'numerical-audit.json', report)
    print(json.dumps(counts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    audit(parser.parse_args().out)
