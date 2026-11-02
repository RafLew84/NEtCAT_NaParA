"""Validate an entire sidecar before applying any per-frame MPP metadata."""

from collections.abc import Callable
from dataclasses import replace
import json
from pathlib import Path
import re

from stmviewer.mpp_missing import MAX_RUNS, encode_missing_samples, restore_missing_samples
from stmviewer.frame import FrameProvenance, ImageFrame
from stmviewer.metadata_values import (json_object as _object, optional_number as _number,
                                       optional_text as _text, source_header as _header, source_provenance)
from stmviewer.alignment_metadata import (
    collect_manual_histories, decode_alignment, encode_alignment, validate_alignment_series,
)
from stmviewer.manual_movie_types import MovieHistory
from stmviewer.manual_movie_metadata import decode_manual_results, encode_manual_results

_MAX_BYTES = 64 * 1024 * 1024
_FIELDS = {'provenance', 'measurement_time_s', 'measurement_time_raw', 'channel', 'signal_unit',
           'size_x_nm', 'size_y_nm', 'offset_x_nm', 'offset_y_nm', 'bias_v', 'setpoint_a',
           'scan_angle_deg', 'calibration_note', 'raw_header'}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Powtórzone pole JSON: {key}.')
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    raise ValueError(f'Niedozwolona stała JSON: {value}.')


def _frame(frame: ImageFrame, value: object, version: int = 1, *,
           finite_fill: bool = False, manual_results: tuple[MovieHistory, ...] = ()) -> ImageFrame:
    record = _object(value, _FIELDS | ({"alignment"} if version >= 2 else set())
                     | ({"missing_samples"} if version == 3 or finite_fill else set()))
    restored = replace(
        frame, provenance=source_provenance(record['provenance']),
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
    if version >= 2 and record["alignment"] is not None:
        restored = replace(restored, alignment=decode_alignment(record["alignment"], restored, manual_results=manual_results))
    return restored


def mpp_sidecar_path(path: Path) -> Path:
    """The versioned companion lives beside the movie, retaining its complete filename."""
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
        shared_history = isinstance(decoded, dict) and decoded.get('version') in (4, 5, 7)
        metadata = _object(decoded, {'format', 'version', 'image_kind', 'movie', 'frames'}
                           | ({'manual_results', 'sample_encoding'} if shared_history else set()))
        if metadata['format'] != 'stmviewer-mpp':
            raise ValueError('Nieobsługiwany format dodatku.')
        if type(metadata['version']) is not int or metadata['version'] not in (1, 2, 3, 4, 5, 7):
            raise ValueError(f'Nieobsługiwana wersja dodatku: {metadata["version"]}.')
        version = metadata['version']
        assert isinstance(version, int)
        manual_results: tuple[MovieHistory, ...] = ()
        finite_fill = version == 3
        if version >= 4:
            manual_results = decode_manual_results(metadata['manual_results'], check_cancelled)
            if version < 7 and any(history.graph_provenance is not None
                                   and history.graph_provenance.settings_version != 1
                                   for history in manual_results):
                raise ValueError('Metoda grafu wymaga nowszej wersji dodatku.')
            if metadata['sample_encoding'] not in ('native-f64', 'finite-fill'):
                raise ValueError('Nieobsługiwany zapis próbek.')
            finite_fill = metadata['sample_encoding'] == 'finite-fill'
        kind = metadata['image_kind']
        if kind not in ('original', 'aligned') or (version == 1 and kind != 'original'):
            raise ValueError('Nieobsługiwany rodzaj obrazu dla wersji dodatku.')
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
                image = _frame(frame, record, version, finite_fill=finite_fill, manual_results=manual_results)
                if finite_fill:
                    assert isinstance(record, dict)
                    image = replace(image, data=restore_missing_samples(
                        frame.data, record['missing_samples'], check_cancelled))
                restored.append(image)
            except (ValueError, OverflowError) as error:
                raise ValueError(f'Klatka {index} dodatku: {error}') from error
        validate_alignment_series(tuple(restored), aligned=kind == "aligned")
        result = tuple(restored)
        note = f'Metadane towarzyszące: wczytano {sidecar.name} ({kind}).'
        if finite_fill:
            note += ' WSxM: odtworzono brakujące próbki z dodatku.'
    except FileNotFoundError:
        note = 'Metadane towarzyszące: brak; dane z nagłówka MPP.'
    except (OSError, ValueError, RecursionError, OverflowError) as error:
        note = f'Metadane towarzyszące: pominięto {sidecar.name}. {error}'
    if result is frames:
        note += ' Bez poprawnego dodatku nie można odtworzyć braków z wariantu WSxM.'
    annotated = []
    for frame in result:
        check_cancelled()
        annotated.append(replace(frame, metadata_note=note))
    check_cancelled()
    return tuple(annotated)


def encode_mpp_metadata(frames: tuple[ImageFrame, ...], sha256: str, *,
                        check_cancelled: Callable[[], None], image_kind: str = "original",
                        wsxm_compatible: bool = False) -> bytes:
    """Keep legacy formats; V7 records method-aware graph provenance (V6 is reserved)."""
    validate_alignment_series(frames, aligned=image_kind == "aligned")
    version = 2 if image_kind == "aligned" or any(f.alignment for f in frames) else 1
    if wsxm_compatible:
        version = 3
    manual_results = collect_manual_histories(frames, check_cancelled)
    manual_ids = {history.revision: index for index, history in enumerate(manual_results)}
    if manual_results:
        version = 4
    if any(history.graph_provenance is not None for history in manual_results):
        version = 5
    if any(history.graph_provenance is not None and history.graph_provenance.settings_version == 3
           for history in manual_results):
        version = 7
    finite_fill = wsxm_compatible
    remaining_runs = MAX_RUNS
    records = []
    for frame in frames:
        check_cancelled()
        provenance = frame.provenance or FrameProvenance(str(frame.source), frame.source_frame_index)
        record = {key: getattr(frame, key) for key in _FIELDS if key != 'provenance'}
        record['raw_header'] = {key: value if isinstance(value, str) else dict(value)
                                for key, value in frame.raw_header.items()}
        record['provenance'] = {'source': provenance.source,
                                'source_frame_index': provenance.source_frame_index}
        if version >= 2:
            record["alignment"] = encode_alignment(frame.alignment, manual_ids=manual_ids)
        if finite_fill:
            missing = encode_missing_samples(frame.data, check_cancelled, remaining_runs=remaining_runs)
            record['missing_samples'] = missing
            runs = missing['runs']
            assert isinstance(runs, list)
            remaining_runs -= len(runs)
        _frame(frame, record, version, finite_fill=finite_fill, manual_results=manual_results)
        records.append(record)
    metadata = dict(format='stmviewer-mpp', version=version, image_kind=image_kind,
                    movie=dict(sha256=sha256, frame_count=len(frames), shape_yx=list(frames[0].data.shape)),
                    frames=records)
    if version >= 4:
        metadata['manual_results'] = encode_manual_results(manual_results, check_cancelled)
        metadata['sample_encoding'] = 'finite-fill' if finite_fill else 'native-f64'
    payload = (json.dumps(metadata, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    if len(payload) > _MAX_BYTES:
        raise ValueError('Dodatek przekracza 64 MiB.')
    check_cancelled()
    return payload
