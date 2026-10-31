"""Issue21a safeguards that differ from the original prediction/evaluation path."""
from pathlib import Path

import numpy as np
import pytest

from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.training import partition
from stmdomains.experiments.training.rvae_followup import evaluate, predict


def test_baseline_reuse_requires_original_hash_and_confined_path(tmp_path):
    baseline=tmp_path/'original'
    source=baseline/'cache/order-thresholds.json'
    write_json(source, {'threshold': .4})
    write_json(baseline/'frozen-predictions.json', {'files': {'cache/order-thresholds.json':file_hash(source)}})
    assert predict.baseline_source(baseline,'cache/order-thresholds.json')==source
    with pytest.raises(ValueError,match='escapes'):
        predict.baseline_source(baseline,'../outside')
    write_json(source, {'threshold': .2})
    with pytest.raises(ValueError,match='changed'):
        predict.baseline_source(baseline,'cache/order-thresholds.json')


def test_new_adapter_excludes_validation_test_and_synthetic_rows(tmp_path,monkeypatch):
    group=dict(group_id='frame/grid/s48', record={'kind':'measurement'})
    rows=[dict(available=True,transfer_split=split,window_id=f'row{i}',raw_edge_xy=[i*16.,0.])
          for i,split in enumerate(('train','train','validation','test'))]
    predict.write_gzip(tmp_path/'cache'/group['group_id']/'rows.json.gz',rows)
    features=np.arange(12).reshape(4,3)
    monkeypatch.setattr(predict,'load_features',lambda *args:features)
    captured={}
    def fit(x,edges,ids,*,scope):
        captured.update(x=x,edges=edges,ids=ids,scope=scope)
        return dict(scope=scope)
    monkeypatch.setattr(partition,'fit_feature_adapter',fit)
    run=dict(run_id='transfer/rvae_lowkl/z32/seed-20261101')
    adapter=predict.fit_new_adapter(tmp_path,run,[group,dict(record={'kind':'synthetic'})])
    assert adapter['fit_window_ids']==['row0','row1']
    np.testing.assert_array_equal(captured['x'],features[:2])
    np.testing.assert_array_equal(captured['edges'],[[0,1]])
    assert captured['scope']['regime']=='transfer'


def test_freeze_verification_checks_external_weights_before_evaluation(tmp_path):
    root=tmp_path/'trial';root.mkdir()
    external=tmp_path/'old-weight.pt';external.write_bytes(b'immutable-weight')
    write_json(root/'predictions/index.json',[])
    write_json(root/'frozen-predictions.json',dict(schema='stmdomains-frozen-predictions-v1',
        evaluation_opened=False,files={'predictions/index.json':file_hash(root/'predictions/index.json')},
        external_files={str(external):file_hash(external)},code_sha256={}))
    assert evaluate.verify_freeze(root)['evaluation_opened'] is False
    external.write_bytes(b'changed')
    with pytest.raises(ValueError,match='external'):
        evaluate.verify_freeze(root)


def test_continuation_uses_fresh_control_seeds(monkeypatch):
    monkeypatch.setattr(evaluate,'ZERO_CASES',set())
    monkeypatch.setattr(evaluate,'TWO_CASES',set())
    monkeypatch.setattr(evaluate,'ABLATION_CASES',set())
    records=[]
    for model_seed in predict.SEEDS:
        for seed in evaluate.CONTROL_SEEDS:
            for case in ('single','insufficient_field'):
                records.append(dict(metadata=dict(regime='transfer',family='rvae_lowkl',latent=32,
                    partition='fh4',sampler='grid',scale_px=48,seed=model_seed,control_seed=seed,
                    kind='synthetic',case=case),metrics={'criteria':{'passed':True}}))
    summary=evaluate.continuation_summary(records,[],[])[0]
    checks=summary['synthetic_controls']['checks']
    assert len(checks)==18
    assert summary['synthetic_controls']['passed'] is True
    assert all('control_seed=92001' in key for key in checks)
    assert summary['continuation']['qualified'] is False


def test_resource_budget_counts_previous_phases_and_failed_attempts(tmp_path):
    write_json(tmp_path/'controls.resources.json',{'cpu_seconds':7.})
    write_json(tmp_path/'encode.resources.json',{'cpu_seconds':5.,'status':'failed'})
    budget=evaluate.PostprocessBudget(tmp_path)
    assert budget.prior_cpu_seconds==12.
    assert len(budget.prior_reports)==2
    assert budget.cpu_limit_seconds==7200.


def test_baseline_audit_detects_assignment_drift(tmp_path):
    baseline=tmp_path/'old';output=tmp_path/'new'
    directory='predictions/transfer/fft/grid/s48/ttmapp-001/fh4'
    files={}
    for name in ('metrics-input.npz','heldout-metrics-input.npz'):
        p=baseline/directory/name;p.parent.mkdir(parents=True,exist_ok=True)
        np.savez(p,before=np.array([1,1]),after=np.array([0,0]),acf_score=np.array([np.nan,.1]))
        files[str(p.relative_to(baseline))]=file_hash(p)
        target=output/directory/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
    write_json(baseline/'frozen-predictions.json',{'files':files})
    index=[dict(kind='measurement',family='fft',directory=directory)]
    assert predict.audit_baseline_predictions(output,baseline,index)['passed']
    np.savez(output/directory/'metrics-input.npz',before=np.array([1,2]),after=np.array([0,0]),acf_score=np.array([np.nan,.1]))
    with pytest.raises(ValueError,match='changed'):
        predict.audit_baseline_predictions(output,baseline,index)


def test_fixed_step_checkpoint_is_authenticated_separately_from_selected(tmp_path):
    selected=tmp_path/'step-1300.pt';selected.write_bytes(b'selected')
    fixed=tmp_path/'step-2000.pt';fixed.write_bytes(b'fixed')
    meta=dict(selected_checkpoint=selected.name,selected_checkpoint_sha256=file_hash(selected),
              checkpoints=[dict(step=2000,file=fixed.name,sha256=file_hash(fixed))])
    assert predict.checkpoint_evidence(tmp_path,meta)==[selected,fixed]
    fixed.write_bytes(b'changed after training')
    with pytest.raises(ValueError,match='checkpoint evidence changed'):
        predict.checkpoint_evidence(tmp_path,meta)
