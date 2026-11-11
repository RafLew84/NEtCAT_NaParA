"""E7 data publication uses mock renderer data, never an encoder or real labels."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from stmdomains.experiments import e7_data
from stmdomains.experiments.bundle import file_hash, write_arrays


def arrays(value=0.):
    xy = np.array([[48., 48.]])
    return dict(image=np.full((96, 96), value), measured=np.ones((96, 96), bool),
                centers_xy=xy, boxes_xyxy=np.array([[46., 46., 50., 50.]]), object_ids=np.array(['m0']))


def fake_bank(tmp_path):
    source = tmp_path / 'source'
    groups, row_sets = {}, {}
    image = arrays()
    for i in range(24):
        ident = f'ttmapp-{i:03}'
        relative = f'samples/{ident}.npz'
        digest = write_arrays(source / relative, image)
        record = dict(sample_id=ident, kind='measurement', file=relative, pixel_spacing_xy=[1., 1.],
                      frame_number=i, origin_in_expanded_xy=[0., 0.], **digest)
        group_id = f'{ident}/centers/s48'
        groups[group_id] = dict(group_id=group_id, sampler='centers', record=record, analysis=str(source))
        row_sets[group_id] = [dict(window_id=f'{ident}/centers/m0/s48', sample_id=ident,
                                  element_id='m0', raw_edge_xy=[48., 48.], sampler='centers',
                                  scale_px=48, scale_raw_px=48, available=True)]
    inputs = SimpleNamespace(groups=groups, sample=lambda g: (g['record'], image),
                             rows=lambda g: row_sets[g['group_id']])
    return SimpleNamespace(inputs=inputs)


def test_all_seed_families_stay_in_one_split_and_stm_bytes_rows_are_preserved(tmp_path, monkeypatch):
    calls = []

    def renderer(case, seed):
        calls.append((case, seed))
        image = arrays(seed / 1e6)
        truth = dict(domain_labels=np.ones((96, 96), np.int16), evaluation_valid=np.ones((96, 96), bool))
        meta = dict(case=case, seed=seed, pixel_spacing_xy=[1., 1.])
        if case == 'inverted':
            meta['base_pair'] = 'single'
        if case == 'empty_gap':
            meta['pair_case'] = 'missing_band'
        return image, truth, meta

    monkeypatch.setattr(e7_data.controls, 'make_control', renderer)
    bank = fake_bank(tmp_path)
    out = tmp_path / 'out'
    entries, files = e7_data.prepare_data(bank, out)
    assert len(entries) == 186 and len(calls) == 162
    assert sum(e['role'] == 'train' for e in entries) == 81
    assert sum(e['role'] == 'validation' for e in entries) == 81
    truth_index = json.loads((out / 'truths/index.json').read_text())
    for seed in e7_data.TRAIN_SEEDS + e7_data.VALIDATION_SEEDS:
        cohort = [r for r in truth_index if r['seed'] == seed]
        assert len(cohort) == 27 and len({r['group_id'] for r in cohort}) == 1
        assert len({r['role'] for r in cohort}) == 1
        assert {r['case'] for r in cohort} == set(e7_data.controls.CASES)
        lookup = {r['case']: r for r in cohort}
        assert lookup['inverted']['base_sample_id'] == lookup['single']['sample_id']
        assert lookup['empty_gap']['paired_sample_id'] == lookup['missing_band']['sample_id']
    for entry in entries:
        assert 'case' not in entry and 'seed' not in entry
        assert 'case' not in entry['record'] and 'seed' not in entry['record']
        if entry['kind'] == 'measurement':
            group = bank.inputs.groups[entry['cache_group']]
            assert entry['truth_file'] is None
            assert (out / entry['source_file']).read_bytes() == (Path(group['analysis']) / group['record']['file']).read_bytes()
            assert json.loads((out / entry['rows_file']).read_text()) == bank.inputs.rows(group)
        else:
            expected = 'training_truth/' if entry['role'] == 'train' else 'evaluation_truth/'
            assert entry['truth_file'].startswith(expected)
        assert file_hash(out / entry['rows_file']) == entry['rows_sha256']
    assert all(file_hash(out / name) == digest for name, digest in files.items())
    with pytest.raises(FileExistsError):
        e7_data.prepare_data(bank, out)


def test_duplicate_synthetic_inputs_across_roles_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(e7_data.controls, 'make_control', lambda case, seed:
        (arrays(), dict(domain_labels=np.ones((96, 96), np.int16)),
         dict(case=case, seed=seed, pixel_spacing_xy=[1., 1.])))
    with pytest.raises(ValueError, match='Identical complete synthetic inputs'):
        e7_data.prepare_data(fake_bank(tmp_path), tmp_path / 'out')
