"""Boundary tests for the isolated issue22 experiment runner."""
from pathlib import Path

import numpy as np
import pytest

from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.training.local_ssl import evaluate, predict


def _write_run(root, regime, latent, seed, *, status='completed'):
    directory = root/'training'/regime/'local_ssl'/f'z{latent}'/f'seed-{seed}'
    directory.mkdir(parents=True)
    (directory/'step-0000.pt').write_bytes(f'initial{latent}/{seed}'.encode())
    (directory/'step-0100.pt').write_bytes(b'learned')
    metadata = dict(status=status, selected_checkpoint='step-0100.pt' if status=='completed' else None,
        selected_checkpoint_sha256=file_hash(directory/'step-0100.pt'), selected_step=100,
        initial_checkpoint='step-0000.pt', initial_checkpoint_sha256=file_hash(directory/'step-0000.pt'))
    write_json(directory/'run.json',metadata)
    return directory


def test_random_controls_are_saved_initializations_without_extra_fits(tmp_path):
    for regime in ('transfer','transductive'):
        for latent in ((16,32) if regime=='transfer' else (32,)):
            for seed in predict.SEEDS:
                _write_run(tmp_path,regime,latent,seed)
    runs = predict.trial_runs(tmp_path)
    assert len(runs) == 15
    random = [run for run in runs if run['initial']]
    assert len(random) == 6
    assert all(run['latent']==32 and run['family']=='local_ssl_untrained' for run in random)
    assert all(run['run_metadata']['selected_step']==0 for run in random)
    for run in random:
        metadata = run['run_metadata']
        assert metadata['selected_checkpoint_sha256']==file_hash(Path(run['directory'])/'step-0000.pt')
    assert len(list((tmp_path/'training').rglob('run.json'))) == 9
    (Path(random[0]['directory'])/'step-0000.pt').write_bytes(b'changed initial weights')
    with pytest.raises(ValueError,match='initialization'):
        predict.trial_runs(tmp_path)


def test_frozen_baseline_artifacts_cannot_escape_or_change(tmp_path):
    baseline = tmp_path/'baseline'
    baseline.mkdir()
    (baseline/'cache.bin').write_bytes(b'fixed')
    write_json(baseline/'frozen-predictions.json',dict(files={'cache.bin':file_hash(baseline/'cache.bin')}))
    assert predict.baseline_source(baseline,'cache.bin')==baseline/'cache.bin'
    with pytest.raises(ValueError,match='escapes'):
        predict.baseline_source(baseline,'../outside.bin')
    (baseline/'cache.bin').write_bytes(b'new')
    with pytest.raises(ValueError,match='changed'):
        predict.baseline_source(baseline,'cache.bin')


def test_shared_cpu_budget_counts_21_and_22_once_and_excludes_21a(tmp_path):
    baseline = tmp_path/'baseline'
    root = tmp_path/'ssl'
    other = tmp_path/'21a'
    for directory in (baseline,root,other):
        directory.mkdir()
    write_json(baseline/'cache-resources.json',dict(cpu_seconds=11,prior_cpu_seconds=1000))
    write_json(baseline/'evaluation-resources.json',dict(cpu_seconds=13,cumulative_postprocess_cpu_seconds=24))
    write_json(root/'cache.resources.json',dict(cpu_seconds=17,prior_cpu_seconds=24))
    write_json(other/'cache.resources.json',dict(cpu_seconds=100))
    budget = evaluate.PostprocessBudget(root,baseline=baseline)
    assert budget.prior_cpu_seconds==41
    assert len(budget.prior_reports)==3
    ledger = [dict(path=str(p),sha256=file_hash(p)) for p in sorted(baseline.glob('*-resources.json'))]
    write_json(root/'prior-budget.json',dict(postprocessing_reports=ledger))
    assert evaluate.PostprocessBudget(root).prior_cpu_seconds==41
    write_json(baseline/'cache-resources.json',dict(cpu_seconds=1))
    with pytest.raises(ValueError,match='resource record changed'):
        evaluate.PostprocessBudget(root)


def test_transfer_adapter_is_invariant_to_heldout_features(tmp_path):
    group = dict(group_id='measurement/grid/s48',record=dict(kind='measurement'))
    rows = [dict(window_id=f'w{i}',element_id=f'e{i}',raw_edge_xy=[8+16*i,8],
                 available=True,transfer_split='train' if i<4 else 'test') for i in range(6)]
    predict.write_gzip(tmp_path/'cache'/group['group_id']/'rows.json.gz',rows)
    run = dict(run_id='transfer/local_ssl/z16/seed-1',family='local_ssl',regime='transfer')
    feature_path = (tmp_path/'features'/run['run_id']/group['group_id']).with_suffix('.npz')
    feature_path.parent.mkdir(parents=True)
    feature = np.random.default_rng(17).normal(size=(6,10))
    np.savez(feature_path,features=feature)
    first = predict.fit_new_adapter(tmp_path,run,[group],48,'grid')
    feature[4:] = np.nan
    np.savez(feature_path,features=feature)
    second = predict.fit_new_adapter(tmp_path,run,[group],48,'grid')
    assert first==second
    assert first['fit_window_ids']==['w0','w1','w2','w3']


def test_freeze_authenticates_external_initialization_and_code(tmp_path):
    root = tmp_path/'output'
    root.mkdir()
    write_json(root/'predictions/index.json',[])
    external = tmp_path/'initial.pt'
    source = tmp_path/'model.py'
    external.write_bytes(b'weights')
    source.write_text('model')
    freeze = dict(schema='stmdomains-frozen-predictions-v1',evaluation_opened=False,
                  files={'predictions/index.json':file_hash(root/'predictions/index.json')},
                  external_files={str(external):file_hash(external)},code_sha256={str(source):file_hash(source)})
    write_json(root/'frozen-predictions.json',freeze)
    evaluate.verify_freeze(root)
    external.write_bytes(b'changed')
    with pytest.raises(ValueError,match='external artifact/code changed'):
        evaluate.verify_freeze(root)


def test_fft_reuse_audit_rejects_changed_baseline_predictions(tmp_path):
    baseline,output = tmp_path/'baseline',tmp_path/'output'
    directory = Path('predictions/transfer/fft/grid/s48/control/fh4')
    for root in (baseline,output):
        (root/directory).mkdir(parents=True)
        np.savez(root/directory/'metrics-input.npz',before=np.array([1,1]),after=np.array([0,0]),
                 acf_score=np.array([np.nan,.1]))
    relative = str(directory/'metrics-input.npz')
    write_json(baseline/'frozen-predictions.json',dict(files={relative:file_hash(baseline/relative)}))
    index = [dict(family='fft',regime='transfer',kind='synthetic',directory=str(directory))]
    assert predict.audit_baseline_predictions(output,baseline,index)['compared_prediction_archives']==1
    np.savez(output/relative,before=np.array([1,2]),after=np.array([0,0]),acf_score=np.array([np.nan,.1]))
    with pytest.raises(ValueError,match='FFT result changed'):
        predict.audit_baseline_predictions(output,baseline,index)


def test_issue22_prediction_cli_denies_reference_access(tmp_path):
    # Audit hooks persist for a process, so exercise the actual CLI in a child.
    import subprocess
    import sys
    truth = tmp_path/'evaluation'/'manual_domain.json'
    write_json(truth,dict(domain=1))
    code = """
import sys
from pathlib import Path
from stmdomains.experiments.training.local_ssl import predict
root,truth = map(Path,sys.argv[1:])
def prohibited(*args):
    truth.read_text()
predict.cache_inputs = prohibited
sys.argv = ['predict','cache','--output',str(root/'output'),'--baseline',str(root/'baseline')]
try:
    predict.main()
except PermissionError:
    pass
else:
    raise AssertionError('Reference read was not denied')
"""
    result = subprocess.run([sys.executable,'-c',code,str(tmp_path),str(truth)],capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    report = predict.read_json(tmp_path/'output/cache.resources.json')
    assert report['status']=='failed'
    assert report['cpu_seconds']>=0


def test_spatial_descriptors_are_saved_once_and_load_unchanged(tmp_path, monkeypatch):
    import torch
    from stmdomains.experiments.training.local_ssl import models
    torch.manual_seed(13)
    model = models.LocalSSL(16).eval()
    run = dict(run_id='transfer/local_ssl/z16/seed-20261101',family='local_ssl',regime='transfer',
               latent=16,seed=20261101,directory=str(tmp_path/'model'),initial=False,run_metadata={})
    group = dict(group_id='sample/grid/s48')
    monkeypatch.setattr(predict,'trial_runs',lambda output:[run])
    monkeypatch.setattr(models,'load_model',lambda *args,**kwargs:model)
    write_json(tmp_path/'cache/index.json',[group])
    predict.write_gzip(tmp_path/'cache'/group['group_id']/'rows.json.gz',[{}, {}, {}, {}])
    patches = np.random.default_rng(42).random((2,64,64),dtype=np.float32)
    np.savez(tmp_path/'cache'/group['group_id']/'transfer.npz',
             available_indices=np.array([0,2]),patches=patches)
    summaries = predict.encode_models(tmp_path,device='cpu')
    loaded = predict.load_features(tmp_path,run,group)
    with torch.inference_mode():
        expected = model.encode(torch.from_numpy(patches[:,None]))['content'].numpy()
    np.testing.assert_array_equal(loaded[[0,2]],expected)
    assert np.isnan(loaded[[1,3]]).all()
    assert loaded.shape==(4,16*7*7)
    path = (tmp_path/'features'/run['run_id']/group['group_id']).with_suffix('.npz')
    with np.load(path,allow_pickle=False) as archive:
        assert set(archive.files)=={'features','angle_radians','reconstruction_mse'}
        assert np.isnan(archive['angle_radians']).all()
        assert np.isnan(archive['reconstruction_mse']).all()
    assert summaries[0]['local_map_shape']==[16,7,7]
