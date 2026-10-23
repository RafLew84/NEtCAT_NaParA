"""Evaluation-only partial reference extraction.

Extraction and PNG reconstruction retained from the audited prototype
4e7a757 (partial_domain_reference.py). This is not a physical boundary mask.
No analysis loader imports this module.
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from .bundle import file_hash, write_arrays


def prepare_references(review, geometry, output):
    """Reconstruct each supplied clean PNG exactly, then extract evaluation cores."""
    records = []
    for manual_path in sorted(review.glob('frame_*_clean_registered_manual_domain.png')):
        number = int(manual_path.name.split('_')[1])
        if number not in range(250, 269):
            raise ValueError('Unexpected reference frame')
        clean_path = manual_path.with_name(manual_path.name.replace('_manual_domain', ''))
        clean = np.asarray(Image.open(clean_path).convert('RGB'))
        manual = np.asarray(Image.open(manual_path).convert('RGB'))
        raw = geometry['raw'][number-1]
        origin = geometry['origins'][number-1]
        expected = render_expected(raw, origin, geometry['canvas_hw'])
        if clean.shape != manual.shape or clean.shape != (*expected.shape, 3):
            raise ValueError('Reference geometry mismatch')
        if not np.array_equal(clean, np.repeat(expected[:, :, None], 3, axis=2)):
            raise ValueError(f'Clean PNG does not match MPP/registration: {number}')
        regions, _ = extract(clean, manual, 3.)
        yy, xx = np.mgrid[:raw.shape[0], :raw.shape[1]]
        px = np.floor(2*(xx+.5+origin[0])).astype(int)
        py = np.floor(2*(yy+.5+origin[1])).astype(int)
        labels = np.zeros(raw.shape, np.int16)
        instances = np.zeros(raw.shape, np.int16)
        candidates = np.zeros(raw.shape, bool)
        region_meta = []
        for ident, region in enumerate(regions, 1):
            core = region['core'][py, px]
            if np.any(labels[core]) or not core.any():
                raise ValueError('Empty/overlapping reference cores')
            labels[core] = region['class_id']; instances[core] = ident
            candidates |= region['candidate'][py, px]
            region_meta.append(dict(region_id=ident, orientation_group=region['class_id'],
                                    core_pixels=int(core.sum()), extraction=region['extraction']))
        arrays = dict(orientation_groups=labels, region_instances=instances,
                      evaluation_valid=labels > 0, boundary_unscored=candidates & (labels == 0))
        relative = f'references/ttmapp-{number:03}.npz'
        hashes = write_arrays(output / relative, arrays)
        records.append(dict(sample_id=f'ttmapp-{number:03}', file=relative, **hashes,
                            clean_sha256=file_hash(clean_path), manual_sha256=file_hash(manual_path),
                            reconstructed_png_max_abs_error=0, regions=region_meta))
    return records

def outline_masks(clean, manual):
    # Thresholds from the legacy calibration script, audited against clean/manual pairs.
    c, m = clean.astype(np.int16), manual.astype(np.int16)
    return [
        (m.max(2)<100) & (c.mean(2)-m.mean(2)>3),
        (m[:,:,0]>150)&(m[:,:,0]>m[:,:,1]*1.55)&(m[:,:,0]>m[:,:,2]*1.55),
        (m[:,:,0]>150)&(m[:,:,1]>120)&(m[:,:,2]<130)&(abs(m[:,:,0]-m[:,:,1])<130),
    ]

def extract(clean, manual, margin):
    outlines = outline_masks(clean, manual)
    # Same gap-closing proposal as the legacy script, but no dilation back toward the stroke.
    barrier = ndi.binary_closing(ndi.binary_dilation(np.logical_or.reduce(outlines), iterations=5), iterations=10)
    labels, count = ndi.label(~barrier)
    candidates = []
    for k in range(1, count+1):
        region = labels == k
        area = int(region.sum())
        if area<1000 or any(np.any(x) for x in [region[0],region[-1],region[:,0],region[:,-1]]):
            continue
        ring = ndi.binary_dilation(region, iterations=10)&~region
        contacts = [int((ring&o).sum()) for o in outlines]
        group = int(np.argmax(contacts))
        if contacts[group]<10 or (group==0 and area<5000):
            continue
        core = ndi.distance_transform_edt(region)>margin*2
        candidates.append(dict(class_id=group+1, candidate=region, core=core, contacts=contacts,
                               extraction='combined_strokes'))
    # A narrow closed outline can share a nearby boundary with another color.
    # Do not silently lose it because the combined contact vote favored that neighbor.
    for group, outline in enumerate(outlines):
        if any(c['class_id']==group+1 for c in candidates):
            continue
        own_barrier=ndi.binary_closing(ndi.binary_dilation(outline,iterations=2),iterations=6)
        inside=ndi.binary_fill_holes(own_barrier)&~own_barrier
        own_labels,own_count=ndi.label(inside)
        occupied=np.logical_or.reduce([c['candidate'] for c in candidates]) if candidates else np.zeros_like(inside)
        for k in range(1,own_count+1):
            region=(own_labels==k)&~occupied
            core=ndi.distance_transform_edt(region)>margin*2
            if region.sum()<1000 or not core.any():
                continue
            candidates.append(dict(class_id=group+1,candidate=region,core=core,contacts=None,
                                   extraction='closed_single_color_missing_class'))
    return candidates, np.logical_or.reduce(outlines)

def render_expected(raw, origin, shape):
    aligned = ndi.affine_transform(np.asarray(raw,np.float32),np.eye(2),offset=-origin[::-1],
                                  output_shape=shape,order=1,mode='constant',cval=np.nan,prefilter=False)
    finite=np.isfinite(aligned);values=aligned.astype(float);lo,hi=np.percentile(values[finite],[1,99])
    norm=np.zeros(shape,float);norm[finite]=np.clip((values[finite]-lo)/max(float(hi-lo),1e-12),0,1)
    return np.asarray(Image.fromarray((norm*255).astype(np.uint8)).resize((shape[1]*2,shape[0]*2),Image.Resampling.LANCZOS))
