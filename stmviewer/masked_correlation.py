"""Fixed masked normalized cross-correlation on two independently selected images."""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray
from nanotrack.core import RegistrationFrameResult

from stmviewer.registration_masks import FrameMask


MASKED_METHOD = 'masked_correlation'
MASKED_LABEL = 'Korelacja z maskami (v1)'


def masked_label(use_masks: bool) -> str:
    return MASKED_LABEL + (' — maski włączone' if use_masks else ' — maski wyłączone')


def mask_settings(reference: FrameMask, moving: FrameMask, use_masks: bool) -> str:
    def rectangles(mask: FrameMask) -> str:
        return '; '.join(f'{r.kind} ({r.x0},{r.y0})–({r.x1},{r.y1})' for r in mask.rectangles) or 'cały dostępny obraz'
    return (f'Masked NCC v1; maski {"włączone" if use_masks else "wyłączone"}; '
            'overlap_ratio=0.3; min_pixels=64; min_span=4; wynik bez niezależnej oceny pewności.\n'
            f'Klatka bazowa: {rectangles(reference)}\nKlatka przesuwana: {rectangles(moving)}')


@dataclass(frozen=True)
class MaskedCorrelationConfig:
    overlap_ratio: float = 0.3
    min_pixels: int = 64
    min_span: int = 4


class MaskedCorrelationShiftBackend:
    def __init__(self) -> None:
        # Local dependency check; no shared backend settings or model downloads.
        from skimage.registration import phase_cross_correlation
        if not callable(phase_cross_correlation):
            raise ImportError('Brak masked NCC w scikit-image.')
        self.config = MaskedCorrelationConfig()

    def validate(self, image: NDArray[np.float64], mask: FrameMask, use_masks: bool) -> None:
        self._normalise(image, (mask if use_masks else FrameMask()).raster(image), 'Klatka')

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult:
        return self.estimate_masked(reference_frame, moving_frame, moving_frame_index=moving_frame_index)

    def estimate_masked(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                        *, moving_frame_index: int, reference_mask: FrameMask = FrameMask(),
                        moving_mask: FrameMask = FrameMask(), use_masks: bool = True) -> RegistrationFrameResult:
        from scipy.ndimage import shift as shift_image
        from skimage.registration import phase_cross_correlation

        if (reference_frame.shape != moving_frame.shape or reference_frame.ndim != 2
                or min(reference_frame.shape) < 1):
            raise ValueError('Masked NCC wymaga jednakowych niepustych obrazów 2D.')
        reference_valid = (reference_mask if use_masks else FrameMask()).raster(reference_frame)
        moving_valid = (moving_mask if use_masks else FrameMask()).raster(moving_frame)
        reference = self._normalise(reference_frame, reference_valid, 'Klatka bazowa')
        moving = self._normalise(moving_frame, moving_valid, 'Klatka przesuwana')
        # Providing BOTH masks always selects masked NCC, including the mask-off
        # comparison. Normalization/upsample_factor do not control this algorithm.
        correlate: Callable[..., tuple[NDArray[np.float64], float, float]] = phase_cross_correlation
        shift_yx, _, _ = correlate(
            reference, moving, reference_mask=reference_valid, moving_mask=moving_valid,
            overlap_ratio=self.config.overlap_ratio,
        )
        shift_yx = np.asarray(shift_yx, dtype=float)
        if shift_yx.shape != (2,) or not np.isfinite(shift_yx).all():
            raise ValueError('Masked NCC nie wyznaczył poprawnego przesunięcia.')
        shifted_mask = shift_image(moving_valid.astype(np.uint8), shift_yx, order=0,
                                  mode='constant', cval=0, prefilter=False).astype(bool)
        overlap = reference_valid & shifted_mask
        count = int(np.count_nonzero(overlap))
        required = self.config.overlap_ratio * min(np.count_nonzero(reference_valid), np.count_nonzero(moving_valid))
        if count < max(self.config.min_pixels, required):
            raise ValueError('Masked NCC: za mało wspólnych ważnych pikseli po dopasowaniu.')
        self._normalise(reference, overlap, 'Wspólna część klatki bazowej')
        moved = np.asarray(shift_image(moving, shift_yx, order=1, mode='constant', cval=0, prefilter=False),
                           dtype=np.float64)
        self._normalise(moved, overlap, 'Wspólna część klatki przesuwanej')
        return RegistrationFrameResult(moving_frame_index, (float(shift_yx[1]), float(shift_yx[0])),
                                       MASKED_METHOD, status='manual_review')

    def _normalise(self, image: NDArray[np.float64], valid: NDArray[np.bool_], name: str) -> NDArray[np.float64]:
        rows, columns = np.nonzero(valid)
        if rows.size < self.config.min_pixels:
            raise ValueError(f'{name}: maska pozostawia za mało danych (minimum {self.config.min_pixels} pikseli).')
        if np.ptp(rows) + 1 < self.config.min_span or np.ptp(columns) + 1 < self.config.min_span:
            raise ValueError(f'{name}: maska ma zbyt małą rozpiętość w X lub Y (minimum 4 px).')
        values = image[valid]
        scale = float(np.max(np.abs(values)))
        if scale == 0:
            raise ValueError(f'{name}: za mało tekstury w wybranych danych.')
        normalized = values / scale
        if float(np.ptp(normalized)) <= 64 * np.finfo(np.float64).eps:
            raise ValueError(f'{name}: za mało tekstury w wybranych danych.')
        result = np.zeros(image.shape, dtype=np.float64)
        result[valid] = normalized
        return result
