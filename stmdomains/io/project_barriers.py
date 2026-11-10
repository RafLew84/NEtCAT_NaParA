"""Bounded validation of optional diagnostic masks; old projects may omit them."""

import io
from math import prod
from pathlib import Path
import numpy as np

from stmdomains.io.project_archive import BLOCK, ProjectError, put_bytes


def save_barriers(archive, entries, index: int, mask: np.ndarray) -> None:
    output = io.BytesIO()
    np.save(output, mask, allow_pickle=False)
    put_bytes(archive, entries, f'frames/{index}.barriers.npy', output.getvalue())


def check_barriers(path: Path, shape: tuple[int, int], expected_pixels: int, check) -> None:
    count = 0
    with path.open('rb') as stream:
        if np.lib.format.read_magic(stream) != (1, 0):
            raise ProjectError('Nieobsługiwany zapis maski barier.')
        saved_shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
        if saved_shape != shape or dtype != np.dtype('bool') or stream.tell() + prod(shape) != path.stat().st_size:
            raise ProjectError('Niepoprawny rozmiar lub typ maski barier.')
        while chunk := stream.read(BLOCK):
            check()
            values = np.frombuffer(chunk, dtype=np.uint8)
            if np.any(values > 1):
                raise ProjectError('Maska barier zawiera wartości inne niż 0/1.')
            count += int(values.sum())
    if type(expected_pixels) is not int or count != expected_pixels:
        raise ProjectError('Maska barier nie odpowiada zapisanym metadanym.')


def load_barriers(path: Path, shape: tuple[int, int], count: int) -> np.ndarray:
    check_barriers(path, shape, count, lambda: None)
    return np.load(path, allow_pickle=False)
