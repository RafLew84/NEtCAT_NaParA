import json
from pathlib import Path

import numpy as np
import pytest

from stmdomains.experiments import e7_evaluate as module
from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.e7_probe import specs


def test_complete_mini_gallery_preserves_physical_quality_denominator(tmp_path, monkeypatch):
    out = tmp_path / 'out'
    out.mkdir()
    reference_dir = tmp_path / '.scratch/unsupervised-input/evaluation'
    reference_dir.mkdir(parents=True)
    write_json(reference_dir / 'manifest.json', {'references': []})
    monkeypatch.setattr(module, 'REPO', tmp_path)
    labels = np.ones((64, 64), np.int16)
    labels[:, 30:] = 2
    truth = {'domain_labels': labels, 'evaluation_valid': np.ones_like(labels, bool)}
    real_truth = {'region_instances': labels, 'evaluation_valid': truth['evaluation_valid']}
    monkeypatch.setattr(module, '_truth_bundle', lambda *args: ({'references': []}, {'ttmapp-259': ({}, real_truth)}))
    entries, index, truths = [], [], []
    for ident, kind, role in (('fresh', 'synthetic', 'validation'), ('ttmapp-259', 'measurement', 'stm_development')):
        source_file, rows_file, truth_file = f'{ident}.npz', f'{ident}.json', f'{ident}-truth.npz'
        xy = [[20., 20.], [26., 20.], [32., 20.]]
        np.savez(out / source_file, image=np.arange(4096).reshape(64, 64), measured=np.ones((64, 64), bool))
        rows = [dict(element_id=str(i), raw_edge_xy=point, available=True, transfer_split=None)
                for i, point in enumerate(xy)]
        write_json(out / rows_file, rows)
        np.savez(out / truth_file, **truth)
        entry = dict(sample_id=ident, kind=kind, role=role, group_id=ident, source_file=source_file,
                     rows_file=rows_file, truth_file=truth_file if kind == 'synthetic' else None,
                     record=dict(frame_number=259, pixel_spacing_xy=[1., 1.]))
        entries.append(entry)
        if kind == 'synthetic':
            truths.append(dict(sample_id=ident, case='two_orientations', sha256=file_hash(out / truth_file)))
        for spec in specs():
            relative = f"{ident}-{spec['id']}.npz"
            valid = np.array([True, True, False])
            data = dict(available=np.ones(3, bool), common_valid=valid, learned_valid=valid,
                        historical_valid=valid, hard=np.ones(3, bool), full_gate=np.zeros(3, bool),
                        edges=np.array([[0, 1], [1, 2]]), learned_score=np.array([.9, np.nan]),
                        historical_distance=np.array([.1, np.nan]))
            for head in ('learned', 'historical'):
                for method in ('fh4', 'mws'):
                    for stage in ('before', 'H_M1', 'A_fixed_M1'):
                        data[f'{head}__{method}__{stage}'] = np.array([1, 1, 0]) if stage != 'A_fixed_M1' else np.zeros(3, int)
            if spec['id'] == 'geometry':
                data['historical_valid'] = np.array([True, False, False])
                data['historical_distance'][:] = np.nan
                for key in data:
                    if key.startswith('historical__'): data[key][:] = 0
            np.savez(out / relative, **data)
            index.append(dict(entry, model_id=spec['id'], family=spec['family'], seed=spec['seed'], prediction_file=relative))
    write_json(out / 'truths/index.json', truths)
    counts = module.evaluate(out, entries, index, {}, lambda: None)
    assert counts['samples'] == 2
    assert counts['gallery_runs'] == 32
    summary = json.loads((out / 'domain-summary.json').read_text())['records']
    chosen = next(r for r in summary if r['role'] == 'stm_development' and r['model_id'] == 'geometry'
                  and r['head'] == 'learned' and r['partition'] == 'fh4' and r['variant'] == 'H_M1')
    assert chosen['metrics']['positive_reference_elements'] == 3
    assert chosen['metrics']['after']['positive_reference_coverage'] == pytest.approx(2 / 3)
    assert (out / 'index.html').exists()
    pair_rows = json.loads((out / 'pair-summary.json').read_text())['records']
    primary = [r for r in pair_rows if r['role'] == 'stm_development' and r['group_id'] == 'all_groups'
               and r['head'] == 'learned' and r['comparison'] == 'learned_common']
    assert len(primary) == 8
    assert {r['metrics']['counts']['scored_pairs'] for r in primary} == {1}
    legacy_pair = next(r for r in pair_rows if r['model_id'] == 'geometry' and r['role'] == 'stm_development'
                       and r['head'] == 'learned' and r['comparison'] == 'historical_matched')
    assert legacy_pair['metrics']['counts']['scored_pairs'] == 0
