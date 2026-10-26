"""Crop geometry in original pixel-edge coordinates, independent of models."""
from dataclasses import asdict, dataclass
import numpy as np
import torch
import torch.nn.functional as F
from stmdomains.experiments.bundle import arrays_hash


@dataclass(frozen=True)
class FeatureConfig:
    model: str
    radius: int = 24
    input_size: int = 112
    normalization: str = 'frame_percentile'
    grid_step: int = 12

    def __post_init__(self):
        if self.model not in ('fcn_resnet101', 'dinov2_vits14'):
            raise ValueError('Unsupported model')
        if self.radius <= 0 or self.grid_step <= 0 or self.input_size <= 0 or self.input_size % 14:
            raise ValueError('Positive scales and input size divisible by 14 required')
        if self.normalization not in ('frame_percentile', 'frame_minmax'):
            raise ValueError('Unsupported normalization')

    @property
    def name(self):
        return f'{self.model}-r{self.radius}-s{self.input_size}-{self.normalization}'

    def as_dict(self):
        return asdict(self)


def image_digest(record, arrays):
    return arrays_hash(dict(image=arrays['image'], measured=arrays['measured'],
                            pixel_spacing_xy=np.asarray(record['pixel_spacing_xy'], dtype=np.float64)))


def prepare_image(arrays, normalization):
    measured=arrays['measured']; image=np.asarray(arrays['image'], dtype=np.float64)
    values=image[measured]
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Missing finite measured pixels')
    if normalization == 'frame_percentile':
        lo,hi=np.percentile(values,[2,98])
    elif normalization == 'frame_minmax':
        lo,hi=values.min(),values.max()
    else:
        raise ValueError('Unknown normalization')
    denominator=hi-lo
    gray=np.zeros(image.shape, dtype=np.float32)
    if denominator>0:
        gray[measured]=np.clip((image[measured]-lo)/denominator,0,1)
        gray[~measured]=np.median(gray[measured])
    return torch.from_numpy(gray)[None,None], dict(low=float(lo),high=float(hi),
        flat=bool(denominator==0),statistics_scope='all measured pixels of original frame',
        missing_fill='median normalized measured value',channels='replicated gray RGB',
        rgb_mean=[.485,.456,.406],rgb_std=[.229,.224,.225])


def locations(record, arrays, config, mode):
    spacing=np.asarray(record['pixel_spacing_xy'],float)
    if spacing.shape!=(2,) or not np.isfinite(spacing).all() or np.any(spacing<=0):
        raise ValueError('Invalid technical pixel spacing')
    height,width=arrays['image'].shape
    if mode=='grid':
        x=np.arange(config.grid_step/2,width*spacing[0],config.grid_step)/spacing[0]
        y=np.arange(config.grid_step/2,height*spacing[1],config.grid_step)/spacing[1]
        xx,yy=np.meshgrid(x,y);xy=np.c_[xx.ravel(),yy.ravel()]
        ids=np.array([f'grid-{i:06}' for i in range(len(xy))],dtype='U64')
    elif mode=='centers':
        order=np.argsort(arrays['object_ids']);xy=arrays['centers_xy'][order];ids=arrays['object_ids'][order]
    else:
        raise ValueError('Unknown sampling mode')
    extent=config.radius/spacing
    boxes=np.c_[xy-extent,xy+extent]
    clipped=boxes.copy();clipped[:,:2]=np.maximum(clipped[:,:2],0);clipped[:,2:]=np.minimum(clipped[:,2:],[width,height])
    return dict(xy=np.asarray(xy,float),object_ids=ids,window_xyxy=boxes,
                clipped_window_xyxy=clipped,source_measured=arrays['measured'].copy())


def sample_crops(gray, measured, boxes, size):
    """Model pixels sample source edge coordinates with align_corners=False.

    Reflection fills the image outside the field; a zero-padded mask separately
    measures the contribution of real pixels. Missing source pixels are imputed.
    """
    h,w=gray.shape[-2:];boxes=torch.as_tensor(boxes,dtype=torch.float32)
    t=(torch.arange(size,dtype=torch.float32)+.5)/size
    x=boxes[:,0,None]+t*(boxes[:,2]-boxes[:,0])[:,None]
    y=boxes[:,1,None]+t*(boxes[:,3]-boxes[:,1])[:,None]
    grid=torch.stack((x[:,None,:].expand(-1,size,-1)*2/w-1,
                      y[:,:,None].expand(-1,-1,size)*2/h-1),-1)
    n=len(boxes)
    crops=F.grid_sample(gray.expand(n,-1,-1,-1),grid,mode='bilinear',padding_mode='reflection',align_corners=False)
    mask=torch.as_tensor(measured,dtype=torch.float32)[None,None].expand(n,-1,-1,-1)
    support=F.grid_sample(mask,grid,mode='bilinear',padding_mode='zeros',align_corners=False)
    rgb=crops.expand(-1,3,-1,-1)
    mean=torch.tensor([.485,.456,.406])[None,:,None,None];std=torch.tensor([.229,.224,.225])[None,:,None,None]
    return (rgb-mean)/std, support[:,0]
