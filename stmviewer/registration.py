"""Adjacent registration and a complete expanded result, independent of presentation."""

from dataclasses import dataclass, replace
from pathlib import Path
import math
from typing import Callable, Protocol

from nanotrack.core import RegistrationFrameResult

import numpy as np
from numpy.typing import NDArray

from stmviewer.frame import ImageFrame
from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend


CPU_METHODS = {
    "phase_correlation": "Phase",
    "tile_correlation_ransac": "Tile+RANSAC",
    "ecc_translation": "ECC",
    "optical_flow_median": "Optical Flow",
}


REGISTRATION_METHODS = {**CPU_METHODS, "deep_matcher_translation": "Deep Matcher"}


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
    quality_score: float
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

    def without_frame(self, index: int) -> 'RegistrationResult | None':
        """Retain historical coordinates and the exact surviving samples."""
        if not 0 <= index < len(self.frames):
            raise IndexError(index)
        frames = self.frames[:index] + self.frames[index + 1:]
        return replace(self, frames=frames) if frames else None


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
    """Align adjacent originals with the selected NanoTrack method and its defaults."""
    from scipy.ndimage import affine_transform

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
        if frame.data.ndim != 2 or min(frame.data.shape) < 1 or frame.data.shape != frames[0].data.shape:
            raise RegistrationError(f"Klatka {i + 1}: niezgodne lub puste wymiary obrazu.")
        if not np.isfinite(frame.data).all():
            raise RegistrationError(f"Klatka {i + 1}: {label} wymaga skończonych próbek; wejście zawiera NaN/Inf.")
    device = 'CPU'
    if method == 'deep_matcher_translation':
        loaded = load_deep_backend(deep_options or DeepMatcherOptions(),
                                   progress=lambda text: report(0, text), cancelled=cancelled)
        backend, device = loaded.backend, loaded.device
    else:
        backend = backend if backend is not None else create_shift_backend(method)
    shifts = [(0.0, 0.0)]
    statuses = ['ok']
    qualities = [1.0]
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
        except Exception as error:
            checkpoint()
            reason = str(error) or type(error).__name__
            if 'too little texture' in reason:
                reason = f'za mało tekstury do rejestracji {label}'
            raise RegistrationError(f"Para {i} → {i + 1}: {reason}") from error
        shifts.append((shifts[-1][0] + float(pair.shift_xy[0]),
                       shifts[-1][1] + float(pair.shift_xy[1])))
        checkpoint()
        if not np.isfinite(shifts[-1]).all():
            raise RegistrationError(f"Para {i} → {i + 1}: nieprawidłowe przesunięcie skumulowane.")
        qualities.append(min(qualities[-1], pair.quality_score))
        statuses.append(max(statuses[-1], pair.status, key=severity.__getitem__))
        report(i + 1, f"{label}: para {i} → {i + 1}")
    left = math.ceil(max(0, -min(x for x, y in shifts)))
    top = math.ceil(max(0, -min(y for x, y in shifts)))
    right = math.ceil(max(0, max(x for x, y in shifts)))
    bottom = math.ceil(max(0, max(y for x, y in shifts)))
    height, width = frames[0].data.shape
    shape = (height + top + bottom, width + left + right)
    pixel_size = _common_pixel_size(frames)
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
                                        i > 0 and statuses[i - 1] != "ok"))
        except Exception as error:
            checkpoint()
            raise RegistrationError(f"Aligned: klatka {i + 1}: {str(error) or type(error).__name__}") from error
        report(len(frames) + i + 1, f"Aligned: klatka {i + 1}/{len(frames)}")
    return RegistrationResult(tuple(aligned), FrameOrigin(frames[0].source, frames[0].source_frame_index),
                              shape, (left, top, right, bottom), pixel_size, method=label, device=device)


def _common_pixel_size(frames: tuple[ImageFrame, ...]) -> tuple[float, float] | None:
    common = None
    for frame in frames:
        x, y = frame.size_x_nm, frame.size_y_nm
        if x is None or y is None or not (math.isfinite(x) and math.isfinite(y) and x > 0 and y > 0):
            return None
        size = (x / frame.data.shape[1], y / frame.data.shape[0])
        if common is not None and not all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(size, common)):
            return None
        if common is None:
            common = size
    return common


def registration_unavailable_reason(method: str) -> str | None:
    """Check local CPU dependencies; never download or substitute a backend."""
    try:
        from scipy.ndimage import affine_transform
        create_shift_backend(method)
    except Exception as error:
        return f"{CPU_METHODS.get(method, method)} niedostępna: {str(error) or type(error).__name__}"
    return None


def create_shift_backend(method: str) -> ShiftBackend:
    """Use the same settings factory as NanoTrack; never pick a substitute."""
    if method not in CPU_METHODS:
        raise RegistrationError(f"Nieznana metoda rejestracji: {method}")
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
