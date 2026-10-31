"""Spatial SSL model and exact correspondence convention frozen before issue22."""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn

from ...bundle import file_hash
from ..checkpoint import config_hash, read_checkpoint
from ..models import _check_images

ARCHITECTURE = {
    "schema": "stmdomains-local-ssl-architecture-v1",
    "input": [1, 64, 64], "local_channels": [16, 32],
    "encoder": {"channels": [16, 32, 64], "kernel": 3, "stride": 2,
                "padding": 0, "activation": "GELU", "batch_norm": False,
                "final_shape": [64, 7, 7]},
    "head": "Conv2d64->z,kernel1,stride1,bias=True,identity activation",
    "descriptor": "Flatten [z,7,7] in channel,y,x order; no spatial pooling",
    "correspondence": {
        "token_receptive_field_input_px": 15, "token_stride_input_px": 8,
        "token_centers_input_edge_px": [7.5, 15.5, 23.5, 31.5, 39.5, 47.5, 55.5],
        "canonical_indices_yx": [1, 2, 3, 4, 5],
        "view_index_xy": "canonical_index_xy - translation_raw_xy * (64/scale_raw_px) / 8",
        "interpolation": "Dense separable linear weights followed by bmm; deterministic backward, no grid_sample",
        "support": "25 interior canonical tokens; all four bilinear neighbors within 7x7 for every declared scale and shift",
        "interpretation": "Known geometric correspondence; interpolated convolutional features are approximately translation equivariant",
    },
    "objective": {
        "weights": {"invariance": 25., "variance": 25., "covariance": 1.},
        "invariance": "MSE of aligned local channels over batch,25 positions,channels",
        "statistics_pool": "Batch times 25 corresponding local positions; channels remain separate",
        "variance": "Mean of two views' mean relu(1-sqrt(population_var+1e-4))",
        "covariance": "Mean of two views' sum squared off-diagonal sample covariance / channels; divisor N-1",
        "collapse_stop": "Maximum population std <=1e-6 either across aligned batch*positions per channel or across batch for flattened spatial descriptors, both views combined; before optimizer step",
    },
    "precision": "float32", "no_global_pooling": True, "no_grid_sample": True,
    "orientation": "No learned angle head; orientation remains in the spatial descriptor",
    "model_scope": "Research candidate; no structural classes, orientation labels or domain labels",
}


class LocalSSL(nn.Module):
    family = "local_ssl"

    def __init__(self, latent_dim: int):
        super().__init__()
        if latent_dim not in (16, 32):
            raise ValueError("Only local channel widths16/32 belong to the frozen experiment")
        self.latent_dim = latent_dim
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 16, 3, stride=2), nn.GELU(),
            nn.Conv2d(16, 32, 3, stride=2), nn.GELU(),
            nn.Conv2d(32, 64, 3, stride=2), nn.GELU(),
        )
        self.head = nn.Conv2d(64, latent_dim, 1)

    def encode(self, images: torch.Tensor) -> dict:
        _check_images(images)
        local_map = self.head(self.encoder(images))
        content = local_map.flatten(1)
        return {"content": content, "descriptor": content, "local_map": local_map,
                "angle_radians": None, "translation_normalized_xy": None,
                "mean": None, "logvar": None}

    def forward(self, images: torch.Tensor, *, sample: bool = False) -> dict:
        return self.encode(images)


def make_model(family: str, latent_dim: int) -> LocalSSL:
    if family not in ("local_ssl", "local_ssl_untrained"):
        raise ValueError(f"Unknown local SSL family: {family}")
    return LocalSSL(latent_dim)


def aligned_tokens(local_maps: torch.Tensor, shifts_xy: torch.Tensor,
                   scales: torch.Tensor) -> torch.Tensor:
    """Map shifted feature maps to the same25 locations in the original patch.

    Extracting a patch centered at center+shift means canonical input locations
    occur at *minus* that shift in the view. All interpolation neighbors have
    complete measured receptive fields; this function never pads a feature map.
    Dense weights keep both forward and backward deterministic on CUDA.
    """
    if local_maps.ndim != 4 or tuple(local_maps.shape[-2:]) != (7, 7):
        raise ValueError("Expected local feature maps [B,z,7,7]")
    batch = len(local_maps)
    shifts = torch.as_tensor(shifts_xy, dtype=local_maps.dtype, device=local_maps.device)
    scale = torch.as_tensor(scales, dtype=local_maps.dtype, device=local_maps.device)
    if tuple(shifts.shape) != (batch, 2) or tuple(scale.shape) != (batch,):
        raise ValueError("Expected shifts [B,2] and scales [B]")
    if (not bool(torch.isfinite(shifts).all()) or bool((shifts.abs() > 2).any())
            or not bool(((scale == 32) | (scale == 48) | (scale == 64)).all())):
        raise ValueError("Correspondence exceeds frozen scale/translation support")
    canonical = torch.arange(1, 6, dtype=local_maps.dtype, device=local_maps.device)
    yy, xx = torch.meshgrid(canonical, canonical, indexing="ij")
    xy = torch.stack((xx.flatten(), yy.flatten()), dim=1)
    coordinates = xy[None] - shifts[:, None] * (8 / scale[:, None, None])
    axis = torch.arange(7, dtype=local_maps.dtype, device=local_maps.device)
    wx = (1 - (coordinates[..., 0, None] - axis).abs()).clamp(min=0)
    wy = (1 - (coordinates[..., 1, None] - axis).abs()).clamp(min=0)
    weights = (wy[..., :, None] * wx[..., None, :]).flatten(2)
    return torch.bmm(weights, local_maps.flatten(2).transpose(1, 2))


def load_model(run_dir: str | Path, device: str = "cpu", step: int | None = None,
               *, initial: bool = False) -> LocalSSL:
    run_dir = Path(run_dir)
    config = json.loads((run_dir / "config.json").read_text())
    run = json.loads((run_dir / "run.json").read_text())
    if file_hash(run_dir / "config.json") != run["config_file_sha256"]:
        raise ValueError("Changed run configuration")
    if initial:
        if step not in (None, 0):
            raise ValueError("Conflicting initial/step checkpoint selection")
        step = 0
    if step is None:
        name, digest = run["selected_checkpoint"], run["selected_checkpoint_sha256"]
    elif step == 0:
        name, digest = run["initial_checkpoint"], run["initial_checkpoint_sha256"]
    else:
        checkpoint = next(row for row in run["checkpoints"] if row["step"] == step)
        name, digest = checkpoint["file"], checkpoint["sha256"]
    if name is None or file_hash(run_dir / name) != digest:
        raise ValueError("Missing or changed requested checkpoint")
    state = read_checkpoint(run_dir / name)
    if state["config_hash"] != config_hash(config):
        raise ValueError("Checkpoint and run configurations differ")
    model = LocalSSL(config["latent_dim"])
    model.load_state_dict(state["model"])
    model.to(device).eval()
    model.run_config = config
    return model
