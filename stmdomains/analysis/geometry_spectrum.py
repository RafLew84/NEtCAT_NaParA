"""Bounded local Fourier peaks, based on the finite-count correction used in v0.4."""

from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.optimize import minimize
from numpy.typing import NDArray


@dataclass(frozen=True)
class GeometrySettings:
    radius_factor: float = 3.
    sigma_factor: float = 4 / 3
    minimum_count: int = 10
    minimum_effective_count: float = 8.
    minimum_coherence: float = .75
    minimum_axis_separation_deg: float = 25.
    radius_variation_fraction: float = .1
    maximum_angle_change_deg: float = 5.
    maximum_period_change_fraction: float = .1
    frequency_minimum: float = .5
    frequency_maximum: float = 2.
    frequency_steps: int = 61
    angle_steps: int = 90

    def parameters(self) -> dict:
        return {'method': 'geometry-fourier-1', **asdict(self),
                'frequency_unit': 'cycles per median NN spacing', 'angle_convention': 'CCW from image +X; axial modulo 180',
                'stability_rule': 'maximum matched-axis change at radius factors 0.9 and 1.1; fixed Gaussian sigma',
                'maximum_input_detections': 3000, 'maximum_image_pixels': 4194304}


@dataclass(frozen=True)
class SpectrumAxis:
    normal_angle_deg: float
    frequency_cycles_per_spacing: float
    coherence: float


@dataclass(frozen=True)
class NeighborhoodMeasurement:
    axes: tuple[SpectrumAxis, ...]
    count: int
    effective_count: float
    reason: str = ''


def axial_difference(a: float, b: float) -> float:
    return abs((a - b + 90.) % 180. - 90.)


def spectrum_axes(offsets: np.ndarray, settings: GeometrySettings,
                  check: Callable[[], None]) -> NeighborhoodMeasurement:
    """Offsets use NN-normalized metric coordinates, with Y pointing upwards."""
    weights = np.exp(-np.sum(offsets**2, axis=1) / (2 * settings.sigma_factor**2))
    weight_sum, self_power = float(weights.sum()), float(weights @ weights)
    effective = weight_sum**2 / max(self_power, 1e-12)
    if len(offsets) < settings.minimum_count or effective < settings.minimum_effective_count:
        return NeighborhoodMeasurement((), len(offsets), effective, 'insufficient_support')
    frequencies = np.linspace(settings.frequency_minimum, settings.frequency_maximum, settings.frequency_steps)
    angles = np.linspace(0, np.pi, settings.angle_steps, endpoint=False)
    aa, ff = np.meshgrid(angles, frequencies)
    waves = np.column_stack(((ff*np.cos(aa)).ravel(), (ff*np.sin(aa)).ravel()))
    denominator = max(weight_sum**2-self_power, 1e-12)
    def scores(q):
        phases = 2 * np.pi * offsets @ np.asarray(q).reshape(-1, 2).T
        power = (weights @ np.cos(phases))**2 + (weights @ np.sin(phases))**2
        return (power-self_power) / denominator
    values = scores(waves).reshape(ff.shape)
    maxima = maximum_filter(values, size=(3, 3), mode=('nearest', 'wrap'))
    candidate_indices = np.flatnonzero((values == maxima) & (values >= settings.minimum_coherence - .05))
    candidates = sorted(candidate_indices, key=lambda i: np.linalg.norm(waves[i]))[:24]
    def objective(q: NDArray[np.float64], *args, **kwargs) -> float:
        return -float(scores(q)[0])

    found: list[SpectrumAxis] = []
    for index in candidates:
        check()
        q0 = waves[index]
        fit = minimize(objective, q0, method='L-BFGS-B',
                       bounds=[(v-.04, v+.04) for v in q0], options={'maxiter': 30})
        q = fit.x
        frequency = float(np.linalg.norm(q))
        coherence = float(scores(q)[0])
        if (coherence < settings.minimum_coherence or
                not settings.frequency_minimum + .005 < frequency < settings.frequency_maximum - .005):
            continue
        # A single line has perfect coherence perpendicular to it at ANY period.
        # Require at least three occupied wave planes, not just a large peak.
        projected = offsets @ q
        phase = np.angle(np.sum(weights * np.exp(2j*np.pi*projected))) / (2*np.pi)
        planes = np.rint(projected-phase).astype(int)
        if np.ptp(projected) < 1.8 or len(np.unique(planes)) < 3:
            continue
        normal = float(np.rad2deg(np.arctan2(q[1], q[0])) % 180)
        if any(axial_difference(normal, axis.normal_angle_deg) < settings.minimum_axis_separation_deg for axis in found):
            continue
        found.append(SpectrumAxis(normal, frequency, coherence))
        if len(found) == 2:
            break
    return NeighborhoodMeasurement(tuple(found), len(offsets), effective, '' if found else 'no_resolved_peak')
