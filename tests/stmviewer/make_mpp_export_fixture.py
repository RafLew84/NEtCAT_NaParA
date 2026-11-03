"""Create a large synthetic source for manual export/cancel trials, without the exporter."""
from argparse import ArgumentParser
from pathlib import Path

import numpy as np


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--frames', type=int, default=1000)
    parser.add_argument('--size', type=int, default=512)
    args = parser.parse_args()
    if args.frames < 1 or args.size < 8:
        parser.error('Wymagane frames >= 1 i size >= 8')
    template = ('WSxM file copyright UAM\nMovie Image file\nImage header size: {size}\n'
                '[General Info]\nImage Data Type: double\n'
                f'Number of columns: {args.size}\nNumber of rows: {args.size}\n'
                f'Number of Frames: {args.frames}\nAcquisition channel: Topography\n'
                'Z Amplitude: 1 nm\n[Control]\nX Amplitude: 100 nm\nY Amplitude: 100 nm\n'
                '[Header end]\n')
    size = 0
    while True:
        header = template.format(size=size).encode('utf-8')
        if size == len(header):
            break
        size = len(header)
    frame = np.arange(args.size * args.size, dtype='<f8').reshape(args.size, args.size)
    frame[2:5, 2:5] = np.nan
    with args.path.open('xb') as stream:
        stream.write(header)
        for index in range(args.frames):
            frame[0, 0] = index
            stream.write(frame.tobytes())
    print(f'{args.path}: {args.frames} × {args.size} × {args.size}, {args.path.stat().st_size} B')


if __name__ == '__main__':
    main()
