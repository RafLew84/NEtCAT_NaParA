"""Transactional AVI export, checked by decoding with the selected backend."""
from dataclasses import dataclass
from pathlib import Path
import math
from typing import Callable, Literal
from tempfile import TemporaryDirectory
import hashlib
import os
import subprocess
import sys

import numpy as np

from stmviewer.avi_raster import MovieGeometry, MoviePresentation, movie_geometry, render_movie_frame
from stmviewer.frame import ImageFrame

Codec = Literal['MJPG', 'FFV1']


@dataclass(frozen=True)
class AviPlan:
    frames: tuple[ImageFrame, ...]
    fps: int
    codec: Codec
    presentation: MoviePresentation
    geometry: MovieGeometry

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration_s(self) -> float:
        return len(self.frames) / self.fps


def prepare_avi(frames: tuple[ImageFrame, ...], *, start: int = 1, end: int | None = None,
                fps: int = 5, codec: Codec = 'MJPG',
                presentation: MoviePresentation = MoviePresentation()) -> AviPlan:
    """Freeze the selected series and options; frame arrays are immutable inputs."""
    end = len(frames) if end is None else end
    if not 1 <= start <= end <= len(frames):
        raise ValueError('Wymagany zakres 1 ≤ od ≤ do ≤ liczba klatek.')
    if not isinstance(fps, int) or not 1 <= fps <= 30:
        raise ValueError('FPS musi być liczbą całkowitą od 1 do 30.')
    if codec not in ('MJPG', 'FFV1'):
        raise ValueError('Wybierz kodek MJPG lub FFV1.')
    selected = frames[start - 1:end]
    return AviPlan(selected, fps, codec, presentation, movie_geometry(selected, presentation))


class AviCancelled(Exception):
    """The temporary movie was discarded; the destination is unchanged."""


def save_avi(path: Path, plan: AviPlan, *, overwrite: bool = False,
             progress: Callable[[int, int, str], None] | None = None,
             cancelled: Callable[[], bool] | None = None) -> Path:
    """Write and decode before publishing. Cancellation is checked between frames."""
    try:
        import cv2
    except ImportError as error:
        raise ValueError('Eksport AVI wymaga OpenCV z FFmpeg (stmviewer/requirements-avi.txt).') from error

    def report(done: int, description: str) -> None:
        if progress is not None:
            progress(done, 2 * plan.frame_count + 2, description)
        if cancelled is not None and cancelled():
            raise AviCancelled()

    def check_destination() -> None:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError('Cel AVI musi być zwykłym plikiem, nie katalogiem ani dowiązaniem.')
        if path.exists() and not overwrite:
            raise FileExistsError(path)

    check_destination()
    report(0, f'Sprawdzanie kodeka {plan.codec}…')
    with TemporaryDirectory(prefix='.stmviewer-avi-', dir=path.parent) as temporary:
        stage = Path(temporary) / 'movie.avi'
        fourcc = int.from_bytes(plan.codec.encode('ascii'), 'little')
        first = render_movie_frame(plan.frames[0], plan.presentation, plan.geometry)
        probe = Path(temporary) / 'probe.avi'
        probe_input = Path(temporary) / 'probe.npy'
        np.save(probe_input, first, allow_pickle=False)
        with (Path(temporary) / 'probe.log').open('w+b') as log:
            # Native encoders can abort on unsupported sizes, without raising a
            # Python exception. Probe in a child before using them in the worker.
            process = subprocess.Popen(
                [sys.executable, '-m', 'stmviewer.avi_probe', str(probe_input), str(probe),
                 plan.codec, str(plan.fps)], cwd=Path(__file__).resolve().parent.parent,
                stdout=log, stderr=log)
            try:
                while process.poll() is None:
                    report(0, f'Sprawdzanie kodeka {plan.codec}…')
                    try:
                        process.wait(timeout=0.05)
                    except subprocess.TimeoutExpired:
                        pass
                if process.returncode != 0:
                    log.seek(0)
                    detail = log.read(2000).decode('utf-8', errors='replace')
                    raise ValueError(f'Kodek {plan.codec} nie obsłużył tego obrazu '
                                     f'(kod procesu {process.returncode}). {detail}')
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
        _verify_movie(probe, plan, [hashlib.sha256(first).digest()], lambda _: report(0, 'Sprawdzanie kodeka…'))
        report(1, f'Zapis {plan.codec}…')
        hashes: list[bytes] = []
        writer = cv2.VideoWriter(str(stage), cv2.CAP_FFMPEG, fourcc, plan.fps, plan.geometry.output_size)
        try:
            if not writer.isOpened():
                raise ValueError(f'Nie można otworzyć zapisu {plan.codec}.')
            for index, frame in enumerate(plan.frames):
                report(index + 1, f'Zapis klatki {index + 1}/{plan.frame_count}…')
                raster = render_movie_frame(frame, plan.presentation, plan.geometry)
                hashes.append(hashlib.sha256(raster).digest())
                writer.write(raster)
        finally:
            writer.release()
        _verify_movie(stage, plan, hashes, lambda count: report(
            plan.frame_count + 1 + count, f'Sprawdzanie filmu {count}/{plan.frame_count}…'))
        with stage.open('r+b') as stream:
            os.fsync(stream.fileno())
        report(2 * plan.frame_count + 2, 'Publikowanie sprawdzonego AVI…')
        check_destination()
        if overwrite:
            os.replace(stage, path)
        else:
            # Atomic no-clobber publication, even if another program created the
            # destination after the dialog. Staging is on the same filesystem.
            os.link(stage, path)
    return path


def _verify_movie(path: Path, plan: AviPlan, hashes: list[bytes],
                  progress: Callable[[int], None]) -> None:
    import cv2
    reader = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not reader.isOpened():
            raise ValueError(f'Nie można odczytać AVI {plan.codec}; sprawdź obsługę kodeka.')
        actual_code = int(reader.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, 'little').decode('ascii', errors='replace')
        if actual_code.upper() != plan.codec or not math.isclose(reader.get(cv2.CAP_PROP_FPS), plan.fps):
            raise ValueError('Kodek lub FPS odczytanego AVI są niezgodne z wyborem.')
        width, height = plan.geometry.output_size
        for index, expected in enumerate(hashes):
            progress(index)
            ok, raster = reader.read()
            if not ok or raster.shape != (height, width, 3) or raster.dtype != np.uint8:
                raise ValueError('AVI jest niepełny lub ma niewłaściwe wymiary obrazu.')
            if plan.codec == 'FFV1' and hashlib.sha256(raster).digest() != expected:
                raise ValueError('FFV1 nie zachował dokładnie obrazu uint8.')
        ok, _ = reader.read()
        if ok:
            raise ValueError('AVI zawiera nadmiarowe klatki.')
        progress(len(hashes))
    finally:
        reader.release()
