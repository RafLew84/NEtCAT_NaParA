import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from stmdomains.experiments import e7a_evaluate as module
from stmdomains.experiments.bundle import write_json
from stmdomains.experiments.e5_evaluate import valid_reference
from stmdomains.experiments.e7_probe import specs
from stmdomains.experiments.e7a_predict import predict_all
from stmdomains.experiments.training.evaluate import evaluate_sample
from test_e7a_predict import fixture_data


def test_evaluation_replays_e7_and_preserves_quality_denominator(tmp_path, monkeypatch):
    source, out = tmp_path / 'source', tmp_path / 'out'
    source.mkdir(); out.mkdir()
    ref_dir = tmp_path / '.scratch/unsupervised-input/evaluation'
    ref_dir.mkdir(parents=True)
    write_json(ref_dir / 'manifest.json', {'references': []})
    monkeypatch.setattr(module, 'REPO', tmp_path)
    rows, data, calibration = fixture_data()
    truth = dict(region_instances=np.ones((64, 64), int), evaluation_valid=np.ones((64, 64), bool))
    monkeypatch.setattr(module, '_truth_bundle', lambda *a: ({'references': []}, {'ttmapp-259': ({}, truth)}))
    np.savez(source / 'image.npz', image=np.arange(4096).reshape(64, 64), measured=np.ones((64, 64), bool))
    write_json(source / 'rows.json', rows)
    write_json(source / 'truths/index.json', [])
    entry = dict(sample_id='ttmapp-259', kind='measurement', role='stm_development', group_id='one-acquisition',
                 source_file='image.npz', rows_file='rows.json', truth_file=None, record=dict(frame_number=259))
    write_json(source / 'data-index.json', [entry])
    index, old_records = [], []
    for spec in specs():
        name = spec['id']
        np.savez(source / f'{name}.npz', **data)
        write_json(source / f'{name}.json', dict(calibration=calibration))
        index.append(dict(entry, model_id=name, family=spec['family'], seed=spec['seed'],
                          prediction_file=f'{name}.npz', model_file=f'{name}.json'))
        for method in ('fh4', 'mws'):
            for gate in ('H_M1', 'A_fixed_M1'):
                after = data[f'learned__{method}__{gate}']
                metric = evaluate_sample(rows, truth['region_instances'], data[f'learned__{method}__before'],
                    after, data['edges'], evaluation_valid=valid_reference(truth),
                    regime='transductive', kind='measurement',
                    states=np.where(after > 0, 'ordered_untyped', 'ambiguous'))
                old_records.append(dict(sample_id='ttmapp-259', model_id=name, partition=method,
                                        variant=gate, head='learned', metrics=metric))
    with gzip.open(source / 'domain-metrics.jsonl.gz', 'wt') as stream:
        for row in old_records: stream.write(json.dumps(row) + '\n')
    new_index, _ = predict_all(source, out, index)
    counts = module.evaluate(source, out, new_index)
    assert counts['baseline_metric_replays'] == 32
    assert counts['gallery_runs'] == 48 and counts['domain_evaluations'] == 96
    summary = json.loads((out / 'domain-summary.json').read_text())['records']
    selected = next(r for r in summary if r['model_id'] == 'geometry' and r['rule'] == 'mws_t050'
                    and r['gate'] == 'H_M1' and r['group_id'] == 'all_groups')
    assert selected['metrics']['positive_reference_elements'] == 10
    assert selected['metrics']['after']['positive_reference_coverage'] == pytest.approx(.9)
    assert selected['metrics']['after']['pairs']['merge_rate'] is None
    assert 'E7a' in (out / 'index.html').read_text()
