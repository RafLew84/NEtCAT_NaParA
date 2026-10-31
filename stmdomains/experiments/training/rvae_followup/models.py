"""One fixed Fourier-coordinate decoder and trusted checkpoint loading for21a."""
from __future__ import annotations

import json
import math
from pathlib import Path

import torch
from torch import nn

from ...bundle import file_hash
from .. import models as original
from ..checkpoint import read_checkpoint

FAMILIES = ("rvae_lowkl", "rvae_fourier", "rvae_fourier_lowkl")
FREQUENCIES = (1., 2., 4., 8., 16.)
BETAS = {"rvae": .001, "rvae_lowkl": .0001,
         "rvae_fourier": .001, "rvae_fourier_lowkl": .0001}
ARCHITECTURE = {
    "schema": "stmdomains-rvae-followup-architecture-v1",
    "base": original.ARCHITECTURE,
    "content_dimension": 32,
    "families": FAMILIES,
    "fourier": {
        "frequencies": FREQUENCIES, "phase": "pi*k*transformed_xy",
        "transform_order": "rotate and translate raw coordinates, then encode",
        "features": "concat(raw_xy,flatten(sin(phase))/sqrt(5),flatten(cos(phase))/sqrt(5))",
        "coordinate_dimensions": 22,
        "decoder": "Linear(32+22,64),Tanh,Linear(64,64),Tanh,Linear(64,1)",
        "initialization": "reuse base encoder/head and decoder hidden/output; replace input linear; restore constructor RNG afterwards",
        "choice": "one logarithmic frequency bank, fixed before training; no search",
    },
    "beta": BETAS,
    "loss": "pixel-mean MSE + beta * latent-sum KL; mean over batch",
}


def pose_coordinates(coordinates: torch.Tensor, latent: torch.Tensor, content_dim: int = 32):
    theta = latent[:, content_dim]
    c, s = theta.cos(), theta.sin()
    rotation = torch.stack((c, -s, s, c), dim=-1).reshape(-1, 2, 2)
    return coordinates @ rotation + .1 * latent[:, None, content_dim + 1:]


def fourier_coordinates(xy: torch.Tensor) -> torch.Tensor:
    frequencies = xy.new_tensor(FREQUENCIES)
    phase = math.pi * xy[..., :, None] * frequencies
    return torch.cat((xy, phase.sin().flatten(-2) / math.sqrt(5),
                      phase.cos().flatten(-2) / math.sqrt(5)), dim=-1)


class FourierRotationalVAE(original.RotationalVAE):
    family = "rvae_fourier"

    def __init__(self, latent_dim: int = 32):
        if latent_dim != 32:
            raise ValueError("Issue21a includes only z32")
        super().__init__(latent_dim)
        # Keep encoder/head/hidden weights and the posterior RNG sequence paired
        # with the original family. This is initialization, not a trained copy.
        state = torch.get_rng_state()
        self.decoder[0] = nn.Linear(latent_dim + 22, 64)
        torch.set_rng_state(state)

    def decode(self, latent: torch.Tensor) -> torch.Tensor:
        xy = pose_coordinates(self.coordinates, latent, self.latent_dim)
        spatial = fourier_coordinates(xy)
        content = latent[:, None, :self.latent_dim].expand(-1, 4096, -1)
        return self.decoder(torch.cat((spatial, content), dim=-1)).reshape(-1, 1, 64, 64)


def make_model(family: str, latent_dim: int = 32) -> nn.Module:
    if family in ("ae", "rvae"):
        return original.make_model(family, latent_dim)
    if latent_dim != 32 or family not in FAMILIES:
        raise ValueError("Unknown issue21a model or dimension")
    model = (FourierRotationalVAE(latent_dim) if "fourier" in family
             else original.RotationalVAE(latent_dim))
    model.family = family
    return model


def load_model(run_dir: str | Path, device: str = "cpu", step: int | None = None) -> nn.Module:
    """Load a selected or explicitly fixed-step checkpoint, checking its hash."""
    run_dir = Path(run_dir)
    result = json.loads((run_dir / "run.json").read_text())
    if step is None:
        if result["status"] != "completed" or not result.get("selected_checkpoint"):
            raise ValueError("Run has no completed selected model")
        filename, digest = result["selected_checkpoint"], result["selected_checkpoint_sha256"]
    else:
        matches = [row for row in result["checkpoints"] if row["step"] == step]
        if len(matches) != 1:
            raise ValueError(f"Checkpoint at step{step} unavailable")
        filename, digest = matches[0]["file"], matches[0]["sha256"]
    path = (run_dir / filename).resolve()
    if not path.is_relative_to(run_dir.resolve()) or file_hash(path) != digest:
        raise ValueError("Checkpoint path/hash mismatch")
    state = read_checkpoint(path)
    if state["config_hash"] != result["config_hash"]:
        raise ValueError("Selected checkpoint configuration mismatch")
    config = state["config"]
    model = make_model(config["family"], config["latent_dim"])
    model.load_state_dict(state["model"])
    model.to(device).eval()
    model.run_config = config
    model.loaded_step = state["progress"]["step"]
    return model
