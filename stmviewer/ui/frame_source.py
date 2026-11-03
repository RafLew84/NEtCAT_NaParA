"""Display opened-file location separately from portable historical provenance."""

from pathlib import PureWindowsPath

from stmviewer.frame import ImageFrame
from stmviewer.manual_movie_types import MovieCorrection


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


def alignment_history_text(frame: ImageFrame) -> str:
    history = frame.alignment
    if history is None:
        return ''
    reference = PureWindowsPath(history.reference.source).name or history.reference.source
    if history.reference.source_frame_index is not None:
        reference += f' · klatka {history.reference.source_frame_index + 1}'
    height, width = history.canvas_shape
    oh, ow = history.original_shape
    def pair(values: tuple[float | None, float | None]) -> str:
        return ' × '.join('nieznane' if v is None else f'{v:g} nm' for v in values)

    count, previous = 0, history.previous
    while previous is not None:
        count += 1
        previous = previous.previous
    quality = ('⚠ Słabe poparcie — sprawdź dopasowanie'
               if history.status == 'low_confidence' and history.quality_score is None
               else '⚠ Do sprawdzenia — pewność niezweryfikowana' if history.quality_score is None
               else 'OK' if history.status == 'ok' else '⚠ Do sprawdzenia')
    return (
        'Historia aligned — wczytane piksele są wejściem original.\n'
        f'{history.method} · {history.device} · {quality}\n'
        f'ΔX: {history.shift_xy[0]:g} px · ΔY: {history.shift_xy[1]:g} px\n'
        f'Obszar: {width} × {height} px\n'
        f'Źródłowa klatka: {ow} × {oh} px\n'
        f'Początek źródła XY: {history.origin_xy[0]:g}, {history.origin_xy[1]:g} px\n'
        f'Źródłowe pole XY: {pair(history.original_size_nm)}\n'
        f'Źródłowy offset XY: {pair(history.original_offset_nm)}\n'
        f'Odniesienie historyczne: {reference}\n'
        f'Wcześniejsze etapy rejestracji: {count}'
        + ('\n' + movie_corrections_text(history.manual_movie.corrections)
           if history.manual_movie is not None else '')
    )


def movie_corrections_text(corrections: tuple[MovieCorrection, ...]) -> str:
    """Expose the applied pair edits without calling them algorithm confidence."""
    if not corrections:
        return ''
    lines = [f'Ręczne korekty filmu: {len(corrections)} · jakość nieoceniona']
    for correction in corrections:
        def source_name(source: str, index: int | None) -> str:
            name = PureWindowsPath(source).name or source
            return name + (f' · MPP {index + 1}' if index is not None else '')
        reference, moving = correction.reference, correction.moving
        lines.append(f'{source_name(reference.source, reference.source_frame_index)} → '
                     f'{source_name(moving.source, moving.source_frame_index)}')
        bx, by = correction.baseline_xy
        sx, sy = correction.start_xy
        dx, dy = correction.correction_xy
        x, y = correction.shift_xy
        lines.append(f'Baza XY: ({bx:g}, {by:g}) · Początek XY: ({sx:g}, {sy:g}) px')
        lines.append(f'Ruchy: ({dx:+d}, {dy:+d}) · Wynik XY: ({x:g}, {y:g}) px '
                     f'· ręczne v{correction.settings_version}')
    return '\n'.join(lines)
