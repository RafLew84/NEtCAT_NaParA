"""Label-free windows with conservative raw and registered support accounting.

Split membership is decided from frame number and geometry before extracting
pixels. Every center and grid position is recorded, including unavailable ones.
The registration guard is a convention, not a measured registration error bound.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import map_coordinates

from ..bundle import arrays_hash, validate_input

SCALES = (32, 48, 64)
STRIDE = 16
OUTPUT_SIZE = 64
SHIFT_PX = 2.0
INTERPOLATION_MARGIN = 1.0
REGISTRATION_GUARD = 8.0
SPLIT_SPEC = {
    "schema": "stmdomains-spatiotemporal-split-v1",
    "canvas_hw": [408, 480],
    "coordinate_system": "expanded_edge_xy",
    "time_blocks_inclusive": {"train": [1, 100], "validation": [150, 200], "test": [250, 268]},
    "time_embargo_inclusive": [[101, 149], [201, 249]],
    "spatial_x_bands": {"train": [320, 480], "validation": [160, 320], "test": [0, 160]},
    "registration_guard_px": REGISTRATION_GUARD,
    "guard_is_calibrated": False,
    "limitation": "one acquisition; disjoint only under saved, often low-confidence registration",
    "scales_raw_px": list(SCALES),
    "grid_stride_raw_px": STRIDE,
    "max_translation_raw_px": SHIFT_PX,
    "interpolation_margin_raw_px": INTERPOLATION_MARGIN,
    "output_size": OUTPUT_SIZE,
}


def json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def temporal_split(frame_number: int) -> str | None:
    for name, (first, last) in SPLIT_SPEC["time_blocks_inclusive"].items():
        if first <= frame_number <= last:
            return name
    return None


def spatial_band(split: str) -> tuple[float, float]:
    left, right = SPLIT_SPEC["spatial_x_bands"][split]
    return (left + (REGISTRATION_GUARD if left > 0 else 0),
            right - (REGISTRATION_GUARD if right < 480 else 0))


def support_available(box: np.ndarray, measured: np.ndarray) -> bool:
    height, width = measured.shape
    if np.any(box[:2] < 0) or np.any(box[2:] > [width, height]):
        return False
    x0, y0 = np.floor(box[:2]).astype(int)
    x1, y1 = np.ceil(box[2:]).astype(int)
    return bool(measured[y0:y1, x0:x1].all())


def transfer_membership(record: dict, support: np.ndarray) -> tuple[str | None, str | None]:
    split = temporal_split(record["frame_number"])
    if split is None:
        return None, "temporal_embargo"
    origin = np.asarray(record["origin_in_expanded_xy"])
    expanded = support + np.tile(origin, 2)
    left, right = spatial_band(split)
    if expanded[0] < left or expanded[2] > right:
        return None, "spatial_holdout_or_guard"
    return split, None


def window_records(record: dict, arrays: dict) -> list[dict]:
    validate_input(arrays)
    height, width = arrays["image"].shape
    origin = np.asarray(record["origin_in_expanded_xy"], dtype=float)
    image_hash = arrays_hash({k: arrays[k] for k in ("image", "measured")})
    positions = [("grid", f"g-{x:g}-{y:g}", [x, y])
                 for y in np.arange(STRIDE / 2, height, STRIDE)
                 for x in np.arange(STRIDE / 2, width, STRIDE)]
    positions += [("centers", str(ident), xy.tolist())
                  for ident, xy in zip(arrays["object_ids"], arrays["centers_xy"])]
    rows = []
    for sampler, element, xy in positions:
        for scale in SCALES:
            half = scale / 2
            center = np.asarray(xy, dtype=float)
            feature_box = np.r_[center - half, center + half]
            margin = SHIFT_PX + INTERPOLATION_MARGIN
            support = feature_box + [-margin, -margin, margin, margin]
            available = support_available(support, arrays["measured"])
            split, reason = transfer_membership(record, support)
            if not available:
                split, reason = None, "incomplete_measured_support"
            rows.append(dict(
                window_id=f'{record["sample_id"]}/{sampler}/{element}/s{scale}',
                sample_id=record["sample_id"], element_id=element, sampler=sampler,
                frame_number=record["frame_number"], raw_edge_xy=list(map(float, xy)),
                position_unit="px", scale_raw_px=scale,
                feature_support_xyxy=feature_box.tolist(), support_xyxy=support.tolist(),
                expanded_support_xyxy=(support + np.tile(origin, 2)).tolist(),
                image_content_sha256=image_hash,
                available=available, unavailable_reason=None if available else "incomplete_measured_support",
                transductive_split="fit" if available else None,
                transfer_split=split, transfer_exclusion_reason=reason,
            ))
    return rows


def fit_normalizers(samples: list[tuple[dict, dict]]) -> dict:
    """One scalar transform per protocol, fitted on raw pixels, never centers.

    Transfer statistics read only train frame pixels inside the guarded train
    band. Windows and their augmentations are constrained to that same band.
    """
    pools = {"transfer": [], "transductive": []}
    pixel_counts = {}
    for record, arrays in samples:
        image, measured = arrays["image"], arrays["measured"]
        pools["transductive"].append(image[measured].astype(np.float64))
        if temporal_split(record["frame_number"]) == "train":
            left, right = spatial_band("train")
            x = np.arange(image.shape[1]) + .5 + record["origin_in_expanded_xy"][0]
            mask = measured & ((x >= left) & (x < right))[None, :]
            pools["transfer"].append(image[mask].astype(np.float64))
            pixel_counts[record["sample_id"]] = int(mask.sum())
    result = {}
    for protocol, chunks in pools.items():
        values = np.concatenate(chunks) if chunks else np.empty(0)
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError(f"No finite normalization pixels for {protocol}")
        low, high = np.quantile(values, [.02, .98], method="linear")
        if high <= low:
            raise ValueError(f"Flat normalization data for {protocol}")
        result[protocol] = dict(low=float(low), high=float(high), pixel_count=int(values.size),
                                percentiles=[2, 98], formula="clip((raw-low)/(high-low),0,1)",
                                fit_region="all measured pixels" if protocol == "transductive" else "train frames, guarded train spatial band",
                                fit_pixel_counts=pixel_counts if protocol == "transfer" else None)
    return result


def extract_patch(arrays: dict, row: dict, normalizer: dict | None = None,
                  *, shift_xy=(0., 0.), size=OUTPUT_SIZE) -> np.ndarray:
    """Bilinear samples of a raw window; no padding and no display gamma."""
    shift = np.asarray(shift_xy, dtype=float)
    if shift.shape != (2,) or not np.isfinite(shift).all() or np.any(np.abs(shift) > SHIFT_PX):
        raise ValueError("Translation exceeds the declared support")
    if not row["available"] or not support_available(np.asarray(row["support_xyxy"]), arrays["measured"]):
        raise ValueError("Cannot extract incomplete measured support")
    center = np.asarray(row["raw_edge_xy"]) + shift
    scale = row["scale_raw_px"]
    offsets = ((np.arange(size) + .5) / size - .5) * scale
    x, y = np.meshgrid(center[0] + offsets - .5, center[1] + offsets - .5)
    image = arrays["image"]
    if x.min() < 0 or y.min() < 0 or x.max() > image.shape[1] - 1 or y.max() > image.shape[0] - 1:
        raise ValueError("Interpolation would access padding")
    patch = map_coordinates(image.astype(np.float32), [y, x], order=1, mode="constant", cval=np.nan, prefilter=False)
    if not np.isfinite(patch).all():
        raise ValueError("Non-finite interpolated patch")
    if normalizer is not None:
        patch = np.clip((patch - normalizer["low"]) / (normalizer["high"] - normalizer["low"]), 0, 1)
    return patch.astype(np.float32)


def synthetic_in_normalizer_units(arrays: dict, normalizer: dict) -> dict:
    """Fixed renderer-unit bridge, not a fit to synthetic evaluation data.

    Applying the frozen real-data normalizer afterwards gives
    clip(0.5 + 0.4 * rendered_signal, 0, 1). This preserves the sign and
    relative contrast of controls, including inversion and annotation gaps.
    It is a model-input convention, not a physical calibration of STM heights.
    Original control files remain unchanged; no truth or case ID is accepted.
    """
    validate_input(arrays)
    low, high = normalizer["low"], normalizer["high"]
    if not np.isfinite([low, high]).all() or high <= low:
        raise ValueError("Invalid frozen intensity range")
    return dict(arrays, image=low + (high - low) * (.5 + .4 * arrays["image"]))


def augmented_pair(arrays: dict, row: dict, normalizer: dict,
                   rng: np.random.Generator) -> tuple[np.ndarray, dict]:
    """Two views of the same window, with exact raw translation metadata.

    Correspondence is not inferred from adjacency. Returned maps must be used
    by local SSL to align positions; a shifted pixel is not the same location.
    """
    views, transforms = [], []
    for _ in range(2):
        shift = rng.uniform(-SHIFT_PX, SHIFT_PX, size=2)
        gain, offset, sigma = rng.uniform(.9, 1.1), rng.uniform(-.1, .1), rng.uniform(0., .03)
        patch = extract_patch(arrays, row, normalizer, shift_xy=shift)
        patch = gain * patch + offset + rng.normal(0., sigma, patch.shape)
        views.append(patch.astype(np.float32))
        transforms.append(dict(translation_raw_xy=shift.tolist(), gain=float(gain), offset=float(offset), noise_sigma=float(sigma)))
    return np.stack(views)[:, None], dict(window_id=row["window_id"], transforms=transforms,
                                         pixels_per_output_pixel=row["scale_raw_px"] / OUTPUT_SIZE,
                                         correspondence="raw_xy = window_center + translation + centered_output_xy * scale/64")


def verify_split(rows: list[dict]) -> dict:
    """An all-frame envelope proof, stricter than testing same-frame overlap."""
    envelopes = {}
    for split in ("train", "validation", "test"):
        selected = [r for r in rows if r["transfer_split"] == split]
        if not selected:
            raise ValueError(f"Empty transfer split: {split}")
        left, right = spatial_band(split)
        for row in selected:
            box = row["expanded_support_xyxy"]
            if not row["available"] or temporal_split(row["frame_number"]) != split or box[0] < left or box[2] > right:
                raise ValueError("Leaking or mislabeled transfer support")
        envelopes[split] = [min(r["expanded_support_xyxy"][0] for r in selected),
                            max(r["expanded_support_xyxy"][2] for r in selected)]
    gaps = {}
    for a, b in (("test", "validation"), ("validation", "train")):
        gap = envelopes[b][0] - envelopes[a][1]
        if gap < 2 * REGISTRATION_GUARD:
            raise ValueError("Cross-split support overlap or missing guard")
        gaps[f"{a}_to_{b}"] = gap
    return dict(expanded_x_envelopes=envelopes, minimum_support_gaps_px=gaps,
                cross_frame_overlap=False, proof="all augmented supports fit disjoint global x bands",
                counts=dict(Counter(f'{r["sampler"]}/s{r["scale_raw_px"]}/{r["transfer_split"] or "excluded"}' for r in rows)))


def read_windows(path: Path) -> list[dict]:
    with path.open() as stream:
        return [json.loads(line) for line in stream]
