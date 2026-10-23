"""Display opened-file location separately from portable historical provenance."""

from pathlib import PureWindowsPath

from stmviewer.frame import ImageFrame


def frame_source_name(frame: ImageFrame) -> str:
    if frame.provenance is None:
        return frame.source.name
    # PureWindowsPath recognizes both separators without interpreting the host filesystem.
    return PureWindowsPath(frame.provenance.source).name or frame.provenance.source


def frame_source_text(frame: ImageFrame) -> str:
    if frame.provenance is None:
        text = str(frame.source)
        if frame.source_frame_index is not None:
            text += f'\nKlatka źródłowa MPP: {frame.source_frame_index + 1}'
        return text
    text = f'Plik otwarty: {frame.source}'
    if frame.source_frame_index is not None:
        text += f'\nKlatka w otwartym MPP: {frame.source_frame_index + 1}'
    text += f'\nPochodzenie: {frame.provenance.source}'
    if frame.provenance.source_frame_index is not None:
        text += f'\nKlatka źródłowa: {frame.provenance.source_frame_index + 1}'
    return text
