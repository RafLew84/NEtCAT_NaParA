"""Validate an entire sidecar before applying any per-frame MPP metadata."""

from collections.abc import Callable
from dataclasses import replace
import json
import math
from pathlib import Path
import re
from typing import Mapping

from stmviewer.frame import FrameProvenance, ImageFrame

_MAX_BYTES = 64 * 1024 * 1024
_FIELDS = {'provenance', 'measurement_time_s', 'measurement_time_raw', 'channel', 'signal_unit',
           'size_x_nm', 'size_y_nm', 'offset_x_nm', 'offset_y_nm', 'bias_v', 'setpoint_a',
           'scan_angle_deg', 'calibration_note', 'raw_header'}


def _object(value: object, keys: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError('Oczekiwano obiektu JSON.')
    result: dict[str, object] = dict(value)
    if keys is not None and result.keys() != keys:
        raise ValueError(f'Pola JSON: brak {sorted(keys - result.keys())}; '
                         f'nieobsługiwane {sorted(result.keys() - keys)}.')
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Powtórzone pole JSON: {key}.')
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    raise ValueError(f'Niedozwolona stała JSON: {value}.')


def _number(record: dict[str, object], key: str, *, positive: bool = False) -> float | None:
    value = record[key]
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError(f'{key}: wymagana liczba albo null.')
    assert isinstance(value, (int, float))
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f'{key}: wymagana skończona {"dodatnia " if positive else ""}liczba.')
    return number


def _text(record: dict[str, object], key: str) -> str | None:
    value = record[key]
    if value is not None and not isinstance(value, str):
        raise ValueError(f'{key}: wymagany tekst albo null.')
    return value


def _header(value: object) -> Mapping[str, str | Mapping[str, str]]:
    result: dict[str, str | Mapping[str, str]] = {}
    for key, entry in _object(value).items():
        if isinstance(entry, str):
            result[key] = entry
        else:
            section: dict[str, str] = {}
            for name, item in _object(entry).items():
                if not isinstance(item, str):
                    raise ValueError('raw_header: wartości nagłówka muszą być tekstem.')
                section[name] = item
            result[key] = section
    return result


def _frame(frame: ImageFrame, value: object) -> ImageFrame:
    record = _object(value, _FIELDS)
    provenance = _object(record['provenance'], {'source', 'source_frame_index'})
    source = _text(provenance, 'source')
    index = provenance['source_frame_index']
    if source is None or not source.strip() or '\x00' in source:
        raise ValueError('provenance.source: wymagany niepusty opis źródła.')
    if index is not None and (type(index) is not int or index < 0):
        raise ValueError('source_frame_index: wymagany indeks od zera albo null.')
    assert index is None or isinstance(index, int)
    return replace(
        frame, provenance=FrameProvenance(source, index),
        measurement_time_s=_number(record, 'measurement_time_s'),
        measurement_time_raw=_text(record, 'measurement_time_raw'),
        channel=_text(record, 'channel'), signal_unit=_text(record, 'signal_unit'),
        size_x_nm=_number(record, 'size_x_nm', positive=True),
        size_y_nm=_number(record, 'size_y_nm', positive=True),
        offset_x_nm=_number(record, 'offset_x_nm'), offset_y_nm=_number(record, 'offset_y_nm'),
        bias_v=_number(record, 'bias_v'), setpoint_a=_number(record, 'setpoint_a'),
        scan_angle_deg=_number(record, 'scan_angle_deg'),
        calibration_note=_text(record, 'calibration_note'), raw_header=_header(record['raw_header']),
    )


def mpp_sidecar_path(path: Path) -> Path:
    """The V1 companion lives beside the movie, retaining its complete filename."""
    return path.with_name(path.name + '.stmviewer.json')


def apply_mpp_metadata(path: Path, frames: tuple[ImageFrame, ...], *, sha256: str,
                       check_cancelled: Callable[[], None]) -> tuple[ImageFrame, ...]:
    """Return the whole validated addon, or untouched header metadata with a reason."""
    sidecar = mpp_sidecar_path(path)
    check_cancelled()
    result = frames
    try:
        chunks = []
        size = 0
        with sidecar.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                check_cancelled()
                size += len(chunk)
                if size > _MAX_BYTES:
                    raise ValueError('Dodatek przekracza 64 MiB.')
                chunks.append(chunk)
        check_cancelled()
        try:
            decoded = json.loads(b''.join(chunks).decode('utf-8'), object_pairs_hook=_unique_object,
                                 parse_constant=_invalid_constant)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f'Nieprawidłowy JSON UTF-8: {error}') from error
        check_cancelled()
        metadata = _object(decoded, {'format', 'version', 'image_kind', 'movie', 'frames'})
        if metadata['format'] != 'stmviewer-mpp':
            raise ValueError('Nieobsługiwany format dodatku.')
        if type(metadata['version']) is not int or metadata['version'] != 1:
            raise ValueError(f'Nieobsługiwana wersja dodatku: {metadata["version"]}.')
        if metadata['image_kind'] != 'original':
            raise ValueError('Nieobsługiwany rodzaj obrazu; wersja 1 obsługuje original.')
        movie = _object(metadata['movie'], {'sha256', 'frame_count', 'shape_yx'})
        digest = movie['sha256']
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or digest != sha256:
            raise ValueError('Niezgodna zawartość MPP (SHA-256).')
        if type(movie['frame_count']) is not int or movie['frame_count'] != len(frames):
            raise ValueError('Niezgodna liczba klatek MPP.')
        shape = movie['shape_yx']
        if (not isinstance(shape, list) or any(type(n) is not int for n in shape)
                or shape != list(frames[0].data.shape)):
            raise ValueError('Niezgodne wymiary klatek MPP (shape_yx).')
        records = metadata['frames']
        if not isinstance(records, list) or len(records) != len(frames):
            raise ValueError('Niezgodna liczba rekordów klatek w dodatku.')
        restored = []
        for index, (frame, record) in enumerate(zip(frames, records, strict=True), 1):
            check_cancelled()
            try:
                restored.append(_frame(frame, record))
            except (ValueError, OverflowError) as error:
                raise ValueError(f'Klatka {index} dodatku: {error}') from error
        result = tuple(restored)
        note = f'Metadane towarzyszące: wczytano {sidecar.name} (original).'
    except FileNotFoundError:
        note = 'Metadane towarzyszące: brak; dane z nagłówka MPP.'
    except (OSError, ValueError, RecursionError, OverflowError) as error:
        note = f'Metadane towarzyszące: pominięto {sidecar.name}. {error}'
    annotated = []
    for frame in result:
        check_cancelled()
        annotated.append(replace(frame, metadata_note=note))
    check_cancelled()
    return tuple(annotated)


def encode_mpp_metadata(frames: tuple[ImageFrame, ...], sha256: str, *,
                        check_cancelled: Callable[[], None]) -> bytes:
    """Serialize original-frame metadata using the same validated V1 contract."""
    records = []
    for frame in frames:
        check_cancelled()
        provenance = frame.provenance or FrameProvenance(str(frame.source), frame.source_frame_index)
        record = {key: getattr(frame, key) for key in _FIELDS if key != 'provenance'}
        record['raw_header'] = {key: value if isinstance(value, str) else dict(value)
                                for key, value in frame.raw_header.items()}
        record['provenance'] = {'source': provenance.source,
                                'source_frame_index': provenance.source_frame_index}
        _frame(frame, record)
        records.append(record)
    metadata = dict(format='stmviewer-mpp', version=1, image_kind='original',
                    movie=dict(sha256=sha256, frame_count=len(frames), shape_yx=list(frames[0].data.shape)),
                    frames=records)
    payload = (json.dumps(metadata, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    if len(payload) > _MAX_BYTES:
        raise ValueError('Dodatek przekracza 64 MiB.')
    check_cancelled()
    return payload
