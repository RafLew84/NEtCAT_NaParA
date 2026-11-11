"""Post-freeze E7a counts and predeclared paired contrasts, without model selection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bundle import file_hash, write_json
from .e5_readout import write_csv
from .e7a_predict import RULES


def flatten(record):
    m, a = record['metrics'], record['metrics']['after']
    result = {k: v for k, v in record.items() if k != 'metrics'}
    result.update(reference=m['positive_reference_elements'], assigned=a['pairs']['assigned_elements'],
        coverage=a['positive_reference_coverage'], merge=a['pairs']['merge_rate'], split=a['pairs']['split_rate'],
        merged_pairs=a['pairs']['merged_pairs'], different_pairs=a['pairs']['different_reference_pairs'],
        split_pairs=a['pairs']['split_pairs'], same_pairs=a['pairs']['same_reference_pairs'],
        false_zero=a['false_known_zero_assignments'], known_zero=m['known_zero_elements'],
        false_zero_rate=a['false_known_zero_fraction'])
    return result


def comparison(base, trial):
    directions = dict(coverage=1, merge=-1, split=-1, false_zero_rate=-1)
    changes, missing = {}, []
    for key, direction in directions.items():
        before, after = base[key], trial[key]
        if before is None and after is None:
            continue
        if before is None or after is None:
            missing.append(key)
        else:
            changes[key] = (after-before) * direction
    if missing or not changes:
        status = 'incomplete_comparison'
    elif any(delta < -1e-12 for delta in changes.values()):
        status = 'tradeoff_or_worse'
    elif any(delta > 1e-12 for delta in changes.values()):
        status = 'improves_observed_metrics_without_cost'
    else:
        status = 'unchanged_observed_metrics'
    return dict(status=status, missing=missing, improvement_signed_deltas=changes,
                scope='Observed metrics only; absent real negative/boundary reference is not certification')


def readout(out):
    out = Path(out)
    summary_path = out / 'domain-summary.json'
    records = json.loads(summary_path.read_text())['records']
    rows = [flatten(r) for r in records]
    keys = ('role', 'case', 'group_id', 'model_id', 'gate')
    lookup = {tuple(r[k] for k in keys)+(r['rule'],): r for r in rows}
    rules = {r['id']: r for r in RULES}
    contrasts = []
    for trial in rows:
        rule = rules[trial['rule']]
        if rule['baseline'] == rule['id']:
            continue
        base = lookup[tuple(trial[k] for k in keys)+(rule['baseline'],)]
        contrasts.append(dict(**{k: trial[k] for k in keys}, rule=rule['id'], baseline=rule['baseline'],
                              **comparison(base, trial), base=base, trial=trial))
    write_json(out / 'readout.json', dict(records=rows, contrasts=contrasts,
        primary='mws_t050 versus e7_mws, H_M1; all eight models and both data roles',
        aggregation='Counts within model/role; no pooling encoder seeds; development-only'))
    write_csv(out / 'readout-domains.csv', rows)
    write_csv(out / 'readout-contrasts.csv', contrasts)
    main = [r for r in rows if r['group_id'] == 'all_groups' and r['gate'] == 'H_M1'
            and r['case'] in ('all_synthetic', 'measurement', 'independent_rows')]
    lines = ['# E7a — wszystkie zamrożone reguły, H_M1', '',
             'Agregacja liczników per model; błędy par warunkowe na przypisaniu.', '']
    def percent(value):
        return '—' if value is None else f'{100*value:.2f}'
    for case in ('all_synthetic', 'measurement', 'independent_rows'):
        lines += [f'## {case}', '', '| Model | Reguła | Pokrycie % | Scalenia % | Podziały % | Fałszywe zera % |',
                  '|---|---|---:|---:|---:|---:|']
        for r in main:
            if r['case'] != case: continue
            lines.append('| '+' | '.join([r['model_id'], r['rule']]+[percent(r[k]) for k in
                          ('coverage', 'merge', 'split', 'false_zero_rate')])+' |')
        lines.append('')
    (out / 'readout-tables.md').write_text('\n'.join(lines))
    names = ('readout.json', 'readout-domains.csv', 'readout-contrasts.csv', 'readout-tables.md')
    write_json(out / 'readout-manifest.json', dict(code_sha256=file_hash(Path(__file__)),
        input_sha256=file_hash(summary_path), outputs={n: file_hash(out/n) for n in names},
        predictions_modified=False, model_selection=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    readout(parser.parse_args().out)
