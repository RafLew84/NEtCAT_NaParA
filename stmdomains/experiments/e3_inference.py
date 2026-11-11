"""E3 deterministic posterior-mean readouts; never decode or train a model."""
from __future__ import annotations

import numpy as np
import torch


def encode_readouts(model, patches, batch_size: int = 128) -> dict[str, np.ndarray]:
    """Encode aligned available64 patches with historical NumPy block packing.

    The caller loads/checks frozen weights and configures deterministic fp32
    execution. One rVAE encode supplies content, full and angle readouts.
    Historical full content normalization has no epsilon: a zero content
    vector remains nonfinite/unavailable rather than gaining a new meaning.
    _translation already has the model's .1 scaling; it is diagnostic only.
    """
    images = np.asarray(patches)
    if images.ndim != 3 or images.shape[1:] != (64, 64):
        raise ValueError("Encoder inputs must have shape N-by64-by64")
    if images.dtype != np.float32 or not np.isfinite(images).all():
        raise ValueError("Encoder inputs must be finite float32")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("Batch size must be a positive integer")
    if getattr(model, "family", None) not in ("ae", "rvae") or getattr(model, "latent_dim", None) != 32:
        raise ValueError("E3 uses the frozen AE/rVAE z32 models")
    count = len(images)
    content = np.empty((count, 32), dtype=np.float32)
    angle = np.full(count, np.nan, dtype=np.float32)
    translation = np.full((count, 2), np.nan, dtype=np.float32)
    parameter = next(model.parameters(), None)
    device = parameter.device if parameter is not None else torch.device("cpu")
    model.eval()
    with torch.inference_mode():
        for start in range(0, count, batch_size):
            stop = min(start + batch_size, count)
            # Copy handles read-only cached arrays without exposing mutable backing storage.
            tensor = torch.from_numpy(np.array(images[start:stop, None], copy=True)).to(device)
            encoded = model.encode(tensor)
            values = encoded["content"].cpu().numpy()
            if values.shape != (stop-start, 32) or not np.isfinite(values).all():
                raise ValueError("Nonfinite or malformed encoder content")
            content[start:stop] = values
            if model.family == "rvae":
                theta = encoded["angle_radians"].cpu().numpy()
                shift = encoded["translation_normalized_xy"].cpu().numpy()
                if (theta.shape != (stop-start,) or shift.shape != (stop-start, 2)
                        or not np.isfinite(theta).all() or not np.isfinite(shift).all()):
                    raise ValueError("Nonfinite or malformed rVAE pose")
                angle[start:stop], translation[start:stop] = theta, shift
    if model.family == "ae":
        return dict(ae=content, _angle=angle, _translation=translation)
    norm = np.linalg.norm(content, axis=1, keepdims=True)
    circular = np.column_stack((np.cos(angle), np.sin(angle)))
    with np.errstate(divide="ignore", invalid="ignore"):
        full = np.concatenate((content/norm, np.cos(angle)[:, None], np.sin(angle)[:, None]), axis=1)/np.sqrt(2)
    return dict(rvae_full=full, rvae_content=content, rvae_angle=circular,
                _angle=angle, _translation=translation)
