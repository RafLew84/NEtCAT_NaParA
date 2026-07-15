from __future__ import annotations

from functools import lru_cache
from math import hypot, pi, sqrt

import numpy as np
from scipy.integrate import quad
from scipy.ndimage import map_coordinates
from scipy.signal import fftconvolve


def rectangular_annulus_overlap_integrals(
    width_nm: float,
    height_nm: float,
    edges_nm: tuple[float, ...],
) -> tuple[float, ...]:
    return _cached_rectangular_annulus_overlap_integrals(width_nm, height_nm, edges_nm)


@lru_cache(maxsize=128)
def _cached_rectangular_annulus_overlap_integrals(
    width_nm: float,
    height_nm: float,
    edges_nm: tuple[float, ...],
) -> tuple[float, ...]:
    cumulative = tuple(
        _rectangular_cumulative_overlap_integral(radius, width_nm, height_nm)
        for radius in edges_nm
    )
    return tuple(max(0.0, right - left) for left, right in zip(cumulative, cumulative[1:]))


def _rectangular_cumulative_overlap_integral(
    radius_nm: float,
    width_nm: float,
    height_nm: float,
) -> float:
    if radius_nm <= 0.0:
        return 0.0
    if radius_nm >= hypot(width_nm, height_nm):
        return (width_nm * height_nm) ** 2
    if radius_nm <= min(width_nm, height_nm):
        return (
            pi * width_nm * height_nm * radius_nm**2
            - (4.0 / 3.0) * (width_nm + height_nm) * radius_nm**3
            + 0.5 * radius_nm**4
        )

    x_max = min(width_nm, radius_nm)

    def integrand(x_offset: float) -> float:
        y_max = min(height_nm, sqrt(max(0.0, radius_nm**2 - x_offset**2)))
        return (width_nm - x_offset) * (height_nm * y_max - 0.5 * y_max**2)

    split = sqrt(max(0.0, radius_nm**2 - height_nm**2))
    points = [split] if 0.0 < split < x_max else None
    quadrant_integral, _error = quad(
        integrand,
        0.0,
        x_max,
        points=points,
        epsabs=1e-10,
        epsrel=1e-10,
        limit=100,
    )
    return 4.0 * quadrant_integral


def masked_annulus_overlap_integrals(
    mask: np.ndarray,
    *,
    pixel_size_nm: tuple[float, float],
    edges_nm: tuple[float, ...],
) -> tuple[float, tuple[float, ...]]:
    pixel_size_x, pixel_size_y = pixel_size_nm
    pixel_area_nm2 = pixel_size_x * pixel_size_y
    mask_values = mask.astype(np.float64, copy=False)
    autocorrelation = fftconvolve(
        mask_values,
        mask_values[::-1, ::-1],
        mode="full",
    )
    autocorrelation = np.maximum(0.0, np.rint(autocorrelation))
    overlap_area_nm2 = np.pad(
        autocorrelation * pixel_area_nm2,
        pad_width=1,
        mode="constant",
    )
    center = (float(mask.shape[0]), float(mask.shape[1]))
    minimum_pixel_size = min(pixel_size_x, pixel_size_y)
    maximum_radius = edges_nm[-1]
    angular_sample_count = max(
        720,
        min(4096, int(np.ceil(8.0 * pi * maximum_radius / minimum_pixel_size))),
    )
    angles = (np.arange(angular_sample_count, dtype=np.float64) + 0.5) * (
        2.0 * pi / angular_sample_count
    )
    cos_angles = np.cos(angles)
    sin_angles = np.sin(angles)
    gauss_nodes, gauss_weights = np.polynomial.legendre.leggauss(8)
    overlap_integrals = tuple(
        _integrate_mask_overlap_annulus(
            overlap_area_nm2,
            inner_radius_nm=inner_radius,
            outer_radius_nm=outer_radius,
            pixel_size_nm=pixel_size_nm,
            center=center,
            cos_angles=cos_angles,
            sin_angles=sin_angles,
            gauss_nodes=gauss_nodes,
            gauss_weights=gauss_weights,
        )
        for inner_radius, outer_radius in zip(edges_nm, edges_nm[1:])
    )
    window_area_nm2 = float(np.count_nonzero(mask) * pixel_area_nm2)
    return window_area_nm2, overlap_integrals


def _integrate_mask_overlap_annulus(
    overlap_area_nm2: np.ndarray,
    *,
    inner_radius_nm: float,
    outer_radius_nm: float,
    pixel_size_nm: tuple[float, float],
    center: tuple[float, float],
    cos_angles: np.ndarray,
    sin_angles: np.ndarray,
    gauss_nodes: np.ndarray,
    gauss_weights: np.ndarray,
) -> float:
    pixel_size_x, pixel_size_y = pixel_size_nm
    center_row, center_column = center
    maximum_radial_step = min(pixel_size_x, pixel_size_y) / 2.0
    subinterval_count = max(
        1,
        int(np.ceil((outer_radius_nm - inner_radius_nm) / maximum_radial_step)),
    )
    radial_edges = np.linspace(
        inner_radius_nm,
        outer_radius_nm,
        subinterval_count + 1,
    )
    integral = 0.0
    angular_step = 2.0 * pi / len(cos_angles)
    for radial_start, radial_end in zip(radial_edges, radial_edges[1:]):
        half_width = (radial_end - radial_start) / 2.0
        midpoint = (radial_start + radial_end) / 2.0
        radii = midpoint + half_width * gauss_nodes
        shift_x = radii[:, None] * cos_angles[None, :]
        shift_y = radii[:, None] * sin_angles[None, :]
        coordinates = np.vstack(
            (
                (center_row + shift_y / pixel_size_y).ravel(),
                (center_column + shift_x / pixel_size_x).ravel(),
            )
        )
        overlap = map_coordinates(
            overlap_area_nm2,
            coordinates,
            order=1,
            mode="constant",
            cval=0.0,
            prefilter=False,
        ).reshape(len(radii), len(cos_angles))
        angular_integrals = np.sum(overlap, axis=1) * angular_step
        integral += half_width * float(
            np.sum(gauss_weights * radii * angular_integrals)
        )
    return integral
