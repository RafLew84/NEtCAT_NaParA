"""Generate REG-04 movies with real field boundaries and known scene translations.

No periodic wrap or filled edge is used: each frame samples a different window
of a larger synthetic scene. The stationary-artifact example deliberately has
no single translation that can align both scene and scanner artifact.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from make_registration_fixtures import write_movie


SHAPE_YX = (192, 256)
SHIFTS_XY = ((0.0, 0.0), (22.4, -13.25), (-18.6, 11.35))


def scene_frames(*, periodic=False, stationary_artifact=False):
    y, x = np.mgrid[:352, :416]
    rng = np.random.default_rng(4304)
    if periodic:
        scene = np.cos(x * 2 * np.pi / 24) + np.cos(y * 2 * np.pi / 24)
        scene += 0.5 * np.cos((x + y) * 2 * np.pi / 24)
    else:
        scene = gaussian_filter(rng.normal(size=x.shape), 1.2)
        for _ in range(140):
            cx, cy = rng.uniform(0, 416), rng.uniform(0, 352)
            sx, sy = rng.uniform(1.5, 8), rng.uniform(1.5, 8)
            amplitude = rng.uniform(-2, 2)
            scene += amplitude * np.exp(-((x - cx) / sx) ** 2 - ((y - cy) / sy) ** 2)
        scene[135:159, 145:185] += 1.8
        scene[210:237, 260:281] -= 1.8
        scene[185:204, 125:166] += 1.2
    yy, xx = np.mgrid[:SHAPE_YX[0], :SHAPE_YX[1]]
    frames = []
    for dx, dy in SHIFTS_XY:
        # A feature moving left/up in the sampled image needs +dx/+dy to align.
        frame = map_coordinates(scene, [yy + 80 + dy, xx + 80 + dx], order=3,
                                mode='constant', cval=np.nan, prefilter=True)
        if stationary_artifact:
            frame = frame.copy()
            frame[38:44] += 5
            frame[118:126] -= 4
            frame[:, 25:29] += 3
        frames.append(frame)
    return tuple(frames)


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        'shape_yx': SHAPE_YX,
        'source': 'Different windows of a larger synthetic scene; no wrapping or edge fill.',
        'scene_cumulative_xy': SHIFTS_XY,
        'scene_adjacent_xy': [[22.4, -13.25], [-41.0, 24.6]],
        'sign_convention': 'Apply +X right and +Y down to moving image; pixels of original.',
        'movies': {},
    }
    for name, options, caution in (
        ('translation.mpp', {}, 'Known rigid scene; all shifts should agree within interpolation tolerance.'),
        ('periodic.mpp', {'periodic': True}, 'Multiple equally plausible translations every 24 pixels; backend score does not resolve ambiguity.'),
        ('stationary-artifact.mpp', {'stationary_artifact': True}, 'Known scene shift plus fixed scanner-like bands. No single translation aligns all content.'),
    ):
        arrays = scene_frames(**options)
        if not all(np.isfinite(a).all() for a in arrays):
            raise ValueError('Fixture window exceeds the source scene.')
        write_movie(destination / name, arrays)
        manifest['movies'][name] = caution
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/stmviewer-reg04-fixtures'))
    print(generate(parser.parse_args().output))
