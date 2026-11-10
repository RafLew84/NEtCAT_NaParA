"""Reusable label-free feature cache. Run with python -m ...frozen.extract."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import time
import numpy as np
import torch
from stmdomains.experiments.bundle import arrays_hash, file_hash, load_sample, write_arrays, write_json
from .geometry import FeatureConfig, image_digest, locations, prepare_image, sample_crops
from .models import FrozenExtractor

PILOT=['ttmapp-001','ttmapp-050','ttmapp-250','ttmapp-255','ttmapp-268',
       'control-0070','control-0072','control-0073','control-0074','control-0081','control-0086','control-0087']


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def implementation_hashes():
    return {p.name:file_hash(p) for p in sorted(Path(__file__).parent.glob('*.py')) if p.name not in ('verify.py','preview.py','assets.py')}


def configure_runtime(threads=4):
    torch.set_num_threads(threads);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True)


def feature_key(record,arrays,config,mode,extractor):
    identity=dict(schema='stmdomains-frozen-features-v1',image_content_sha256=image_digest(record,arrays),
                  config=config.as_dict(),sampling=mode,model=extractor.identity,implementation=implementation_hashes(),
                  interpolation='bilinear; edge coordinates; align_corners=False; reflect image, zero mask',
                  normalization_scope='original measured frame; no per-crop statistics',
                  pooling_context='entire requested crop; frame-wide normalization dependence recorded separately')
    if mode=='centers':
        order=np.argsort(arrays['object_ids']);identity['annotations_sha256']=arrays_hash(dict(centers_xy=arrays['centers_xy'][order],object_ids=arrays['object_ids'][order]))
    return digest(identity),identity


def extract_one(record,arrays,config,mode,extractor,cache,batch_size=32):
    key,identity=feature_key(record,arrays,config,mode,extractor)
    path=cache/(key+'.npz');meta_path=cache/(key+'.json')
    if path.exists() and meta_path.exists():
        meta=json.loads(meta_path.read_text())
        if meta['identity']!=identity or meta['sha256']!=file_hash(path):
            raise ValueError('Corrupted or incompatible cached features')
        return dict(cache_key=key,cache_hit=True,path=str(path),metadata_path=str(meta_path),count=meta['count'])
    start=time.perf_counter();geo=locations(record,arrays,config,mode)
    gray,normalization=prepare_image(arrays,config.normalization);parts=[];support=[]
    if extractor.device.type=='cuda':torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
    for begin in range(0,len(geo['xy']),batch_size):
        batch=geo['window_xyxy'][begin:begin+batch_size]
        crops,masks=sample_crops(gray,arrays['measured'],batch,config.input_size)
        parts.append(extractor(crops));support.append(masks.mean(dim=(-2,-1)).numpy())
    if extractor.device.type=='cuda':torch.cuda.synchronize()
    feature=np.concatenate(parts) if parts else np.empty((0,extractor.dimension),np.float32)
    if not np.isfinite(feature).all():raise ValueError('Non-finite model output')
    geo.update(features=feature,measured_support_fraction=np.concatenate(support) if support else np.empty(0,np.float32))
    area=np.prod(geo['window_xyxy'][:,2:]-geo['window_xyxy'][:,:2],axis=1)
    geo['inside_field_fraction']=np.prod(geo['clipped_window_xyxy'][:,2:]-geo['clipped_window_xyxy'][:,:2],axis=1)/area
    hashes=write_arrays(path,geo)
    meta=dict(identity=identity,**hashes,count=len(feature),dimension=extractor.dimension,
              normalization=normalization,native_feature_maps=extractor.map_shapes(config.input_size),
              window_width_reference_px=2*config.radius,input_size=config.input_size,
              model_pixel_to_reference_pixel=2*config.radius/config.input_size,
              source_shape=list(arrays['image'].shape),batch_size=batch_size,
              internal_padding='FCN convolution/maxpool zero/implicit padding; DINO no spatial padding (input divisible by14)',
              measured_support='fractional bilinear contribution of measured source pixels; reflected/imputed context remains synthetic',
              seconds=time.perf_counter()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              peak_cuda_allocated=torch.cuda.max_memory_allocated() if extractor.device.type=='cuda' else None,
              peak_cuda_reserved=torch.cuda.max_memory_reserved() if extractor.device.type=='cuda' else None)
    write_json(meta_path,meta)
    return dict(cache_key=key,cache_hit=False,path=str(path),metadata_path=str(meta_path),count=len(feature))


def run(analysis,assets,out,cache,device='cpu',sample_ids=None,models=None,radii=(24,36),sizes=(112,224),normalizations=('frame_percentile','frame_minmax'),modes=('grid','centers'),batch_size=32):
    start=time.perf_counter();cache.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((analysis/'manifest.json').read_text());ids=sample_ids or PILOT
    available={r['sample_id'] for r in manifest['samples']}
    if set(ids)-available:raise ValueError('Unknown requested sample')
    loaded={sid:load_sample(analysis,sid) for sid in ids};entries=[];proofs={}
    for model_name in models or ['fcn_resnet101','dinov2_vits14']:
        extractor=FrozenExtractor(model_name,assets,device)
        for radius in radii:
            for size in sizes:
                for normalization in normalizations:
                    cfg=FeatureConfig(model_name,radius,size,normalization)
                    for sid,(rec,a) in loaded.items():
                        for mode in modes:
                            result=extract_one(rec,a,cfg,mode,extractor,cache,batch_size)
                            result['path']=os.path.relpath(result['path'],out)
                            result['metadata_path']=os.path.relpath(result['metadata_path'],out)
                            entries.append(dict(sample_id=sid,config=cfg.as_dict(),sampling=mode,input_content_sha256=rec['content_sha256'],**result))
                    print(cfg.name,'entries',len(entries),'seconds',round(time.perf_counter()-start,1),flush=True)
        proofs[model_name]=extractor.frozen_proof();del extractor
        if device.startswith('cuda'):torch.cuda.empty_cache()
    write_json(out/'manifest.json',dict(schema='stmdomains-frozen-run-v1',analysis_manifest_sha256=file_hash(analysis/'manifest.json'),samples=ids,entries=entries,
                                       frozen_models=proofs,seconds=time.perf_counter()-start,scope='feature preparation only; no domain labels, grouping, or quality assessment'))
    print('complete',len(entries),'entries',round(time.perf_counter()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cache',type=Path);p.add_argument('--device',default='cpu');p.add_argument('--sample',action='append');p.add_argument('--model',action='append');p.add_argument('--radius',type=int,action='append');p.add_argument('--size',type=int,action='append');p.add_argument('--normalization',action='append');p.add_argument('--mode',action='append');p.add_argument('--batch-size',type=int,default=32);p.add_argument('--threads',type=int,default=4)
    a=p.parse_args();configure_runtime(a.threads)
    run(a.analysis,a.assets,a.out,a.cache or a.out/'cache',a.device,a.sample,a.model,a.radius or (24,36),a.size or (112,224),a.normalization or ('frame_percentile','frame_minmax'),a.mode or ('grid','centers'),a.batch_size)
