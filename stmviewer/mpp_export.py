"""Write original measurement values in WSxM double movie orientation."""

from pathlib import Path
from decimal import Decimal
import hashlib
import os
import shutil
import tempfile
from typing import BinaryIO
from collections.abc import Callable

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.mpp_metadata import encode_mpp_metadata


def _header(frames: tuple[ImageFrame, ...]) -> bytes:
    rows, columns = frames[0].data.shape
    def common(name: str) -> object:
        values = [getattr(frame, name) for frame in frames]
        return values[0] if values[0] is not None and all(value == values[0] for value in values) else None

    def text(name: str, unknown: str) -> str:
        value = common(name)
        return value if isinstance(value, str) and value.strip() and all(ord(c) >= 32 for c in value) else unknown

    lines = ['WSxM file copyright UAM', 'Movie Image file', 'Image header size: {size}',
             '[General Info]', 'Image Data Type: double', f'Number of columns: {columns}',
             f'Number of rows: {rows}', f'Number of Frames: {len(frames)}',
             f'Acquisition channel: {text("channel", "Unknown")}',
             f'Z Amplitude: 1 {text("signal_unit", "a.u.")}']
    angle = common('scan_angle_deg')
    if angle is not None:
        lines.append(f'Angle: {angle}')
    lines.append('[Control]')
    for field, key, pixels in [('size_x_nm', 'X Amplitude', columns), ('size_y_nm', 'Y Amplitude', rows)]:
        value = common(field)
        lines.append(f'{key}: {value} nm' if value is not None else f'{key}: {pixels} a.u.')
    for field, key, unit in [('offset_x_nm', 'X Offset', 'nm'), ('offset_y_nm', 'Y Offset', 'nm'),
                             ('bias_v', 'Gap Voltage', 'V'), ('setpoint_a', 'Setpoint', 'nA')]:
        value = common(field)
        if value is not None:
            # The legacy reader confuses A with angstrom; nA is unambiguous.
            if field == 'setpoint_a':
                value = Decimal(str(value)) * Decimal('1e9')
            lines.append(f'{key}: {value} {unit}')
    lines.append('[Frames Synchronization]')
    lines.extend(f'Frame {i:04d}: {frame.measurement_time_s!r} s' for i, frame in enumerate(frames)
                 if frame.measurement_time_s is not None)
    lines.append('[Header end]')
    template = '\n'.join(lines) + '\n'
    size = 0
    while True:
        encoded = template.replace('{size}', str(size), 1).encode('utf-8')
        if len(encoded) == size:
            return encoded
        size = len(encoded)


class ExportCancelled(Exception):
    """The export was cancelled before its completed pair was committed."""


def _write(stream: BinaryIO, payload: bytes) -> None:
    if stream.write(payload) != len(payload):
        raise OSError('Niepełny zapis pliku MPP lub metadanych.')


def _sync(stream: BinaryIO) -> None:
    stream.flush()
    os.fsync(stream.fileno())


def _check_destinations(destinations: tuple[Path, Path], overwrite: bool) -> None:
    for destination in destinations:
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise OSError(f'Cel musi być zwykłym plikiem: {destination}')
        if destination.exists() and not overwrite:
            raise FileExistsError(f'Plik już istnieje: {destination}')


def save_original_mpp(path: str | Path, frames: tuple[ImageFrame, ...], *,
                      overwrite: bool = False,
                      progress: Callable[[int, int, str], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> Path:
    """Stage and publish a movie plus its bound metadata; roll back on failure.

    The caller keeps the input images unchanged until this synchronous call ends.
    Only small row buffers are copied. Two filesystem renames cannot be atomic
    as a pair: after a process crash the reader detects stale JSON by SHA-256.
    """
    target = Path(path).absolute()
    destinations = (target, target.with_name(target.name + '.stmviewer.json'))
    frames = tuple(frames)
    if not frames:
        raise ValueError('Nie można zapisać pustej serii.')
    shape = frames[0].data.shape
    if len(shape) != 2 or min(shape) < 1:
        raise ValueError('Klatki muszą mieć dodatnie wymiary 2D.')
    for frame in frames:
        if frame.data.shape != shape or frame.data.dtype.kind != 'f' or frame.data.dtype.itemsize != 8:
            raise ValueError('Wymagane klatki float64 o jednakowych wymiarach.')
    _check_destinations(destinations, overwrite)

    def checkpoint() -> None:
        if cancelled is not None and cancelled():
            raise ExportCancelled('Anulowano zapis MPP.')

    def report(done: int, message: str) -> None:
        checkpoint()
        if progress is not None:
            progress(done, len(frames) + 3, message)
        checkpoint()

    report(0, 'Przygotowanie zapisu original…')
    staging = Path(tempfile.mkdtemp(prefix='.stmviewer-export-', dir=target.parent))
    staged = (staging / 'movie.part', staging / 'metadata.part')
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    keep_backups = False
    try:
        digest = hashlib.sha256()
        with staged[0].open('xb') as stream:
            header = _header(frames)
            _write(stream, header)
            digest.update(header)
            block_rows = max(1, (4 * 1024 * 1024) // (shape[1] * 8))
            for index, frame in enumerate(frames, 1):
                image = np.rot90(frame.data, 2)
                for row in range(0, shape[0], block_rows):
                    checkpoint()
                    payload = image[row:row + block_rows].astype('<f8').tobytes()
                    _write(stream, payload)
                    digest.update(payload)
                report(index, f'Zapis klatki {index} z {len(frames)}')
            _sync(stream)
        metadata = encode_mpp_metadata(frames, digest.hexdigest(), check_cancelled=checkpoint)
        with staged[1].open('xb') as stream:
            _write(stream, metadata)
            _sync(stream)
        report(len(frames) + 1, 'Przygotowanie metadanych…')
        _check_destinations(destinations, overwrite)
        for index, destination in enumerate(destinations):
            if destination.exists():
                backup = staging / f'{index}.backup'
                with destination.open('rb') as source, backup.open('xb') as output:
                    while chunk := source.read(4 * 1024 * 1024):
                        checkpoint()
                        _write(output, chunk)
                    _sync(output)
                shutil.copystat(destination, backup)
                backups[destination] = backup
        report(len(frames) + 2, 'Zatwierdzanie pary MPP i metadanych…')
        for source_path, destination in zip(staged, destinations, strict=True):
            checkpoint()
            os.replace(source_path, destination)
            published.append(destination)
        report(len(frames) + 3, 'Zapisano MPP i metadane.')
    except BaseException as error:
        recovery_errors = []
        for destination in reversed(published):
            try:
                if destination in backups:
                    os.replace(backups[destination], destination)
                else:
                    destination.unlink()
            except OSError as recovery_error:
                recovery_errors.append(str(recovery_error))
        if recovery_errors:
            keep_backups = True
            raise OSError(f'Błąd zapisu: {error}. Nie udało się przywrócić całej pary: '
                          f'{"; ".join(recovery_errors)}. Kopie do odzyskania: {staging}') from error
        raise
    finally:
        if not keep_backups:
            shutil.rmtree(staging, ignore_errors=True)
    return target
