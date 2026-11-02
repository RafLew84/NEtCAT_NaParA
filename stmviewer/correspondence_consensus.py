"""Versioned global translation from original-pixel correspondences."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

import numpy as np
from numpy.typing import NDArray

from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal


@dataclass(frozen=True)
class CorrespondenceConfig:
    inlier_radius: float = 2.0
    max_hypotheses: int = 128
    minimum_span_fraction: float = 0.25
    minimum_orthogonal_spread: float = 0.05
    minimum_cells: int = 4
    minimum_grid_lines: int = 3
    minimum_matches: int = 8
    minimum_inliers: int = 4
    review_minimum_inliers: int = 8
    minimum_fraction: float = 0.25
    competing_fraction: float = 0.8
    settings_version: int = 2


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        from stmviewer.registration import RegistrationCancelled
        raise RegistrationCancelled


def _cluster(vectors: NDArray[np.float64], config: CorrespondenceConfig,
             cancelled: Callable[[], bool] | None) -> NDArray[np.bool_]:
    # A fixed seed makes the bounded hypothesis set reproducible. No score
    # weighting: model confidence is not comparable across model families.
    indices: NDArray[np.int64] = np.arange(len(vectors), dtype=np.int64)
    if len(indices) > config.max_hypotheses:
        indices = np.asarray(np.random.default_rng(0).choice(indices, config.max_hypotheses, replace=False), dtype=np.int64)
    best = np.zeros(len(vectors), dtype=np.bool_)
    for index in indices:
        _check_cancelled(cancelled)
        selected = np.linalg.norm(vectors - vectors[index], axis=1) <= config.inlier_radius
        if np.count_nonzero(selected) > np.count_nonzero(best):
            best = selected
    for _ in range(2):
        center = np.median(vectors[best], axis=0)
        best = np.linalg.norm(vectors - center, axis=1) <= config.inlier_radius
    return best


def _support(points: NDArray[np.float64], shape: tuple[int, int]
             ) -> tuple[tuple[int, ...], tuple[float, float]]:
    width, height = shape[1], shape[0]
    bins = np.floor(points / (width, height) * 4).astype(int)
    counts = np.bincount(bins[:, 1] * 4 + bins[:, 0], minlength=16)
    span = np.ptp(points, axis=0) / (width, height)
    return tuple(int(n) for n in counts), (float(span[0]), float(span[1]))


def _grid_lines(counts: tuple[int, ...]) -> int:
    occupied = np.asarray(counts).reshape(4, 4) > 0
    return min(int(np.count_nonzero(occupied.any(axis=0))), int(np.count_nonzero(occupied.any(axis=1))))


def _orthogonal_spread(points: NDArray[np.float64], shape: tuple[int, int]) -> float:
    normalized = points / (shape[1], shape[0])
    centered = normalized - np.mean(normalized, axis=0)
    covariance = centered.T @ centered / len(points)
    return float(np.sqrt(max(0., float(np.linalg.eigvalsh(covariance)[0]))))


def estimate_correspondence_translation(
        reference_points: NDArray[np.float64], moving_points: NDArray[np.float64],
        reference_shape: tuple[int, int], moving_shape: tuple[int, int], *,
        config: CorrespondenceConfig = CorrespondenceConfig(),
        cancelled: Callable[[], bool] | None = None) -> CorrespondenceDiagnostics:
    _check_cancelled(cancelled)
    p0, p1 = np.asarray(reference_points, dtype=np.float64), np.asarray(moving_points, dtype=np.float64)
    if p0.ndim != 2 or p0.shape[1] != 2 or p0.shape != p1.shape:
        raise ValueError('Korespondencje wymagają zgodnych tablic N × 2.')
    if min(*reference_shape, *moving_shape) < 1:
        raise ValueError('Nieprawidłowe wymiary obrazów.')
    count = len(p0)
    valid = np.isfinite(p0).all(axis=1) & np.isfinite(p1).all(axis=1)
    valid &= (p0 >= 0).all(axis=1) & (p1 >= 0).all(axis=1)
    valid &= (p0 < (reference_shape[1], reference_shape[0])).all(axis=1)
    valid &= (p1 < (moving_shape[1], moving_shape[0])).all(axis=1)
    p0, p1 = p0[valid], p1[valid]
    shifts = p0 - p1
    settings = '; '.join(f'{key}={value}' for key, value in asdict(config).items())
    if len(shifts) < config.minimum_matches:
        raise CorrespondenceRefusal(CorrespondenceDiagnostics(
            None, count, len(shifts), 0, 0., (0,) * 16, (0,) * 16, (0., 0.), (0., 0.),
            None, 'failed', (f'Za mało poprawnych korespondencji: {len(shifts)}; '
                             f'wymagane co najmniej {config.minimum_matches}.'), settings,
            settings_version=config.settings_version))
    selected = _cluster(shifts, config, cancelled)
    xy = np.median(shifts[selected], axis=0)
    residuals = np.linalg.norm(shifts[selected] - xy, axis=1)
    ref_grid, ref_span = _support(p0[selected], reference_shape)
    mov_grid, mov_span = _support(p1[selected], moving_shape)
    settings = '; '.join(f'{key}={value}' for key, value in asdict(config).items())
    diagnostic = CorrespondenceDiagnostics(
        (float(xy[0]), float(xy[1])), count, len(shifts), int(selected.sum()), float(selected.mean()),
        ref_grid, mov_grid, ref_span, mov_span, float(np.median(residuals)),
        'manual_review', 'Poparcie korespondencji wymaga oceny obrazu.', settings,
        settings_version=config.settings_version,
    )
    if diagnostic.inlier_count < config.minimum_inliers:
        raise CorrespondenceRefusal(replace(diagnostic, final_shift_xy=None, status='failed',
                                           reason=(f'Za mało zgodnych wektorów przesunięcia: '
                                                   f'{diagnostic.inlier_count}/{diagnostic.valid_count}; '
                                                   f'wymagane co najmniej {config.minimum_inliers} zgodne.')))
    warnings = []
    if diagnostic.inlier_count < config.review_minimum_inliers:
        warnings.append(f'mała liczba zgodnych punktów (próg ostrzeżenia {config.review_minimum_inliers})')
    if diagnostic.inlier_fraction < config.minimum_fraction:
        warnings.append(f'niski udział zgodnych punktów (próg ostrzeżenia {config.minimum_fraction:.0%})')
    remaining = shifts[~selected]
    if len(remaining) >= config.minimum_inliers:
        alternative = _cluster(remaining, config, cancelled)
        second = int(alternative.sum())
        alternative_xy = np.median(remaining[alternative], axis=0)
        if (second >= config.minimum_inliers and second >= config.competing_fraction * diagnostic.inlier_count
                and np.linalg.norm(alternative_xy - xy) > 2 * config.inlier_radius):
            warnings.append(f'konkurencyjne przesunięcia o podobnym poparciu: '
                            f'{diagnostic.inlier_count} i {second} punktów; '
                            f'alternatywa XY=({alternative_xy[0]:.3f}, {alternative_xy[1]:.3f}) px')
    if (min(_grid_lines(ref_grid), _grid_lines(mov_grid)) < config.minimum_grid_lines
            or min(_orthogonal_spread(p0[selected], reference_shape),
            _orthogonal_spread(p1[selected], moving_shape)) < config.minimum_orthogonal_spread
            or min(*ref_span, *mov_span) < config.minimum_span_fraction
            or min(sum(n > 0 for n in ref_grid), sum(n > 0 for n in mov_grid)) < config.minimum_cells):
        warnings.append('ograniczone poparcie przestrzenne — dopasowanie może dotyczyć tylko fragmentu obrazu')
    if warnings:
        return replace(diagnostic, status='low_confidence', reason=(
            f'Słabe poparcie: {diagnostic.inlier_count}/{diagnostic.valid_count} zgodnych punktów '
            f'({diagnostic.inlier_fraction:.1%}). ' + '; '.join(warnings) + '. '
            'Wynik niepewny — sprawdź dopasowanie obrazu.'))
    return diagnostic
