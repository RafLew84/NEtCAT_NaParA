"""Check stored raster labels in bounded chunks; materialize only requested frames."""

from collections.abc import Callable
from math import prod
from pathlib import Path
from typing import BinaryIO

import numpy as np

from stmdomains.io.project_archive import BLOCK, ProjectError


def check_header(stream: BinaryIO, shape: tuple[int, int], size: int) -> None:
    if np.lib.format.read_magic(stream) != (1, 0):
        raise ProjectError('Nieobsługiwany zapis tablicy domen.')
    saved_shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
    if saved_shape != shape or dtype != np.dtype('<i4') or stream.tell() + prod(shape) * 4 != size:
        raise ProjectError('Niepoprawny nagłówek lub rozmiar tablicy domen.')


def check_labels(path: Path, shape: tuple[int, int], domains: set[int], check: Callable[[], None]) -> None:
    seen: set[int] = set()
    with path.open('rb') as stream:
        check_header(stream, shape, path.stat().st_size)
        while chunk := stream.read(BLOCK):
            check()
            values = set(int(value) for value in np.unique(np.frombuffer(chunk, dtype='<i4'))) - {0}
            if not values <= domains:
                raise ProjectError('Maska zawiera ID domen nieobecnych w przypisaniach.')
            seen.update(values)
    if seen != domains:
        raise ProjectError('Maska nie zawiera wszystkich przypisanych domen.')


def load_labels(path: Path, shape: tuple[int, int]) -> np.ndarray:
    with path.open('rb') as stream:
        check_header(stream, shape, path.stat().st_size)
        stream.seek(0)
        return np.load(stream, allow_pickle=False)
