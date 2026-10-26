"""Generate GUI fixtures for odd edges, anisotropy, missing and constant frames.

Run from the repository: PYTHONPATH=. python tests/stmviewer/make_avi_fixtures.py
These are manual inputs, not independent writer/reader oracle fixtures.
"""
from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.mpp_export import save_original_mpp


def generate(destination: Path, *, long_movie: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    frames = []
    for index in range(4):
        values = np.zeros((49, 65), dtype=np.float64)
        values[5:28, 3 + 12 * index:13 + 12 * index] = 4
        values[30:40, 4:22] = 1
        values[8:22, 52:60] = np.nan
        values[-1, :] = 1
        values[:, -1] = 4
        frames.append(ImageFrame(Path(f'pattern{index + 1}.stp'), values, {}, 'Height', 'nm',
                                 65, 49, None, None, None, None, None,
                                 measurement_time_s=(10, 15, 35, 40)[index]))
    frames.extend((replace(frames[0], data=np.full((49, 65), np.nan)),
                   replace(frames[0], data=np.full((49, 65), 7.0))))
    save_original_mpp(destination / 'odd.mpp', tuple(frames), overwrite=True)
    save_original_mpp(destination / 'anisotropic.mpp', tuple(replace(f, size_x_nm=130) for f in frames),
                      overwrite=True)
    if long_movie:
        # Local-only cancellation input; reuse a few deterministic arrays while
        # writing. Random texture makes the codec do meaningful work per frame.
        rng = np.random.default_rng(14)
        large = tuple(replace(f, data=rng.random((512, 512))) for f in frames)
        save_original_mpp(destination / 'long.mpp', large * 100, overwrite=True)
    print(destination.resolve())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--long', action='store_true', help='Dodatkowo 600 × 512 × 512, około 1,26 GB na dysku')
    generate(Path('data/avi-ticket14'), long_movie=parser.parse_args().long)
