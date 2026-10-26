"""Geometry and cache identity tests; official model execution is verified separately."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from stmdomains.experiments.frozen.geometry import FeatureConfig, locations, prepare_image, sample_crops
from stmdomains.experiments.frozen.extract import feature_key, extract_one


def sample():
    y,x=np.mgrid[:64,:80];image=(x+.5)+2*(y+.5)
    a=dict(image=image,measured=np.ones_like(image,bool),centers_xy=np.array([[20.5,24.5],[40.5,40.5]]),object_ids=np.array(['b','a']))
    return dict(pixel_spacing_xy=[1.,1.]),a


def test_sampling_coordinates_follow_pixel_edges_and_preserve_ramp():
    rec,a=sample();gray=torch.from_numpy(a['image'].astype(np.float32))[None,None]
    boxes=np.array([[10.,12.,30.,32.]])
    rgb,mask=sample_crops(gray,a['measured'],boxes,20)
    restored=rgb[0,0]*.229+.485
    expected=a['image'][12:32,10:30]
    np.testing.assert_allclose(restored.numpy(),expected,atol=2e-5,rtol=1e-6)
    assert torch.all(mask==1)


def test_edge_reflection_never_becomes_measured_and_holes_are_missing():
    rec,a=sample();gray,_=prepare_image(a,'frame_minmax')
    _,mask=sample_crops(gray,a['measured'],np.array([[-10.,-10.,10.,10.]]),20)
    assert mask.mean()==.25
    a['measured'][20:24,20:24]=False;a['image'][~a['measured']]=np.nan
    gray,_=prepare_image(a,'frame_minmax')
    crops,mask=sample_crops(gray,a['measured'],np.array([[16.,16.,28.,28.]]),12)
    assert torch.isfinite(crops).all()
    assert torch.count_nonzero(mask==0)==16


def test_technical_resampling_does_not_change_physical_windows():
    rec,a=sample();cfg=FeatureConfig('dinov2_vits14');base=locations(rec,a,cfg,'grid')
    b=dict(a,image=np.repeat(np.repeat(a['image'],2,axis=0),2,axis=1),measured=np.ones((128,160),bool),centers_xy=a['centers_xy']*2)
    enlarged=locations(dict(pixel_spacing_xy=[.5,.5]),b,cfg,'grid')
    np.testing.assert_allclose(enlarged['xy']*.5,base['xy'])
    np.testing.assert_allclose(enlarged['window_xyxy']*.5,base['window_xyxy'])
    assert len(base['xy'])==len(enlarged['xy'])


def test_image_cache_ignores_centers_but_tracks_model_preprocessing_and_image():
    rec,a=sample();cfg=FeatureConfig('dinov2_vits14');model=SimpleNamespace(identity={'weights':'A'})
    key=lambda x,c=cfg,m=model:feature_key(rec,x,c,'grid',m)[0]
    original=key(a);b=dict(a,centers_xy=np.empty((0,2)),object_ids=np.array([],dtype='U1'))
    assert key(b)==original
    assert feature_key(rec,a,cfg,'centers',model)[0]!=feature_key(rec,b,cfg,'centers',model)[0]
    assert key(a,replace(cfg,radius=36))!=original
    assert key(a,replace(cfg,normalization='frame_minmax'))!=original
    assert key(a,m=SimpleNamespace(identity={'weights':'B'}))!=original
    c=dict(a,image=a['image']+1);assert key(c)!=original


def test_cache_roundtrip_and_corruption_are_not_silent(tmp_path):
    rec,a=sample();cfg=FeatureConfig('fcn_resnet101')
    class Extractor:
        identity={'test':'mean'};device=torch.device('cpu');dimension=3
        def __call__(self,x):return x.mean(dim=(-2,-1)).numpy()
        def map_shapes(self,size):return [[3,size,size]]
    model=Extractor();first=extract_one(rec,a,cfg,'grid',model,tmp_path)
    second=extract_one(rec,a,cfg,'grid',model,tmp_path)
    assert second['cache_hit'] and first['cache_key']==second['cache_key']
    from pathlib import Path
    Path(first['path']).write_bytes(b'broken')
    with pytest.raises(ValueError,match='Corrupted'):extract_one(rec,a,cfg,'grid',model,tmp_path)


def test_flat_image_and_empty_annotations_are_explicit(tmp_path):
    rec,a=sample();a['image'][:]=10
    gray,stats=prepare_image(a,'frame_percentile');assert stats['flat'];assert torch.count_nonzero(gray)==0
    a.update(centers_xy=np.empty((0,2)),object_ids=np.array([],dtype='U1'))
    geo=locations(rec,a,FeatureConfig('dinov2_vits14'),'centers');assert geo['window_xyxy'].shape==(0,4)
