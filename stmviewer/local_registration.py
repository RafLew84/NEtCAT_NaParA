"""Exact Deep initial estimate followed by spatially separated image evidence."""

from dataclasses import asdict, is_dataclass, replace
from typing import TYPE_CHECKING, Callable

import numpy as np
from numpy.typing import NDArray
from nanotrack.core import RegistrationFrameResult

from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason, load_deep_backend
from stmviewer.local_consensus import (
    LocalConsensusConfig, LocalConsensusError, LocalDiagnostics, estimate_local_consensus,
)

if TYPE_CHECKING:
    from stmviewer.registration import ShiftBackend

LOCAL_METHOD = 'deep_local_consensus'
LOCAL_LABEL = 'Deep Matcher + lokalne fragmenty (v1)'


def local_unavailable_reason(options: DeepMatcherOptions) -> str | None:
    reason = deep_unavailable_reason(options)
    if reason:
        return reason
    try:
        from scipy.signal import correlate
        if not callable(correlate):
            return 'Fragmenty: brak scipy.signal.correlate.'
    except Exception as error:
        return f'Fragmenty: {str(error) or type(error).__name__}'
    return None


class DeepLocalBackend:
    """Reuse one model and preserve the exact start plus compact local evidence."""

    def __init__(self, deep: 'ShiftBackend', options: DeepMatcherOptions, device: str, *,
                 config: LocalConsensusConfig = LocalConsensusConfig(),
                 progress: Callable[[str], None] | None = None,
                 cancelled: Callable[[], bool] | None = None, pair_label: str | None = None) -> None:
        self._deep = deep
        self.options, self.device, self.config = options, device, config
        self._progress, self._cancelled, self._pair_label = progress, cancelled, pair_label
        deep_config = getattr(deep, 'config', None)
        settings = asdict(deep_config) if is_dataclass(deep_config) and not isinstance(deep_config, type) else {}
        for name in ('device', 'pretrained'):
            settings.pop(name, None)
        self.settings_text = (
            f'{LOCAL_LABEL}; oryginały; Deep={settings}; '
            + '; '.join(f'{key}={value}' for key, value in asdict(config).items())
            + f'; wagi={options.weights}; wybrane urządzenie={options.device}; Deep={device}'
        )
        self.last_diagnostics: LocalDiagnostics | None = None
        self.trial_settings = {'deep': settings, 'local': asdict(config), 'settings_version': 1}

    def _checkpoint(self) -> None:
        from stmviewer.registration import RegistrationCancelled
        if self._cancelled is not None and self._cancelled():
            raise RegistrationCancelled

    def _report(self, text: str) -> None:
        self._checkpoint()
        if self._progress is not None:
            self._progress(text)
        self._checkpoint()

    def _details(self, local: LocalDiagnostics, deep: RegistrationFrameResult) -> LocalDiagnostics:
        return replace(local, settings_text=self.settings_text, weights=str(self.options.weights),
                       requested_device=self.options.device, actual_device=self.device,
                       deep_status=str(deep.status), deep_quality_score=float(deep.quality_score))

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64], *,
                 moving_frame_index: int) -> RegistrationFrameResult:
        from stmviewer.registration import RegistrationCancelled, RegistrationError
        self.last_diagnostics = None
        pair = self._pair_label or f'Para {moving_frame_index} → {moving_frame_index + 1}'
        stage = 'Deep Matcher'
        try:
            self._report(f'{pair} — Deep Matcher ({self.device})')
            deep = self._deep.estimate(reference_frame, moving_frame, moving_frame_index=moving_frame_index)
            shift = np.asarray(deep.shift_xy, dtype=np.float64)
            quality = float(deep.quality_score)
            if (deep.frame_index != moving_frame_index
                    or deep.status not in ('ok', 'low_confidence', 'manual_review')
                    or shift.shape != (2,) or not np.isfinite(shift).all()
                    or not np.isfinite(quality) or not 0 <= quality <= 1):
                raise ValueError('Brak poprawnego wyniku Deep.')
            self.last_diagnostics = self._details(LocalDiagnostics(
                (float(shift[0]), float(shift[1])), None, (), 'failed',
                'Nie ukończono lokalnego dopasowania.', self.settings_text,
            ), deep)
            stage = 'Lokalne fragmenty'
            self._report(f'{pair} — {stage} (CPU)')
            def retain_partial(evidence: LocalDiagnostics) -> None:
                self.last_diagnostics = self._details(evidence, deep)

            try:
                local = estimate_local_consensus(
                    reference_frame, moving_frame, (float(shift[0]), float(shift[1])), config=self.config,
                    cancelled=self._cancelled, progress=lambda text: self._report(f'{pair} — {text}'),
                    diagnostics=retain_partial,
                )
            except LocalConsensusError as error:
                diagnostics = self._details(error.diagnostics, deep)
                diagnostics = replace(diagnostics, reason=f'{pair} — {stage}: {diagnostics.reason}')
                self.last_diagnostics = diagnostics
                raise LocalConsensusError(diagnostics) from error
            self.last_diagnostics = self._details(local, deep)
            if local.final_shift_xy is None:
                raise ValueError('Brak końcowego XY lokalnego konsensusu.')
            return RegistrationFrameResult(frame_index=moving_frame_index, shift_xy=local.final_shift_xy,
                                           method=LOCAL_METHOD, quality_score=0.0, status='manual_review')
        except RegistrationCancelled:
            if self.last_diagnostics is not None:
                self.last_diagnostics = replace(
                    self.last_diagnostics, reason=f'{pair} — {stage}: Anulowano próbę.',
                )
            raise
        except LocalConsensusError:
            raise
        except Exception as error:
            self._checkpoint()
            raise RegistrationError(f'{pair} — {stage}: {str(error) or type(error).__name__}') from error


def load_deep_local_backend(options: DeepMatcherOptions, *,
                            progress: Callable[[str], None] | None = None,
                            cancelled: Callable[[], bool] | None = None,
                            pair_label: str | None = None) -> DeepLocalBackend:
    from stmviewer.registration import RegistrationError
    reason = local_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'{LOCAL_LABEL} — przygotowanie: {reason}')
    loaded = load_deep_backend(options, progress=progress, cancelled=cancelled)
    return DeepLocalBackend(loaded.backend, options, loaded.device, progress=progress,
                            cancelled=cancelled, pair_label=pair_label)
