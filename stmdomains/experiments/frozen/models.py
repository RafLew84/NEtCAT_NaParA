"""Official fixed weights, explicit taps, no downloads during extraction."""
import hashlib
import os
from pathlib import Path
import sys
import torch
import torchvision
from torchvision.models.segmentation import fcn_resnet101
from stmdomains.experiments.bundle import file_hash

DINO_PIN='7764ea0f912e53c92e82eb78a2a1631e92725fc8'
ASSETS={
 'fcn_resnet101':dict(file='fcn_resnet101_coco-7ecb50ca.pth',sha256='7ecb50ca17844860a70d5ed0c748d997cf8adb62932abaa0233430c68594d749',url='https://download.pytorch.org/models/fcn_resnet101_coco-7ecb50ca.pth'),
 'dinov2_vits14':dict(file='dinov2_vits14_pretrain.pth',sha256='b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9',url='https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth')}


def state_digest(model):
    digest=hashlib.sha256()
    for name,value in sorted(model.state_dict().items()):
        data=value.detach().cpu().contiguous().numpy()
        digest.update(name.encode());digest.update(str(data.dtype).encode());digest.update(str(data.shape).encode());digest.update(data.tobytes())
    return digest.hexdigest()


class FrozenExtractor:
    def __init__(self, name, assets, device):
        self.name=name;self.device=torch.device(device);asset=ASSETS[name];path=Path(assets)/asset['file']
        if file_hash(path)!=asset['sha256']:
            raise ValueError('Weight SHA-256 mismatch')
        state=torch.load(path,map_location='cpu',weights_only=True)
        if name=='fcn_resnet101':
            full=fcn_resnet101(weights=None,weights_backbone=None,aux_loss=True)
            full.load_state_dict(state,strict=True)
            self.model=torch.nn.ModuleDict({k:full.backbone[k] for k in ['conv1','bn1','relu','maxpool','layer1','layer2']})
            self.dimension=768
            source_files=[Path(torchvision.models.segmentation.fcn.__file__),Path(torchvision.models.resnet.__file__)]
            layers=dict(names=['backbone.layer1','backbone.layer2'],channels=[256,512],native_strides=[4,8],convolution_receptive_fields=[35,91],pooling='spatial mean of each layer, concatenated; no classifier')
            self.map_shapes=lambda size:[[256,(size+3)//4,(size+3)//4],[512,(size+7)//8,(size+7)//8]]
        elif name=='dinov2_vits14':
            source=Path(assets)/('dinov2-'+DINO_PIN)
            sys.path.insert(0,str(source));os.environ['XFORMERS_DISABLED']='1'
            from dinov2.hub.backbones import dinov2_vits14
            self.model=dinov2_vits14(pretrained=False)
            self.model.load_state_dict(state,strict=True);self.dimension=384
            source_files=sorted((source/'dinov2').rglob('*.py'))
            layers=dict(names=['x_norm_patchtokens'],channels=[384],block=11,patch_size=14,registers=0,pooling='mean of final LayerNorm patch tokens, no CLS, no additional L2',context='all pixels of the input crop through self-attention')
            self.map_shapes=lambda size:[[384,size//14,size//14]]
        else:
            raise ValueError('Unsupported model')
        self.model.eval().requires_grad_(False).to(self.device)
        self.before=state_digest(self.model)
        self.identity=dict(name=name,weights=asset,layers=layers,torch=torch.__version__,torchvision=torchvision.__version__,
                           source_hashes={str(p.relative_to(source)) if name=='dinov2_vits14' else p.name:file_hash(p) for p in source_files},
                           dinov2_commit=DINO_PIN if name=='dinov2_vits14' else None,
                           device=str(self.device),gpu=torch.cuda.get_device_name(self.device) if self.device.type=='cuda' else None,
                           cuda_runtime=torch.version.cuda,cudnn=torch.backends.cudnn.version(),
                           compute_capability=list(torch.cuda.get_device_capability(self.device)) if self.device.type=='cuda' else None,
                           dtype='float32',tf32=False,state_before=self.before)

    @torch.inference_mode()
    def maps(self,x):
        x=x.to(self.device)
        if self.name=='dinov2_vits14':
            tokens=self.model.forward_features(x)['x_norm_patchtokens']
            n=int(tokens.shape[1]**.5)
            return [tokens.transpose(1,2).reshape(len(x),384,n,n)]
        for name in ['conv1','bn1','relu','maxpool','layer1']:
            x=self.model[name](x)
        a=x;b=self.model['layer2'](a)
        return [a,b]

    @torch.inference_mode()
    def __call__(self,x):
        return torch.cat([m.mean(dim=(-2,-1)) for m in self.maps(x)],dim=1).cpu().numpy()

    def frozen_proof(self):
        after=state_digest(self.model)
        proof=dict(state_before=self.before,state_after=after,equal=self.before==after,
                   training_modules=sum(m.training for m in self.model.modules()),
                   trainable_parameters=sum(p.numel() for p in self.model.parameters() if p.requires_grad),
                   parameters_with_grad=sum(p.grad is not None for p in self.model.parameters()))
        if not proof['equal'] or any(proof[k] for k in ['training_modules','trainable_parameters','parameters_with_grad']):
            raise RuntimeError('Frozen model changed')
        return proof
