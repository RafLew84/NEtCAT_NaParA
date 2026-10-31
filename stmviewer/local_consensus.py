"""Local image measurements for one translation, without deforming the images."""

from dataclasses import asdict, dataclass, replace
from typing import Callable, Literal

import numpy as np
from numpy.typing import NDArray

Rect = tuple[int, int, int, int]
FloatRect = tuple[float, float, float, float]


@dataclass(frozen=True)
class LocalConsensusConfig:
    grid_rows: int = 4
    grid_columns: int = 4
    patch_size: int = 32
    search_radius: int = 16
    minimum_patch_size: int = 16
    minimum_texture_strength: float = 1e-4
    minimum_correlation: float = 0.1
    minimum_peak_contrast: float = 3.5
    minimum_peak_margin: float = 0.025
    peak_exclusion_radius: int = 3
    inlier_radius: float = 1.5
    minimum_support: int = 4
    minimum_rows: int = 2
    minimum_columns: int = 2
    competing_fraction: float = 0.6
    settings_version: int = 1


@dataclass(frozen=True)
class LocalPatchEvidence:
    reference_rect: Rect
    moving_rect: FloatRect | None
    shift_xy: tuple[float, float] | None
    score: float | None
    peak_margin: float | None
    status: Literal['inlier', 'outlier', 'unmatched']
    reason: str
    peak_contrast: float | None = None


@dataclass(frozen=True)
class LocalDiagnostics:
    deep_shift_xy: tuple[float, float]
    final_shift_xy: tuple[float, float] | None
    patches: tuple[LocalPatchEvidence, ...]
    status: str
    reason: str
    settings_text: str
    weights: str = ''
    requested_device: str = ''
    actual_device: str = ''
    deep_status: str = ''
    deep_quality_score: float | None = None
    settings_version: int = 1


class LocalConsensusError(ValueError):
    """No local estimate; preserve the evidence for the pair comparison."""

    def __init__(self, diagnostics: LocalDiagnostics) -> None:
        super().__init__(diagnostics.reason)
        self.diagnostics = diagnostics


def _checkpoint(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        from stmviewer.registration import RegistrationCancelled
        raise RegistrationCancelled


def _normalized(data: NDArray[np.float64]) -> NDArray[np.float64]:
    # Divide before centering to avoid overflow with large physical offsets.
    scale = float(max(float(np.max(np.abs(data))), float(np.finfo(np.float64).tiny)))
    values = np.asarray(data / scale, dtype=np.float64)
    values -= float(np.mean(values))
    spread = float(np.std(values))
    return values / spread if spread > np.finfo(np.float64).tiny else values


def _correlation(search: NDArray[np.float64], template: NDArray[np.float64]) -> NDArray[np.float64]:
    from scipy.signal import correlate
    centered = template - float(template.mean())
    energy = float(np.sum(centered * centered))
    kernel = np.ones(template.shape, dtype=np.float64)
    sums = np.asarray(correlate(search, kernel, mode='valid', method='fft'), dtype=np.float64)
    squares = np.asarray(correlate(search * search, kernel, mode='valid', method='fft'), dtype=np.float64)
    variance = np.maximum(squares - sums * sums / template.size, 0)
    denominator = np.sqrt(variance * energy)
    numerator = np.asarray(correlate(search, centered, mode='valid', method='fft'), dtype=np.float64)
    score = np.full(denominator.shape, -1.0, dtype=np.float64)
    np.divide(numerator, denominator, out=score, where=denominator > np.finfo(np.float64).eps)
    return np.clip(score, -1, 1)


def _subpixel(values: NDArray[np.float64], y: int, x: int) -> tuple[float, float]:
    def offset(left: float, center: float, right: float) -> float:
        denominator = left - 2 * center + right
        return float(np.clip(0.5 * (left - right) / denominator, -0.5, 0.5)) if denominator < -1e-12 else 0.0
    dx = offset(float(values[y, x - 1]), float(values[y, x]), float(values[y, x + 1])) if 0 < x < values.shape[1] - 1 else 0.0
    dy = offset(float(values[y - 1, x]), float(values[y, x]), float(values[y + 1, x])) if 0 < y < values.shape[0] - 1 else 0.0
    return dx, dy


def _texture_strength(template: NDArray[np.float64]) -> float:
    spread = float(np.std(template))
    if spread <= np.finfo(np.float64).eps * max(1.0, float(np.max(np.abs(template)))):
        return 0.0
    gy, gx = np.gradient((template - float(template.mean())) / spread)
    xx, yy, xy = float(np.mean(gx * gx)), float(np.mean(gy * gy)), float(np.mean(gx * gy))
    # The weak direction prevents a pure scan line from supplying a 2D location.
    return float(max(0.0, 0.5 * (xx + yy - float(np.hypot(xx - yy, 2 * xy)))))


def _select_patch(reference: NDArray[np.float64], bounds: Rect, size: int) -> Rect:
    x0, y0, width, height = bounds
    xs = sorted({x0, x0 + (width - size) // 2, x0 + width - size})
    ys = sorted({y0, y0 + (height - size) // 2, y0 + height - size})
    candidates = [(x, y, size, size) for y in ys for x in xs]
    return max(candidates, key=lambda r: _texture_strength(reference[r[1]:r[1] + size, r[0]:r[0] + size]))


def _peak_contrast(scores: NDArray[np.float64], py: int, px: int, radius: int) -> float | None:
    """Peak prominence against robust sidelobe spread; not a calibrated probability."""
    outside = np.ones(scores.shape, dtype=np.bool_)
    outside[max(0, py - radius):py + radius + 1, max(0, px - radius):px + radius + 1] = False
    background = scores[outside]
    if background.size < 9:
        return None
    median = float(np.median(background))
    spread = 1.4826 * float(np.median(np.abs(background - median)))
    # NCC is bounded by [-1, 1]; the floor avoids division by zero for a flat
    # sidelobe while keeping the diagnostic finite. It does not create certainty.
    return (float(scores[py, px]) - median) / max(spread, 1e-12)


def _match_patch(reference: NDArray[np.float64], moving: NDArray[np.float64], rect: Rect,
                 start: tuple[float, float], config: LocalConsensusConfig) -> LocalPatchEvidence:
    x, y, width, height = rect
    template = reference[y:y + height, x:x + width]
    if _texture_strength(template) < config.minimum_texture_strength:
        return LocalPatchEvidence(rect, None, None, None, None, 'unmatched', 'Za mało tekstury w dwóch kierunkach.')
    x0 = max(0, int(np.floor(x - start[0] - config.search_radius)))
    y0 = max(0, int(np.floor(y - start[1] - config.search_radius)))
    x1 = min(moving.shape[1], int(np.ceil(x - start[0] + config.search_radius)) + width)
    y1 = min(moving.shape[0], int(np.ceil(y - start[1] + config.search_radius)) + height)
    if x1 - x0 < width or y1 - y0 < height:
        return LocalPatchEvidence(rect, None, None, None, None, 'unmatched', 'Brak wspólnego pola w obszarze poszukiwania.')
    search = moving[y0:y1, x0:x1]
    scores = _correlation(search, template)
    peak_y, peak_x = np.unravel_index(int(scores.argmax()), scores.shape)
    px, py = int(peak_x), int(peak_y)
    score = float(scores[py, px])
    if px in (0, scores.shape[1] - 1) or py in (0, scores.shape[0] - 1):
        return LocalPatchEvidence(rect, None, None, score, None, 'unmatched', 'Maksimum na brzegu obszaru poszukiwania.')
    alternative = scores.copy()
    radius = config.peak_exclusion_radius
    alternative[max(0, py - radius):py + radius + 1, max(0, px - radius):px + radius + 1] = -1
    margin = score - float(alternative.max())
    contrast = _peak_contrast(scores, py, px, radius)
    if score < config.minimum_correlation:
        return LocalPatchEvidence(rect, None, None, score, margin, 'unmatched', 'Za mała korelacja fragmentu.', contrast)
    if margin < config.minimum_peak_margin:
        return LocalPatchEvidence(rect, None, None, score, margin, 'unmatched', 'Niejednoznaczne maksima korelacji.', contrast)
    if contrast is None or contrast < config.minimum_peak_contrast:
        return LocalPatchEvidence(rect, None, None, score, margin, 'unmatched',
                                  'Pik niewystarczająco wyróżnia się na tle odpowiedzi korelacji.', contrast)
    dx, dy = _subpixel(scores, py, px)
    mx, my = x0 + px + dx, y0 + py + dy
    return LocalPatchEvidence(rect, (mx, my, float(width), float(height)),
                              (x - mx, y - my), score, margin, 'inlier', 'Lokalne dopasowanie.', contrast)


def estimate_local_consensus(reference: NDArray[np.float64], moving: NDArray[np.float64],
                             initial_shift_xy: tuple[float, float], *,
                             config: LocalConsensusConfig = LocalConsensusConfig(),
                             cancelled: Callable[[], bool] | None = None,
                             progress: Callable[[str], None] | None = None,
                             diagnostics: Callable[[LocalDiagnostics], None] | None = None) -> LocalDiagnostics:
    """Measure separated patches around an exact initial XY and return global XY."""
    _checkpoint(cancelled)
    settings = '; '.join(f'{key}={value}' for key, value in asdict(config).items())
    start = tuple(float(v) for v in initial_shift_xy)
    if len(start) != 2 or not np.isfinite(start).all():
        raise ValueError('Nieprawidłowy początkowy wektor XY.')
    start_xy = (start[0], start[1])
    if reference.ndim != 2 or moving.ndim != 2 or reference.shape != moving.shape or not reference.size:
        raise LocalConsensusError(LocalDiagnostics(start_xy, None, (), 'failed', 'Niezgodne lub puste wymiary obrazów.', settings))
    if min(reference.shape[0] // config.grid_rows, reference.shape[1] // config.grid_columns, config.patch_size) < config.minimum_patch_size:
        raise LocalConsensusError(LocalDiagnostics(start_xy, None, (), 'failed', 'Za mały obraz dla rozdzielonych fragmentów.', settings))
    if not np.isfinite(reference).all() or not np.isfinite(moving).all():
        raise LocalConsensusError(LocalDiagnostics(start_xy, None, (), 'failed',
                                                   'Wejście zawiera NaN/Inf; brakujące próbki nie są zerami.', settings))
    reference, moving = _normalized(reference), _normalized(moving)
    patches: list[LocalPatchEvidence] = []

    def publish_partial(reason: str) -> None:
        if diagnostics is not None:
            # A measured candidate is not yet an inlier of a spatial consensus.
            pending = tuple(replace(p, status='unmatched', reason='Nie oceniono w konsensusie; ' + p.reason)
                            if p.status == 'inlier' else p for p in patches)
            diagnostics(LocalDiagnostics(start_xy, None, pending, 'failed', reason, settings))

    height, width = reference.shape
    from stmviewer.registration import RegistrationCancelled
    try:
        for row in range(config.grid_rows):
            y0, y1 = row * height // config.grid_rows, (row + 1) * height // config.grid_rows
            for column in range(config.grid_columns):
                _checkpoint(cancelled)
                x0, x1 = column * width // config.grid_columns, (column + 1) * width // config.grid_columns
                size = min(config.patch_size, x1 - x0, y1 - y0)
                rect = _select_patch(reference, (x0, y0, x1 - x0, y1 - y0), size)
                patches.append(_match_patch(reference, moving, rect, start_xy, config))
                publish_partial('Nie zakończono dopasowania fragmentów ani oceny konsensusu.')
                if progress is not None:
                    progress(f'Fragmenty: {len(patches)}/{config.grid_rows * config.grid_columns}')
                _checkpoint(cancelled)
    except RegistrationCancelled:
        publish_partial('Anulowano przed wyznaczeniem konsensusu.')
        raise
    candidates = [p.shift_xy for p in patches if p.shift_xy is not None]
    if not candidates:
        raise LocalConsensusError(LocalDiagnostics(start_xy, None, tuple(patches), 'failed', 'Brak lokalnych dopasowań.', settings))
    vectors = np.asarray(candidates, dtype=np.float64)
    memberships = np.linalg.norm(vectors[:, None, :] - vectors[None, :, :], axis=2) <= config.inlier_radius
    best = memberships[int(np.argmax(memberships.sum(axis=1)))]
    median = np.median(vectors[best], axis=0)
    final = float(median[0]), float(median[1])
    patches = [replace(p, status='outlier', reason='Wektor poza dominującą grupą.')
               if p.shift_xy is not None and np.linalg.norm(np.asarray(p.shift_xy) - median) > config.inlier_radius
               else p for p in patches]
    supported = [p for p in patches if p.status == 'inlier']
    rows = {int((p.reference_rect[1] + p.reference_rect[3] / 2) * config.grid_rows / height) for p in supported}
    columns = {int((p.reference_rect[0] + p.reference_rect[2] / 2) * config.grid_columns / width) for p in supported}
    if (len(supported) < config.minimum_support or len(rows) < config.minimum_rows
            or len(columns) < config.minimum_columns):
        raise LocalConsensusError(LocalDiagnostics(
            start_xy, None, tuple(patches), 'failed',
            f'Za mało poparcia przestrzennego: {len(supported)} fragmentów, {len(rows)} rzędów, {len(columns)} kolumn.', settings,
        ))
    remaining = np.asarray([p.shift_xy for p in patches if p.status == 'outlier'], dtype=np.float64)
    competing = 0
    if remaining.size:
        separation = np.linalg.norm(remaining[:, None, :] - remaining[None, :, :], axis=2)
        competing = int(np.max(np.sum(separation <= config.inlier_radius, axis=1)))
    uncertain = competing >= max(2, len(supported) * config.competing_fraction)
    reason = (f'Konkurujące grupy przesunięć: {len(supported)} i {competing} fragmentów. Jedno XY nie dopasuje obu.'
              if uncertain else f'Poparcie: {len(supported)} fragmentów w {len(rows)} rzędach i {len(columns)} kolumnach. Wynik wymaga oceny struktur.')
    return LocalDiagnostics(start_xy, final, tuple(patches), 'low_confidence' if uncertain else 'manual_review', reason, settings)
