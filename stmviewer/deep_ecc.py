"""One versioned Deep→ECC translation experiment, without fallback or image warps."""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np
from numpy.typing import NDArray
from nanotrack.core import RegistrationFrameResult

from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason, load_deep_backend

if TYPE_CHECKING:
    from stmviewer.registration import ShiftBackend

HYBRID_METHOD = 'deep_matcher_ecc'
HYBRID_LABEL = 'Deep Matcher + ECC (v1)'


@dataclass(frozen=True)
class HybridDiagnostics:
    """Exact estimates from one run; scores are backend measures, not validation."""

    deep_shift_xy: tuple[float, float]
    final_shift_xy: tuple[float, float]
    correction_xy: tuple[float, float]
    deep_status: str
    deep_quality_score: float
    ecc_status: str
    ecc_score: float
    settings_text: str
    weights: str
    requested_device: str
    actual_device: str
    settings_version: int = 1


def hybrid_unavailable_reason(options: DeepMatcherOptions) -> str | None:
    reason = deep_unavailable_reason(options)
    if reason:
        return reason
    try:
        from cv2 import findTransformECC
        from nanotrack.registration.ecc_translation import ECCTranslationBackend
        if not callable(findTransformECC):
            return 'OpenCV cv2: brak funkcji findTransformECC.'
        ECCTranslationBackend()
    except Exception as error:
        return f'ECC: {str(error) or type(error).__name__}'
    return None


class DeepEccBackend:
    """Reuse one loaded model; record only scalar diagnostics for the last pair."""

    def __init__(self, deep: 'ShiftBackend', options: DeepMatcherOptions, device: str, *,
                 progress: Callable[[str], None] | None = None,
                 cancelled: Callable[[], bool] | None = None, pair_label: str | None = None) -> None:
        from nanotrack.registration.ecc_translation import ECCTranslationBackend, ECCTranslationConfig

        self._deep = deep
        self._pair_label = pair_label
        self.options = options
        self.device = device
        self._progress, self._cancelled = progress, cancelled
        self._ecc = ECCTranslationBackend(ECCTranslationConfig(
            max_iterations=100, epsilon=1e-6, gaussian_filter_size=5,
            min_texture_std=1e-8, min_mask_pixels=16, low_confidence_ecc_score=0.75,
        ))
        # With an injected local LoFTR, shared config.device/pretrained are unused.
        deep_config = {key: value for key, value in asdict(getattr(deep, 'config')).items()
                       if key not in ('device', 'pretrained')}
        self.settings_text = (
            'Deep Matcher + ECC v1; oryginały; ECC CPU; MOTION_TRANSLATION; '
            f'Deep={deep_config}; max_iterations=100; epsilon=1e-06; '
            'gaussian_filter_size=5; min_texture_std=1e-08; low_confidence_ecc_score=0.75; '
            f'wagi={options.weights}; wybrane urządzenie={options.device}; Deep={device}'
        )
        self.last_diagnostics: HybridDiagnostics | None = None

    def _checkpoint(self) -> None:
        from stmviewer.registration import RegistrationCancelled
        if self._cancelled is not None and self._cancelled():
            raise RegistrationCancelled

    def _report(self, text: str) -> None:
        self._checkpoint()
        if self._progress is not None:
            self._progress(text)
        self._checkpoint()

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult:
        from stmviewer.registration import RegistrationCancelled, RegistrationError

        self.last_diagnostics = None
        pair_label = self._pair_label or f'Para {moving_frame_index} → {moving_frame_index + 1}'
        stage = 'Deep Matcher'
        try:
            self._report(f'{pair_label} — Deep Matcher ({self.device})')
            deep = self._deep.estimate(reference_frame, moving_frame, moving_frame_index=moving_frame_index)
            self._checkpoint()
            start = _valid_result(deep, moving_frame_index)
            stage = 'ECC'
            self._report(f'{pair_label} — ECC (CPU), start Deep X={start[0]:.3f}, Y={start[1]:.3f}')
            refined = self._ecc.estimate(reference_frame, moving_frame,
                                         moving_frame_index=moving_frame_index, initial_shift_xy=start)
            self._checkpoint()
            final = _valid_result(refined, moving_frame_index)
            score = float(refined.ecc_score)
            if not np.isfinite(score):
                raise ValueError('nieprawidłowy score ECC')
            self.last_diagnostics = HybridDiagnostics(
                start, final, (final[0] - start[0], final[1] - start[1]),
                str(deep.status), float(deep.quality_score), str(refined.status), score,
                self.settings_text, str(self.options.weights), self.options.device, self.device,
            )
            return RegistrationFrameResult(frame_index=moving_frame_index, shift_xy=final,
                                           method=HYBRID_METHOD, quality_score=0.0,
                                           ecc_score=score, status='manual_review')
        except RegistrationCancelled:
            raise
        except Exception as error:
            self._checkpoint()
            reason = str(error) or type(error).__name__
            if error.__cause__ is not None:
                reason += f' Przyczyna: {str(error.__cause__) or type(error.__cause__).__name__}'
            raise RegistrationError(f'{pair_label} — {stage}: {reason}') from error


def _valid_result(result: RegistrationFrameResult, index: int) -> tuple[float, float]:
    if (result is None or result.frame_index != index
            or result.status not in ('ok', 'low_confidence', 'manual_review')):
        raise ValueError('brak poprawnego wyniku lub status failed')
    shift = np.asarray(result.shift_xy, dtype=np.float64)
    if shift.shape != (2,) or not np.isfinite(shift).all():
        raise ValueError('nieprawidłowe przesunięcie XY')
    quality = float(result.quality_score)
    if not np.isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError('nieprawidłowa miara backendu')
    return float(shift[0]), float(shift[1])


def load_deep_ecc_backend(options: DeepMatcherOptions, *,
                          progress: Callable[[str], None] | None = None,
                          cancelled: Callable[[], bool] | None = None,
                          pair_label: str | None = None) -> DeepEccBackend:
    from stmviewer.registration import RegistrationError

    reason = hybrid_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'Deep Matcher + ECC — przygotowanie: {reason}')
    loaded = load_deep_backend(options, progress=progress, cancelled=cancelled)
    return DeepEccBackend(loaded.backend, options, loaded.device, progress=progress, cancelled=cancelled,
                          pair_label=pair_label)
