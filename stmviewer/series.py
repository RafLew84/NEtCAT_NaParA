"""Import a complete STP selection without publishing partial results."""

from collections.abc import Callable, Sequence
from pathlib import Path
import re

from stmviewer.frame import ImageFrame
from stmviewer.io import open_stp


def _natural_key(path: Path) -> tuple[tuple[tuple[int, str | int], ...], str]:
    parts = tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                  for part in re.split(r"(\d+)", path.name))
    return parts, str(path)


class ImportCancelled(Exception):
    """The caller cancelled before a complete result could be published."""


def open_stp_series(
    paths: Sequence[str | Path],
    *,
    progress: Callable[[int, int, Path], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> tuple[ImageFrame, ...]:
    """Decode STP files in natural filename order, retaining per-frame metadata."""
    if not paths:
        raise ValueError("Nie wybrano plików STP.")
    frames: list[ImageFrame] = []
    for path in sorted(map(Path, paths), key=_natural_key):
        if cancelled is not None and cancelled():
            raise ImportCancelled
        frame = open_stp(path)
        if frames and frame.data.shape != frames[0].data.shape:
            height, width = frame.data.shape
            expected_height, expected_width = frames[0].data.shape
            raise ValueError(
                f"{path}: rozmiar {width} × {height} px; "
                f"wymagany {expected_width} × {expected_height} px."
            )
        frames.append(frame)
        if progress is not None:
            progress(len(frames), len(paths), path)
        if cancelled is not None and cancelled():
            raise ImportCancelled
    return tuple(frames)
