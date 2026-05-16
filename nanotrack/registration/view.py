"""Build independent frame views for translation-only registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter

from nanotrack.core.data_models import RegistrationSettings


SUPPORTED_REGISTRATION_VIEWS = (
    "raw",
    "normalized",
    "gradient_magnitude",
    "high_pass",
    "dog",
)


@dataclass
class RegistrationViewResult:
    """Processed stack used only by registration backends."""

    frames: np.ndarray
    view_name: str
    roi_mask_applied: bool = False
    hann_window_applied: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frames = np.asarray(self.frames, dtype=np.float32)
        if frames.ndim != 3:
            raise ValueError("registration view frames must be a 3D stack.")
        self.frames = frames
        self.view_name = str(self.view_name).strip()
        if not self.view_name:
            raise ValueError("view_name must be a non-empty string.")
        self.roi_mask_applied = bool(self.roi_mask_applied)
        self.hann_window_applied = bool(self.hann_window_applied)
        self.metadata = dict(self.metadata)


def build_registration_view(
    frames: np.ndarray,
    *,
    view_name: str = "raw",
    roi_mask: np.ndarray | None = None,
    apply_hann_window: bool = False,
    high_pass_sigma: float = 8.0,
    dog_sigma_low: float = 1.0,
    dog_sigma_high: float = 8.0,
) -> RegistrationViewResult:
    """Return a registration-only stack without mutating analysis frames."""

    view_name = _normalize_view_name(view_name)
    stack = _ensure_frame_stack(frames)
    mask = _normalize_roi_mask(roi_mask, frame_shape=stack.shape[1:])
    stack_for_view = _apply_roi_mask(stack, mask) if mask is not None else stack

    metadata: dict[str, Any] = {}
    if view_name == "raw":
        processed = stack_for_view.copy()
    elif view_name == "normalized":
        processed = _robust_normalize_stack(stack_for_view)
    elif view_name == "gradient_magnitude":
        processed = _gradient_magnitude_view(stack_for_view)
    elif view_name == "high_pass":
        sigma = _positive_float(high_pass_sigma, "high_pass_sigma")
        processed = _high_pass_view(stack_for_view, sigma=sigma)
        metadata["high_pass_sigma"] = sigma
    elif view_name == "dog":
        sigma_low = _positive_float(dog_sigma_low, "dog_sigma_low")
        sigma_high = _positive_float(dog_sigma_high, "dog_sigma_high")
        if sigma_high <= sigma_low:
            raise ValueError("dog_sigma_high must be greater than dog_sigma_low.")
        processed = _dog_view(stack_for_view, sigma_low=sigma_low, sigma_high=sigma_high)
        metadata["dog_sigma_low"] = sigma_low
        metadata["dog_sigma_high"] = sigma_high
    else:  # pragma: no cover - guarded by _normalize_view_name
        raise ValueError(f"Unsupported registration view: {view_name}")

    if apply_hann_window:
        processed = processed * _hann_window(stack.shape[1:])

    return RegistrationViewResult(
        frames=np.asarray(processed, dtype=np.float32),
        view_name=view_name,
        roi_mask_applied=mask is not None,
        hann_window_applied=apply_hann_window,
        metadata=metadata,
    )


def build_registration_view_from_settings(
    frames: np.ndarray,
    settings: RegistrationSettings,
) -> RegistrationViewResult:
    """Build a registration view using the shared registration settings model."""

    if not isinstance(settings, RegistrationSettings):
        raise TypeError("settings must be a RegistrationSettings instance.")

    params = dict(settings.backend_params)
    apply_hann_window = bool(
        params.get("apply_hann_window", params.get("hann_window", False))
    )
    return build_registration_view(
        frames,
        view_name=settings.registration_view,
        roi_mask=settings.roi_mask,
        apply_hann_window=apply_hann_window,
        high_pass_sigma=float(params.get("high_pass_sigma", 8.0)),
        dog_sigma_low=float(params.get("dog_sigma_low", 1.0)),
        dog_sigma_high=float(params.get("dog_sigma_high", 8.0)),
    )


def _normalize_view_name(view_name: str) -> str:
    normalized = str(view_name).strip().lower()
    if normalized not in SUPPORTED_REGISTRATION_VIEWS:
        supported = ", ".join(SUPPORTED_REGISTRATION_VIEWS)
        raise ValueError(f"Unsupported registration view '{view_name}'. Supported: {supported}.")
    return normalized


def _ensure_frame_stack(frames: np.ndarray) -> np.ndarray:
    stack = np.array(frames, dtype=np.float32, copy=True)
    if stack.ndim != 3:
        raise ValueError("frames must be a 3D array with shape (frame, height, width).")
    if stack.shape[0] < 1 or stack.shape[1] < 1 or stack.shape[2] < 1:
        raise ValueError("frames must contain at least one non-empty frame.")
    if not np.all(np.isfinite(stack)):
        raise ValueError("frames must contain only finite values.")
    return stack


def _normalize_roi_mask(
    roi_mask: np.ndarray | None,
    *,
    frame_shape: tuple[int, int],
) -> np.ndarray | None:
    if roi_mask is None:
        return None
    mask = np.asarray(roi_mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("roi_mask must be a 2D boolean image.")
    if mask.shape != frame_shape:
        raise ValueError("roi_mask shape must match registration frame shape.")
    if not np.any(mask):
        raise ValueError("roi_mask must contain at least one selected pixel.")
    return mask


def _apply_roi_mask(stack: np.ndarray, mask: np.ndarray) -> np.ndarray:
    masked = stack.copy()
    outside = ~mask
    for frame_index in range(masked.shape[0]):
        inside_values = masked[frame_index][mask]
        fill_value = float(np.median(inside_values))
        masked[frame_index][outside] = fill_value
    return masked


def _positive_float(value: float, name: str) -> float:
    normalized = float(value)
    if not np.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be a finite positive value.")
    return normalized


def _robust_normalize_stack(stack: np.ndarray) -> np.ndarray:
    return np.stack([_robust_normalize_frame(frame) for frame in stack]).astype(np.float32)


def _robust_normalize_frame(frame: np.ndarray) -> np.ndarray:
    low, high = np.percentile(frame, [1.0, 99.0])
    if not np.isfinite(low) or not np.isfinite(high) or high <= low + 1e-12:
        return np.zeros_like(frame, dtype=np.float32)
    normalized = (frame - low) / (high - low)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def _gradient_magnitude_view(stack: np.ndarray) -> np.ndarray:
    normalized = _robust_normalize_stack(stack)
    output = np.empty_like(normalized, dtype=np.float32)
    for frame_index, frame in enumerate(normalized):
        grad_y, grad_x = np.gradient(frame)
        output[frame_index] = np.sqrt(grad_x * grad_x + grad_y * grad_y)
    return _robust_normalize_stack(output)


def _high_pass_view(stack: np.ndarray, *, sigma: float) -> np.ndarray:
    normalized = _robust_normalize_stack(stack)
    output = np.empty_like(normalized, dtype=np.float32)
    for frame_index, frame in enumerate(normalized):
        background = gaussian_filter(frame, sigma=sigma, mode="nearest")
        output[frame_index] = frame - background
    return _robust_normalize_stack(output)


def _dog_view(stack: np.ndarray, *, sigma_low: float, sigma_high: float) -> np.ndarray:
    normalized = _robust_normalize_stack(stack)
    output = np.empty_like(normalized, dtype=np.float32)
    for frame_index, frame in enumerate(normalized):
        narrow = gaussian_filter(frame, sigma=sigma_low, mode="nearest")
        wide = gaussian_filter(frame, sigma=sigma_high, mode="nearest")
        output[frame_index] = narrow - wide
    return _robust_normalize_stack(output)


def _hann_window(frame_shape: tuple[int, int]) -> np.ndarray:
    height, width = frame_shape
    return np.outer(np.hanning(height), np.hanning(width)).astype(np.float32)
