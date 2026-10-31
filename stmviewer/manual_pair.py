"""Operator edits of a single pair; never changes the full registration."""

from math import isfinite

from stmviewer.frame import ImageFrame
from stmviewer.pair_comparison import ManualProvenance, PairTrial
from stmviewer.registration import FrameOrigin


class ManualPairDraft:
    """Keep integer nudges separate from the initial shift and saved trials."""

    def __init__(self, reference: ImageFrame, moving: ImageFrame,
                 start: PairTrial | None = None) -> None:
        self._reference = FrameOrigin(reference.source, reference.source_frame_index)
        self._moving = FrameOrigin(moving.source, moving.source_frame_index)
        if start is not None:
            if (start.reference, start.moving) != (self._reference, self._moving):
                raise ValueError('Punkt startu dotyczy innej pary klatek.')
            if len(start.shift_xy) != 2 or not all(isfinite(value) for value in start.shift_xy):
                raise ValueError('Nieprawidłowe przesunięcie XY punktu startu.')
        self._start_xy = start.shift_xy if start is not None else (0.0, 0.0)
        self._source_label: str | None = None
        if start is not None:
            if start.manual is None:
                self._source_label = f'{start.label}; {start.settings_text}; {start.device}'
            else:
                # Describe the immediate source only, never copy its ancestry text.
                sx, sy = start.manual.start_xy
                dx, dy = start.manual.correction_xy
                self._source_label = (f'{start.label} v{start.manual.settings_version}; '
                                      f'początek XY=({sx:g}, {sy:g}) px; '
                                      f'korekta XY=({dx:+d}, {dy:+d}) px; {start.device}')
        self._correction_xy = (0, 0)

    @property
    def start_xy(self) -> tuple[float, float]:
        return self._start_xy

    @property
    def correction_xy(self) -> tuple[int, int]:
        return self._correction_xy

    @property
    def shift_xy(self) -> tuple[float, float]:
        x, y = self._start_xy
        dx, dy = self._correction_xy
        return x + dx, y + dy

    def nudge(self, dx: int, dy: int) -> None:
        if type(dx) is not int or type(dy) is not int or abs(dx) + abs(dy) != 1:
            raise ValueError('Ruch ręczny wymaga dokładnie 1 piksela w jednej osi.')
        x, y = self._correction_xy
        self._correction_xy = (x + dx, y + dy)

    def reset(self) -> None:
        self._correction_xy = (0, 0)

    def apply(self) -> PairTrial:
        x, y = self.start_xy
        dx, dy = self.correction_xy
        settings = ('Ręczne v1; krok 1 px oryginału; +X w prawo, +Y w dół\n'
                    f'Początek XY=({x:g}, {y:g}) px; Korekta XY=({dx:+d}, {dy:+d}) px\n'
                    f'Źródło: {self._source_label or "od zera"}')
        return PairTrial(
            self._reference, self._moving, 'manual', 'Ręczne',
            settings,
            'Operator', self.shift_xy, 'manual', None,
            ManualProvenance(self._start_xy, self._correction_xy, self._source_label),
        )
