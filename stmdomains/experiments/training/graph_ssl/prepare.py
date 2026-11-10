"""Freeze and audit one bounded graph trial; no model selection from references."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

from ...bundle import file_hash, write_json
from ..checkpoint import read_checkpoint
from .data import CONFIG
from .fit import ARCHITECTURE, CAPS, run_specs, source_hashes, verified_plan


def read(path):
    return json.loads(Path(path).read_text())


def plan(root):
    target=root/'plan.json'
    if target.exists() or (root/'training').exists():
        raise FileExistsError('Graph plan must precede all scientific fits')
    own=Path(__file__).parent
    names=('__init__.py','data.py','controls.py','models.py','fit.py','legacy_geometry.py',
           'predict.py','prepare.py','evaluation.py','summary.py')
    paths=[own/name for name in names]
    paths += [own.parent/name for name in ('partition.py','evaluate.py','data.py','controls.py','checkpoint.py')]
    paths += [own.parent.parent/name for name in ('bundle.py','controls.py','results.py')]
    code={str(path):file_hash(path) for path in paths}
    # Record repository-relative paths, independent of cwd spelling.
    repo=Path.cwd().resolve()
    code={str(Path(name).resolve().relative_to(repo)):digest for name,digest in code.items()}
    preflight=read(root/'preflight-model-cuda.json')
    if not preflight['passed'] or preflight['optimizer_steps'] > 12:
        raise ValueError('Successful bounded CUDA technical audit required')
    if any(code.get(name)!=digest for name,digest in preflight['code_sha256'].items()):
        raise ValueError('Technical preflight sources changed')
    if any(code.get(name)!=digest for name,digest in source_hashes().items()):
        raise ValueError('Incomplete model source freeze')
    protocol=Path('docs/stmdomains/graph-self-supervised-protocol.md')
    result=dict(schema='stmdomains-graph24-plan-v1', frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                parent_commit='05d32f2', user_authorization='wykonaj 24; separate bounded extension after issue23',
                protocol_document=str(protocol), protocol_sha256=file_hash(protocol),
                code_sha256=code, data_manifest_sha256=file_hash(root/'prepared/manifest.json'),
                input_geometry=CONFIG, architecture=ARCHITECTURE, training_caps=CAPS,
                primary_loss='sce_scale', diagnostic_loss='sce', runs=run_specs(),
                control_seeds=[920021,920022,920023], controls=93, real_frames=24,
                postprocess_cpu_seconds_cap=7200, data_counts=read(root/'prepared/manifest.json')['counts'],
                adapter='train-only per-channel standardization then PCA<=24 without sample L2 or whitening',
                catalogue=dict(method='HDBSCAN',min_cluster_size=8,min_samples=4,allow_single_cluster=True,
                               assignment='nearest train centroid within training95% radius',meaning='descriptor groups only'),
                order_gate=dict(source='geometry15',radius=36,tolerance=.24,mode=1,threshold=.25,min_component=8),
                evaluation='fixed graph24 criteria and all local-edge midpoint boundary, tolerance8; refs only after prediction freeze',
                technical_cuda_audit_sha256=file_hash(root/'preflight-model-cuda.json'),
                initial_preparation_cost='CPU/RSS not instrumented; separately measured identical replay available; report this limitation')
    write_json(target,result)
    return dict(plan_sha256=file_hash(target),source_files=len(code),fits=len(result['runs']))


def audit_training(root):
    frozen=verified_plan(root,root)
    results=[read(root/spec['run_id']/'run.json') for spec in run_specs()]
    completed=[r for r in results if r['status']=='completed']
    checks=[]; checkpoint_count=0
    for run in completed:
        directory=root/run['run_id']
        config=read(directory/'config.json')
        assert config['plan_sha256']==file_hash(root/'plan.json')
        assert config['code_sha256']==frozen['code_sha256']
        assert run['completed_steps']==run['completed_optimizer_steps']+run['skipped_uninformative_steps']
        for entry in run['checkpoints']:
            checkpoint=directory/entry['file']
            assert file_hash(checkpoint)==entry['sha256']
            saved=read_checkpoint(checkpoint)
            assert saved['progress']['step']==entry['step']
            checkpoint_count+=1
        if run['regime']=='transfer':
            best=min(run['validation_history'],key=lambda r:(r['loss'],r['step']))
            assert run['selected_step']==best['step']
        checks.append(dict(run_id=run['run_id'],selected_step=run['selected_step'],
                           selected_checkpoint_sha256=run['selected_checkpoint_sha256'],
                           initial_state_sha256=run['initial_state_sha256'],verified=True))
    pairs=[]
    for seed in (20261101,20261102,20261103):
        a=next(r for r in results if r['regime']=='transfer' and r['loss_name']=='sce' and r['seed']==seed)
        b=next(r for r in results if r['regime']=='transfer' and r['loss_name']=='sce_scale' and r['seed']==seed)
        assert a['initial_state_sha256']==b['initial_state_sha256']
        assert a['validation_content_sha256']==b['validation_content_sha256']
        paired=zip(a['loss_history'],b['loss_history'])
        count=0
        for x,y in paired:
            assert x['batch_content_sha256']==y['batch_content_sha256']
            count+=1
        pairs.append(dict(seed=seed,identical_initialization=True,identical_validation=True,matched_batches=count))
    selected=[r['selected_step'] for r in results if r['regime']=='transfer' and r['loss_name']=='sce_scale' and r['status']=='completed']
    if len(selected)==3:
        assert all(r['completed_steps']==statistics.median(selected) for r in results if r['regime']=='transductive' and r['status']=='completed')
    result=dict(schema='stmdomains-graph24-training-audit-v1',passed=True,runs=checks,
                completed_runs=len(completed),attempted_runs=len(results),paired_losses=pairs,
                periodic_checkpoints_checked=checkpoint_count,
                total_optimizer_steps=sum(r['completed_optimizer_steps'] for r in results),
                fit_seconds=sum(r['seconds'] for r in results),
                checkpoint_files=len(list((root/'training').rglob('*.pt'))),
                checkpoint_bytes=sum(p.stat().st_size for p in (root/'training').rglob('*.pt')))
    assert result['fit_seconds'] <= CAPS['max_total_fit_seconds']
    assert result['checkpoint_bytes'] <= CAPS['all_checkpoint_bytes']
    write_json(root/'training-audit.json',result)
    return {key:value for key,value in result.items() if key not in ('runs','paired_losses')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('plan','audit-training'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps((plan if args.stage=='plan' else audit_training)(args.output.resolve())))


if __name__=='__main__':
    main()
