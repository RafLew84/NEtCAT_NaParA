"""Local inputs for aligned AVI, with visible drift and brightness changes.

Run: PYTHONPATH=. python tests/stmviewer/make_aligned_avi_fixtures.py
"""
from dataclasses import replace
from pathlib import Path

import numpy as np

from make_cpu_registration_fixtures import cpu_frames
from stmviewer.frame import ImageFrame
from stmviewer.mpp_export import save_original_mpp


def generate(destination: Path, *, long_movie: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = cpu_frames()[0]
    frames = []
    for index, (dy, dx, gain) in enumerate(((0, 0, 1), (4, -7, 1.8), (-3, 5, 0.6), (1, 2, 1.2))):
        data = np.roll(base, (dy, dx), (0, 1)) * gain
        data.setflags(write=False)
        frames.append(ImageFrame(Path(f'drift{index + 1}.stp'), data, {}, 'Height', 'nm',
                                 80, 80, None, None, None, None, None,
                                 measurement_time_s=(10, 20, 35, 45)[index]))
    save_original_mpp(destination / 'drift.mpp', tuple(frames), overwrite=True)
    save_original_mpp(destination / 'anisotropic.mpp', tuple(replace(f, size_x_nm=160) for f in frames),
                      overwrite=True)
    save_original_mpp(destination / 'mixed.mpp', (replace(frames[0], size_x_nm=None), *frames[1:]),
                      overwrite=True)
    if long_movie:
        # Repeated translations keep the aligned canvas bounded; distinct random
        # texture makes Phase unambiguous and encoding long enough to cancel.
        large = np.random.default_rng(16).normal(size=(512, 512))
        images = tuple(np.roll(large, shift, (0, 1)) for shift in ((0, 0), (4, -7), (-3, 5), (1, 2)))
        for image in images:
            image.setflags(write=False)
        long_frames = tuple(replace(frames[i % 4], data=images[i % 4], size_x_nm=512,
                                    size_y_nm=512, measurement_time_s=float(i * 10)) for i in range(256))
        save_original_mpp(destination / 'long.mpp', long_frames, overwrite=True)
    print(destination.resolve())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--long', action='store_true', help='Także 256 × 512 × 512, około 537 MB')
    generate(Path('data/avi-ticket16'), long_movie=parser.parse_args().long)
