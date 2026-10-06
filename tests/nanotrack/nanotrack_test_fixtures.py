"""Synthetic input for loader/GUI tests, independent of private data/ files."""

import atexit
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


@lru_cache(maxsize=1)
def sample_mpp_path() -> Path:
    directory = TemporaryDirectory(prefix="nanotrack-test-mpp-")
    atexit.register(directory.cleanup)
    path = Path(directory.name) / "sample.MPP"
    size = 256
    frame_count = 17
    header = "\n".join([
        "[General Info]",
        f"Number of columns: {size}",
        f"Number of rows: {size}",
        f"Number of Frames: {frame_count}",
        "Acquisition channel: Topography",
        "[Control]", "X Amplitude: 25 nm", "Y Amplitude: 25 nm",
        "[Frames Synchronization]",
        *(f"Frame {index:04d}: 0 s" for index in range(frame_count)),
        "[Header end]", "",
    ])
    rng = np.random.default_rng(17)
    base = rng.normal(size=(size, size))
    with path.open("wb") as stream:
        stream.write(header.encode("ascii"))
        for index in range(frame_count):
            frame = np.roll(base, (index % 3, index % 5), axis=(0, 1))
            stream.write(np.asarray(frame, dtype="<f8").tobytes())
    return path
