"""E7 fresh synthetic encoding and cached STM branches with mock-only models."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from stmdomains.experiments import e7_features
from stmdomains.experiments.bundle import file_hash, write_arrays, write_json
from stmdomains.experiments.training.predict import synthetic_rows


class EncoderOnly(torch.nn.Module):
    latent_dim = 32

    def __init__(self, family):
        super().__init__()
        self.family, self.calls = family, 0
        self.inputs = []
        self.run_config = dict(data=dict(normalizer=dict(low=-2., high=2.)))

    def encode(self, image):
        self.calls += 1
        self.inputs.append(image.cpu().numpy().copy())
        mean = image.mean((1, 2, 3))
        content = torch.arange(1., 33.)[None] + mean[:, None]
        return dict(content=content, angle_radians=mean,
                    translation_normalized_xy=torch.zeros((len(image), 2)))

    def forward(self, *_args):
        raise AssertionError('Decoder must not run')


def fixture(tmp_path):
    yy, xx = np.mgrid[:96, :96]
    xy = np.array([[48., 48.], [60., 48.], [10., 10.]])
    arrays = dict(image=np.cos(xx / 2.) + np.cos(yy / 3.), measured=np.ones((96, 96), bool),
                  centers_xy=xy, boxes_xyxy=np.column_stack((xy - 1, xy + 1)), object_ids=np.array(['a', 'b', 'c']))
    entries = []
    for sample_id, kind, role in (('new', 'synthetic', 'train'), ('stm', 'measurement', 'stm_development')):
        source = f'analysis/samples/{sample_id}.npz'
        digest = write_arrays(tmp_path / source, arrays)
        record = dict(sample_id=sample_id, kind=kind, pixel_spacing_xy=[1., 1.], **digest)
        rows = [r for r in synthetic_rows(record, arrays) if r['sampler'] == 'centers' and r['scale_px'] == 48]
        rows_file = f'rows/{sample_id}.json'
        write_json(tmp_path / rows_file, rows)
        entries.append(dict(sample_id=sample_id, kind=kind, role=role, group_id=sample_id,
                            record=record, source_file=source, rows_file=rows_file,
                            rows_sha256=file_hash(tmp_path / rows_file),
                            cache_group='old/centers/s48', truth_file='must-not-be-opened.npz'))
    old_rows = json.loads((tmp_path / entries[-1]['rows_file']).read_text())
    desc = dict(available=np.array([True, True, False]), valid=np.array([True, True, False]),
                acf_score=np.array([.8, .8, np.nan]), second_direction_ratio=np.array([.8, .8, np.nan]),
                energy=np.array([1., 1., np.nan]))
    read = []

    def cached_features(run, group):
        read.append(run)
        dimension = 8 if '/geometry' in run else 3 if '/photometry' in run else 34 if '/rvae_full/' in run else 32
        values = np.full((3, dimension), 7.)
        values[2] = np.nan
        return values

    inputs = SimpleNamespace(threshold=.1, group=lambda group: group, rows=lambda group: old_rows,
                             descriptor=lambda group, regime: desc)
    lineage = dict(runs={f'transfer/{family}/z32/seed-{seed}': dict(checkpoint='mock-only', checkpoint_sha256='mock')
                         for family in ('ae', 'rvae') for seed in e7_features.SEEDS},
                   normalization_path='mock', normalization_sha256='mock')
    bank = SimpleNamespace(inputs=inputs, features=cached_features, audit=lambda: dict(checkpoint_lineage=lineage))
    models = {(family, seed): EncoderOnly(family) for family in ('ae', 'rvae') for seed in e7_features.SEEDS}
    return bank, models, entries, read


def test_fresh_synthetic_all_six_encoders_but_stm_only_reads_frozen_transfer_cache(tmp_path, monkeypatch):
    bank, models, entries, read = fixture(tmp_path)
    monkeypatch.setattr(e7_features, 'models_for', lambda bank, regime: models)
    result, files = e7_features.prepare_features(bank, tmp_path, entries)
    assert all(model.calls == 1 for model in models.values())
    assert len(read) == 8 and all(run.startswith('transfer/') for run in read)
    for entry in result:
        with np.load(tmp_path / entry['features_file'], allow_pickle=False) as z:
            assert z['edges'].shape == (1, 2)
            np.testing.assert_array_equal(z['edges'], [[0, 1]])
            assert z['available'].tolist() == [True, True, False]
            for seed in e7_features.SEEDS:
                assert z[f'ae_{seed}'].shape == (3, 32)
                assert z[f'rvae_{seed}'].shape == (3, 34)
                assert np.isnan(z[f'ae_{seed}'][2]).all()
                if entry['kind'] == 'measurement':
                    assert (z[f'ae_{seed}'][:2] == 7.).all()
                else:
                    np.testing.assert_allclose(np.linalg.norm(z[f'rvae_{seed}'][:2], axis=1), 1., rtol=1e-6)
    assert all(file_hash(tmp_path / name) == digest for name, digest in files.items())
    provenance = json.loads((tmp_path / 'feature-provenance.json').read_text())
    assert provenance['stm_encoder_inference'] is False and provenance['truth_files_opened'] is False
    schedule = json.loads((tmp_path / 'feature-schedule.json').read_text())
    assert schedule['seed'] == 20261117
    assert schedule['sample_ids'] == [entry['sample_id'] for entry in result]


def test_tampered_published_source_is_rejected_before_forward(tmp_path, monkeypatch):
    bank, models, entries, _ = fixture(tmp_path)
    monkeypatch.setattr(e7_features, 'models_for', lambda bank, regime: models)
    (tmp_path / entries[0]['source_file']).write_bytes(b'not the published arrays')
    with pytest.raises(ValueError, match='path/hash mismatch'):
        e7_features.prepare_features(bank, tmp_path, entries)
    assert all(model.calls == 0 for model in models.values())


def test_empty_centers_do_not_call_mock_models():
    xy = np.empty((0, 2))
    arrays = dict(image=np.zeros((64, 64)), measured=np.ones((64, 64), bool), centers_xy=xy,
                  boxes_xyxy=np.empty((0, 4)), object_ids=np.array([], dtype='U1'))
    models = {(family, seed): EncoderOnly(family) for family in ('ae', 'rvae') for seed in e7_features.SEEDS}
    values, desc = e7_features.synthetic_features(arrays, [], dict(low=-2., high=2.), models)
    assert values['geometry'].shape == (0, 8) and values['photometry'].shape == (0, 3)
    assert not desc['available'].any() and all(model.calls == 0 for model in models.values())


def test_resampled_patch_uses_reference_scale_and_frozen_renderer_intensity_bridge():
    _, xx = np.mgrid[:128, :128]
    xy = np.array([[64., 64.]])
    arrays = dict(image=xx / 127., measured=np.ones((128, 128), bool), centers_xy=xy,
                  boxes_xyxy=np.array([[62., 62., 66., 66.]]), object_ids=np.array(['a']))
    record = dict(sample_id='resampled', kind='synthetic', pixel_spacing_xy=[.5, .5])
    rows = [r for r in synthetic_rows(record, arrays) if r['sampler'] == 'centers' and r['scale_px'] == 48]
    assert rows[0]['scale_raw_px'] == 96
    models = {(family, seed): EncoderOnly(family) for family in ('ae', 'rvae') for seed in e7_features.SEEDS}
    e7_features.synthetic_features(arrays, rows, dict(low=-239., high=219.), models)
    raw_x = 64. + ((np.arange(64) + .5) / 64. - .5) * 96. - .5
    expected = np.broadcast_to(.5 + .4 * raw_x / 127., (64, 64))
    for model in models.values():
        np.testing.assert_allclose(model.inputs[0][0, 0], expected, rtol=1e-6, atol=1e-7)
