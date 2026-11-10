"""Finite-count corrected Fourier order with freshly generated scale-matched nulls."""

from collections.abc import Callable
from typing import Any, cast
import hashlib
import json

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from stmdomains.analysis.order_settings import OrderSettings


ORDER_SEED = 20261102


def metrics(points: NDArray[np.float64], spacing: float, check: Callable[[], None],
            settings: OrderSettings = OrderSettings()) -> dict[str, NDArray[Any]]:
    angles = np.linspace(0, np.pi, 48, endpoint=False)
    frequencies = np.linspace(.5, 2., 22) / spacing
    aa, rr = np.meshgrid(angles, frequencies)
    waves = 2 * np.pi * np.column_stack(((rr * np.cos(aa)).ravel(), (rr * np.sin(aa)).ravel()))
    neighbors = cast(list[list[int]], cKDTree(points).query_ball_point(
        points, settings.order_radius_factor * spacing, return_length=False))
    output: dict[str, NDArray[Any]] = {key: np.zeros(len(points)) for key in ("score", "effective_n", "local_n", "frequency", "angle_deg")}
    for index, selected in enumerate(neighbors):
        check()
        offsets = points[selected] - points[index]
        weights = np.exp(-np.sum(offsets**2, axis=1) / (2 * (settings.order_sigma_factor * spacing)**2))
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
    *, settings: OrderSettings = OrderSettings(),
) -> tuple[dict[str, NDArray[Any]], dict[str, Any]]:
    real = metrics(points, spacing, check, settings)
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
                parts.append(metrics(control, 1., check, settings))
        count_array = np.concatenate([part["local_n"] for part in parts])
        effective = np.concatenate([part["effective_n"] for part in parts])
        score = np.concatenate([part["score"] for part in parts])
        eligible = ((count_array >= settings.order_minimum_local_count)
                    & (effective >= settings.order_minimum_effective_count))
        effective, score = effective[eligible], score[eligible]
        if not len(score):
            raise ValueError("Brak wystarczających kontroli do kalibracji porządku przy tych ustawieniach. "
                             "Zwiększ promień/sigmę lub zmniejsz wymagane minimum punktów.")
        thresholds = []
        for center in centers:
            nearest = np.argsort(np.abs(effective - center), kind="stable")[:min(350, len(score))]
            threshold = float(np.quantile(score[nearest], settings.order_quantile))
            thresholds.append(threshold)
            calibration.append({"null_type": "hard_core" if hard_core else "poisson",
                                "effective_n_center": float(center), "threshold": threshold,
                                "quantile": settings.order_quantile,
                                "samples": len(nearest), "effective_n_min": float(effective[nearest].min()),
                                "effective_n_max": float(effective[nearest].max())})
        thresholds_by_type.append(thresholds)
    thresholds = np.max(thresholds_by_type, axis=0)
    real["threshold"] = np.interp(real["effective_n"], centers, thresholds)
    real["sufficient"] = ((real["local_n"] >= settings.order_minimum_local_count)
                           & (real["effective_n"] >= settings.order_minimum_effective_count))
    real["supported"] = real["sufficient"] & (real["score"] > real["threshold"])
    metadata = {
        "method": "maximum finite-count-corrected Fourier coherence",
        "seed": ORDER_SEED, "null_types": ["poisson", "hard_core"],
        "null_field_side_in_spacings": 12., "null_counts": [60, 120, 180], "null_repeats": 2,
        "hard_core_min_distance_in_spacings": .6, "quantile": settings.order_quantile,
        "settings": settings.parameters(), "version": "fourier-null-1",
        "scale_rule": "Coordinates divided by frame spacing; controls use spacing 1 with the same radius and sigma factors.",
        "threshold_rule": "Maximum of two null quantiles; 350 nearest effective-count samples per anchor; linear interpolation with clamped ends.",
        "threshold_effective_n": centers.tolist(), "threshold_values": thresholds.tolist(),
        "calibration": calibration,
        "interpretation": "Exploratory order gate; a single periodic direction is sufficient, not proof of a 2D lattice.",
    }
    metadata["identifier"] = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
    return real, metadata
