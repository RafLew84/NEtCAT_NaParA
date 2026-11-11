"""E5 frozen AE map readout and fixed equal-weight multiscale composition.

No model loading, fitting, decoding, preprocessing or reference access occurs
here. The caller supplies finite float32 normalized64 inputs and frozen models.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import torch

from .training.partition import _unit_features

SCALES = (32, 48, 64)
MAP_SHAPE = (64, 7, 7)
MAP_DIMENSION = 3136


def encode_ae_readouts(model, patches, batch_size: int = 128) -> dict[str, np.ndarray]:
    """Return z32 and the entire channel/y/x flattened map from ONE encode.

    Both outputs use exactly the same spatial context. There is no pooling,
    crop, activation change, L2 normalization or decoder call. The caller fits
    the separately frozen adapter; map features need not remain in memory
    after their group is saved. Empty batches do not invoke the model.
    """
    images = np.asarray(patches)
    if images.ndim != 3 or images.shape[1:] != (64, 64):
        raise ValueError("Encoder inputs must have shape N-by64-by64")
    if images.dtype != np.float32 or not np.isfinite(images).all():
        raise ValueError("Encoder inputs must be finite float32")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("Batch size must be a positive integer")
    if getattr(model, "family", None) != "ae" or getattr(model, "latent_dim", None) != 32:
        raise ValueError("E5 map readout requires the frozen AE z32 architecture")
    result = dict(ae=np.empty((len(images), 32), np.float32),
                  ae_map=np.empty((len(images), MAP_DIMENSION), np.float32))
    parameter = next(model.parameters(), None)
    device = parameter.device if parameter is not None else torch.device("cpu")
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(images), batch_size):
            stop = min(start + batch_size, len(images))
            tensor = torch.from_numpy(np.array(images[start:stop, None], copy=True)).to(device)
            spatial = model.encoder(tensor)
            if spatial.shape != (stop - start, MAP_DIMENSION):
                raise ValueError("Encoder does not expose the expected flattened 64x7x7 map")
            content = model.head(spatial)
            if content.shape != (stop - start, 32):
                raise ValueError("AE head does not expose z32")
            for key, values in (("ae_map", spatial), ("ae", content)):
                if values.dtype != torch.float32 or not torch.isfinite(values).all():
                    raise ValueError("Nonfinite or non-float32 AE readout")
                result[key][start:stop] = values.cpu().numpy()
    return result


def equal_blocks(blocks_by_scale: Mapping[int, np.ndarray]) -> np.ndarray:
    """Concatenate unit32, unit48, unit64 in that order, each divided by sqrt3.

    This is a prescribed representation change, not a fitted scaler. Every
    scale has equal squared norm independent of descriptor dimension or raw
    magnitude. A missing/nonfinite/zero block makes the entire row missing;
    no imputation or renormalization over the remaining scales is performed.
    The stable unit normalization matches the historical adapter's convention.
    """
    if not isinstance(blocks_by_scale, Mapping) or set(blocks_by_scale) != set(SCALES):
        raise ValueError("Supply exactly the separate 32, 48 and 64 scale blocks")
    units, validity, count = [], [], None
    for scale in SCALES:
        values = np.asarray(blocks_by_scale[scale])
        unit, valid = _unit_features(values)
        if count is not None and len(values) != count:
            raise ValueError("Multiscale blocks must have aligned rows")
        count = len(values)
        units.append(unit)
        validity.append(valid)
    result = np.concatenate(units, axis=1) / np.sqrt(3.)
    result[~np.logical_and.reduce(validity)] = np.nan
    return result


def spatial_geometry(scale: int = 48) -> dict:
    """Nominal map receptive fields, in raw edge coordinates relative to anchor.

    Three unpadded k3/s2 convolutions give RF15/stride8 in normalized64 input.
    Bilinear sampling has its own raw-pixel interpolation footprint; the
    historical conservative S+6 extraction support remains required. These
    bounds describe nominal neural context, not calibrated physical locality.
    """
    if isinstance(scale, bool) or scale not in SCALES:
        raise ValueError("E5 raw scale must be 32, 48 or 64")
    ratio = scale / 64.
    centers = 7.5 + 8. * np.arange(7)
    return dict(map_shape=list(MAP_SHAPE), dimension=MAP_DIMENSION,
                flatten_order="channel,y,x", scale_raw_px=int(scale),
                input_size=64, receptive_field_input_px=15, stride_input_px=8,
                centers_input_edge_px=centers.tolist(),
                receptive_field_raw_px=15. * ratio, stride_raw_px=8. * ratio,
                centers_raw_relative_px=((centers - 32.) * ratio).tolist(),
                axis_bounds_raw_relative_px=np.column_stack((
                    (centers - 7.5 - 32.) * ratio,
                    (centers + 7.5 - 32.) * ratio)).tolist(),
                full_context_input_edge_interval=[0., 63.],
                full_context_raw_relative_interval=[-scale / 2., 31. * ratio],
                ignored_input_indices="last row and column (index63)",
                extraction_support_side_raw_px=int(scale + 6),
                interpolation="historical bilinear raw sampling; nominal RF excludes interpolation footprint")
