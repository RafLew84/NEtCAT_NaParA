"""Lightweight pair trials and a fixed reference field for visual comparison."""


from dataclasses import dataclass, asdict, is_dataclass
from typing import Callable, Literal

import numpy as np
from numpy.typing import NDArray

from stmviewer.method_parameters import MethodProfiles
from stmviewer.akaze_matcher import AKAZE_METHOD, AKAZE_LABEL, AkazeBackend
from stmviewer.lightglue_matcher import LIGHTGLUE_METHOD, LightGlueBackend, load_lightglue_backend
from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal
from stmviewer.efficient_matcher import EFFICIENT_METHOD, EfficientBackend, load_efficient_backend
from stmviewer.roma_matcher import ROMA_METHOD, RomaBackend, load_roma_backend
from stmviewer.matchanything_matcher import MATCHANYTHING_METHOD, MatchAnythingBackend, load_matchanything_backend
from stmviewer.local_consensus import LocalDiagnostics, LocalConsensusError
from stmviewer.local_registration import LOCAL_METHOD, DeepLocalBackend, load_deep_local_backend
from stmviewer.frame import ImageFrame
from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
from stmviewer.deep_ecc import HYBRID_METHOD, HybridDiagnostics, DeepEccBackend, load_deep_ecc_backend
from stmviewer.registration import (
    FrameOrigin, REGISTRATION_METHODS, RegistrationCancelled, RegistrationError,
    ShiftBackend, create_shift_backend, estimate_confidence,
)


@dataclass(frozen=True)
class ManualProvenance:
    """A bounded record of one manual edit, independent of backend confidence."""

    start_xy: tuple[float, float]
    correction_xy: tuple[int, int]
    source_label: str | None
    settings_version: int = 1


@dataclass(frozen=True)
class PairTrial:
    reference: FrameOrigin
    moving: FrameOrigin
    method: str
    label: str
    settings_text: str
    device: str
    shift_xy: tuple[float, float]
    status: str
    quality_score: float | None
    manual: ManualProvenance | None = None
    movie_revision: str | None = None
    hybrid: HybridDiagnostics | None = None
    local: LocalDiagnostics | None = None
    correspondence: CorrespondenceDiagnostics | None = None


def estimate_pair(reference: ImageFrame, moving: ImageFrame, *,
                  method: str = 'phase_correlation',
                  deep_options: DeepMatcherOptions | None = None,
                  method_profiles: MethodProfiles = MethodProfiles(),
                  backend: ShiftBackend | None = None,
                  cancelled: Callable[[], bool] | None = None,
                  progress: Callable[[str], None] | None = None) -> PairTrial:
    """Estimate one original pair without creating any aligned images."""
    def checkpoint() -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    def report(text: str) -> None:
        checkpoint()
        if progress is not None:
            progress(text)
        checkpoint()

    checkpoint()
    if method not in REGISTRATION_METHODS:
        raise RegistrationError(f'Nieznana metoda rejestracji: {method}')
    label = REGISTRATION_METHODS[method]
    pair_label = _source_pair_label(reference, moving)
    try:
        _check_shape(reference, moving)
    except RegistrationError as error:
        if method in (HYBRID_METHOD, LOCAL_METHOD):
            raise RegistrationError(f'{pair_label} — Deep Matcher (wejście): {error}') from error
        raise
    if not np.isfinite(reference.data).all() or not np.isfinite(moving.data).all():
        prefix = f'{pair_label} — Deep Matcher (wejście)' if method in (HYBRID_METHOD, LOCAL_METHOD) else label
        raise RegistrationError(f'{prefix}: para wymaga skończonych próbek; wejście zawiera NaN/Inf.')
    device = 'CPU'
    settings = 'Oryginały; ustawienia NanoTrack'
    if method == AKAZE_METHOD:
        akaze = AkazeBackend(parameters=method_profiles.akaze, cancelled=cancelled, progress=report)
        backend, settings = akaze, akaze.settings_text
    elif method == LIGHTGLUE_METHOD:
        lightglue = load_lightglue_backend(deep_options or DeepMatcherOptions(),
                                         parameters=method_profiles.lightglue,
                                         cancelled=cancelled, progress=report)
        backend, device, settings = lightglue, lightglue.device, lightglue.settings_text
    elif method == MATCHANYTHING_METHOD:
        matchanything = load_matchanything_backend(deep_options or DeepMatcherOptions(),
                                                   cancelled=cancelled, progress=report)
        backend, device, settings = matchanything, matchanything.device, matchanything.settings_text
    elif method == ROMA_METHOD:
        roma = load_roma_backend(deep_options or DeepMatcherOptions(),
                                 cancelled=cancelled, progress=report)
        backend, device, settings = roma, roma.device, roma.settings_text
    elif method == EFFICIENT_METHOD:
        efficient = load_efficient_backend(deep_options or DeepMatcherOptions(),
                                           cancelled=cancelled, progress=report)
        backend, device, settings = efficient, efficient.device, efficient.settings_text
    elif method == LOCAL_METHOD:
        local = load_deep_local_backend(deep_options or DeepMatcherOptions(), cancelled=cancelled,
                                       progress=report, pair_label=pair_label)
        backend, device, settings = local, local.device, local.settings_text
    elif method == HYBRID_METHOD:
        hybrid = load_deep_ecc_backend(deep_options or DeepMatcherOptions(), cancelled=cancelled,
                                       progress=report, pair_label=pair_label)
        backend, device, settings = hybrid, hybrid.device, hybrid.settings_text
    elif method == 'deep_matcher_translation':
        options = deep_options or DeepMatcherOptions()
        loaded = load_deep_backend(options, cancelled=cancelled, progress=report)
        backend, device = loaded.backend, loaded.device
        settings += f'; wagi={options.weights}; wybrane urządzenie={options.device}'
    else:
        backend = backend if backend is not None else create_shift_backend(method)
    try:
        configuration = getattr(backend, 'config', None)
        # The local wrapper already describes both stages and its full configuration.
        if (not isinstance(backend, (DeepLocalBackend, EfficientBackend, RomaBackend, MatchAnythingBackend, LightGlueBackend, AkazeBackend))
                and is_dataclass(configuration) and not isinstance(configuration, type)):
            settings += '; ' + '; '.join(f'{k}={v}' for k, v in asdict(configuration).items())
        report(f'{label}: wyznaczanie przesunięcia pary…')
        try:
            result = backend.estimate(reference.data, moving.data, moving_frame_index=1)
            checkpoint()
            if (result is None or result.frame_index != 1
                    or result.status not in ('ok', 'low_confidence', 'manual_review')):
                raise ValueError('brak poprawnego wyniku pary lub status failed')
            shift = np.asarray(result.shift_xy, dtype=np.float64)
            if shift.shape != (2,) or not np.isfinite(shift).all():
                raise ValueError('nieprawidłowe przesunięcie XY')
            status, quality = estimate_confidence(method, result)
        except (RegistrationCancelled, RegistrationError, LocalConsensusError, CorrespondenceRefusal):
            checkpoint()
            raise
        except Exception as error:
            checkpoint()
            reason = str(error) or type(error).__name__
            if 'too little texture' in reason:
                reason = f'za mało tekstury do rejestracji {label}'
            raise RegistrationError(f'Para ({label}): {reason}') from error
        return PairTrial(
            FrameOrigin(reference.source, reference.source_frame_index),
            FrameOrigin(moving.source, moving.source_frame_index),
            method, label, settings, device, (float(result.shift_xy[0]), float(result.shift_xy[1])),
            status, quality, hybrid=backend.last_diagnostics if isinstance(backend, DeepEccBackend) else None,
            local=backend.last_diagnostics if isinstance(backend, DeepLocalBackend) else None,
            correspondence=backend.last_diagnostics if isinstance(backend, (EfficientBackend, RomaBackend, MatchAnythingBackend, LightGlueBackend, AkazeBackend)) else None,
        )
    finally:
        if isinstance(backend, (EfficientBackend, RomaBackend, MatchAnythingBackend, LightGlueBackend, AkazeBackend)):
            backend.close()


def _source_pair_label(reference: ImageFrame, moving: ImageFrame) -> str:
    if reference.source_frame_index is not None and moving.source_frame_index is not None:
        return f'Para {reference.source_frame_index + 1} → {moving.source_frame_index + 1} (numery źródłowe)'
    return f'Para {reference.source.name} → {moving.source.name}'


def _check_shape(reference: ImageFrame, moving: ImageFrame) -> None:
    if (reference.data.ndim != 2 or moving.data.ndim != 2
            or min(reference.data.shape) < 1 or reference.data.shape != moving.data.shape):
        raise RegistrationError('Para: niezgodne lub puste wymiary obrazów.')


PairLayer = Literal['reference', 'moving', 'overlay']


@dataclass(frozen=True)
class PairRaster:
    rgba: NDArray[np.uint8]
    overlap_pixels: int
    overlap_fraction: float


class PairImages:
    """Render only the reference field, with frozen contrast from both originals."""

    def __init__(self, reference: ImageFrame, moving: ImageFrame) -> None:
        _check_shape(reference, moving)
        self.reference = reference
        self.moving = moving
        finite_values = [f.data[np.isfinite(f.data)] for f in (reference, moving)]
        nonempty = [values for values in finite_values if values.size]
        self.contrast = (min(float(a.min()) for a in nonempty),
                         max(float(a.max()) for a in nonempty)) if nonempty else (0.0, 0.0)

    def render(self, shift_xy: tuple[float, float] = (0.0, 0.0), *,
               gamma: float = 1.0, layer: PairLayer = 'overlay') -> PairRaster:
        if not 0.1 <= gamma <= 4.0:
            raise ValueError('Gamma musi mieścić się w zakresie 0,1–4.')
        if layer not in ('reference', 'moving', 'overlay'):
            raise ValueError('Nieznana warstwa podglądu pary.')
        shift = np.asarray(shift_xy, dtype=np.float64)
        if shift.shape != (2,) or not np.isfinite(shift).all():
            raise ValueError('Nieprawidłowe przesunięcie XY podglądu.')
        reference = self.reference.data
        moving = self.moving.data
        if np.any(shift):
            from scipy.ndimage import affine_transform

            x, y = shift
            moving = np.asarray(affine_transform(
                moving, matrix=np.eye(2), offset=(-y, -x), output_shape=reference.shape,
                order=1, mode='constant', cval=np.nan, prefilter=False,
            ), dtype=np.float64)
        overlap = np.isfinite(reference) & np.isfinite(moving)
        reference_gray = self._gray(reference, gamma)
        moving_gray = self._gray(moving, gamma)
        if layer == 'reference':
            gray, valid = reference_gray, np.isfinite(reference)
        elif layer == 'moving':
            gray, valid = moving_gray, np.isfinite(moving)
        else:
            gray = (reference_gray + moving_gray) / 2
            valid = overlap
        rgba = np.full((*reference.shape, 4), 255, dtype=np.uint8)
        rgba[valid, :3] = (gray[valid, None] * 255).astype(np.uint8)
        rgba[:, :, 3] = valid * 255
        rgba.setflags(write=False)
        count = int(np.count_nonzero(overlap))
        return PairRaster(rgba, count, count / reference.size)

    def _gray(self, data: NDArray[np.float64], gamma: float) -> NDArray[np.float64]:
        result = np.zeros(data.shape, dtype=np.float64)
        finite = np.isfinite(data)
        low, high = self.contrast
        if low == high:
            result[finite] = 0.5 ** (1 / gamma)
        else:
            scale = max(abs(low), abs(high))
            normalized = (data[finite] / scale - low / scale) / (high / scale - low / scale)
            result[finite] = np.clip(normalized, 0, 1) ** (1 / gamma)
        return result
