"""Portable session archives: exact pixels, bounded streaming IO, atomic publish."""
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, IO
import ast
import io
import json
import math
import os
import struct
import tempfile
import zipfile
import zlib

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from stmviewer.session_state import SessionState

Progress = Callable[[int, int, str], None]
Cancelled = Callable[[], bool]
MAX_IMAGE_BYTES = 8 * 1024 ** 3
MAX_METADATA_BYTES = 64 * 1024 ** 2
_CHUNK_BYTES = 1024 * 1024
_HEADER_BYTES = 65536
_MANIFEST = 'manifest.json'


class SessionError(ValueError):
    """A session cannot be saved or decoded as a complete active state."""


class SessionCancelled(Exception):
    """Cancellation leaves the old session/file untouched."""


def _checkpoint(cancelled: Cancelled | None) -> None:
    if cancelled is not None and cancelled():
        raise SessionCancelled


def _report(progress: Progress | None, done: int, total: int, text: str,
            cancelled: Cancelled | None) -> None:
    _checkpoint(cancelled)
    if progress is not None:
        progress(done, total, text)
    _checkpoint(cancelled)


def _budget(shapes: dict[str, tuple[int, int]]) -> None:
    total = 0
    for shape in shapes.values():
        if len(shape) != 2 or any(type(v) is not int or v <= 0 for v in shape):
            raise SessionError('Sesja: nieprawidłowe wymiary obrazu.')
        total += math.prod(shape) * 8
    if total > MAX_IMAGE_BYTES:
        raise SessionError('Sesja przekracza limit 8 GiB wartości obrazów original i aligned.')


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SessionError(f'Sesja: powtórzone pole JSON: {key}.')
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise SessionError(f'Sesja: niedozwolona stała JSON: {value}.')


def _write_pixels(stream: IO[bytes], values: NDArray[np.float64], cancelled: Cancelled | None) -> None:
    if values.dtype != np.dtype('float64') or values.ndim != 2:
        raise SessionError('Sesja: wymagany dwuwymiarowy obraz float64.')
    # At most one frame is converted on a big-endian/non-contiguous input.
    pixels = np.ascontiguousarray(values, dtype='<f8')
    header = io.BytesIO()
    np.lib.format.write_array_header_2_0(header, {'descr': '<f8', 'fortran_order': False,  # type: ignore[no-untyped-call]
                                               'shape': pixels.shape})
    stream.write(header.getvalue())
    raw = memoryview(pixels).cast('B')
    for offset in range(0, len(raw), _CHUNK_BYTES):
        _checkpoint(cancelled)
        stream.write(raw[offset:offset + _CHUNK_BYTES])


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise SessionError('Sesja: ucięty obraz NPY.')
    return data


def _read_pixels(stream: IO[bytes], expected: tuple[int, int], size: int,
                 cancelled: Cancelled | None) -> NDArray[np.float64]:
    _checkpoint(cancelled)
    if _read_exact(stream, 6) != b'\x93NUMPY':
        raise SessionError('Sesja: nieprawidłowy nagłówek obrazu NPY.')
    version = tuple(_read_exact(stream, 2))
    if version not in ((1, 0), (2, 0)):
        raise SessionError('Sesja: nieobsługiwana wersja obrazu NPY.')
    count_bytes = 2 if version == (1, 0) else 4
    header_size = int.from_bytes(_read_exact(stream, count_bytes), 'little')
    if not 0 < header_size <= _HEADER_BYTES:
        raise SessionError('Sesja: nagłówek obrazu NPY jest zbyt duży.')
    header = ast.literal_eval(_read_exact(stream, header_size).decode('latin1').strip())
    if (not isinstance(header, dict) or set(header) != {'descr', 'fortran_order', 'shape'}
            or header['descr'] != '<f8' or header['fortran_order'] is not False
            or not isinstance(header['shape'], tuple) or len(header['shape']) != 2
            or any(type(n) is not int for n in header['shape']) or header['shape'] != expected):
        raise SessionError('Sesja: typ lub wymiary obrazu NPY nie zgadzają się z metadanymi.')
    bytes_count = math.prod(expected) * 8
    if size != 8 + count_bytes + header_size + bytes_count:
        raise SessionError('Sesja: niezgodna długość obrazu NPY.')
    pixels = np.empty(expected, dtype='<f8')
    raw = memoryview(pixels).cast('B')
    for offset in range(0, len(raw), _CHUNK_BYTES):
        _checkpoint(cancelled)
        block = _read_exact(stream, min(_CHUNK_BYTES, len(raw) - offset))
        raw[offset:offset + len(block)] = block
    if stream.read(1):
        raise SessionError('Sesja: nadmiarowe dane obrazu.')
    pixels.setflags(write=False)
    return pixels


def save_session(path: Path, state: 'SessionState', *, progress: Progress | None = None,
                 cancelled: Cancelled | None = None) -> Path:
    """Stream all stored pixels into one archive and publish it only after success."""
    from stmviewer.session_metadata import encode_session, session_array_shapes

    _checkpoint(cancelled)
    path = Path(path)
    protected = {p for frame in state.frames for p in (
        frame.source.resolve(), frame.source.with_name(frame.source.name + '.stmviewer.json').resolve(),
    )}
    if path.resolve() in protected:
        raise SessionError('Sesja nie może zastąpić źródłowego obrazu ani jego metadanych.')
    temporary: Path | None = None
    try:
        metadata, arrays = encode_session(state, check_cancelled=lambda: _checkpoint(cancelled))
        shapes = session_array_shapes(metadata)
        _budget(shapes)
        if set(shapes) != set(arrays):
            raise SessionError('Sesja: niepełny zestaw obrazów.')
        body = {'format': 'stmviewer-session', 'version': 1, 'state': metadata}
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False,
                             separators=(',', ':')).encode('utf-8')
        if len(encoded) > MAX_METADATA_BYTES:
            raise SessionError('Metadane sesji przekraczają 64 MiB.')
        _report(progress, 0, len(arrays) + 1, 'Zapisywanie sesji…', cancelled)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.',
                                         suffix='.tmp', delete=False) as target:
            temporary = Path(target.name)
            with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=1, allowZip64=True) as archive:
                archive.writestr(_MANIFEST, encoded)
                for index, (name, values) in enumerate(arrays.items(), 1):
                    if values.shape != shapes[name]:
                        raise SessionError('Sesja: niezgodne wymiary zapisywanego obrazu.')
                    with archive.open(name, 'w', force_zip64=True) as stream:
                        _write_pixels(stream, values, cancelled)
                    _report(progress, index, len(arrays) + 1,
                            f'Zapis obrazów: {index}/{len(arrays)}', cancelled)
            target.flush()
            os.fsync(target.fileno())
        _report(progress, len(arrays) + 1, len(arrays) + 1, 'Zatwierdzanie zapisu sesji…', cancelled)
        os.replace(temporary, path)
        return path
    except (OSError, ValueError, TypeError, OverflowError, RecursionError, zipfile.BadZipFile) as error:
        raise SessionError(f'Nie można zapisać sesji: {error}') from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_session(path: Path, *, progress: Progress | None = None,
                 cancelled: Cancelled | None = None) -> 'SessionState':
    """Decode a complete state without opening historical image/model paths."""
    from stmviewer.session_metadata import decode_session, session_array_shapes

    _checkpoint(cancelled)
    try:
        with zipfile.ZipFile(path, 'r') as archive:
            infos = archive.infolist()
            members = {info.filename: info for info in infos}
            if len(members) != len(infos) or _MANIFEST not in members:
                raise SessionError('Sesja: powtórzone pliki lub brak manifestu.')
            if members[_MANIFEST].file_size > MAX_METADATA_BYTES:
                raise SessionError('Metadane sesji przekraczają 64 MiB.')
            body = json.loads(archive.read(_MANIFEST), object_pairs_hook=_unique_object,
                              parse_constant=_invalid_constant)
            if (not isinstance(body, dict) or set(body) != {'format', 'version', 'state'}
                    or body['format'] != 'stmviewer-session'):
                raise SessionError('Nie jest to sesja STM Viewer.')
            if type(body['version']) is not int or body['version'] != 1:
                raise SessionError('Nieobsługiwana wersja sesji.')
            shapes = session_array_shapes(body['state'])
            _budget(shapes)
            if set(members) != {*shapes, _MANIFEST}:
                raise SessionError('Sesja: niekompletny lub nadmiarowy zestaw obrazów.')
            arrays = {}
            _report(progress, 0, len(shapes) + 1, 'Odczyt obrazów sesji…', cancelled)
            for index, (name, shape) in enumerate(shapes.items(), 1):
                size = members[name].file_size
                expected_bytes = math.prod(shape) * 8
                if not expected_bytes < size <= expected_bytes + _HEADER_BYTES + 12:
                    raise SessionError('Sesja: niezgodny rozmiar pliku obrazu.')
                with archive.open(name) as stream:
                    arrays[name] = _read_pixels(stream, shape, size, cancelled)
                _report(progress, index, len(shapes) + 1,
                        f'Odczyt obrazów: {index}/{len(shapes)}', cancelled)
            state = decode_session(body['state'], arrays, check_cancelled=lambda: _checkpoint(cancelled))
            _report(progress, len(shapes) + 1, len(shapes) + 1, 'Sesja gotowa do otwarcia.', cancelled)
            return state
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError,
            SyntaxError, UnicodeError, struct.error, EOFError, zipfile.BadZipFile, zlib.error, RuntimeError) as error:
        raise SessionError(f'Nie można otworzyć sesji: {error}') from error
