"""Small reproducible registration movies in source file orientation."""

from pathlib import Path

import numpy as np
from scipy.ndimage import fourier_shift

from make_mpp_fixtures import movie_bytes


def write_movie(path, frames):
    height, width = frames[0].shape
    path.write_bytes(movie_bytes(
        [frame[::-1, ::-1].ravel() for frame in frames], rows=height, columns=width,
        times={i: f'{time} s' for i, time in enumerate((10, 20, 35)[:len(frames)])},
    ))


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    frame = np.random.default_rng(42).normal(size=(32, 48))
    frame[8:15, 10:18] += 4
    write_movie(destination / 'integer.mpp', [
        frame, np.roll(frame, (2, -3), (0, 1)), np.roll(frame, (1, 2), (0, 1)),
    ])
    subpixel = np.random.default_rng(42).normal(size=(64, 64))
    shifted = np.fft.ifftn(fourier_shift(np.fft.fftn(subpixel), shift=(2.4, -3.25))).real
    write_movie(destination / 'subpixel.mpp', [subpixel, shifted])
    y, x = np.mgrid[:48, :48]
    pattern = (((x // 4) + (y // 4)) % 2).astype(float)
    write_movie(destination / 'uncertain.mpp', [pattern, np.roll(pattern, (4, 4), (0, 1)), pattern])
    write_movie(destination / 'flat.mpp', [np.ones((32, 48)), np.ones((32, 48))])
    missing = frame.copy()
    missing[5, 7] = np.nan
    write_movie(destination / 'missing.mpp', [frame, missing])


if __name__ == '__main__':
    generate(Path(__file__).parent / 'fixtures' / 'registration')
