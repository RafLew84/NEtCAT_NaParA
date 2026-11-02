"""Finite-count corrected Fourier order with freshly generated scale-matched nulls."""

from collections.abc import Callable
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree


ORDER_SEED = 20261102


def metrics(points: NDArray[np.float64], spacing: float, check: Callable[[], None]) -> dict[str, NDArray[Any]]:
    angles = np.linspace(0, np.pi, 48, endpoint=False)
    frequencies = np.linspace(.5, 2., 22) / spacing
    aa, rr = np.meshgrid(angles, frequencies)
    waves = 2 * np.pi * np.column_stack(((rr * np.cos(aa)).ravel(), (rr * np.sin(aa)).ravel()))
    neighbors = cast(list[list[int]], cKDTree(points).query_ball_point(points, 3 * spacing, return_length=False))
    output: dict[str, NDArray[Any]] = {key: np.zeros(len(points)) for key in ("score", "effective_n", "local_n", "frequency", "angle_deg")}
    for index, selected in enumerate(neighbors):
        check()
        offsets = points[selected] - points[index]
        weights = np.exp(-np.sum(offsets**2, axis=1) / (2 * (4 / 3 * spacing)**2))
        weight_sum = float(weights.sum())
        self_power = float(weights @ weights)
        phases = offsets @ waves.T
        power = (weights @ np.cos(phases)) ** 2 + (weights @ np.sin(phases)) ** 2
        coherence = (power - self_power) / max(weight_sum**2 - self_power, 1e-12)
        peak = int(np.argmax(coherence))
        output["score"][index] = coherence[peak]
        output["effective_n"][index] = weight_sum**2 / max(self_power, 1e-12)
        output["local_n"][index] = len(selected)
        output["frequency"][index] = frequencies[peak // len(angles)]
        output["angle_deg"][index] = np.rad2deg(angles[peak % len(angles)])
    return output


def _null_points(count: int, rng: np.random.Generator, hard_core: bool, check: Callable[[], None]) -> NDArray[np.float64]:
    if not hard_core:
        return rng.uniform(0, 12., (count, 2))
    points: list[NDArray[np.float64]] = []
    for attempt in range(100000):
        if attempt % 128 == 0:
            check()
        candidate = rng.uniform(0, 12., 2)
        if not points or np.min(np.sum((np.asarray(points) - candidate) ** 2, axis=1)) >= .6**2:
            points.append(candidate)
            if len(points) == count:
                return np.asarray(points)
    raise ValueError("Nie udało się przygotować kontroli porządku przy zadanej gęstości.")


def evaluate_order(
    points: NDArray[np.float64], spacing: float, check: Callable[[], None], progress: Callable[[str], None],
) -> tuple[dict[str, NDArray[Any]], dict[str, Any]]:
    real = metrics(points, spacing, check)
    centers = np.asarray([8, 10, 12, 14, 16, 18, 20, 24, 28, 32], float)
    rng = np.random.default_rng(ORDER_SEED)
    thresholds_by_type = []
    calibration = []
    for hard_core in (False, True):
        progress("Kalibracja porządku: " + ("kontrole z wykluczeniem…" if hard_core else "kontrole losowe…"))
        parts = []
        for repeat in range(2):
            for count in (60, 120, 180):
                check()
                # Normalized controls are evaluated at spacing 1: the resulting
                # threshold is dimensionless and scales exactly with the input.
                control = _null_points(count, rng, hard_core, check)
                parts.append(metrics(control, 1., check))
        count_array = np.concatenate([part["local_n"] for part in parts])
        effective = np.concatenate([part["effective_n"] for part in parts])
        score = np.concatenate([part["score"] for part in parts])
        eligible = (count_array >= 10) & (effective >= 8)
        effective, score = effective[eligible], score[eligible]
        if not len(score):
            raise ValueError("Brak wystarczających kontroli do kalibracji porządku.")
        thresholds = []
        for center in centers:
            nearest = np.argsort(np.abs(effective - center), kind="stable")[:min(350, len(score))]
            threshold = float(np.quantile(score[nearest], .95))
            thresholds.append(threshold)
            calibration.append({"null_type": "hard_core" if hard_core else "poisson",
                                "effective_n_center": float(center), "threshold95": threshold,
                                "samples": len(nearest), "effective_n_min": float(effective[nearest].min()),
                                "effective_n_max": float(effective[nearest].max())})
        thresholds_by_type.append(thresholds)
    thresholds = np.max(thresholds_by_type, axis=0)
    real["threshold"] = np.interp(real["effective_n"], centers, thresholds)
    real["sufficient"] = (real["local_n"] >= 10) & (real["effective_n"] >= 8)
    real["supported"] = real["sufficient"] & (real["score"] > real["threshold"])
    metadata = {
        "method": "maximum finite-count-corrected Fourier coherence",
        "seed": ORDER_SEED, "null_types": ["poisson", "hard_core"],
        "null_field_side_in_spacings": 12., "null_counts": [60, 120, 180], "null_repeats": 2,
        "hard_core_min_distance_in_spacings": .6, "quantile": .95,
        "threshold_effective_n": centers.tolist(), "threshold_values": thresholds.tolist(),
        "calibration": calibration,
        "interpretation": "Exploratory order gate; a single periodic direction is sufficient, not proof of a 2D lattice.",
    }
    return real, metadata
