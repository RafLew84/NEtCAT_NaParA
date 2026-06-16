from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from moltrack.core import MolTrackImageSeries
from nanotrack.io import load_stm_sequence


SequenceLoader = Callable[..., object]


def load_moltrack_image_series(
    source_path: str | os.PathLike[str],
    *,
    reverse_frame_order: bool = False,
    sequence_loader: SequenceLoader = load_stm_sequence,
) -> MolTrackImageSeries:
    if not isinstance(source_path, (str, os.PathLike)):
        raise ValueError("MolTrack currently supports one MPP source file.")
    path = Path(source_path)
    if path.suffix.lower() != ".mpp":
        raise ValueError("MolTrack currently supports one MPP source file.")
    try:
        sequence = sequence_loader(source_path, reverse_frame_order=reverse_frame_order)
    except Exception as exc:
        raise ValueError(f"Cannot load MolTrack STM source: {source_path}") from exc
    series = MolTrackImageSeries.from_stm_sequence(sequence)
    series.set_active_frame(0)
    return series
