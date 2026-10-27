"""Small local movies for scale bars, series numbers and measurement times."""
from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.mpp_export import save_original_mpp


def annotation_frames():
    y, x = np.mgrid[:256, :256]
    values = .25 * np.sin(x / 12) + .2 * np.cos(y / 17)
    values[45:90, 35:95] += 2
    values[130:185, 150:215] -= 1
    values[195:225, 45:80] += 1
    values += np.random.default_rng(17).normal(0, .02, values.shape)
    values.setflags(write=False)
    return tuple(ImageFrame(Path(f'pattern{i + 1}.stp'), values, {}, 'Height', 'nm',
                            512, 256, None, None, None, None, None,
                            measurement_time_s=None if i == 6 else float(i * 15))
                 for i in range(21))


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    frames = annotation_frames()
    save_original_mpp(destination / 'calibrated.mpp', frames, overwrite=True)
    save_original_mpp(destination / 'unknown.mpp', tuple(replace(f, size_x_nm=None) for f in frames), overwrite=True)
    save_original_mpp(destination / 'mixed.mpp', (replace(frames[0], size_x_nm=256), *frames[1:]), overwrite=True)
    save_original_mpp(destination / 'tiny.mpp', tuple(replace(f, data=f.data[:64, :80]) for f in frames), overwrite=True)
    drift = tuple(replace(f, data=np.roll(f.data, ((0, 0), (4, -7), (-3, 5), (1, 2))[i % 4], (0, 1)))
                  for i, f in enumerate(frames))
    save_original_mpp(destination / 'drift.mpp', drift, overwrite=True)
    print(destination.resolve())


if __name__ == '__main__':
    generate(Path('data/avi-ticket17'))
