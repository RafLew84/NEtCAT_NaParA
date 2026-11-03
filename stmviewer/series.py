"""Import STP/S94 images or one MPP movie without publishing partial results."""

from collections.abc import Callable, Sequence
from pathlib import Path
import re

from stmviewer.frame import ImageFrame
from stmviewer.io import open_frame
from stmviewer.mpp import open_mpp_series


def _natural_key(path: Path) -> tuple[tuple[tuple[int, str | int], ...], str]:
    parts = tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                  for part in re.split(r"(\d+)", path.name))
    return parts, str(path)


class ImportCancelled(Exception):
    """The caller cancelled before a complete result could be published."""


def open_frame_series(
    paths: Sequence[str | Path],
    *,
    progress: Callable[[int, int, Path], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> tuple[ImageFrame, ...]:
    """Decode images in natural filename order or one movie in its source order."""
    if not paths:
        raise ValueError("Nie wybrano plików STP/S94 ani MPP.")
    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise ImportCancelled

    check_cancelled()
    if any(Path(path).suffix.lower() == ".mpp" for path in paths):
        if len(paths) != 1:
            raise ValueError("Wybierz dokładnie jeden MPP albo serię STP/S94. Nie można ich łączyć.")
        return open_mpp_series(Path(paths[0]), progress=progress, check_cancelled=check_cancelled)
    frames: list[ImageFrame] = []
    for path in sorted(map(Path, paths), key=_natural_key):
        check_cancelled()
        frame = open_frame(path)
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
        check_cancelled()
    return tuple(frames)
