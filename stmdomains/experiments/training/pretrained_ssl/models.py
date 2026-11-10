"""Bounded local DINO adaptation of the pinned, unchanged ViT-S/14 asset.

The 256 training outputs are not domain classes. Exported features are the
384-dimensional mean of final normalized patch tokens, before the head.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys

import torch
from torch import nn
import torch.nn.functional as F

from ...bundle import arrays_hash, file_hash
from ...frozen.models import ASSETS, DINO_PIN
from ..checkpoint import config_hash, read_checkpoint
from ..models import _check_images


DEFAULT_ASSETS = Path(__file__).resolve().parents[4] / ".scratch/frozen-feature-assets"
ARCHITECTURE = dict(
    schema="stmdomains-local-dino26-v1", backbone="dinov2_vits14", commit=DINO_PIN,
    backbone_parameters=22056576, trainable_parameters=1907392,
    input="Original20 gray64; bilinear112 align_corners=False; RGB repeat; ImageNet mean/std",
    patch_grid=[8, 8], feature_dimension=384, trainable_blocks=[11], trainable_final_norm=True,
    head=dict(input=384, hidden=256, bottleneck=64, outputs=256, layers=2,
              batch_norm=False, output_weight_norm=True, frozen_weight_g=1.),
    readout="Mean of all64 x_norm_patchtokens after final LayerNorm, no CLS/head/additionalL2",
    primary_role="teacher", masking=False, student_temperature=.1, teacher_temperature=.04,
    center_momentum=.9, ema="Cosine .996 to1 over fixed1000 optimizer steps",
    correspondence="6x6 canonical indices1..6; view index=i-8*translation_raw/scale_raw; dense bilinear weights",
    precision="float32; no AMP/TF32; tensor SDPA without xformers",
    sources=["https://arxiv.org/abs/2104.14294", "https://arxiv.org/abs/2111.07832",
             "https://github.com/facebookresearch/dinov2/tree/" + DINO_PIN],
    distinction="Local cross-view self-distillation inspired by DINO; not full DINO/iBOT reproduction",
)


def asset_identity(assets=DEFAULT_ASSETS):
    assets = Path(assets).resolve()
    weight = assets / ASSETS["dinov2_vits14"]["file"]
    if file_hash(weight) != ASSETS["dinov2_vits14"]["sha256"]:
        raise ValueError("Changed DINOv2 pretrained weights")
    source = assets / ("dinov2-" + DINO_PIN)
    paths = sorted((source / "dinov2").rglob("*.py"))
    if not paths:
        raise ValueError("Missing pinned DINOv2 source")
    return dict(assets_root=str(assets), weights_file=str(weight), weights_sha256=file_hash(weight),
                source_root=str(source), commit=DINO_PIN,
                source_sha256={str(p.relative_to(source)): file_hash(p) for p in paths})


def official_backbone(assets=DEFAULT_ASSETS):
    identity = asset_identity(assets)
    os.environ["XFORMERS_DISABLED"] = "1"
    source = identity["source_root"]
    if source not in sys.path:
        sys.path.insert(0, source)
    from dinov2.hub.backbones import dinov2_vits14
    from dinov2.layers.dino_head import DINOHead
    import dinov2
    if not Path(dinov2.__file__).resolve().is_relative_to(Path(source)):
        raise ValueError("DINO import resolved outside pinned source")
    model = dinov2_vits14(pretrained=False)
    model.load_state_dict(torch.load(identity["weights_file"], map_location="cpu", weights_only=True), strict=True)
    model.eval().requires_grad_(False)
    return model, DINOHead, identity


def state_digest(module):
    return arrays_hash({name: value.detach().cpu().numpy() for name, value in module.state_dict().items()})


def transform(images):
    _check_images(images)
    if not bool(torch.isfinite(images).all()):
        raise ValueError("Non-finite fully measured model input")
    rgb = F.interpolate(images, size=(112, 112), mode="bilinear", align_corners=False).repeat(1, 3, 1, 1)
    mean = images.new_tensor([.485, .456, .406])[None, :, None, None]
    std = images.new_tensor([.229, .224, .225])[None, :, None, None]
    return (rgb - mean) / std


def aligned_tokens(local_maps, shifts_xy, scales):
    """Same raw positions in each translated crop; no token extrapolation."""
    if local_maps.ndim != 4 or local_maps.shape[-2:] != (8, 8):
        raise ValueError("Expected [B,C,8,8] token maps")
    b = len(local_maps)
    shifts = torch.as_tensor(shifts_xy, dtype=local_maps.dtype, device=local_maps.device)
    scales = torch.as_tensor(scales, dtype=local_maps.dtype, device=local_maps.device)
    if shifts.shape != (b, 2) or scales.shape != (b,):
        raise ValueError("Expected shifts[B,2], scales[B]")
    if not bool(torch.isfinite(shifts).all()) or bool((shifts.abs() > 2).any()) or not bool(((scales == 32) | (scales == 48) | (scales == 64)).all()):
        raise ValueError("Correspondence exceeds declared measured support")
    axis = torch.arange(8, dtype=local_maps.dtype, device=local_maps.device)
    canonical = axis[1:7]
    yy, xx = torch.meshgrid(canonical, canonical, indexing="ij")
    xy = torch.stack((xx.flatten(), yy.flatten()), dim=-1)
    coordinates = xy[None] - shifts[:, None] * (8 / scales[:, None, None])
    wx = (1 - (coordinates[..., 0, None] - axis).abs()).clamp(min=0)
    wy = (1 - (coordinates[..., 1, None] - axis).abs()).clamp(min=0)
    weights = (wy[..., :, None] * wx[..., None, :]).flatten(2)
    return torch.bmm(weights, local_maps.flatten(2).transpose(1, 2))


def entropy_statistics(probabilities):
    """Retain image and position axes to expose position-only degeneracy."""
    p = probabilities.float()  # [B,2,36,256]
    entropy = lambda x: -(x * x.clamp_min(1e-30).log()).sum(-1)
    marginal = entropy(p.mean((0, 1, 2)))
    conditional = entropy(p).mean()
    position_information = (entropy(p.mean(0)) - entropy(p).mean(0)).mean()
    return dict(head_marginal_entropy=marginal, head_mean_entropy=conditional,
                head_mutual_information=marginal-conditional,
                head_position_conditional_information=position_information)


class LocalDINO(nn.Module):
    """One immutable backbone plus small student/EMA suffixes and heads."""
    def __init__(self, assets=DEFAULT_ASSETS):
        super().__init__()
        self.backbone, head_class, self.asset = official_backbone(assets)
        self.base_digest = state_digest(self.backbone)
        student = nn.ModuleDict(dict(block=deepcopy(self.backbone.blocks[-1]), norm=deepcopy(self.backbone.norm),
            head=head_class(384, 256, use_bn=False, nlayers=2, hidden_dim=256, bottleneck_dim=64)))
        teacher = nn.ModuleDict(dict(block=deepcopy(self.backbone.blocks[-1]), norm=deepcopy(self.backbone.norm),
            head=head_class(384, 256, use_bn=False, nlayers=2, hidden_dim=256, bottleneck_dim=64)))
        teacher.load_state_dict(student.state_dict())
        student.requires_grad_(True)
        student["head"].last_layer.weight_g.requires_grad_(False)
        teacher.eval().requires_grad_(False)
        self.delta = nn.ModuleDict(dict(student=student, teacher=teacher))
        self.delta.register_buffer("center", torch.zeros(1, 1, 256))
        self.train()
        if sum(p.numel() for p in self.parameters() if p.requires_grad) != ARCHITECTURE["trainable_parameters"]:
            raise ValueError("Unexpected trainable capacity")

    def train(self, mode=True):
        super().train(mode)
        self.backbone.eval()
        self.delta["teacher"].eval()
        return self

    def prefix(self, gray):
        # Not inference_mode: the trainable suffix needs to save these tensors.
        with torch.no_grad():
            x = self.backbone.prepare_tokens_with_masks(transform(gray))
            for block in self.backbone.blocks[:-1]:
                x = block(x)
        return x

    def tokens(self, prefix, role):
        module = self.delta[role]
        return module["norm"](module["block"](prefix))[:, 1:]

    @torch.no_grad()
    def base_tokens(self, prefix):
        return self.backbone.norm(self.backbone.blocks[-1](prefix))[:, 1:]

    @torch.no_grad()
    def update_teacher(self, step, total_steps, teacher_logits):
        if not 1 <= step <= total_steps:
            raise ValueError("Invalid EMA step")
        momentum = 1 - .004 * (math.cos(math.pi * step / total_steps) + 1) / 2
        student = dict(self.delta["student"].named_parameters())
        for name, parameter in self.delta["teacher"].named_parameters():
            if student[name].requires_grad:
                parameter.mul_(momentum).add_(student[name], alpha=1-momentum)
            else:
                parameter.copy_(student[name])
        self.delta.center.mul_(.9).add_(teacher_logits.detach().mean((0, 1, 2))[None, None], alpha=.1)
        return momentum

    def frozen_proof(self):
        digest = state_digest(self.backbone)
        proof = dict(base_state_sha256=self.base_digest, after_state_sha256=digest,
                     unchanged=digest == self.base_digest,
                     frozen_parameters_with_grad=sum(p.grad is not None for p in self.backbone.parameters()),
                     frozen_trainable_parameters=sum(p.requires_grad for p in self.backbone.parameters()),
                     teacher_parameters_with_grad=sum(p.grad is not None for p in self.delta["teacher"].parameters()))
        if not proof["unchanged"] or any(proof[k] for k in ("frozen_parameters_with_grad", "frozen_trainable_parameters", "teacher_parameters_with_grad")):
            raise RuntimeError("Frozen backbone or teacher gradient contract violated")
        return proof


def batch_terms(model, batch, device, *, details=False):
    views = batch["views"].to(device)
    shifts, scales = batch["shifts"].to(device), batch["scales"].to(device)
    b = len(views)
    prefix = model.prefix(views.flatten(0, 1))
    student = model.tokens(prefix, "student").reshape(b, 2, 64, 384)
    with torch.no_grad():
        teacher = model.tokens(prefix, "teacher").reshape(b, 2, 64, 384)
    aligned = {}
    for role, tokens in (("student", student), ("teacher", teacher)):
        maps = tokens.permute(0, 1, 3, 2).reshape(b*2, 384, 8, 8)
        aligned[role] = aligned_tokens(maps, shifts.flatten(0, 1), scales.repeat_interleave(2)).reshape(b, 2, 36, 384)
    student_logits = model.delta["student"]["head"](aligned["student"])
    with torch.no_grad():
        teacher_logits = model.delta["teacher"]["head"](aligned["teacher"])
        probabilities = F.softmax((teacher_logits-model.delta.center) / .04, dim=-1)
    loss = -(probabilities[:, [1, 0]] * F.log_softmax(student_logits/.1, dim=-1)).sum(-1).mean()
    token_std = aligned["student"].detach().flatten(0, 2).std(0, unbiased=False)
    descriptor = student.mean(2)
    descriptor_std = descriptor.detach().flatten(0, 1).std(0, unbiased=False)
    terms = dict(loss=loss, token_std_max=token_std.max(), descriptor_std_max=descriptor_std.max(),
                 descriptor_std_mean=descriptor_std.mean(), **entropy_statistics(probabilities))
    extra = dict(teacher_logits=teacher_logits)
    if details:
        with torch.no_grad():
            base = model.base_tokens(prefix).reshape(b, 2, 64, 384).mean(2)
        extra.update(student_descriptor=descriptor.detach(), teacher_descriptor=teacher.mean(2),
                     base_descriptor=base, probabilities=probabilities,
                     aligned_student=aligned["student"].detach(), aligned_teacher=aligned["teacher"])
    return terms, extra


class DINOEncoder(nn.Module):
    family = "dino_adapted"
    latent_dim = 384

    def __init__(self, assets=DEFAULT_ASSETS):
        super().__init__()
        self.backbone, _, self.asset = official_backbone(assets)

    def encode(self, images):
        tokens = self.backbone.forward_features(transform(images))["x_norm_patchtokens"]
        content = tokens.mean(1)
        return dict(content=content, descriptor=content,
                    local_map=tokens.transpose(1, 2).reshape(len(images), 384, 8, 8),
                    angle_radians=None, translation_normalized_xy=None, mean=None, logvar=None)

    def forward(self, images):
        return self.encode(images)


def load_frozen(assets=DEFAULT_ASSETS, device="cpu"):
    model = DINOEncoder(assets).to(device).eval().requires_grad_(False)
    model.family = "dino_frozen"
    return model


def load_model(run_dir, device="cpu", *, role="teacher", initial=False):
    if role not in ("student", "teacher"):
        raise ValueError("Unknown checkpoint encoder role")
    directory = Path(run_dir).resolve()
    run = json.loads((directory / "run.json").read_text())
    config = json.loads((directory / "config.json").read_text())
    if file_hash(directory / "config.json") != run["config_file_sha256"]:
        raise ValueError("Changed run config")
    key = "initial" if initial else "selected"
    if not initial and run["status"] != "completed":
        raise ValueError("No completed checkpoint")
    path = (directory / run[key + "_checkpoint"]).resolve()
    if not path.is_relative_to(directory) or file_hash(path) != run[key + "_checkpoint_sha256"]:
        raise ValueError("Changed or escaping checkpoint")
    saved = read_checkpoint(path)
    if saved["config_hash"] != config_hash(config):
        raise ValueError("Checkpoint/config mismatch")
    model = DINOEncoder(config["assets_root"])
    if model.asset != config["asset"] or state_digest(model.backbone) != config["base_state_sha256"]:
        raise ValueError("Changed required base checkpoint or source")
    values = saved["model"]
    for name, module in (("block", model.backbone.blocks[-1]), ("norm", model.backbone.norm)):
        prefix = role + "." + name + "."
        module.load_state_dict({k[len(prefix):]: v for k, v in values.items() if k.startswith(prefix)}, strict=True)
    model.to(device).eval().requires_grad_(False)
    model.run_config = config
    return model
