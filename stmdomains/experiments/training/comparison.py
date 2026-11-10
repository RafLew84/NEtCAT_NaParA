"""Read-only comparison of completed trials 21, 21a and 22 for decision 23.

Run from the repository root. This module only reads saved evaluations: it never
loads a model, changes a prediction or adjusts a threshold. Earlier trials with
different samples/protocols belong in the accompanying historical report.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics


TRIALS = {
    '21': ('autoencoder-21', 'autoencoder-domains'),
    '21a': ('rvae-21a', 'rvae-decoder-kl'),
    '22': ('local-ssl-22', 'local-self-supervised'),
}
KEYS = ('regime', 'family', 'latent', 'partition')
BOUNDARIES = {'two_orientations', 'orientation_8deg', 'different_spacing', 'phase_boundary'}
SEEDS = [20261101, 20261102, 20261103]
DENOMINATORS = ('planned_elements', 'scope_elements', 'full_support_elements',
                'evaluated_elements', 'positive_reference_elements',
                'known_zero_elements', 'unavailable_elements')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def primary(meta):
    return (meta.get('scale_px') == 48 and meta.get('sampler') == 'grid'
            and meta.get('latent') in (None, 32))


def distribution(values):
    """Do not turn missing denominators into zero or drop seeds silently."""
    available = [v for v in values if v is not None]
    return dict(n=len(values), available=len(available), values=values,
                median=statistics.median(available) if available else None,
                minimum=min(available) if available else None,
                maximum=max(available) if available else None)


def counts(values):
    return dict(assessments=len(values), passed=sum(v is True for v in values),
                failed=sum(v is False for v in values),
                unavailable=sum(v is None for v in values))


def group(rows, keys=KEYS):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row['metadata'].get(k) for k in keys)].append(row)
    return sorted(result.items(), key=lambda item: str(item[0]))


def summarize_metrics(rows):
    """Median/range across model seeds; pooled counts remain within samples."""
    rows = sorted(rows, key=lambda r: str(r['metadata'].get('seed')))
    result = dict(seeds=[r['metadata'].get('seed') for r in rows])
    for name in DENOMINATORS:
        result[name] = distribution([r['metrics'][name] for r in rows])
    for stage in ('before', 'after'):
        values = [r['metrics'][stage] for r in rows]
        result[stage] = {
            name: distribution([v[name] for v in values])
            for name in ('coverage', 'assigned_evaluated_elements',
                         'assigned_full_support_elements', 'domain_count_sum',
                         'false_known_zero_fraction')}
        for scope in ('pairs', 'local_pairs', 'boundary'):
            # All rows in a group share the metric schema, including null F1.
            result[stage][scope] = {
                name: distribution([v[scope][name] for v in values])
                for name in values[0][scope]}
        result[stage]['per_orientation_group'] = {
            label: {name: distribution([v['per_orientation_group'][label][name]
                                        for v in values])
                    for name in values[0]['per_orientation_group'][label]}
            for label in values[0]['per_orientation_group']}
    return result


def audit_trial(repo, issue, folder, manifest_name):
    root = repo / '.scratch' / folder
    manifest_path = repo / 'docs/stmdomains' / (manifest_name + '-manifest.json')
    manifest = read(manifest_path)
    checked = {}

    def verify(path, expected, origin):
        actual = sha(path)
        require(actual == expected, f'{issue}: hash mismatch: {path} ({origin})')
        checked[str(path.relative_to(repo))] = dict(sha256=actual, pinned_by=origin)

    for name, expected in manifest['artifacts_sha256'].items():
        verify(root / name, expected, str(manifest_path.relative_to(repo)))
    for name, expected in manifest.get('code_sha256', manifest.get('source_sha256', {})).items():
        verify(repo / name, expected, str(manifest_path.relative_to(repo)))
    freeze = read(root / 'frozen-predictions.json')
    for name, expected in freeze['code_sha256'].items():
        verify(Path(name), expected, str((root / 'frozen-predictions.json').relative_to(repo)))
    evidence = read(root / 'evaluation/evaluation-evidence.json')
    verify(root / 'frozen-predictions.json', evidence['frozen_manifest_sha256'], 'evaluation evidence')
    controls = (repo / '.scratch/training-20/controls/evaluation/manifest.json'
                if issue != '21a' else root / 'controls/evaluation/manifest.json')
    measurement = repo / '.scratch/unsupervised-input/evaluation/manifest.json'
    verify(controls, evidence['controls_manifest_sha256'], 'evaluation evidence')
    verify(measurement, evidence['measurement_manifest_sha256'], 'evaluation evidence')
    # Small input metadata and arrays are checked if pinned by the freeze.
    # The already audited tens of thousands of predictions are not rehashed.
    for name, expected in freeze.get('external_files', {}).items():
        if Path(name).name in {'manifest.json', 'split.json', 'normalization.json', 'windows.jsonl'}:
            verify(Path(name), expected, 'frozen external input metadata')
    if issue != '21':
        verify(root / 'plan.json', manifest['plan_sha256'], 'versioned plan hash')
        baseline = read(root / 'baseline-audit.json')
        verify(repo / '.scratch/autoencoder-21/frozen-predictions.json',
               baseline['frozen_manifest_sha256'], 'recorded baseline audit')
        require(read(root / 'baseline-reuse-audit.json')['passed'], 'Baseline reuse failed')
    else:
        verify(repo / 'stmdomains/experiments/training/experiment-plan.json',
               manifest['plan_sha256'], 'versioned common protocol')
    summary = read(root / 'evaluation/summary.json')
    require(summary['schema'] == 'stmdomains-training-summary-v1', 'Unexpected summary schema')
    for section, filename in [('aggregates', 'aggregates'), ('stability', 'stability'),
                              ('benefits', 'benefits'), ('criteria', 'continuation'),
                              ('ablations', 'ablations'), ('comparisons', 'pooled-comparisons')]:
        require(summary[section] == read(root / 'evaluation' / (filename + '.json')),
                f'{issue}: summary {section} differs from standalone output')
    original_pins = manifest['artifacts_sha256']
    current_only = {}
    for name in ('summary', 'pooled-comparisons', 'stability', 'benefits'):
        relative = f'evaluation/{name}.json'
        if relative not in original_pins:
            current_only[relative] = sha(root / relative)
    control_manifest = read(controls)
    result = dict(
        issue=issue, manifest=str(manifest_path.relative_to(repo)), manifest_sha256=sha(manifest_path),
        checked_hash_count=len(checked), checked=checked,
        summary_sections_match_standalone_outputs=True,
        current_hash_only_outputs=current_only,
        integrity_scope=('All versioned artifact/source pins and freeze source pins checked. '
                         'Original prediction archive audits are reused, not repeated. '
                         '21 summary/per-sample/matched-coverage details had no historical hash; '
                         'its aggregate, stability, benefits, continuation and ablation sections '
                         'match independently pinned files. Current hashes alone do not establish historical identity.'),
        control_seeds=control_manifest['seeds'],
        control_count=len(control_manifest['controls']),
        evaluation=evidence,
    )
    return root, manifest, summary, result


def summarize_trial(issue, root, manifest, summary):
    aggregates = [r for r in summary['aggregates'] if primary(r['metadata'])]
    records = [r for r in summary['records'] if primary(r['metadata'])]
    real = []
    for key, rows in group([r for r in aggregates if r['metadata']['kind'] == 'measurement']):
        expected = [None] if key[1] == 'fft' else SEEDS
        require(sorted((r['metadata']['seed'] for r in rows), key=str) == expected,
                f'{issue}: missing or duplicate model seed: {key}')
        real.append(dict(zip(KEYS, key)) | summarize_metrics(rows))
    controls = []
    for key, rows in group([r for r in records if r['metadata']['kind'] == 'synthetic'], KEYS + ('case',)):
        seeds = sorted({r['metadata']['seed'] for r in rows}, key=str)
        control_seeds = sorted({r['metadata']['control_seed'] for r in rows})
        require(len(rows) == len(seeds) * 3 and len(control_seeds) == 3,
                f'{issue}: incomplete control seed product {key}')
        values = [r['metrics']['criteria']['passed'] for r in rows]
        controls.append(dict(zip(KEYS + ('case',), key)) | dict(
            model_seeds=seeds, control_seeds=control_seeds,
            counts=counts(values),
            after_coverage=distribution([r['metrics']['after']['coverage'] for r in rows]),
            assessments=[dict(model_seed=r['metadata']['seed'],
                              control_seed=r['metadata']['control_seed'],
                              sample_id=r['metadata']['sample_id'],
                              passed=r['metrics']['criteria']['passed']) for r in rows]))
    boundary = []
    for key, rows in group([r for r in aggregates if r['metadata'].get('case') in BOUNDARIES], KEYS + ('case',)):
        boundary.append(dict(zip(KEYS + ('case',), key)) | summarize_metrics(rows))
    continuation = [r for r in summary['criteria'] if r['metadata']['latent'] in (None, 32)]
    # Link per-realization pass counts to the historically pinned continuation.
    for row in continuation:
        meta = row['metadata']
        checks = row['synthetic_controls']['checks']
        for record in records:
            rm = record['metadata']
            if rm['kind'] != 'synthetic' or any(rm[k] != meta[k] for k in KEYS):
                continue
            name = f"model_seed={rm['seed']}/case={rm['case']}/control_seed={rm['control_seed']}"
            if name in checks:
                require(checks[name] == record['metrics']['criteria']['passed'],
                        f'{issue}: per-realization criterion differs from pinned continuation')
    stability = [r for r in summary['stability'] if primary(r['metadata'])]
    stability_groups = []
    for key, rows in group(stability, KEYS + ('kind', 'case')):
        pairs = [p for r in rows for p in r['stability']['pairs']]
        stability_groups.append(dict(zip(KEYS + ('kind', 'case'), key)) | dict(
            samples=len(rows), counts=counts([r['stability']['criteria']['passed'] for r in rows]),
            coverage_spread=distribution([r['stability']['coverage_spread'] for r in rows]),
            common_assigned_fraction=distribution([p['common_assigned_fraction'] for p in pairs]),
            changed_pair_fraction=distribution([p['changed_pair_fraction'] for p in pairs]),
            compared_pairs=sum(p['compared_pairs'] for p in pairs),
            changed_pairs=sum(p['changed_pairs'] for p in pairs)))
    paired_path = root / 'evaluation/paired-model-comparisons.json'
    paired = []
    if paired_path.exists():
        for row in read(paired_path):
            if issue == '21a':
                # 21a's frozen paired output omits these invariant scope fields.
                # Its entire experiment is transfer/grid48/z32, unlike 21/22.
                row = row | dict(metadata=dict(regime='transfer', latent=32,
                                               scale_px=48, sampler='grid', **row['metadata']))
            if primary(row['metadata']):
                paired.append(row)
    return dict(issue=issue, ttmapp=real, controls=controls, boundaries=boundary,
                continuation=continuation, stability=stability_groups,
                stability_per_sample=stability,
                matched_coverage_vs_fft=[r for r in summary['comparisons'] if primary(r['metadata'])],
                benefit_vs_fft=[r for r in summary['benefits'] if primary(r['metadata'])],
                paired_model_comparisons=paired,
                before_full_assignment_vs_fft=before_comparisons(aggregates),
                primary_aggregates=aggregates)


def before_comparisons(aggregates):
    """Diagnostic comparison on the identical fully assigned reference set.

    This does not impute refused elements into final domains and is not the
    post-refusal continuation test. The frozen mean of merge/split errors is
    reused; local edges are recorded separately.
    """
    real = [r for r in aggregates if r['metadata']['kind'] == 'measurement']
    baselines = {(r['metadata']['regime'], r['metadata']['partition']): r['metrics']
                 for r in real if r['metadata']['family'] == 'fft'}
    result = []
    for row in real:
        meta, metrics = row['metadata'], row['metrics']
        if meta['family'] == 'fft':
            continue
        base = baselines[meta['regime'], meta['partition']]
        require(metrics['before']['coverage'] == base['before']['coverage'] == 1,
                'Before comparison requires full assignment on both sides')
        comparison = {}
        for scope in ('pairs', 'local_pairs'):
            baseline, candidate = base['before'][scope], metrics['before'][scope]
            for name in ('same_reference_pairs', 'different_reference_pairs'):
                require(baseline[name] == candidate[name], 'Before comparison denominator differs')
            changes = {name: candidate[name] - baseline[name]
                       if candidate[name] is not None and baseline[name] is not None else None
                       for name in ('merge_rate', 'split_rate')}
            improvement = (-sum(changes.values()) / 2
                           if all(v is not None for v in changes.values()) else None)
            comparison[scope] = dict(baseline=baseline, candidate=candidate,
                                     candidate_minus_baseline=changes,
                                     error_improvement=improvement)
        result.append(dict(metadata=meta, comparison=comparison,
                           interpretation='Before refusals on full identical reference support; component diagnostic only.'))
    return result


def verify_cross_trial(data, audits):
    def index(issue, family=None, real_only=False):
        result = {}
        for r in data[issue]['primary_aggregates']:
            m = r['metadata']
            if family is not None and m['family'] != family:
                continue
            if real_only and m['kind'] != 'measurement':
                continue
            key = tuple(m.get(k) for k in ('regime', 'family', 'latent', 'seed', 'partition', 'kind', 'case'))
            result[key] = r['metrics']
        return result
    fft21, fft22 = index('21', 'fft'), index('22', 'fft')
    require(fft21 == fft22, 'FFT21/22 primary aggregate metrics differ')
    a21, a21a = index('21', real_only=True), index('21a', real_only=True)
    old21a = {k: v for k, v in a21a.items() if k[1] in {'fft', 'ae', 'rvae'}}
    require(all(a21[k] == v for k, v in old21a.items()), 'Reused21a real baseline metrics differ')
    require(audits['21']['control_seeds'] == audits['22']['control_seeds'] == [920001, 920002, 920003],
            'Original controls differ')
    require(audits['21a']['control_seeds'] == [920011, 920012, 920013], 'Fresh control seeds differ')
    require(len({a['evaluation']['measurement_manifest_sha256'] for a in audits.values()}) == 1,
            'Real reference input differs')
    denominator_rows = {}
    for issue, item in data.items():
        for r in item['primary_aggregates']:
            m, v = r['metadata'], r['metrics']
            expected = 174 if m['regime'] == 'transfer' else 782
            if m['kind'] == 'measurement':
                require(v['evaluated_elements'] == expected, f'{issue}: changed real denominator')
                if m['regime'] == 'transfer':
                    require(v['after']['per_orientation_group']['3']['coverage'] is None,
                            'Absent YELLOW must be null')
            key = (issue if issue == '21a' and m['kind'] == 'synthetic' else 'original',
                   m['regime'], m['kind'], m['case'])
            den = {k: v[k] for k in DENOMINATORS}
            den['before_pair_counts'] = {scope: {k: v['before'][scope][k]
                                               for k in ('same_reference_pairs', 'different_reference_pairs')}
                                        for scope in ('pairs', 'local_pairs')}
            if key in denominator_rows:
                require(denominator_rows[key] == den, f'Input/support/pair scope differs: {key}')
            denominator_rows[key] = den
    return dict(passed=True, identical_primary_fft_aggregate_rows_21_22=len(fft21),
                identical_real_baseline_rows_21_21a=len(old21a),
                input_and_pair_denominator_groups_checked=len(denominator_rows),
                transfer_evaluated_windows=174, transductive_evaluated_windows=782,
                missing_transfer_yellow_preserved_as_null=True,
                controls_21_22='same 81 realizations', controls_21a='separate 81 fresh realizations',
                interpretation='Model seeds are not independent control realizations or acquisitions.')


def resource_summary(issue, root, manifest):
    runs = manifest.get('fits', manifest.get('runs'))
    audit = read(root / 'training/training-audit.json')
    resources = manifest['resources']
    for name, value in resources.items():
        require(read(root / name) == value, f'{issue}: resource record differs from versioned manifest')
    groups = []
    by_group = defaultdict(list)
    for run in runs:
        regime = run.get('regime') or ('diagnostic' if run.get('diagnostic') else 'transfer')
        latent = run.get('latent_dim') or (32 if issue == '21a' else None)
        by_group[(run['family'], regime, latent)].append(run)
    for (family, regime, latent), rows in sorted(by_group.items(), key=lambda x: str(x[0])):
        groups.append(dict(family=family, regime=regime, latent=latent, runs=len(rows),
                           seeds=[r['seed'] for r in rows],
                           parameter_counts=sorted({r['parameter_count'] for r in rows}),
                           seconds=distribution([r['seconds'] for r in rows]),
                           steps=sum(r['completed_steps'] for r in rows),
                           max_gpu_tensor_bytes=max(r['cuda_peak_allocated_bytes'] for r in rows),
                           max_rss_bytes=max(r['peak_rss_bytes'] for r in rows)))
    return dict(issue=issue, fits=len(runs), diagnostic_fits=sum(bool(r.get('diagnostic')) for r in runs),
                training_seconds=sum(r['seconds'] for r in runs),
                steps=sum(r['completed_steps'] for r in runs),
                checkpoint_bytes=audit['checkpoint_bytes'],
                max_gpu_tensor_bytes=max(r['cuda_peak_allocated_bytes'] for r in runs),
                max_rss_bytes=max(r['peak_rss_bytes'] for r in runs),
                groups=groups, resources=resources,
                postprocessing_cpu_seconds=sum(r['cpu_seconds'] for r in resources.values()),
                note='Sum each resource record once; cumulative/prior fields are not additional costs.')


def flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = f'{prefix}.{key}' if prefix else key
        if isinstance(item, dict):
            result.update(flatten(item, name))
        elif isinstance(item, list):
            result[name] = json.dumps(item, separators=(',', ':'), ensure_ascii=False)
        else:
            result[name] = item
    return result


def table(path, rows):
    rows = [flatten(r) for r in rows]
    columns = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        writer.writerows(rows)


def compact_distribution(value):
    return dict(median=value['median'], range=[value['minimum'], value['maximum']],
                values=value['values'])


def compact_ttmapp(row):
    result = {k: row[k] for k in KEYS + ('seeds',)}
    if 'source_issue' in row:
        result['source_issue'] = row['source_issue']
    result['evaluated_windows'] = row['evaluated_elements']['values'][0]
    result['full_support_windows'] = row['full_support_elements']['values'][0]
    result['before_pair_denominators'] = {
        scope: {name: row['before'][scope][name]['values'][0]
                for name in ('same_reference_pairs', 'different_reference_pairs')}
        for scope in ('pairs', 'local_pairs')}
    for stage in ('before', 'after'):
        result[stage] = {
            name: compact_distribution(row[stage][name])
            for name in ('coverage', 'assigned_evaluated_elements')}
        for scope in ('pairs', 'local_pairs'):
            result[stage][scope] = {
                name: compact_distribution(row[stage][scope][name])
                for name in ('merge_rate', 'split_rate')}
    result['after_orientation_groups'] = {
        label: {name: value['values'] for name, value in metrics.items()}
        for label, metrics in row['after']['per_orientation_group'].items()}
    return result


def markdown_tables(output, original, followup):
    def number(value, percent=False):
        if value is None:
            return 'null'
        return f'{value * (100 if percent else 1):.3f}'

    def interval(value, percent=False):
        middle = number(value['median'], percent)
        if value['median'] is None:
            return middle
        return f"{middle} [{number(value['minimum'], percent)}–{number(value['maximum'], percent)}]"

    lines = ['# Tabele 23 z zapisanych metryk', '',
             'Okno 48 px, siatka, z32. Mediana [minimum–maksimum] trzech ziaren modelu; FFT bez ziarna treningu.', '',
             'Coverage dotyczy okien z referencją i pełnym wsparciem, nie wykrywalności molekuł. Null oznacza brak mianownika lub porównania.', '',
             'Zakresy ziaren nie są przedziałami ufności. Kontrole 21/22: te same 81 realizacji; 21a: osobne 81 nowych realizacji znanych rodzin.', '']
    for title, data in [('Wspólne 21/22', original), ('Oddzielne 21a', followup)]:
        lines += [f'## {title}: TTMAPP', '',
                  '| Reżim | Cechy | Podział | Etap | Scaleń par % | Podziałów par % | Scaleń krawędzi % | Podziałów krawędzi % | Przypisania | Coverage % |',
                  '| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for row in data['ttmapp']:
            for stage in ('before', 'after'):
                values = row[stage]
                fields = [row['regime'], row['family'], row['partition'], stage]
                fields += [interval(values[scope][name], True)
                           for scope in ('pairs', 'local_pairs') for name in ('merge_rate', 'split_rate')]
                fields += [f"{values['assigned_evaluated_elements']['values']} / {row['evaluated_elements']['values'][0]}",
                           interval(values['coverage'], True)]
                lines.append('| ' + ' | '.join(fields) + ' |')
        lines += ['', f'## {title}: kontrole po odmowach', '',
                  'Licznik: spełnione kryteria; mianownik: oceny (3 ziarna modelu × 3 realizacje kontroli, FFT tylko 3 realizacje).', '',
                  '| Reżim | Cechy | Podział | Kontrola | Zaliczone / ocenione | Niedostępne |',
                  '| --- | --- | --- | --- | ---: | ---: |']
        for row in data['controls']:
            count = row['counts']
            lines.append('| ' + ' | '.join([row['regime'], row['family'], row['partition'], row['case'],
                                           f"{count['passed']} / {count['assessments']}", str(count['unavailable'])]) + ' |')
        lines += ['', f'## {title}: granice', '',
                  'F1 liczone tylko dla styku dwóch dodatnich domen, z tolerancją 8 reference_px. Kontrole trzech realizacji łączone na poziomie liczników osobno dla każdego ziarna modelu.', '',
                  '| Reżim | Cechy | Podział | Kontrola | F1 przed | F1 po |',
                  '| --- | --- | --- | --- | ---: | ---: |']
        for row in data['boundaries']:
            lines.append('| ' + ' | '.join([row['regime'], row['family'], row['partition'], row['case'],
                                           interval(row['before']['boundary']['f1']),
                                           interval(row['after']['boundary']['f1'])]) + ' |')
        lines += ['', f'## {title}: wspólne przypisania TTMAPP względem FFT po odmowach', '',
                  'Ocena błędów wymaga wspólnego coverage ≥20% oraz obu rodzajów par.', '',
                  '| Reżim | Cechy | Podział | Wspólne coverage % | Zmiana średniego błędu, pp |',
                  '| --- | --- | --- | ---: | ---: |']
        for key, rows in group([r for r in data['matched_coverage_vs_fft'] if r['metadata']['kind'] == 'measurement']):
            fields = [key[0], key[1], key[3]]
            fields += [interval(distribution([r['comparison'][name] for r in rows]), True)
                       for name in ('common_coverage', 'common_error_improvement')]
            lines.append('| ' + ' | '.join(fields) + ' |')
        lines += ['', f'## {title}: zmiana błędu TTMAPP względem FFT przed odmowami', '',
                  'Obie procedury przypisują 100% tego samego zakresu. Dodatnia zmiana oznacza spadek średniej (merge+split)/2. To diagnostyka składnika, bez zaliczenia końcowych kryteriów domen.', '',
                  '| Reżim | Cechy | Podział | Poprawa wszystkich par, pp | Poprawa krawędzi, pp |',
                  '| --- | --- | --- | ---: | ---: |']
        for key, rows in group(data['before_full_assignment_vs_fft']):
            fields = [key[0], key[1], key[3]]
            fields += [interval(distribution([r['comparison'][scope]['error_improvement'] for r in rows]), True)
                       for scope in ('pairs', 'local_pairs')]
            lines.append('| ' + ' | '.join(fields) + ' |')
        lines += ['', f'## {title}: stabilność TTMAPP po odmowach', '',
                  'Kryteria liczone per klatka. Brak wspólnych przypisań nie zalicza stabilności; poniższe rozkłady obejmują klatki, a zmiany relacji wszystkie pary ziaren.', '',
                  '| Reżim | Cechy | Podział | Zaliczone klatki | Rozstęp coverage, pp | Wspólna część, % | Zmienione relacje, % |',
                  '| --- | --- | --- | ---: | ---: | ---: | ---: |']
        for row in data['stability']:
            if row['kind'] != 'measurement':
                continue
            fields = [row['regime'], row['family'], row['partition'],
                      f"{row['counts']['passed']} / {row['counts']['assessments']}"]
            fields += [interval(row[name], True) for name in
                       ('coverage_spread', 'common_assigned_fraction', 'changed_pair_fraction')]
            lines.append('| ' + ' | '.join(fields) + ' |')
        lines.append('')
    (output / 'tables.md').write_text('\n'.join(lines) + '\n')


def build(repo, output, destination=None):
    repo, output = repo.resolve(), output.resolve()
    require(output != repo and repo not in output.parents or output.is_relative_to(repo / '.scratch'),
            'Generated output must be outside the repository or inside .scratch')
    output.mkdir(parents=True, exist_ok=True)
    data, audits, costs = {}, {}, []
    for issue, (folder, manifest_name) in TRIALS.items():
        root, manifest, summary, audit = audit_trial(repo, issue, folder, manifest_name)
        data[issue] = summarize_trial(issue, root, manifest, summary)
        audits[issue] = audit
        costs.append(resource_summary(issue, root, manifest))
        del summary
    consistency = verify_cross_trial(data, audits)
    # The common FFT is retained once; its identity across trials was checked.
    original = {name: [dict(source_issue=issue, **row)
                       for issue in ('21', '22') for row in data[issue][name]
                       if not (issue == '22' and row.get('family', row.get('metadata', {}).get('family')) == 'fft')]
                for name in ('ttmapp', 'controls', 'boundaries', 'continuation', 'stability',
                             'matched_coverage_vs_fft', 'benefit_vs_fft', 'paired_model_comparisons',
                             'before_full_assignment_vs_fft')}
    followup = {k: v for k, v in data['21a'].items()
                if k not in {'primary_aggregates', 'stability_per_sample'}}
    require(costs[0]['fits'] + costs[2]['fits'] == 27, 'Original fit budget count differs')
    require(costs[1]['fits'] == 11 and costs[1]['diagnostic_fits'] == 2, 'Followup fit count differs')
    totals = dict(original21_22_fits=27, original21_22_seconds=costs[0]['training_seconds'] + costs[2]['training_seconds'],
                  original21_22_checkpoint_bytes=costs[0]['checkpoint_bytes'] + costs[2]['checkpoint_bytes'],
                  original21_22_postprocessing_cpu_seconds=costs[0]['postprocessing_cpu_seconds'] + costs[2]['postprocessing_cpu_seconds'],
                  separate21a_full_fits=9, separate21a_diagnostic_fits=2,
                  separate21a_seconds=costs[1]['training_seconds'])
    definitions = dict(
        primary='grid48; z32 primary; all three model seeds, FFT has no training seed',
        coverage='Assigned evaluated grid windows / evaluated windows with full support; not molecule detection accuracy or material area.',
        before='Feature/relation components before order and connected-size refusals.',
        after='Candidate domains after frozen order gate and connected-size filtering.',
        boundaries='Only four contacting positive-domain synthetic cases; tolerance 8 reference pixels; never exact TTMAPP contours.',
        uncertainty='Ranges across the three seeds, not confidence intervals; one correlated acquisition.',
        control_counts='For learned models: 3 model seeds x 3 control realizations = 9 assessments per case. FFT: 3 realizations. No pooling into independent acquisitions.',
        transfer='Same-acquisition spatially held-out test graph only. Partial BLACK/RED; absent YELLOW remains null.',
        transductive='Whole available partial-reference interiors; distinct denominator and inference scope.',
        matched='Frozen ACF ranking and achieved assignment intersection only; common coverage below 0.20 or a missing pair kind makes error gain unavailable.',
        control_reuse='21/22 original81 are development evidence after viewing in21. Fresh21a controls use separate realizations of known families.',
    )
    write(output / 'comparison.json', dict(schema='stmdomains-training-comparison23-v1',
                                          definitions=definitions, original21_22=original,
                                          separate21a=followup, resource_costs=costs,
                                          budget_totals=totals, consistency=consistency))
    write(output / 'input-audit.json', dict(schema='stmdomains-comparison23-input-audit-v1',
                                           trials=audits, cross_trial=consistency))
    write(output / 'stability-per-sample.json', {issue: value['stability_per_sample'] for issue, value in data.items()})
    for name in ('ttmapp', 'controls', 'boundaries', 'stability'):
        table(output / (name + '-original21-22.csv'), original[name])
        table(output / (name + '-separate21a.csv'), followup[name])
    table(output / 'costs.csv', costs)
    table(output / 'continuation.csv', original['continuation'] + [dict(source_issue='21a', **r) for r in followup['continuation']])
    markdown_tables(output, original, followup)
    compact = dict(
        schema='stmdomains-training-comparison23-manifest-v1',
        scope='Read-only aggregation; no training, new predictions, selection, threshold changes or application acceptance.',
        source_manifests={issue: dict(path=a['manifest'], sha256=a['manifest_sha256']) for issue, a in audits.items()},
        source_sha256={'stmdomains/experiments/training/comparison.py': sha(Path(__file__))},
        output=str(output.relative_to(repo)) if output.is_relative_to(repo) else str(output),
        command='python -m stmdomains.experiments.training.comparison --output .scratch/training-comparison-23 --manifest docs/stmdomains/training-comparison-manifest.json',
        definitions=definitions, consistency=consistency, budget_totals=totals,
        ttmapp=[compact_ttmapp(r) for r in original['ttmapp']],
        separate21a_ttmapp=[compact_ttmapp(r) for r in followup['ttmapp']],
        detailed_tables='tables.md and CSV files in the output directory; all seeds retained in comparison.json',
        resource_costs=[{k: v for k, v in r.items() if k != 'resources'} for r in costs],
        continuation=[{k: r[k] for k in ('source_issue', 'metadata', 'continuation', 'stability', 'benefit')}
                      for r in original['continuation'] + [dict(source_issue='21a', **r) for r in followup['continuation']]],
        artifacts_sha256={p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()},
        historical_integrity_limit=audits['21']['integrity_scope'],
    )
    if destination is not None:
        write(destination, compact)
    return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    result = build(args.repo, args.output, args.manifest)
    print(json.dumps(dict(consistency=result['consistency'], costs=result['budget_totals'])))


if __name__ == '__main__':
    main()
