"""End-to-end checks on official models, separate from domain quality evaluation."""
import argparse,json,time
from pathlib import Path
import numpy as np
import torch
from stmdomains.experiments.bundle import load_sample,write_arrays,write_json,file_hash
from .extract import run,configure_runtime,extract_one
from .geometry import FeatureConfig,prepare_image,sample_crops
from .models import FrozenExtractor

ATOL=1e-5
RTOL=1e-4


def verify(root,assets,device,check_existing_replay=False):
    start=time.perf_counter();main=json.loads((root/'manifest.json').read_text())
    analysis=root/'input/analysis';target=root/'replay/input/analysis'
    manifest=json.loads((analysis/'manifest.json').read_text())
    for rec in manifest['samples']:
        _,a=load_sample(analysis,rec['sample_id'])
        a.update(centers_xy=np.empty((0,2)),boxes_xyxy=np.empty((0,4)),object_ids=np.array([],dtype='U64'))
        rec.update(write_arrays(target/rec['file'],a),annotation_count=0)
    write_json(target/'manifest.json',manifest)
    # Deliberately invalid evaluation data: an extractor must never read it.
    fake=target.parent/'evaluation/manifest.json';fake.parent.mkdir(exist_ok=True);fake.write_text('invalid changed reference data — forbidden to extraction')
    if not check_existing_replay:
        run(target,assets,root/'replay',root/'replay/cache',device,sample_ids=main['samples'],modes=('grid',))
    replay=json.loads((root/'replay/manifest.json').read_text())
    baseline={r['cache_key']:r for r in main['entries'] if r['sampling']=='grid'};comparisons=[];seen=set()
    for item in replay['entries']:
        if item['cache_key'] not in seen:
            assert not item['cache_hit'],'Replay must recompute each distinct image/configuration'
        seen.add(item['cache_key'])
        original=baseline[item['cache_key']];a=np.load(root/original['path']);b=np.load(root/'replay'/item['path'])
        for key in a.files:
            if key!='features':assert np.array_equal(a[key],b[key]),key
        np.testing.assert_allclose(a['features'],b['features'],atol=ATOL,rtol=RTOL)
        comparisons.append(dict(sample_id=item['sample_id'],config=item['config'],maximum_absolute_difference=float(np.max(abs(a['features']-b['features']),initial=0)),exact=bool(np.array_equal(a['features'],b['features']))))
    # A different batch shape and order can select different numerical kernels.
    batch_checks=[];cache_checks=[];witnesses=[]
    for name in ['fcn_resnet101','dinov2_vits14']:
        extractor=FrozenExtractor(name,assets,device)
        for size in [112,224]:
            cfg=FeatureConfig(name,24,size,'frame_percentile');rec,a=load_sample(analysis,'ttmapp-250')
            from .geometry import locations
            geo=locations(rec,a,cfg,'grid');gray,_=prepare_image(a,cfg.normalization)
            ii=np.array([0,1,21,220,440]);crops,masks=sample_crops(gray,a['measured'],geo['window_xyxy'][ii],size)
            together=extractor(crops);separate=np.concatenate([extractor(crops[i:i+1]) for i in range(len(crops))])
            reverse=extractor(crops.flip(0))[::-1]
            for label,other in [('batch_one',separate),('reversed_batch',reverse)]:
                np.testing.assert_allclose(together,other,atol=1e-4,rtol=RTOL)
                batch_checks.append(dict(model=name,size=size,check=label,maximum_absolute_difference=float(np.max(abs(together-other))),passes_original_atol_1e5=bool(np.allclose(together,other,atol=ATOL,rtol=RTOL))))
            maps=[m.cpu().numpy() for m in extractor.maps(crops)]
            witness=root/'witness-maps'/f'{name}-{size}.npz'
            arrays={f'layer{i}':m for i,m in enumerate(maps)};arrays.update(xy=geo['xy'][ii],window_xyxy=geo['window_xyxy'][ii],model_input=crops.numpy(),measured_support=masks.numpy())
            hashes=write_arrays(witness,arrays);witnesses.append(dict(model=name,size=size,file=str(witness.relative_to(root)),**hashes))
            cached=extract_one(rec,a,cfg,'grid',extractor,root/'cache');assert cached['cache_hit'];cache_checks.append(cached['cache_key'])
        extractor.frozen_proof();del extractor
        if device.startswith('cuda'):torch.cuda.empty_cache()
    # Original full-resolution image and registered padding are not confused.
    footprints=[]
    for item in main['entries']:
        a=np.load(root/item['path']);meta=json.loads((root/item['metadata_path']).read_text())
        assert meta['sha256']==file_hash(root/item['path'])
        assert len(a['features'])==len(a['xy'])==len(a['object_ids'])
        assert np.isfinite(a['features']).all()
        assert np.all((a['measured_support_fraction']>=0)&(a['measured_support_fraction']<=1))
        rec,src=load_sample(analysis,item['sample_id'])
        if item['sampling']=='centers':
            order=np.argsort(src['object_ids']);np.testing.assert_array_equal(a['xy'],src['centers_xy'][order])
        footprints.append(dict(sample_id=item['sample_id'],config=item['config'],sampling=item['sampling'],count=len(a['features']),minimum_support=float(a['measured_support_fraction'].min(initial=1)),maximum_support=float(a['measured_support_fraction'].max(initial=0))))
    report=dict(atol=ATOL,rtol=RTOL,batch_atol=1e-4,batch_rtol=RTOL,checked_existing_fresh_replay=check_existing_replay,unique_recomputed_grids=len(seen),grid_replay=comparisons,batch_checks=batch_checks,cache_hits=len(cache_checks),
                coordinate_and_cache_checks=len(footprints),footprints=footprints,witness_maps=witnesses,
                original_reference_tree_absent=not (root/'input/evaluation').exists(),replay_reference_data_changed=True,
                replay_annotations_removed=True,frozen_models=main['frozen_models'],replay_frozen_models=replay['frozen_models'],seconds=time.perf_counter()-start)
    write_json(root/'verification.json',report)
    print('verified',len(comparisons),'fresh grid outputs;',len(footprints),'geometries;',len(batch_checks),'batch checks',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--device',default='cpu');p.add_argument('--check-existing-replay',action='store_true');a=p.parse_args();configure_runtime();verify(a.root,a.assets,a.device,a.check_existing_replay)
