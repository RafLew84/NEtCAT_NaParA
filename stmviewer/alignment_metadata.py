"""Portable alignment geometry, separate from the validity of saved samples."""
from collections.abc import Callable
from dataclasses import asdict, replace
import math

import numpy as np

from stmviewer.graph_methods import graph_method_label
from stmviewer.correspondence_metadata import decode_correspondence, encode_correspondence, validate_correspondence_shape
from stmviewer.frame import AlignmentHistory, FrameProvenance, ImageFrame
from stmviewer.metadata_values import json_object, optional_number, optional_text, source_provenance
from stmviewer.registration import RegistrationResult
from stmviewer.manual_movie_types import MovieHistory, MovieSource
from stmviewer.manual_movie_metadata import manual_frame_state
from stmviewer.graph_movie_provenance import movie_history

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


def _decode(value: object, depth: int = 0, *,
            manual_results: tuple[MovieHistory, ...] = ()) -> AlignmentHistory:
    if depth >= _MAX_DEPTH:
        raise ValueError('Historia rejestracji przekracza 32 etapy.')
    has_manual = isinstance(value, dict) and 'manual_result' in value
    fields = json_object(value)
    extra = {'manual_result', 'manual_frame_index'} if has_manual else set()
    if 'correspondence' in fields:
        extra.add('correspondence')
    record = json_object(fields, _KEYS | extra)
    manual = None
    manual_index: int | None = None
    if has_manual:
        result_index, frame_index = record['manual_result'], record['manual_frame_index']
        if type(result_index) is not int or not 0 <= result_index < len(manual_results):
            raise ValueError('Historia: nieznany wynik ręcznej korekty filmu.')
        manual = manual_results[result_index]
        if type(frame_index) is not int or not 0 <= frame_index < len(manual.baseline):
            raise ValueError('Historia: nieznana klatka bazy ręcznej korekty.')
        manual_index = frame_index
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
    if manual is not None:
        assert manual_index is not None
        expected = manual_frame_state(manual, manual_index)
        if not all(_same(a, b) for a, b in zip(shift, expected.shift_xy)):
            raise ValueError('Historia: skumulowane XY nie zgadza się z ręcznymi korektami.')
        if (status, quality, inherited) != (expected.status, expected.quality_score, expected.inherited_uncertainty):
            raise ValueError('Historia: pewność nie zgadza się z wpływem ręcznych korekt.')
        graph = manual.graph_provenance
        if graph is not None and (method != f'{graph_method_label(graph.config.method)} — graf {graph.solver}'
                                  or device != graph.config.device):
            raise ValueError('Historia: opis metody nie odpowiada pochodzeniu grafu.')
        source = manual.baseline[0].source
        if (reference.source, reference.source_frame_index) != (source.source, source.source_frame_index):
            raise ValueError('Historia: odniesienie nie zgadza się z bazą korekt filmu.')
    pixel_size = None if record['pixel_size_nm'] is None else _xy(record['pixel_size_nm'], positive=True)
    original_size = _numbers(record['original_size_nm'], nullable=True, positive=True)
    if pixel_size is not None and any(size is None or not _same(size, pixels * scale)
                                      for size, pixels, scale in zip(original_size, (ow, oh), pixel_size)):
        raise ValueError('Historia: skala źródła nie zgadza się ze skalą obszaru aligned.')
    previous = None if record['previous'] is None else _decode(record['previous'], depth + 1, manual_results=manual_results)
    original_offset = _numbers(record['original_offset_nm'], nullable=True)
    if previous is not None:
        _validate_image_metadata(previous, (oh, ow), original_size, original_offset)
    correspondence = decode_correspondence(record.get('correspondence'))
    validate_correspondence_shape(correspondence, (oh, ow), (oh, ow))
    if correspondence is not None and (method != 'EfficientLoFTR' or correspondence.final_shift_xy is None):
        raise ValueError('Historia: metoda lub wynik nie odpowiada diagnostyce korespondencji.')
    return AlignmentHistory((height, width), (left, top, right, bottom), pixel_size,
                            reference, method, device, (oh, ow), original_size,
                            original_offset, shift, origin,
                            status, quality, inherited, previous, manual, manual_index,
                            correspondence)


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


def decode_alignment(value: object, frame: ImageFrame, *,
                     manual_results: tuple[MovieHistory, ...] = ()) -> AlignmentHistory:
    """Validate all geometry before accepting it as history of the opened pixels."""
    history = _decode(value, manual_results=manual_results)
    _validate_image_metadata(history, frame.data.shape, (frame.size_x_nm, frame.size_y_nm),
                             (frame.offset_x_nm, frame.offset_y_nm))
    return history


def encode_alignment(history: AlignmentHistory | None, depth: int = 0, *,
                     manual_ids: dict[str, int] | None = None) -> dict[str, object] | None:
    if history is None:
        return None
    if depth >= _MAX_DEPTH:
        raise ValueError('Historia rejestracji przekracza 32 etapy.')
    # Exclude the recursive chain before asdict; encode it with a bounded depth.
    record = asdict(replace(history, previous=None, manual_movie=None, manual_frame_index=None))
    record.pop('manual_movie')
    record.pop('manual_frame_index')
    if history.correspondence is None:
        record.pop('correspondence')
    else:
        record['correspondence'] = encode_correspondence(history.correspondence)
    if history.manual_movie is not None:
        if manual_ids is None or history.manual_movie.revision not in manual_ids:
            raise ValueError('Historia: brak wspólnego zapisu ręcznej korekty filmu.')
        record['manual_result'] = manual_ids[history.manual_movie.revision]
        record['manual_frame_index'] = history.manual_frame_index
    elif history.manual_frame_index is not None:
        raise ValueError('Historia: indeks ręcznej klatki bez wyniku.')
    record.update(validity='isfinite(samples)', original_rect=list(history.original_rect),
                  previous=encode_alignment(history.previous, depth + 1, manual_ids=manual_ids))
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
                    history.reference, history.method, history.device,
                    history.manual_movie.revision if history.manual_movie else None)
        if shared is not None and geometry != shared:
            raise ValueError('Aligned: klatki opisują różne wyniki rejestracji.')
        shared = geometry


def aligned_export_frames(result: RegistrationResult,
                          check_cancelled: Callable[[], None]) -> tuple[ImageFrame, ...]:
    """Attach historical geometry to existing samples without materializing again."""
    frames = []
    manual = movie_history(result) if result.corrections or result.graph_application is not None else None
    source_indices = {frame.source: i for i, frame in enumerate(result.baseline)}
    if result.correspondence_diagnostics and len(result.correspondence_diagnostics) != len(result.frames):
        raise ValueError('Aligned: diagnostyka korespondencji ma inną liczbę klatek.')
    for frame_index, aligned in enumerate(result.frames):
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
        manual_index = None
        if manual is not None:
            source = MovieSource(str(original.source), original.source_frame_index)
            if source not in source_indices:
                raise ValueError('Aligned: brak źródła w bazie ręcznych korekt filmu.')
            manual_index = source_indices[source]
        history = AlignmentHistory(
            result.canvas_shape, result.padding_ltrb, result.pixel_size_nm,
            FrameProvenance(str(result.reference.source), result.reference.source_frame_index),
            result.method, result.device, (original.data.shape[0], original.data.shape[1]),
            (original.size_x_nm, original.size_y_nm), (original.offset_x_nm, original.offset_y_nm),
            aligned.shift_xy, aligned.origin_xy, aligned.status, aligned.quality_score,
            aligned.inherited_uncertainty, original.alignment, manual, manual_index,
            result.correspondence_diagnostics[frame_index] if result.correspondence_diagnostics else None)
        frame = replace(image, alignment=history)
        histories = collect_manual_histories((frame,), check_cancelled)
        ids = {item.revision: i for i, item in enumerate(histories)}
        decode_alignment(encode_alignment(history, manual_ids=ids), frame, manual_results=histories)
        frames.append(frame)
    return tuple(frames)


def collect_manual_histories(frames: tuple[ImageFrame, ...],
                             check_cancelled: Callable[[], None]) -> tuple[MovieHistory, ...]:
    """Share metadata across frames and prior stages instead of repeating it N times."""
    results: dict[str, MovieHistory] = {}
    for frame in frames:
        history = frame.alignment
        depth = 0
        while history is not None:
            check_cancelled()
            if depth >= _MAX_DEPTH:
                raise ValueError('Historia rejestracji przekracza 32 etapy.')
            manual = history.manual_movie
            if manual is not None:
                previous = results.get(manual.revision)
                if previous is not None and previous is not manual and previous != manual:
                    raise ValueError('Historia: sprzeczne dane tej samej wersji korekty filmu.')
                results[manual.revision] = manual
            history = history.previous
            depth += 1
    return tuple(results.values())
