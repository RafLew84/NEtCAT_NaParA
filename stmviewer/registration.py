"""Adjacent registration and a complete expanded result, independent of presentation."""

from dataclasses import dataclass, field, replace
from pathlib import Path
import math
from typing import TYPE_CHECKING, Callable, Protocol
from uuid import uuid4

from nanotrack.core import RegistrationFrameResult

import numpy as np
from numpy.typing import NDArray

from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal
from stmviewer.efficient_matcher import (
    EFFICIENT_METHOD, EFFICIENT_LABEL, EfficientBackend, load_efficient_backend,
)
from stmviewer.local_consensus import LocalDiagnostics, LocalConsensusError
from stmviewer.local_registration import LOCAL_METHOD, LOCAL_LABEL, DeepLocalBackend, load_deep_local_backend
from stmviewer.frame import ImageFrame
from stmviewer.calibration import common_pixel_size
from stmviewer.manual_movie_types import MovieBaselineFrame, MovieCorrection, MovieSource
from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
from stmviewer.deep_ecc import (
    HYBRID_METHOD, HYBRID_LABEL, HybridDiagnostics, DeepEccBackend, load_deep_ecc_backend,
)


if TYPE_CHECKING:
    from stmviewer.graph_application_types import GraphApplication, MovieSnapshot


CPU_METHODS = {
    "phase_correlation": "Phase",
    "phase_no_normalization": "Korelacja bez normalizacji (v1)",
    "tile_correlation_ransac": "Tile+RANSAC",
    "ecc_translation": "ECC",
    "optical_flow_median": "Optical Flow",
}


DEEP_METHODS = ("deep_matcher_translation", HYBRID_METHOD, LOCAL_METHOD, EFFICIENT_METHOD)
REGISTRATION_METHODS = {**CPU_METHODS, "deep_matcher_translation": "Deep Matcher",
                        HYBRID_METHOD: HYBRID_LABEL, LOCAL_METHOD: LOCAL_LABEL,
                        EFFICIENT_METHOD: EFFICIENT_LABEL}


@dataclass(frozen=True)
class FrameOrigin:
    source: Path
    source_frame_index: int | None


@dataclass(frozen=True)
class AlignedFrame:
    original: ImageFrame
    image: ImageFrame
    valid_mask: NDArray[np.bool_]
    shift_xy: tuple[float, float]
    origin_xy: tuple[float, float]
    status: str
    quality_score: float | None
    inherited_uncertainty: bool

    @property
    def original_rect(self) -> tuple[float, float, int, int]:
        """Pixel-edge rectangle, independent of the interpolated sample mask."""
        height, width = self.original.data.shape
        return (*self.origin_xy, width, height)


@dataclass(frozen=True)
class RegistrationResult:
    frames: tuple[AlignedFrame, ...]
    reference: FrameOrigin
    canvas_shape: tuple[int, int]
    padding_ltrb: tuple[int, int, int, int]
    pixel_size_nm: tuple[float, float] | None
    method: str = 'Phase'
    device: str = 'CPU'
    settings_version: int = 1
    revision: str = field(default_factory=lambda: uuid4().hex)
    baseline: tuple[MovieBaselineFrame, ...] = ()
    corrections: tuple[MovieCorrection, ...] = ()
    corrections_editable: bool = True
    pair_diagnostics: tuple[HybridDiagnostics | None, ...] = ()
    local_diagnostics: tuple[LocalDiagnostics | None, ...] = ()
    graph_application: "GraphApplication | None" = None
    predecessor: "MovieSnapshot | None" = None
    correspondence_diagnostics: tuple[CorrespondenceDiagnostics | None, ...] = ()

    def without_frame(self, index: int) -> 'RegistrationResult | None':
        """Retain historical coordinates and the exact surviving samples."""
        if not 0 <= index < len(self.frames):
            raise IndexError(index)
        frames = self.frames[:index] + self.frames[index + 1:]
        # Retain lightweight history, including source pairs removed from the movie.
        diagnostics = (self.pair_diagnostics[:index] + self.pair_diagnostics[index + 1:]
                       if self.pair_diagnostics else ())
        local = (self.local_diagnostics[:index] + self.local_diagnostics[index + 1:]
                 if self.local_diagnostics else ())
        correspondence = (self.correspondence_diagnostics[:index] + self.correspondence_diagnostics[index + 1:]
                          if self.correspondence_diagnostics else ())
        return replace(self, frames=frames, corrections_editable=False,
                       correspondence_diagnostics=correspondence,
                       pair_diagnostics=diagnostics, local_diagnostics=local,
                       revision=uuid4().hex) if frames else None


class RegistrationError(ValueError):
    """An attempt cannot provide a complete usable result."""


class RegistrationCancelled(Exception):
    """The entire attempt was discarded at a safe cancellation point."""


class ShiftBackend(Protocol):
    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult: ...


def register_series(frames: tuple[ImageFrame, ...], *, method: str = "phase_correlation",
                    backend: ShiftBackend | None = None,
                    deep_options: DeepMatcherOptions | None = None,
                    progress: Callable[[int, int, str], None] | None = None,
                    cancelled: Callable[[], bool] | None = None) -> RegistrationResult:
    """Align adjacent originals with the selected method and fixed settings."""
    def checkpoint() -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    def report(done: int, description: str) -> None:
        if progress is not None:
            progress(done, len(frames) * 2, description)
        checkpoint()

    checkpoint()
    if method not in REGISTRATION_METHODS:
        raise RegistrationError(f"Nieznana metoda rejestracji: {method}")
    label = REGISTRATION_METHODS[method]
    if not frames:
        raise RegistrationError("Seria jest pusta.")
    for i, frame in enumerate(frames):
        checkpoint()
        prefix = (f"Para {max(i, 1)} → {max(i, 1) + 1} — Deep Matcher (wejście), klatka {i + 1}"
                  if method in (HYBRID_METHOD, LOCAL_METHOD) and len(frames) > 1 else f"Klatka {i + 1}")
        if frame.data.ndim != 2 or min(frame.data.shape) < 1 or frame.data.shape != frames[0].data.shape:
            raise RegistrationError(f"{prefix}: niezgodne lub puste wymiary obrazu.")
        if not np.isfinite(frame.data).all():
            raise RegistrationError(f"{prefix}: {label} wymaga skończonych próbek; wejście zawiera NaN/Inf.")
    device = 'CPU'
    completed_pairs = 0
    if method == EFFICIENT_METHOD:
        efficient = load_efficient_backend(
            deep_options or DeepMatcherOptions(),
            progress=lambda text: report(completed_pairs, text), cancelled=cancelled,
        )
        backend, device = efficient, efficient.device
    elif method == LOCAL_METHOD:
        local_backend = load_deep_local_backend(
            deep_options or DeepMatcherOptions(),
            progress=lambda text: report(completed_pairs, text), cancelled=cancelled,
        )
        backend, device = local_backend, local_backend.device
    elif method == HYBRID_METHOD:
        hybrid = load_deep_ecc_backend(
            deep_options or DeepMatcherOptions(),
            progress=lambda text: report(completed_pairs, text), cancelled=cancelled,
        )
        backend, device = hybrid, hybrid.device
    elif method == 'deep_matcher_translation':
        loaded = load_deep_backend(deep_options or DeepMatcherOptions(),
                                   progress=lambda text: report(0, text), cancelled=cancelled)
        backend, device = loaded.backend, loaded.device
    else:
        backend = backend if backend is not None else create_shift_backend(method)
    try:
        diagnostics: list[HybridDiagnostics | None] = [None]
        local_diagnostics: list[LocalDiagnostics | None] = [None]
        correspondence_diagnostics: list[CorrespondenceDiagnostics | None] = [None]
        shifts = [(0.0, 0.0)]
        statuses = ['ok']
        qualities: list[float | None] = [1.0]
        severity = {'ok': 0, 'low_confidence': 1, 'manual_review': 2, 'failed': 3}
        report(1, "Odniesienie: klatka 1")
        for i in range(1, len(frames)):
            checkpoint()
            try:
                pair = backend.estimate(frames[i - 1].data, frames[i].data, moving_frame_index=i)
                if (pair is None or pair.frame_index != i or pair.status not in severity
                        or pair.status == 'failed'):
                    raise ValueError("brak poprawnego wyniku klatki lub status failed")
                pair_shift = np.asarray(pair.shift_xy, dtype=np.float64)
                if pair_shift.shape != (2,) or not np.isfinite(pair_shift).all():
                    raise ValueError("nieprawidłowe przesunięcie XY")
                pair_status, pair_quality = estimate_confidence(method, pair)
            except CorrespondenceRefusal as error:
                checkpoint()
                raise RegistrationError(f"Para {i} → {i + 1} ({label}): {error}") from error
            except (RegistrationCancelled, RegistrationError, LocalConsensusError):
                checkpoint()
                raise
            except Exception as error:
                checkpoint()
                reason = str(error) or type(error).__name__
                if 'too little texture' in reason:
                    reason = f'za mało tekstury do rejestracji {label}'
                raise RegistrationError(f"Para {i} → {i + 1}: {reason}") from error
            diagnostics.append(backend.last_diagnostics if isinstance(backend, DeepEccBackend) else None)
            local_diagnostics.append(backend.last_diagnostics if isinstance(backend, DeepLocalBackend) else None)
            correspondence_diagnostics.append(backend.last_diagnostics if isinstance(backend, EfficientBackend) else None)
            completed_pairs = i
            shifts.append((shifts[-1][0] + float(pair.shift_xy[0]),
                           shifts[-1][1] + float(pair.shift_xy[1])))
            checkpoint()
            if not np.isfinite(shifts[-1]).all():
                raise RegistrationError(f"Para {i} → {i + 1}: nieprawidłowe przesunięcie skumulowane.")
            previous_quality = qualities[-1]
            qualities.append(None if previous_quality is None or pair_quality is None
                             else min(previous_quality, pair_quality))
            statuses.append(max(statuses[-1], pair_status, key=severity.__getitem__))
            report(i + 1, f"{label}: para {i} → {i + 1}")
    finally:
        if isinstance(backend, EfficientBackend):
            backend.close()
    rendered = render_registration(
        frames, tuple(shifts), tuple(statuses), tuple(qualities),
        tuple(i > 0 and statuses[i - 1] != 'ok' for i in range(len(frames))),
        reference=FrameOrigin(frames[0].source, frames[0].source_frame_index),
        method=label, device=device, cancelled=cancelled,
        progress=lambda done, total, text: report(len(frames) + done, text),
    )
    return replace(rendered, pair_diagnostics=tuple(diagnostics) if method == HYBRID_METHOD else (),
                   local_diagnostics=tuple(local_diagnostics) if method == LOCAL_METHOD else (),
                   correspondence_diagnostics=(tuple(correspondence_diagnostics)
                                               if method == EFFICIENT_METHOD else ()))


def render_registration(
        frames: tuple[ImageFrame, ...], shifts: tuple[tuple[float, float], ...],
        statuses: tuple[str, ...], qualities: tuple[float | None, ...],
        inherited: tuple[bool, ...], *, reference: FrameOrigin, method: str, device: str,
        progress: Callable[[int, int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        padding_ltrb: tuple[int, int, int, int] | None = None) -> RegistrationResult:
    """Build one aligned image per original with a single linear interpolation."""
    from scipy.ndimage import affine_transform

    def checkpoint() -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    checkpoint()
    if not frames or not (len(frames) == len(shifts) == len(statuses) == len(qualities) == len(inherited)):
        raise RegistrationError('Aligned: wymagany kompletny zestaw klatek i przesunięć.')
    for frame, shift in zip(frames, shifts):
        checkpoint()
        if (frame.data.ndim != 2 or min(frame.data.shape) < 1
                or frame.data.shape != frames[0].data.shape):
            raise RegistrationError('Aligned: niezgodne lub puste wymiary obrazu.')
        if len(shift) != 2 or not np.isfinite(shift).all():
            raise RegistrationError('Aligned: nieprawidłowe przesunięcie XY.')
    left = math.ceil(max(0, -min(x for x, y in shifts)))
    top = math.ceil(max(0, -min(y for x, y in shifts)))
    right = math.ceil(max(0, max(x for x, y in shifts)))
    bottom = math.ceil(max(0, max(y for x, y in shifts)))
    if padding_ltrb is not None:
        minimum = (left, top, right, bottom)
        if (len(padding_ltrb) != 4
                or any(type(value) is not int or value < required
                       for value, required in zip(padding_ltrb, minimum))):
            raise RegistrationError('Aligned: zachowany obszar nie obejmuje pełnych oryginałów.')
        left, top, right, bottom = padding_ltrb
    height, width = frames[0].data.shape
    shape = (height + top + bottom, width + left + right)
    pixel_size = common_pixel_size(frames)
    aligned = []
    for i, (frame, shift, status) in enumerate(zip(frames, shifts, statuses)):
        checkpoint()
        try:
            x, y = left + shift[0], top + shift[1]
            values = np.asarray(affine_transform(
                frame.data, matrix=np.eye(2), offset=(-y, -x), output_shape=shape,
                order=1, mode='constant', cval=np.nan, prefilter=False,
            ), dtype=np.float64)
            mask = np.isfinite(values)
            values.setflags(write=False)
            mask.setflags(write=False)
            image = replace(frame, data=values,
                            size_x_nm=shape[1] * pixel_size[0] if pixel_size else None,
                            size_y_nm=shape[0] * pixel_size[1] if pixel_size else None,
                            offset_x_nm=None, offset_y_nm=None, alignment=None)
            aligned.append(AlignedFrame(frame, image, mask, shift, (x, y), status, qualities[i],
                                        inherited[i]))
        except Exception as error:
            checkpoint()
            raise RegistrationError(f"Aligned: klatka {i + 1}: {str(error) or type(error).__name__}") from error
        if progress is not None:
            progress(i + 1, len(frames), f"Aligned: klatka {i + 1}/{len(frames)}")
        checkpoint()
    baseline = tuple(MovieBaselineFrame(
        MovieSource(str(frame.source), frame.source_frame_index), shift, status, quality, uncertainty,
    ) for frame, shift, status, quality, uncertainty in zip(frames, shifts, statuses, qualities, inherited))
    return RegistrationResult(tuple(aligned), reference, shape, (left, top, right, bottom),
                              pixel_size, method=method, device=device, baseline=baseline)


def registration_unavailable_reason(method: str) -> str | None:
    """Check local CPU dependencies; never download or substitute a backend."""
    try:
        from scipy.ndimage import affine_transform  # noqa: F401 — dependency availability probe
        create_shift_backend(method)
    except Exception as error:
        return f"{CPU_METHODS.get(method, method)} niedostępna: {str(error) or type(error).__name__}"
    return None


def create_shift_backend(method: str) -> ShiftBackend:
    """Use NanoTrack defaults or the explicit unnormalized variant; never substitute."""
    if method not in CPU_METHODS:
        raise RegistrationError(f"Nieznana metoda rejestracji: {method}")
    if method == "phase_no_normalization":
        from nanotrack.registration.phase_correlation import (
            PhaseCorrelationShiftBackend, PhaseCorrelationShiftConfig,
        )
        # Fixed v1 settings: preserve the version in pair, series and MPP labels.
        unnormalized: ShiftBackend = PhaseCorrelationShiftBackend(PhaseCorrelationShiftConfig(
            upsample_factor=20, normalization=None, min_texture_std=1e-8,
            peak_exclusion_radius=3, low_confidence_peak_ratio=3.0,
        ))
        return unnormalized
    if method == "ecc_translation":
        # Construction alone does not import OpenCV in the shared ECC backend.
        from cv2 import findTransformECC
        if not callable(findTransformECC):
            raise RegistrationError("OpenCV cv2: brak funkcji findTransformECC")
    from nanotrack.core import RegistrationSettings
    from nanotrack.registration import build_registration_backend_from_settings

    backend: ShiftBackend = build_registration_backend_from_settings(RegistrationSettings(
        backend=method, reference_strategy="adjacent", registration_view="raw",
    ))
    return backend


def estimate_confidence(method: str, result: RegistrationFrameResult) -> tuple[str, float | None]:
    """Do not reuse the phase-peak score for an unnormalized estimate."""
    if method in ('phase_no_normalization', HYBRID_METHOD, LOCAL_METHOD, EFFICIENT_METHOD):
        return 'manual_review', None
    quality = float(result.quality_score)
    if not np.isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError('nieprawidłowy wskaźnik jakości')
    return str(result.status), quality
