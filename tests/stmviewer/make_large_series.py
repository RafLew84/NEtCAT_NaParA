"""Opt-in, streamed deterministic MPP fixture; never creates a stack in RAM."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter


def generate(destination, count=1000, size=512, drift=128):
    if count < 2 or size < 128 or not 0 < drift < size // 2:
        raise ValueError('Require count >= 2, size >= 128, 0 < drift < size/2.')
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / 'large.mpp'
    # Exclusive creation prevents overwriting an existing measurement/fixture.
    header = (
        'WSxM file copyright UAM\nMovie Image file\nImage header size: {size}\n'
        '[General Info]\nImage Data Type: double\n'
        f'Number of columns: {size}\nNumber of rows: {size}\nNumber of Frames: {count}\n'
        'Acquisition channel: Topography\nZ Amplitude: 10 nm\n'
        f'[Control]\nX Amplitude: {size} nm\nY Amplitude: {size} nm\n'
        '[Frames Synchronization]\n' +
        ''.join(f'Frame {i:04d}: {i * 1.5} s\n' for i in range(count)) + '[Header end]\n'
    )
    length = 0
    while True:
        encoded = header.format(size=length).encode('ascii')
        if len(encoded) == length:
            break
        length = len(encoded)
    texture = gaussian_filter(np.random.default_rng(1801).normal(size=(size, size)), 2)
    texture[40:80, 60:100] += 3
    texture[100:120, 20:90] -= 2
    texture -= texture.min()
    texture /= texture.max()
    shifts = []
    digest = hashlib.sha256()
    with path.open('xb') as stream:
        stream.write(encoded)
        digest.update(encoded)
        for i in range(count):
            triangle = lambda n: drift - abs(n % (2 * drift) - drift)
            x, y = triangle(i), triangle(i // 2)
            values = texture.copy()
            # A small moving binary marker distinguishes frames even after alignment.
            for bit in range(max(10, count.bit_length())):
                values[12:16, 8 + bit * 6:12 + bit * 6] += .02 if i & (1 << bit) else -.02
            values = np.roll(values, (y, x), (0, 1))
            payload = values[::-1, ::-1].astype('<f8').tobytes()
            stream.write(payload)
            digest.update(payload)
            shifts.append([x, y])
    manifest = dict(generator='large-series-v2', seed=1801, file=path.name,
                    shape=[count, size, size], dtype='float64', pixel_size_nm=[1, 1],
                    source_shift_xy=shifts, measurement_interval_s=1.5,
                    expected_canvas_shape=[size + max(y for x, y in shifts),
                                           size + max(x for x, y in shifts)],
                    bytes=path.stat().st_size, sha256=digest.hexdigest())
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--count', type=int, default=1000)
    parser.add_argument('--size', type=int, default=512)
    parser.add_argument('--drift', type=int, default=128)
    args = parser.parse_args()
    print(json.dumps(generate(args.destination, args.count, args.size, args.drift), indent=2))
