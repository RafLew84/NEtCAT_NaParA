"""Block-masked reconstruction with exactly the issue-21 AE32 parameters.

This is a convolutional masked-autoencoder task, not a reproduction of the
asymmetric ViT-MAE architecture. Inference always uses the unmasked encoder.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from ...bundle import file_hash
from ..checkpoint import config_hash, read_checkpoint
from ..models import ARCHITECTURE as AE_ARCHITECTURE, Autoencoder, _check_images


MASK_RATIOS = {"mask25": .25, "mask50": .5}
BLOCK_SIZE = 16
ARCHITECTURE = dict(
    schema="stmdomains-block-masked-ae25-v1", backbone=AE_ARCHITECTURE,
    latent_dimension=32, parameter_count=250513,
    masking=dict(block_shape=[16, 16], grid_shape=[4, 4], fill=0.,
        ratios=MASK_RATIOS, order="Independent uniform16-block permutation per image; first4/8 removed",
        normalization="Original fixed20 scalar transform; no patch or per-image normalization",
        physical_block_sizes_px={32: 8, 48: 12, 64: 16},
        placement="After original21 resampling and photometric augmentation; before encoder",
        capacity="No mask channel, learned token, new layer or extra parameter"),
    objective="MSE on artificially masked measured pixels only",
    inference="Unmasked original AE32 encode(images)['content']; decoder unused for domains",
    source="https://github.com/facebookresearch/mae/blob/main/models_mae.py",
    distinction="Convolutional zero-masked task; not token-dropping ViT-MAE reproduction",
)


def make_model(family: str, latent_dim: int = 32):
    if family not in MASK_RATIOS or latent_dim != 32:
        raise ValueError("Only mask25/mask50 AE32 belong to this frozen trial")
    model = Autoencoder(32)
    model.family = family
    return model


def block_masks(batch_size: int, fraction: float, rng: np.random.Generator, *, with_order=False):
    """CPU boolean masks; both fractions consume exactly the same RNG draws."""
    if batch_size < 1 or fraction not in MASK_RATIOS.values():
        raise ValueError("Expected a positive batch and mask fraction .25 or .5")
    order = np.stack([rng.permutation(16) for _ in range(batch_size)]).astype(np.int16)
    tiles = np.zeros((batch_size, 16), dtype=bool)
    tiles[np.arange(batch_size)[:, None], order[:, :int(16 * fraction)]] = True
    pixels = tiles.reshape(batch_size, 1, 4, 4).repeat(BLOCK_SIZE, axis=2).repeat(BLOCK_SIZE, axis=3)
    mask = torch.from_numpy(pixels)
    return (mask, order) if with_order else mask


def _check_mask(mask, images, name):
    if mask.dtype != torch.bool or mask.shape != images.shape or mask.device != images.device:
        raise ValueError(f"{name} must be a boolean mask matching the image tensor/device")


def apply_mask(images, mask, measured=None):
    """Artificial masking only; reject partial measurement rather than pad it."""
    _check_images(images)
    _check_mask(mask, images, "Artificial mask")
    if measured is not None:
        _check_mask(measured, images, "Measured mask")
        if not bool(measured.all()):
            raise ValueError("Issue25 admits only fully measured prepared windows; no measurement padding")
    if not bool(torch.isfinite(images).all()):
        raise ValueError("Non-finite measured model input")
    return torch.where(mask, torch.zeros_like(images), images)


def masked_losses(prediction, target, mask, measured=None):
    """Ignore unmeasured values even if they contain NaN; never use them as truth."""
    _check_images(prediction)
    _check_images(target)
    if prediction.shape != target.shape or prediction.device != target.device:
        raise ValueError("Prediction and target tensors differ")
    _check_mask(mask, target, "Artificial mask")
    measured = torch.ones_like(mask) if measured is None else measured
    _check_mask(measured, target, "Measured mask")
    hidden, visible = mask & measured, ~mask & measured
    if not bool(hidden.any()):
        raise ValueError("No measured masked target pixels")
    if not bool(torch.isfinite(target[measured]).all()):
        raise ValueError("Non-finite measured target")
    # Index before subtraction: NaNs outside measured support never enter loss.
    masked_mse = (prediction[hidden] - target[hidden]).square().mean()
    visible_mse = ((prediction[visible] - target[visible]).square().mean()
                   if bool(visible.any()) else prediction[hidden].sum() * 0.)
    full_mse = (prediction[measured] - target[measured]).square().mean()
    return dict(loss=masked_mse, masked_mse=masked_mse, visible_mse=visible_mse,
                full_mse=full_mse, masked_pixels=hidden.sum(), measured_pixels=measured.sum())


def load_model(run_dir, device="cpu", *, initial=False, step=None):
    run_dir = Path(run_dir).resolve()
    run = json.loads((run_dir / "run.json").read_text())
    config_path = run_dir / "config.json"
    config = json.loads(config_path.read_text())
    if file_hash(config_path) != run["config_file_sha256"]:
        raise ValueError("Changed masked-AE run configuration")
    if initial:
        if step not in (None, 0):
            raise ValueError("Conflicting initial/step checkpoint selection")
        step = 0
    if step == 0:
        name, digest = run["initial_checkpoint"], run["initial_checkpoint_sha256"]
    elif step is None:
        if run["status"] != "completed":
            raise ValueError("Run has no completed selected model")
        name, digest = run["selected_checkpoint"], run["selected_checkpoint_sha256"]
    else:
        entry = next(row for row in run["checkpoints"] if row["step"] == step)
        name, digest = entry["file"], entry["sha256"]
    path = (run_dir / name).resolve()
    if not path.is_relative_to(run_dir) or file_hash(path) != digest:
        raise ValueError("Changed or escaping checkpoint")
    saved = read_checkpoint(path)
    if saved["config_hash"] != config_hash(config):
        raise ValueError("Checkpoint configuration differs from its run")
    model = make_model(config["family"], config["latent_dim"])
    model.load_state_dict(saved["model"])
    model.to(device).eval()
    model.run_config = config
    return model
