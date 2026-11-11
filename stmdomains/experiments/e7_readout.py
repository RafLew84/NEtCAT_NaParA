"""Readable post-freeze E7 tables; no fitting or prediction changes."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from .bundle import file_hash, write_json
from .e5_readout import write_csv
from .e7_evaluate import model_label
from .e7_probe import specs


def readout(out):
    out = Path(out)
    names = ('domain-summary.json', 'pair-summary.json', 'probe-fit-audit.json',
             'truths/index.json', 'manifest.json')
    inputs = {name: file_hash(out / name) for name in names}
    domains = json.loads((out / names[0]).read_text())['records']
    pairs = json.loads((out / names[1]).read_text())['records']
    census = json.loads((out / names[2]).read_text())['samples']
    truth = {r['sample_id']: r for r in json.loads((out / names[3]).read_text())}
    training = [dict(r, case=truth[r['sample_id']]['case']) for r in census]
    train_cases = defaultdict(lambda: dict(same=0, different=0, calibration_edges=0))
    for row in training:
        cell = train_cases[row['case']]
        cell['same'] += row['selected_same']
        cell['different'] += row['selected_different']
        cell['calibration_edges'] += row['usable_train_edges']
    domain_rows, pair_rows = [], []
    for row in domains:
        if row['group_id'] != 'all_groups' or row['case'] not in ('all_synthetic', 'measurement'):
            continue
        m = row['metrics']
        a = m['after']
        domain_rows.append(dict(
            **{k: row[k] for k in ('role', 'case', 'model_id', 'head', 'partition', 'variant')},
            positive_reference=m['positive_reference_elements'], assigned_positive=a['pairs']['assigned_elements'],
            coverage=a['positive_reference_coverage'], merge_rate=a['pairs']['merge_rate'],
            split_rate=a['pairs']['split_rate'], merged_pairs=a['pairs']['merged_pairs'],
            different_pairs=a['pairs']['different_reference_pairs'], split_pairs=a['pairs']['split_pairs'],
            same_pairs=a['pairs']['same_reference_pairs'], false_zero=a['false_known_zero_assignments'],
            known_zero=m['known_zero_elements'], false_zero_rate=a['false_known_zero_fraction']))
    for row in pairs:
        if row['group_id'] != 'all_groups' or row['case'] not in ('all_synthetic', 'measurement'):
            continue
        m = row['metrics']
        pair_rows.append(dict(**{k: row[k] for k in ('role', 'case', 'model_id', 'head', 'comparison')},
                              **m['counts'], roc_auc=m['roc_auc'], average_precision=m['average_precision'],
                              fixed_threshold=m.get('fixed_threshold')))
    result = dict(domain_rows=domain_rows, pair_rows=pair_rows, training_by_case=dict(train_cases),
                  aggregation='Counts pooled within each model/role across frames; never across model seeds',
                  limitation='Synthetic renderer-family validation; known partial STM development only')
    write_json(out / 'readout.json', result)
    write_csv(out / 'readout-domains.csv', domain_rows)
    write_csv(out / 'readout-pairs.csv', pair_rows)
    write_csv(out / 'training-census.csv', training)
    labels = {s['id']: model_label(s) for s in specs()}
    tables = []
    def percent(value):
        return '—' if value is None else f'{100*value:.2f}'
    for case in ('all_synthetic', 'measurement'):
        for method in ('fh4', 'mws'):
            tables += [f'## {case}, {method}, H_M1', '',
                       '| Uczony odczyt | Pokrycie % | Błędne scalenia % | Błędne podziały % | Fałszywe zera % |',
                       '|---|---:|---:|---:|---:|']
            for row in domain_rows:
                if (row['case'], row['partition'], row['variant'], row['head']) != (case, method, 'H_M1', 'learned'):
                    continue
                values = [percent(row[key]) for key in ('coverage', 'merge_rate', 'split_rate', 'false_zero_rate')]
                tables.append('| ' + ' | '.join([labels[row['model_id']], *values]) + ' |')
            tables.append('')
    (out / 'readout-tables.md').write_text('\n'.join(tables))
    outputs = ('readout.json', 'readout-domains.csv', 'readout-pairs.csv', 'training-census.csv', 'readout-tables.md')
    write_json(out / 'readout-manifest.json', dict(
        code_sha256=file_hash(Path(__file__)), input_sha256=inputs,
        output_sha256={name: file_hash(out / name) for name in outputs},
        predictions_modified=False, fitting=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    readout(parser.parse_args().out)
