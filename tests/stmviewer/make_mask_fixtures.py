"""A stationary scanner artefact hides the known translation of sample texture."""

from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

from make_registration_fixtures import write_movie


def artefact_arrays():
    rng = np.random.default_rng(301)
    sample = gaussian_filter(rng.normal(size=(64, 80)), 1.1)
    yy, xx = np.mgrid[:64, :80]
    sample += 2 * np.exp(-((xx - 25) ** 2 + (yy - 35) ** 2) / 35)
    sample -= 1.8 * np.exp(-((xx - 59) ** 2 + (yy - 42) ** 2) / 60)
    artefact = 20 * rng.normal(size=(12, 80))
    arrays = []
    for dy, dx in ((0, 0), (-3, 4), (-1, 7)):
        image = np.roll(sample, (dy, dx), axis=(0, 1))
        image[:12] = artefact
        arrays.append(image)
    return tuple(arrays)


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    write_movie(destination / 'masked-artifact.mpp', artefact_arrays())


if __name__ == '__main__':
    generate(Path(__file__).parent / 'fixtures' / 'registration')
