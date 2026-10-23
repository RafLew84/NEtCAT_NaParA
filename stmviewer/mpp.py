"""Decode WSxM double movies in the same image orientation as STP/NanoTrack."""

from collections.abc import Callable
from pathlib import Path
import hashlib
import os
import re
from typing import BinaryIO

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.mpp_metadata import apply_mpp_metadata
from stmviewer.quantities import CURRENT_A, LENGTH_NM, VOLTAGE_V, parse_quantity, scaled_quantity


_TIME_S = {"s": 1.0, "sec": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6,
           "μs": 1e-6, "min": 60.0, "h": 3600.0}


def _header(stream: BinaryIO, check_cancelled: Callable[[], None],
            consume: Callable[[bytes], None]) -> dict[str, dict[str, str]]:
    header: dict[str, dict[str, str]] = {}
    section = ''
    # No header-line count limit: synchronization adds one line per movie frame.
    while raw := stream.readline(65537):
        check_cancelled()
        consume(raw)
        if len(raw) > 65536:
            raise ValueError('Zbyt długa linia nagłówka MPP.')
        try:
            line = raw.decode('utf-8').strip()
        except UnicodeDecodeError:
            line = raw.decode('latin1').strip()
        if line.lower() == '[header end]':
            return header
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
        elif ':' in line:
            key, value = line.split(':', 1)
            header.setdefault(section, {})[key.strip()] = value.strip()
    raise ValueError('Brak [Header end] w nagłówku MPP.')


def open_mpp_series(
    path: Path, *, check_cancelled: Callable[[], None],
    progress: Callable[[int, int, Path], None] | None = None,
) -> tuple[ImageFrame, ...]:
    source = path.resolve()
    try:
        with source.open('rb') as stream:
            digest = hashlib.sha256()
            header = _header(stream, check_cancelled, digest.update)
            general = header.get('General Info', {})
            control = header.get('Control', {})
            data_type = general.get('Image Data Type', 'double')
            if data_type.lower() != 'double':
                raise ValueError(f'Nieobsługiwany typ danych MPP: {data_type} (wymagany double).')
            columns = int(general.get('Number of columns', '0'))
            rows = int(general.get('Number of rows', '0'))
            count = int(general.get('Number of Frames', '0'))
            if min(columns, rows, count) <= 0:
                raise ValueError('Nieprawidłowe wymiary lub liczba klatek MPP.')
            bytes_per_frame = rows * columns * 8
            available = os.fstat(stream.fileno()).st_size - stream.tell()
            if available < bytes_per_frame * count:
                incomplete = available // bytes_per_frame + 1
                raise ValueError(f"Niepełne dane klatki {incomplete}/{count} MPP.")
            amplitude = parse_quantity(general.get('Z Amplitude', ''))
            times = {int(match[1]): value
                     for key, value in header.get("Frames Synchronization", {}).items()
                     if (match := re.fullmatch(r"Frame\s+(\d+)", key))}
            if progress is not None:
                progress(0, count, source)
            frames = []
            for index in range(count):
                check_cancelled()
                payload = stream.read(bytes_per_frame)
                digest.update(payload)
                check_cancelled()
                if len(payload) != bytes_per_frame:
                    raise ValueError(f"Niepełne dane klatki {index + 1}/{count} MPP.")
                # The shared reader returns file row order; the NanoTrack loader
                # and STP reader apply this same 180-degree orientation correction.
                data = np.frombuffer(payload, dtype='<f8').reshape(rows, columns)
                frames.append(ImageFrame(
                    source=source, data=np.rot90(data, 2).copy(), raw_header=header,
                    source_frame_index=index,
                    measurement_time_s=scaled_quantity(times.get(index, ""), _TIME_S),
                    measurement_time_raw=times.get(index),
                    channel=general.get('Acquisition channel') or None,
                    signal_unit=(amplitude[1] or None) if amplitude else None,
                    size_x_nm=scaled_quantity(control.get('X Amplitude', ''), LENGTH_NM, positive=True),
                    size_y_nm=scaled_quantity(control.get('Y Amplitude', ''), LENGTH_NM, positive=True),
                    offset_x_nm=scaled_quantity(control.get('X Offset', general.get('X-Offset', '')), LENGTH_NM),
                    offset_y_nm=scaled_quantity(control.get('Y Offset', general.get('Y-Offset', '')), LENGTH_NM),
                    bias_v=scaled_quantity(control.get('Gap Voltage', control.get('Topography Bias',
                                           general.get('Bias', ''))), VOLTAGE_V),
                    setpoint_a=scaled_quantity(control.get('Setpoint', control.get('Set Point',
                                               general.get('Current', ''))), CURRENT_A),
                    scan_angle_deg=scaled_quantity(general.get('Angle', ''), {'': 1, 'deg': 1, '°': 1}),
                ))
                if progress is not None:
                    progress(index + 1, count, source)
            check_cancelled()
            # Bind metadata to exactly the bytes decoded, including any file trailer.
            while chunk := stream.read(1024 * 1024):
                check_cancelled()
                digest.update(chunk)
            return apply_mpp_metadata(source, tuple(frames), sha256=digest.hexdigest(),
                                      check_cancelled=check_cancelled)
    except (OSError, ValueError, OverflowError) as error:
        raise ValueError(f'{source}: {error}') from error
