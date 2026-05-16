"""
U-Net denoiser helper: model definition, weight loading, and single-image inference.
"""
from __future__ import annotations

import numpy as np
import torch
from pathlib import Path
from typing import Tuple


class DoubleConv(torch.nn.Module):
    """Two Conv2d+ReLU blocks used across encoder/decoder."""
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
            torch.nn.ReLU(inplace=True),
            torch.nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
            torch.nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        return self.net(x)


class UNet(torch.nn.Module):
    """Classic 2D U-Net (4 downs, 4 ups) for single-channel STM denoising."""
    def __init__(self, in_ch: int = 1, out_ch: int = 1, base_ch: int = 64):
        super().__init__()
        self.down1 = DoubleConv(in_ch, base_ch)
        self.down2 = DoubleConv(base_ch, base_ch * 2)
        self.down3 = DoubleConv(base_ch * 2, base_ch * 4)
        self.down4 = DoubleConv(base_ch * 4, base_ch * 8)
        self.pool = torch.nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(base_ch * 8, base_ch * 16)

        self.up4 = torch.nn.ConvTranspose2d(base_ch * 16, base_ch * 8, kernel_size=2, stride=2)
        self.conv4 = DoubleConv(base_ch * 16, base_ch * 8)
        self.up3 = torch.nn.ConvTranspose2d(base_ch * 8, base_ch * 4, kernel_size=2, stride=2)
        self.conv3 = DoubleConv(base_ch * 8, base_ch * 4)
        self.up2 = torch.nn.ConvTranspose2d(base_ch * 4, base_ch * 2, kernel_size=2, stride=2)
        self.conv2 = DoubleConv(base_ch * 4, base_ch * 2)
        self.up1 = torch.nn.ConvTranspose2d(base_ch * 2, base_ch, kernel_size=2, stride=2)
        self.conv1 = DoubleConv(base_ch * 2, base_ch)

        self.out_conv = torch.nn.Conv2d(base_ch, out_ch, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        x1 = self.down1(x)
        x2 = self.down2(self.pool(x1))
        x3 = self.down3(self.pool(x2))
        x4 = self.down4(self.pool(x3))
        x5 = self.bottleneck(self.pool(x4))

        x = self.up4(x5)
        x = self.conv4(torch.cat([x4, x], dim=1))
        x = self.up3(x)
        x = self.conv3(torch.cat([x3, x], dim=1))
        x = self.up2(x)
        x = self.conv2(torch.cat([x2, x], dim=1))
        x = self.up1(x)
        x = self.conv1(torch.cat([x1, x], dim=1))
        return self.out_conv(x)


def _pad_to_multiple(img: np.ndarray, mult: int = 16) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Pad a 2D array so H,W are divisible by `mult`; returns padded image and (pad_h, pad_w)."""
    h, w = img.shape[-2], img.shape[-1]
    pad_h = (mult - h % mult) % mult
    pad_w = (mult - w % mult) % mult
    if pad_h == 0 and pad_w == 0:
        return img, (0, 0)
    padded = np.pad(img, ((0, pad_h), (0, pad_w)), mode="reflect")
    return padded, (pad_h, pad_w)


def _default_weight_path() -> Path:
    """
    Return the first existing default weights path.
    Tries:
    1) napara/models/unet_synthetic_v1.pth (package-local)
    2) project_root/models/unet_synthetic_v1.pth (one level above napara/)
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "models" / "unet_synthetic_v1.pth",
        here.parents[2] / "models" / "unet_synthetic_v1.pth",
    ]
    for p in candidates:
        if p.is_file():
            return p
    # return the first candidate even if missing to report a consistent path
    return candidates[0]


def load_unet(weights_path: str | Path | None = None, device: torch.device | None = None) -> tuple[UNet, torch.device]:
    """
    Load the pretrained U-Net weights and return (model, device).
    Raises FileNotFoundError if the weights are missing.
    """
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if weights_path is None:
        weights_path = _default_weight_path()
    weights_path = Path(weights_path)
    if not weights_path.is_file():
        raise FileNotFoundError(f"Missing U-Net weights: {weights_path}")

    model = UNet(in_ch=1, out_ch=1, base_ch=64).to(device)
    state = torch.load(weights_path, map_location=device)
    model.load_state_dict(state)
    model.eval()
    return model, device


def denoise_stm_image(img_2d: np.ndarray, model: UNet, device: torch.device) -> np.ndarray:
    """
    Run a single STM frame through the U-Net with per-image mean/std normalization.
    Returns a float32 array with the original H×W.
    """
    if img_2d is None:
        raise ValueError("Input image is None.")
    if img_2d.ndim != 2:
        raise ValueError(f"Expected 2D array, got shape {img_2d.shape}.")

    img = np.asarray(img_2d, dtype=np.float32)
    mean = float(img.mean())
    std = float(img.std() + 1e-8)
    img_norm = (img - mean) / std

    img_pad, (ph, pw) = _pad_to_multiple(img_norm, mult=16)
    x = torch.from_numpy(img_pad).unsqueeze(0).unsqueeze(0).to(device)  # [1,1,H,W]

    with torch.no_grad():
        y = model(x)

    out = y.detach().cpu().numpy()[0, 0]
    if ph or pw:
        out = out[: img.shape[0], : img.shape[1]]

    out_denorm = out * std + mean
    return out_denorm.astype(np.float32, copy=False)
