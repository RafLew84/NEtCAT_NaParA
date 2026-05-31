from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from nanotrack.io import load_stm_sequence

from moltrack.core import MolTrackProject, SourceImageSeries


def import_image_series(
    source_paths: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    project_name: str = "Untitled MolTrack Project",
    reverse_frame_order: bool = False,
) -> MolTrackProject:
    sequence = load_stm_sequence(source_paths)
    source_uris = _source_uris(source_paths)
    source_series = SourceImageSeries(
        source_uri=sequence.source_path,
        source_uris=tuple(source_uris),
        frame_count=sequence.frame_count,
        display_name=Path(sequence.source_path).name,
        raw_frames=sequence.raw_frames,
        metadata=sequence.metadata,
    )
    return MolTrackProject.from_source_series(
        source_series,
        project_name=project_name,
        reverse_frame_order=reverse_frame_order,
    )


def _source_uris(source_paths: str | os.PathLike[str] | Sequence[str | os.PathLike[str]]) -> list[str]:
    if isinstance(source_paths, (str, os.PathLike)):
        return [os.fspath(source_paths)]
    return [os.fspath(path) for path in source_paths]
