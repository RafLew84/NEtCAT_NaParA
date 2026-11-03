"""Generate REG-05 manual movies with known scene motion and competing evidence.

Each original is a window of a larger synthetic field. No padding or periodic
wrapping creates the borders. Periodic content is deliberately ambiguous.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from make_registration_fixtures import write_movie


SHAPE_YX = (192, 256)


def sample(field, xy):
    y, x = np.mgrid[:SHAPE_YX[0], :SHAPE_YX[1]].astype(float)
    result = map_coordinates(field, [y + 64 + xy[1], x + 64 + xy[0]],
                             order=3, mode='constant', cval=np.nan)
    if not np.isfinite(result).all():
        raise ValueError('The requested window exceeds the synthetic source field.')
    return result


def scene_frames(kind):
    rng = np.random.default_rng(730)
    field = gaussian_filter(rng.normal(size=(320, 384)), 1.25)
    reference = sample(field, (0, 0))
    if kind == 'noisy':
        rng = np.random.default_rng(202605)
        field = gaussian_filter(rng.normal(size=(320, 384)), 1.25)
        field /= field.std()
        frames = [sample(field, (0, 0)), sample(field, (7, -5))]
        for frame in frames:
            noise = rng.normal(size=frame.shape)
            frame += noise / noise.std() * np.sqrt(1 / 0.3 - 1)
        return tuple(frames)
    if kind == 'translation':
        return (reference, sample(field, (13.25, -8.5)), sample(field, (-6.5, 9.25)))
    if kind == 'stationary-artifact':
        moving = sample(field, (7, -5))
        artifact = gaussian_filter(np.random.default_rng(99).normal(size=(192, 40)), 0.8) * 40
        reference[:, 76:116] += artifact
        moving[:, 76:116] += artifact
        return reference, moving
    if kind == 'split-motion':
        moving = sample(field, (3, -2))
        moving[96:] = sample(field, (-5, 4))[96:]
        return reference, moving
    if kind == 'periodic':
        y, x = np.mgrid[:320, :384]
        field = np.cos(x * 2 * np.pi / 8) + np.sin(y * 2 * np.pi / 8)
        return sample(field, (0, 0)), sample(field, (3, -2))
    if kind == 'one-band':
        field[:] = 0
        field[120:152] = gaussian_filter(np.random.default_rng(41).normal(size=(32, 384)), 1)
        return sample(field, (0, 0)), sample(field, (7, 0))
    raise ValueError(f'Unknown scene: {kind}')


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    descriptions = {
        'noisy': {
            'scene_xy': [7, -5], 'signal_to_total_variance': 0.3,
            'expected': 'A distinct peak can have NCC below 0.45; robust peak contrast and spatial support determine the local estimate. Deep still must supply a usable initial XY.',
        },
        'translation': {
            'cumulative_xy': [[0, 0], [13.25, -8.5], [-6.5, 9.25]],
            'adjacent_xy': [[13.25, -8.5], [-19.75, 17.75]],
            'expected': 'One scene translation; subpixel matching should recover the known XY.',
        },
        'stationary-artifact': {
            'scene_xy': [7, -5], 'artifact_xy': [0, 0],
            'expected': 'A stationary high-amplitude band competes with image structures in other regions.',
        },
        'split-motion': {
            'upper_xy': [3, -2], 'lower_xy': [-5, 4],
            'split_moving_y': 96,
            'expected': 'No single XY aligns both halves; competing groups must remain visible.',
        },
        'periodic': {
            'one_possible_xy': [3, -2], 'period_xy': [8, 8],
            'expected': 'Equally plausible peaks; a local refusal is expected, not proof of one shift.',
        },
        'one-band': {
            'scene_xy': [7, 0],
            'expected': 'Textured support from only one scan band cannot establish a global spatial consensus.',
        },
    }
    manifest = {
        'shape_yx': SHAPE_YX,
        'sign_convention': 'Apply +X right and +Y down to the moving image, in original pixels.',
        'source': 'Windows of larger fields; no edge fill or wrapping. Model may refuse some scenes.',
        'movies': {},
    }
    for kind, details in descriptions.items():
        arrays = scene_frames(kind)
        name = f'{kind}.mpp'
        write_movie(destination / name, arrays)
        manifest['movies'][name] = details
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/stmviewer-reg05-fixtures'))
    print(generate(parser.parse_args().output))
