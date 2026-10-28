"""Lossless recovery of nonfinite samples from finite WSxM movie pixels."""
from collections.abc import Callable
import math
import re

import numpy as np
from numpy.typing import NDArray

from stmviewer.metadata_values import json_object, optional_number

# Bound run-list allocation before the enclosing 64 MiB JSON limit is checked.
# A 1000-frame 512-row drift canvas alone needs just over 512,000 runs.
MAX_RUNS = 1_000_000


def background_value(data: NDArray[np.float64], checkpoint: Callable[[], None]) -> float:
    maximum = -math.inf
    for row in range(0, data.shape[0], 128):
        checkpoint()
        block = data[row:row + 128]
        maximum = max(maximum, float(np.max(block, where=np.isfinite(block), initial=-np.inf)))
    return maximum if math.isfinite(maximum) else 0.0


def encode_missing_samples(data: NDArray[np.float64], checkpoint: Callable[[], None],
                           *, remaining_runs: int) -> dict[str, object]:
    """Runs use C-order coordinates of the displayed image, before MPP rotation."""
    runs: list[list[int | str]] = []
    width = data.shape[1]
    for row in range(0, data.shape[0], 128):
        checkpoint()
        values = data[row:row + 128].astype('<f8').ravel()
        bits = values.view('<u8')
        missing = ~np.isfinite(values)
        changed = bits[1:] != bits[:-1]
        starts = np.flatnonzero(missing & np.r_[True, ~missing[:-1] | changed])
        ends = np.flatnonzero(missing & np.r_[~missing[1:] | changed, True]) + 1
        for start, end in zip(starts, ends, strict=True):
            if len(runs) % 1024 == 0:
                checkpoint()
            offset, count = row * width + int(start), int(end - start)
            encoded = int(bits[start]).to_bytes(8, 'little').hex()
            if runs and runs[-1][2] == encoded and int(runs[-1][0]) + int(runs[-1][1]) == offset:
                runs[-1][1] = int(runs[-1][1]) + count
            else:
                if len(runs) >= remaining_runs:
                    raise ValueError('Zbyt wiele przedziałów braków: dodatek może zawierać najwyżej 1 000 000.')
                runs.append([offset, count, encoded])
    return {'encoding': 'runs-f64le-v1', 'fill_value': background_value(data, checkpoint), 'runs': runs}


def restore_missing_samples(data: NDArray[np.float64], value: object,
                            checkpoint: Callable[[], None]) -> NDArray[np.float64]:
    """Restore on a copy so rejecting any later record leaves the movie untouched."""
    record = json_object(value, {'encoding', 'fill_value', 'runs'})
    fill = optional_number(record, 'fill_value')
    runs = record['runs']
    if record['encoding'] != 'runs-f64le-v1' or fill is None or not isinstance(runs, list):
        raise ValueError('Nieprawidłowy opis brakujących próbek WSxM.')
    if len(runs) > MAX_RUNS:
        raise ValueError('Zbyt wiele przedziałów braków WSxM.')
    for row in range(0, data.shape[0], 128):
        checkpoint()
        if not np.isfinite(data[row:row + 128]).all():
            raise ValueError('Wariant WSxM wymaga skończonych próbek w MPP.')
    restored = data.copy() if runs else data
    flat = restored.reshape(-1)
    previous_end = 0
    for index, run in enumerate(runs):
        if index % 1024 == 0:
            checkpoint()
        if not isinstance(run, list) or len(run) != 3:
            raise ValueError('Nieprawidłowy przedział braków WSxM.')
        start, count, encoded = run
        if (type(start) is not int or type(count) is not int or start < previous_end
                or count < 1 or start + count > data.size or not isinstance(encoded, str)
                or re.fullmatch('[0-9a-f]{16}', encoded) is None):
            raise ValueError('Nieprawidłowe pozycje lub bity braków WSxM.')
        sample = np.frombuffer(bytes.fromhex(encoded), dtype='<f8')[0]
        if np.isfinite(sample):
            raise ValueError('Opis braków WSxM nie może zastępować skończoną wartością.')
        for offset in range(start, start + count, 524288):
            checkpoint()
            part = flat[offset:min(offset + 524288, start + count)]
            if not np.all(part == fill):
                raise ValueError('Wypełnienie MPP nie zgadza się z opisem braków WSxM.')
            part[:] = sample
        previous_end = start + count
    return restored
