"""Frozen local AE/rVAE definitions for the bounded issue-21 comparison."""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn

from ..bundle import file_hash
from .checkpoint import read_checkpoint


ARCHITECTURE = {
    "schema": "stmdomains-ae-rvae-architecture-v1",
    "input": [1, 64, 64], "content_dimensions": [16, 32],
    "encoder": {"channels": [16, 32, 64], "kernel": 3, "stride": 2,
                "padding": 0, "activation": "GELU", "batch_norm": False,
                "final_shape": [64, 7, 7]},
    "ae": {"head": "Linear3136->z", "decoder": "Linear(z,3136),GELU,reshape64x7x7,ConvTranspose64->32(k3,s2),GELU,ConvTranspose32->16(k3,s2),GELU,ConvTranspose16->1(k4,s2)",
           "output_activation": "identity", "loss": "mean squared error over batch,pixels"},
    "rvae": {"head": "Linear3136->2*(z+3), diagonal Gaussian mean/logvar",
             "latent_order": "content[z],angle,translation_x,translation_y",
             "logvar_bounds": [-12., 8.], "prior": "independent standard normal",
             "coordinate_range": "pixel centers in [-1,1]^2",
             "coordinate_transform": "row_xy @ [[cos(theta),-sin(theta)],[sin(theta),cos(theta)]] + 0.1*(tx,ty)",
             "translation_scale": .1,
             "decoder": "Linear(z+2,64),Tanh,Linear64->64,Tanh,Linear64->1 per coordinate",
             "output_activation": "identity",
             "KL_reduction": "sum latent dimensions then mean batch",
             "validation": "posterior mean reconstruction, fixed beta0.001"},
    "precision": "float32", "no_grid_sample": True,
    "model_scope": "research candidates; no assumed molecular symmetry or domain classes",
}


def _encoder() -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(1, 16, 3, stride=2), nn.GELU(),
        nn.Conv2d(16, 32, 3, stride=2), nn.GELU(),
        nn.Conv2d(32, 64, 3, stride=2), nn.GELU(), nn.Flatten(),
    )


def _check_images(images: torch.Tensor) -> None:
    if images.ndim != 4 or tuple(images.shape[1:]) != (1, 64, 64):
        raise ValueError("Model input must have shape [B,1,64,64]")
    if images.dtype != torch.float32:
        raise ValueError("The frozen experiment uses float32 inputs")


class Autoencoder(nn.Module):
    family = "ae"

    def __init__(self, latent_dim: int):
        super().__init__()
        if latent_dim not in (16, 32):
            raise ValueError("Only z16 and z32 belong to the frozen experiment")
        self.latent_dim = latent_dim
        self.encoder = _encoder()
        self.head = nn.Linear(3136, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 3136), nn.GELU(), nn.Unflatten(1, (64, 7, 7)),
            nn.ConvTranspose2d(64, 32, 3, stride=2), nn.GELU(),
            nn.ConvTranspose2d(32, 16, 3, stride=2), nn.GELU(),
            nn.ConvTranspose2d(16, 1, 4, stride=2),
        )

    def encode(self, images: torch.Tensor) -> dict:
        _check_images(images)
        return {"content": self.head(self.encoder(images)), "angle_radians": None,
                "translation_normalized_xy": None, "mean": None, "logvar": None}

    def forward(self, images: torch.Tensor, *, sample: bool = True) -> dict:
        result = self.encode(images)
        return {**result, "reconstruction": self.decoder(result["content"]),
                "kl_per_sample": images.new_zeros(len(images))}

    def predict(self, images: torch.Tensor) -> torch.Tensor:
        return self(images, sample=False)["reconstruction"]


class RotationalVAE(nn.Module):
    family = "rvae"

    def __init__(self, latent_dim: int):
        super().__init__()
        if latent_dim not in (16, 32):
            raise ValueError("Only z16 and z32 belong to the frozen experiment")
        self.latent_dim = latent_dim
        self.encoder = _encoder()
        self.head = nn.Linear(3136, 2 * (latent_dim + 3))
        self.decoder = nn.Sequential(nn.Linear(latent_dim + 2, 64), nn.Tanh(),
                                     nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 1))
        axis = (torch.arange(64, dtype=torch.float32) + .5) / 32 - 1
        yy, xx = torch.meshgrid(axis, axis, indexing="ij")
        self.register_buffer("coordinates", torch.stack((xx, yy), dim=-1).reshape(1, -1, 2))

    def encode(self, images: torch.Tensor) -> dict:
        _check_images(images)
        mean, logvar = self.head(self.encoder(images)).chunk(2, dim=1)
        logvar = logvar.clamp(-12., 8.)
        return {"content": mean[:, :self.latent_dim],
                "angle_radians": mean[:, self.latent_dim],
                "translation_normalized_xy": .1 * mean[:, self.latent_dim + 1:],
                "mean": mean, "logvar": logvar}

    def decode(self, latent: torch.Tensor) -> torch.Tensor:
        theta = latent[:, self.latent_dim]
        c, s = theta.cos(), theta.sin()
        rotation = torch.stack((c, -s, s, c), dim=-1).reshape(-1, 2, 2)
        xy = self.coordinates @ rotation + .1 * latent[:, None, self.latent_dim + 1:]
        content = latent[:, None, :self.latent_dim].expand(-1, 4096, -1)
        return self.decoder(torch.cat((xy, content), dim=-1)).reshape(-1, 1, 64, 64)

    def forward(self, images: torch.Tensor, *, sample: bool = True) -> dict:
        encoded = self.encode(images)
        mean, logvar = encoded["mean"], encoded["logvar"]
        latent = mean + (.5 * logvar).exp() * torch.randn_like(mean) if sample else mean
        kl = .5 * (mean.square() + logvar.exp() - 1 - logvar).sum(dim=1)
        return {**encoded, "reconstruction": self.decode(latent), "kl_per_sample": kl}

    def predict(self, images: torch.Tensor) -> torch.Tensor:
        return self(images, sample=False)["reconstruction"]


def make_model(family: str, latent_dim: int) -> nn.Module:
    if family == "ae":
        return Autoencoder(latent_dim)
    if family == "rvae":
        return RotationalVAE(latent_dim)
    raise ValueError(f"Unknown issue-21 family: {family}")


def load_model(run_dir: str | Path, device: str = "cpu") -> nn.Module:
    """Load our own selected local checkpoint; models expose encode/predict."""
    run_dir = Path(run_dir)
    result = json.loads((run_dir / "run.json").read_text())
    if result["status"] != "completed" or not result.get("selected_checkpoint"):
        raise ValueError("Run has no completed selected model")
    path = (run_dir / result["selected_checkpoint"]).resolve()
    if not path.is_relative_to(run_dir.resolve()) or file_hash(path) != result["selected_checkpoint_sha256"]:
        raise ValueError("Selected checkpoint path/hash mismatch")
    state = read_checkpoint(path)
    if state["config_hash"] != result["config_hash"]:
        raise ValueError("Selected checkpoint configuration mismatch")
    config = state["config"]
    model = make_model(config["family"], config["latent_dim"])
    model.load_state_dict(state["model"])
    model.to(device).eval()
    model.run_config = config
    return model
