"""Small inputs for comparing AVI contrast, gamma and backgrounds.

Run from repo: PYTHONPATH=. python tests/stmviewer/make_avi_presentation_fixtures.py
"""
from pathlib import Path

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.mpp_export import save_original_mpp


def presentation_frames() -> tuple[ImageFrame, ...]:
    arrays = []
    for low, high in ((-1000, 1000), (100, 125), (125, 200)):
        data = np.full((49, 65), np.nan)
        data[:, :20] = low
        data[:, 20:40] = high
        arrays.append(data)
    arrays.extend((np.full((49, 65), np.nan), np.full((49, 65), 125.0)))
    return tuple(ImageFrame(Path(f'contrast-{index + 1}.stp'), data, {}, 'Height', 'nm',
                            65, 49, None, None, None, None, None)
                 for index, data in enumerate(arrays))


if __name__ == '__main__':
    destination = Path('data/avi-ticket15/presentation.mpp')
    destination.parent.mkdir(parents=True, exist_ok=True)
    save_original_mpp(destination, presentation_frames(), overwrite=True)
    print(destination.resolve())
