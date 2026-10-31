"""Versioned, lightweight registration trials bound to the original sources."""

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable
import hashlib
import json
import os
import tempfile
from math import isclose

from stmviewer.frame import ImageFrame
from stmviewer.trial_validation import validate_payload, integer, object_record

Progress = Callable[[int, int, str], None]
Cancelled = Callable[[], bool]
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024


class TrialDocumentError(ValueError):
    """A document or its associated source series is not usable."""


class TrialCancelled(Exception):
    """An IO operation was cancelled without publishing its result."""


@dataclass(frozen=True)
class SourceIdentity:
    source: str
    source_frame_index: int | None
    source_group: int
    file_sha256: str | None
    frame_sha256: str
    geometry_sha256: str
    shape: tuple[int, int]
    origin_source: str | None = None


@dataclass(frozen=True)
class TrialDocument:
    payload: dict[str, Any]
    sources: tuple[SourceIdentity, ...] = ()
    format_version: int = 1


def _checkpoint(cancelled: Cancelled | None) -> None:
    if cancelled is not None and cancelled():
        raise TrialCancelled


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _identities(frames: tuple[ImageFrame, ...], *, progress: Progress | None,
                cancelled: Cancelled | None) -> tuple[SourceIdentity, ...]:
    hashes: dict[Path, str | None] = {}
    result = []
    for index, frame in enumerate(frames):
        _checkpoint(cancelled)
        path = frame.source.resolve()
        if path not in hashes:
            digest = hashlib.sha256()
            if path.is_file():
                with path.open('rb') as stream:
                    while block := stream.read(1024 * 1024):
                        _checkpoint(cancelled)
                        digest.update(block)
                hashes[path] = digest.hexdigest()
            else:
                hashes[path] = None
        values_hash = hashlib.sha256()
        for row in frame.data:
            _checkpoint(cancelled)
            values_hash.update(row.astype('<f8', copy=False).tobytes())
        geometry = {key: getattr(frame, key) for key in (
            'size_x_nm', 'size_y_nm', 'offset_x_nm', 'offset_y_nm', 'scan_angle_deg',
            'channel', 'signal_unit', 'measurement_time_s', 'measurement_time_raw',
        )}
        geometry['alignment'] = asdict(frame.alignment) if frame.alignment is not None else None
        geometry['provenance'] = asdict(frame.provenance) if frame.provenance is not None else None
        geometry_hash = hashlib.sha256(_canonical(geometry)).hexdigest()
        result.append(SourceIdentity(str(frame.source), frame.source_frame_index,
                                     list(hashes).index(path), hashes[path], values_hash.hexdigest(),
                                     geometry_hash, (int(frame.data.shape[0]), int(frame.data.shape[1])), str(frame.source)))
        if progress is not None:
            progress(index + 1, len(frames), f'Sprawdzanie źródeł: {index + 1}/{len(frames)}')
    _checkpoint(cancelled)
    return tuple(result)


def save_trial(path: Path, trial: TrialDocument, frames: tuple[ImageFrame, ...], *,
               progress: Progress | None = None, cancelled: Cancelled | None = None) -> TrialDocument:
    _checkpoint(cancelled)
    protected = {item for frame in frames for item in (
        frame.source.resolve(), frame.source.with_name(frame.source.name + '.stmviewer.json').resolve(),
    )}
    if path.resolve() in protected:
        raise TrialDocumentError('Nie można zastąpić pliku źródłowego ani jego metadanych dokumentem próby.')
    try:
        if type(trial.format_version) is not int or trial.format_version != 1:
            raise ValueError('Nieobsługiwana wersja dokumentu próby.')
        validate_payload(trial.payload, frame_count=len(frames))
    except (ValueError, TypeError, OverflowError) as error:
        raise TrialDocumentError(str(error)) from error
    sources = _identities(frames, progress=progress, cancelled=cancelled)
    if trial.sources:
        _same_sources(trial.sources, sources)
        sources = tuple(replace(current, origin_source=old.origin_source)
                        for old, current in zip(trial.sources, sources))
    _manual_source_binding(trial.payload, sources)
    bound = TrialDocument(json.loads(_canonical(trial.payload)), sources)
    body = {'format': 'stmviewer-registration-trial', 'version': bound.format_version,
            'sources': [asdict(source) for source in sources], 'trial': bound.payload}
    encoded = _canonical(body)
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise TrialDocumentError('Dokument próby jest zbyt duży (maksymalnie 64 MiB).')
    if progress is not None:
        progress(0, 1, 'Zapisywanie dokumentu próby…')
    _checkpoint(cancelled)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent,
                                         prefix=f'.{path.name}.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            for offset in range(0, len(encoded), 1024 * 1024):
                _checkpoint(cancelled)
                stream.write(encoded[offset:offset + 1024 * 1024])
            stream.flush()
            os.fsync(stream.fileno())
        _checkpoint(cancelled)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return bound


def load_trial(path: Path, frames: tuple[ImageFrame, ...], *,
               progress: Progress | None = None, cancelled: Cancelled | None = None) -> TrialDocument:
    _checkpoint(cancelled)
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise TrialDocumentError('Dokument próby jest zbyt duży (maksymalnie 64 MiB).')
    try:
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Powtórzone pole dokumentu.')
                result[key] = value
            return result
        body = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
        if not isinstance(body, dict) or body.get('format') != 'stmviewer-registration-trial':
            raise ValueError('Nie jest to dokument próby STM Viewer.')
        if type(body.get('version')) is not int or body['version'] != 1:
            raise ValueError('Nieobsługiwana wersja dokumentu próby.')
        if not isinstance(body.get('sources'), list) or len(body['sources']) != len(frames):
            raise ValueError('Dokument: liczba klatek źródłowych nie zgadza się z serią.')
        payload = validate_payload(body.get('trial'), frame_count=len(frames))
        sources = tuple(_decode_source(item) for item in body['sources'])
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        raise TrialDocumentError(f'Nieprawidłowy dokument próby: {error}') from error
    current = _identities(frames, progress=progress, cancelled=cancelled)
    _same_sources(sources, current)
    _manual_source_binding(payload, sources)
    current = tuple(replace(item, origin_source=old.origin_source) for old, item in zip(sources, current))
    return TrialDocument(payload, current, body['version'])


def _same_sources(expected: tuple[SourceIdentity, ...], actual: tuple[SourceIdentity, ...]) -> None:
    if tuple(replace(item, source='', origin_source=None) for item in expected) != tuple(
            replace(item, source='', origin_source=None) for item in actual):
        raise TrialDocumentError('Próba dotyczy innej zawartości, geometrii lub kolejności źródeł.')


def _manual_source_binding(payload: dict[str, Any], sources: tuple[SourceIdentity, ...]) -> None:
    if payload['manual_movie'] is None:
        return
    from stmviewer.manual_movie_metadata import decode_manual_results, manual_frame_state
    from stmviewer.manual_movie_types import MovieSource
    history = decode_manual_results([payload['manual_movie']], lambda: None)[0]
    positions = {frame.source: index for index, frame in enumerate(history.baseline)}
    for record in payload['records']:
        source = sources[record['index']]
        origin = MovieSource(source.origin_source or source.source, source.source_frame_index)
        index = positions.get(origin)
        if index is None:
            raise TrialDocumentError('Korekta filmu: źródło nie należy do zapisanej historii.')
        expected = manual_frame_state(history, index)
        if (not all(isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
                    for a, b in zip(expected.shift_xy, record['cumulative_xy']))
                or expected.status != record['status']
                or expected.quality_score != record['quality_score']
                or expected.inherited_uncertainty != record['inherited_uncertainty']):
            raise TrialDocumentError('Korekta filmu: wynik nie odpowiada historii tej klatki źródłowej.')


def _decode_source(value: Any) -> SourceIdentity:
    from dataclasses import fields
    record = object_record(value, 'Źródło')
    if set(record) != {field.name for field in fields(SourceIdentity)}:
        raise ValueError('Źródło: nieprawidłowe pola tożsamości.')
    for key in ('source', 'origin_source'):
        if not isinstance(record[key], str) or not record[key] or '\x00' in record[key]:
            raise ValueError('Źródło: nieprawidłowa ścieżka.')
    if record['source_frame_index'] is not None:
        integer(record['source_frame_index'], 'Indeks źródłowy')
    integer(record['source_group'], 'Grupa źródłowa')
    for key in ('file_sha256', 'frame_sha256', 'geometry_sha256'):
        digest = record[key]
        if key == 'file_sha256' and digest is None:
            continue
        if (not isinstance(digest, str) or len(digest) != 64
                or any(letter not in '0123456789abcdef' for letter in digest)):
            raise ValueError('Źródło: nieprawidłowy skrót zawartości.')
    shape = record['shape']
    if not isinstance(shape, list) or len(shape) != 2:
        raise ValueError('Źródło: nieprawidłowe wymiary.')
    for size in shape:
        integer(size, 'Wymiar źródła', minimum=1)
    return SourceIdentity(**{**record, 'shape': (shape[0], shape[1])})
