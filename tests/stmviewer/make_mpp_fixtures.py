"""Small deterministic WSxM-style double movies; payloads use file row order."""

from pathlib import Path
import struct


def movie_bytes(frames, *, rows=3, columns=4, times=None, extra="", encoding="utf-8"):
    header = (
        "WSxM file copyright UAM\nMovie Image file\nImage header size: {size}\n"
        "[General Info]\nImage Data Type: double\n"
        f"Number of columns: {columns}\nNumber of rows: {rows}\nNumber of Frames: {len(frames)}\n"
        "Acquisition channel: Current\nZ Amplitude: 99 nA\nAngle: 37\n"
        "[Control]\nX Amplitude: 8 nm\nY Amplitude: 9 nm\n"
        "X Offset: 2 nm\nY Offset: -1 nm\nTopography Bias: -200 mV\nSet Point: 400 pA\n"
        "[Frames Synchronization]\n"
    )
    if times is not None:
        header += ''.join(f"Frame {i:04d}: {value}\n" for i, value in times.items())
    header += extra + "[Header end]\n"
    size = 0
    while True:
        encoded = header.format(size=size).encode(encoding)
        if len(encoded) == size:
            break
        size = len(encoded)
    return encoded + b''.join(struct.pack(f'<{len(frame)}d', *frame) for frame in frames)


# A rotated white L, with distinct markers, encoded in file order.
FIRST = (1, 8, 8, 8, 0, 4, 0, 8, 2, 0, 0, 8)
SECOND = tuple(range(12))
THIRD = (8, 0, 0, 2, 8, 0, 4, 0, 8, 8, 8, 1)


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    payload = movie_bytes([FIRST, SECOND, THIRD], times={0: '1500 ms', 2: '4.25 s'})
    (destination / 'timed.MPP').write_bytes(payload)
    (destination / 'truncated.mpp').write_bytes(payload[:-1])
    (destination / 'no-times.mpp').write_bytes(movie_bytes([FIRST]))
    (destination / 'long.mpp').write_bytes(movie_bytes(
        [(float(i),) for i in range(1000)], rows=1, columns=1,
        times={i: f'{i} s' for i in range(1000)},
    ))


if __name__ == '__main__':
    generate(Path(__file__).parent / 'fixtures' / 'mpp')
