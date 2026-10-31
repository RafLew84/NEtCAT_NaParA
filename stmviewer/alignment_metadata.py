"""Portable alignment geometry, separate from the validity of saved samples."""
from collections.abc import Callable
from dataclasses import asdict, replace
import math

import numpy as np

from stmviewer.frame import AlignmentHistory, FrameProvenance, ImageFrame
from stmviewer.metadata_values import json_object, optional_number, optional_text, source_provenance
from stmviewer.registration import RegistrationResult

_KEYS = {'canvas_shape', 'padding_ltrb', 'pixel_size_nm', 'reference', 'method', 'device',
         'original_shape', 'original_size_nm', 'original_offset_nm', 'shift_xy', 'origin_xy',
         'status', 'quality_score', 'inherited_uncertainty', 'previous', 'validity', 'original_rect'}
_MAX_DEPTH = 32


def _vector(value: object, count: int) -> list[object]:
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f'Geometria: oczekiwano wektora o długości {count}.')
    return list(value)


def _integers(value: object, count: int, minimum: int) -> list[int]:
    result = []
    for item in _vector(value, count):
        if type(item) is not int or item < minimum:
            raise ValueError('Geometria: nieprawidłowy wymiar lub padding.')
        result.append(item)
    return result


def _numbers(value: object, *, nullable: bool = False,
             positive: bool = False) -> tuple[float | None, float | None]:
    result = []
    for item in _vector(value, 2):
        number = optional_number({'coordinate': item}, 'coordinate', positive=positive)
        if number is None and not nullable:
            raise ValueError('Geometria: współrzędne nie mogą być null.')
        result.append(number)
    return result[0], result[1]


def _xy(value: object, *, positive: bool = False) -> tuple[float, float]:
    x, y = _numbers(value, positive=positive)
    assert x is not None and y is not None
    return x, y


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def _decode(value: object, depth: int = 0) -> AlignmentHistory:
    if depth >= _MAX_DEPTH:
        raise ValueError('Historia rejestracji przekracza 32 etapy.')
    record = json_object(value, _KEYS)
    if record['validity'] != 'isfinite(samples)':
        raise ValueError('Nieobsługiwana reguła ważności próbek.')
    height, width = _integers(record['canvas_shape'], 2, 1)
    oh, ow = _integers(record['original_shape'], 2, 1)
    left, top, right, bottom = _integers(record['padding_ltrb'], 4, 0)
    if (height, width) != (oh + top + bottom, ow + left + right):
        raise ValueError('Geometria: obszar nie zgadza się z wymiarem źródła i paddingiem.')
    shift = _xy(record['shift_xy'])
    origin = _xy(record['origin_xy'])
    if not all(_same(a, b) for a, b in zip(origin, (left + shift[0], top + shift[1]))):
        raise ValueError('Geometria: origin_xy nie zgadza się z przesunięciem i paddingiem.')
    if (origin[0] < -1e-9 or origin[1] < -1e-9
            or origin[0] + ow > width + 1e-9 or origin[1] + oh > height + 1e-9):
        raise ValueError('Geometria: prostokąt źródła wykracza poza obszar aligned.')
    rect = _vector(record['original_rect'], 4)
    if any(type(v) not in (float, int) for v in rect) or rect != [*origin, ow, oh]:
        raise ValueError('Geometria: niespójny prostokąt źródła.')
    reference = source_provenance(record['reference'])
    method, device = optional_text(record, 'method'), optional_text(record, 'device')
    if not method or not method.strip() or not device or not device.strip():
        raise ValueError('Historia: wymagana metoda i urządzenie.')
    status = optional_text(record, 'status')
    if status not in ('ok', 'low_confidence', 'manual_review'):
        raise ValueError('Historia: nieprawidłowy status dopasowania.')
    assert status is not None
    quality = optional_number(record, 'quality_score')
    inherited = record['inherited_uncertainty']
    if (quality is None and status != 'manual_review') or type(inherited) is not bool:
        raise ValueError('Historia: nieprawidłowa pewność dopasowania.')
    pixel_size = None if record['pixel_size_nm'] is None else _xy(record['pixel_size_nm'], positive=True)
    original_size = _numbers(record['original_size_nm'], nullable=True, positive=True)
    if pixel_size is not None and any(size is None or not _same(size, pixels * scale)
                                      for size, pixels, scale in zip(original_size, (ow, oh), pixel_size)):
        raise ValueError('Historia: skala źródła nie zgadza się ze skalą obszaru aligned.')
    previous = None if record['previous'] is None else _decode(record['previous'], depth + 1)
    original_offset = _numbers(record['original_offset_nm'], nullable=True)
    if previous is not None:
        _validate_image_metadata(previous, (oh, ow), original_size, original_offset)
    return AlignmentHistory((height, width), (left, top, right, bottom), pixel_size,
                            reference, method, device, (oh, ow), original_size,
                            original_offset, shift, origin,
                            status, quality, inherited, previous)


def _validate_image_metadata(history: AlignmentHistory, shape: tuple[int, ...],
                             size_nm: tuple[float | None, float | None],
                             offset_nm: tuple[float | None, float | None]) -> None:
    if history.canvas_shape != shape:
        raise ValueError('Historia: obszar aligned nie odpowiada wymiarom obrazu.')
    expected = (None, None) if history.pixel_size_nm is None else (
        history.canvas_shape[1] * history.pixel_size_nm[0],
        history.canvas_shape[0] * history.pixel_size_nm[1])
    for actual, size in zip(size_nm, expected):
        if (actual is None) != (size is None) or (actual is not None and size is not None and not _same(actual, size)):
            raise ValueError('Historia: niespójna skala zapisanego obrazu.')
    if offset_nm != (None, None):
        raise ValueError('Historia: offset źródła musi być oddzielony od obszaru aligned.')


def decode_alignment(value: object, frame: ImageFrame) -> AlignmentHistory:
    """Validate all geometry before accepting it as history of the opened pixels."""
    history = _decode(value)
    _validate_image_metadata(history, frame.data.shape, (frame.size_x_nm, frame.size_y_nm),
                             (frame.offset_x_nm, frame.offset_y_nm))
    return history


def encode_alignment(history: AlignmentHistory | None, depth: int = 0) -> dict[str, object] | None:
    if history is None:
        return None
    if depth >= _MAX_DEPTH:
        raise ValueError('Historia rejestracji przekracza 32 etapy.')
    # Exclude the recursive chain before asdict; encode it with a bounded depth.
    record = asdict(replace(history, previous=None))
    record.update(validity='isfinite(samples)', original_rect=list(history.original_rect),
                  previous=encode_alignment(history.previous, depth + 1))
    return record


def validate_alignment_series(frames: tuple[ImageFrame, ...], *, aligned: bool) -> None:
    """Aligned exports must describe one complete, consistent result."""
    if not aligned:
        return
    shared = None
    for frame in frames:
        history = frame.alignment
        if history is None:
            raise ValueError('Aligned wymaga kompletnej geometrii każdej klatki.')
        geometry = (history.canvas_shape, history.padding_ltrb, history.pixel_size_nm,
                    history.reference, history.method, history.device)
        if shared is not None and geometry != shared:
            raise ValueError('Aligned: klatki opisują różne wyniki rejestracji.')
        shared = geometry


def aligned_export_frames(result: RegistrationResult,
                          check_cancelled: Callable[[], None]) -> tuple[ImageFrame, ...]:
    """Attach historical geometry to existing samples without materializing again."""
    frames = []
    for aligned in result.frames:
        check_cancelled()
        image, original = aligned.image, aligned.original
        if aligned.valid_mask.shape != image.data.shape or image.data.shape != result.canvas_shape:
            raise ValueError('Aligned: niespójny rozmiar obrazu lub maski.')
        block_rows = max(1, (4 * 1024 * 1024) // (image.data.shape[1] * 8))
        for row in range(0, image.data.shape[0], block_rows):
            check_cancelled()
            if not np.array_equal(aligned.valid_mask[row:row + block_rows],
                                  np.isfinite(image.data[row:row + block_rows])):
                raise ValueError('Aligned: maska nie odpowiada skończonym próbkom.')
        history = AlignmentHistory(
            result.canvas_shape, result.padding_ltrb, result.pixel_size_nm,
            FrameProvenance(str(result.reference.source), result.reference.source_frame_index),
            result.method, result.device, (original.data.shape[0], original.data.shape[1]),
            (original.size_x_nm, original.size_y_nm), (original.offset_x_nm, original.offset_y_nm),
            aligned.shift_xy, aligned.origin_xy, aligned.status, aligned.quality_score,
            aligned.inherited_uncertainty, original.alignment)
        frame = replace(image, alignment=history)
        decode_alignment(encode_alignment(history), frame)
        frames.append(frame)
    return tuple(frames)
