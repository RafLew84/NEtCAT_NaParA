"""Native-patch Fourier features and a separately calibrated order diagnostic.

Adapted from texture_trial.py at3bb4d36: no full-frame Gaussian/RMS, no
reflected image padding, and no reference-dependent crop selection. FFT zero
extension computes spectral samples/linear autocorrelation; it is not measured
image padding. The order score alone does not establish a physical domain.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

from stmdomains.experiments import controls as old_controls


OLD_NEGATIVE_CASES = ("random", "random_minsep", "random_gradient", "noise", "stripes")
OLD_DEVELOPMENT_SEEDS = (1701, 1702, 1703, 2701, 2702, 2703)
SCALES = (32, 48, 64)


def describe_patches(patches) -> dict[str, np.ndarray]:
    """Describe N normalized native square patches, without fitting anything.

    An unsupported input can be an all-NaN patch: its output remains unavailable.
    Flat finite patches are valid measurements, with zero energy/feature vector
    and no positive order evidence. Spatial vectors are ACF diagnostics, never
    automatically reported as validated lattice angles.
    """
    images = np.asarray(patches, dtype=np.float64)
    if images.ndim != 3 or images.shape[1] != images.shape[2] or images.shape[1] not in SCALES:
        raise ValueError("Expected native patches with shape N-by-S-by-S; S=32,48,64")
    count, size, _ = images.shape
    features = np.full((count, 216), np.nan, dtype=np.float64)
    scores = np.full(count, np.nan)
    ratios = np.full(count, np.nan)
    energies = np.full(count, np.nan)
    vectors = np.full((count, 2, 2), np.nan)
    valid = np.isfinite(images).all(axis=(1, 2))
    window = np.hanning(size)[:, None] * np.hanning(size)[None, :]
    frequencies = np.linspace(1 / 28, 1 / 6, 12)
    angles = np.arange(18) * np.pi / 18
    nfft = 2 * size
    coords = np.array([
        (frequencies[:, None] * np.sin(angles)).ravel() * nfft + nfft // 2,
        (frequencies[:, None] * np.cos(angles)).ravel() * nfft + nfft // 2,
    ])
    lag = 24
    yy, xx = np.mgrid[-lag:lag + 1, -lag:lag + 1]
    radius = np.hypot(xx, yy)
    allowed_lag = (radius >= 6) & (radius <= 24)
    for index in np.flatnonzero(valid):
        patch = images[index] - images[index].mean()
        energies[index] = float(np.mean(patch * patch))
        fourier = np.fft.fft2(patch * window, s=(nfft, nfft))
        power = np.abs(fourier) ** 2
        sampled = ndi.map_coordinates(np.fft.fftshift(power), coords, order=1,
                                      mode="constant", cval=0., prefilter=False).reshape(12, 18)
        total = float(sampled.sum())
        features[index] = np.sqrt(sampled.ravel() / max(total, 1e-20))
        angular = sampled.sum(axis=0)
        dominant = int(np.argmax(angular))
        different_direction = np.abs(np.sin(angles - angles[dominant])) >= .35
        ratios[index] = float(angular[different_direction].max() / max(angular[dominant], 1e-20))

        acf = np.fft.fftshift(np.fft.ifft2(power).real)
        mid = nfft // 2
        acf = acf[mid - lag:mid + lag + 1, mid - lag:mid + lag + 1] / max(acf[mid, mid], 1e-20)
        maxima = (acf == ndi.maximum_filter(acf, size=5)) & allowed_lag
        positions = np.argwhere(maxima)
        heights = acf[maxima]
        order = np.argsort(-heights, kind="stable")[:24]
        candidates = positions[order, ::-1] - lag
        heights = heights[order]
        scores[index] = 0.
        if len(candidates) > 1:
            lengths = np.linalg.norm(candidates, axis=1)
            cross = candidates[:, 0, None] * candidates[None, :, 1] - candidates[:, 1, None] * candidates[None, :, 0]
            sine = np.abs(cross) / np.maximum(lengths[:, None] * lengths[None, :], 1e-20)
            noncollinear = np.triu(sine >= .35, 1)
            choices = np.where(noncollinear, np.minimum(heights[:, None], heights[None, :]), 0.)
            a, b = np.unravel_index(np.argmax(choices), choices.shape)
            scores[index] = float(choices[a, b])
            if scores[index] > 0:
                vectors[index] = candidates[[a, b]]
    return dict(features=features, acf_score=scores, second_direction_ratio=ratios,
                energy=energies, valid=valid, basis_vectors=vectors)


def order_mask(description: dict, threshold: float) -> np.ndarray:
    """One shared strict ACF threshold, spectral direction and positive energy."""
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Order threshold must be finite and nonnegative")
    score = np.asarray(description["acf_score"])
    ratio = np.asarray(description["second_direction_ratio"])
    energy = np.asarray(description["energy"])
    valid = np.asarray(description["valid"], dtype=bool)
    if score.ndim != 1 or any(value.shape != score.shape for value in (ratio, energy, valid)):
        raise ValueError("Inconsistent order-description arrays")
    return valid & np.isfinite(score) & np.isfinite(ratio) & np.isfinite(energy) & (score > threshold) & (ratio >= .25) & (energy > 0)


def calibrate_order_thresholds(scales=SCALES, *, seeds=OLD_DEVELOPMENT_SEEDS) -> dict:
    """Quantile .999 of OLD negative-grid scores; no evaluation-file access.

    Regenerates only the five known issue14 negatives and six previously viewed
    seeds. Both the new81 controls and all manual references are outside this
    interface. Full scale+6 support follows the fixed augmentation/interpolation
    footprint. This one grid-calibrated threshold per scale also applies to the
    centers diagnostic and to all representations/partition methods.
    """
    scales = tuple(scales)
    seeds = tuple(seeds)
    if not scales or len(set(scales)) != len(scales) or not set(scales) <= set(SCALES):
        raise ValueError("Calibration scales must be a nonempty subset of32/48/64")
    if not seeds or len(set(seeds)) != len(seeds) or not set(seeds) <= set(OLD_DEVELOPMENT_SEEDS):
        raise ValueError("Only already-viewed development seeds are allowed")
    distributions = {size: [] for size in scales}
    sources = []
    for case in OLD_NEGATIVE_CASES:
        for seed in seeds:
            arrays, _, _ = old_controls.make_control(case, seed)
            # Same fixed model-input convention as synthetic_in_normalizer_units.
            image = np.clip(.5 + .4 * arrays["image"], 0, 1).astype(np.float32)
            measured = arrays["measured"]
            height, width = image.shape
            counts = {}
            for size in scales:
                half = size // 2
                margin = half + 3
                patches = []
                for y in range(8, height, 16):
                    for x in range(8, width, 16):
                        if x - margin < 0 or y - margin < 0 or x + margin > width or y + margin > height:
                            continue
                        if not measured[y - margin:y + margin, x - margin:x + margin].all():
                            continue
                        patches.append(image[y - half:y + half, x - half:x + half])
                batch = np.asarray(patches, dtype=np.float32).reshape(-1, size, size)
                description = describe_patches(batch)
                scores = description["acf_score"][description["valid"]]
                distributions[size].extend(scores.tolist())
                counts[str(size)] = len(scores)
            sources.append(dict(case=case, seed=int(seed), counts=counts))
    thresholds = {}
    for size, values in distributions.items():
        if not values:
            raise ValueError(f"No available old-negative patches at scale{size}")
        thresholds[str(size)] = dict(threshold=float(np.quantile(values, .999, method="linear")),
                                    count=len(values), median=float(np.median(values)),
                                    maximum=float(max(values)))
    return dict(schema="stmdomains-order-calibration-v1", scales=thresholds,
                quantile=.999, cases=list(OLD_NEGATIVE_CASES), seeds=list(seeds), sources=sources,
                sampling="grid_stride16_full_scale_plus6_support", applies_to=["grid", "centers"],
                score_selection="all available finite old-negative grid patches; no second-direction prefilter",
                synthetic_units="clip(0.5+0.4*renderer_image,0,1)",
                source_sha256=hashlib.sha256(Path(old_controls.__file__).read_bytes()).hexdigest(),
                texture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
