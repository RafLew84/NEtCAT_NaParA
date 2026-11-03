"""Small manual patterns, or an optional larger series outside the repository."""

import argparse
from pathlib import Path
import struct

from make_fixtures import stp

FIXTURES = Path(__file__).parent / "fixtures"


def write_small_series() -> None:
    series = FIXTURES / "series"
    series.mkdir(parents=True, exist_ok=True)
    # Decoded rows: top-right bar, left/bottom L, and a right-edge L.
    (series / "klatka1.stp").write_bytes(stp(
        "", (0, 0, 0, 0, 0, 3, 0, 0, 3, 3, 3, 0)
    ))
    (series / "klatka2.stp").write_bytes(stp(
        "Acquisition channel: Topo\nX Amplitude: 8 nm\nY Amplitude: 9 nm\n"
        "Z Amplitude: 99 nm\nGap Voltage: 0 V\n",
        (1.5, 12, 12, 12, 0, 6, 0, 12, 3, 0, 0, 12),
    ))
    (series / "klatka10.stp").write_bytes(stp(
        "Acquisition channel: Current\nX Amplitude: 16 nm\nY Amplitude: 12 nm\n"
        "Z Amplitude: 250 pA\nGap Voltage: 1.5 V\n",
        (5, 5, 5, 0, 5, 0, 0, 0, 5, 0, 0, 1),
    ))
    payload = (series / "klatka1.stp").read_bytes()
    (FIXTURES / "smaller.stp").write_bytes(payload.replace(
        b"Number of columns: 4", b"Number of columns: 2"
    )[:-48])


def write_large_series(directory: Path, count: int, size: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    # Positive doubles, with an asymmetric corner marker. No random data.
    samples = tuple(float((x + y) % 256) if x > size // 8 else 255.0
                    for y in range(size) for x in range(size))
    header = (
        "WSxM file copyright Nanotec Electronica\nSxM Image file\n"
        "Image header Size: {header_size:06d}\n[General Info]\nImage Data Type: double\n"
        f"Number of columns: {size}\nNumber of rows: {size}\n"
        "[Header end]\n"
    )
    data = header.format(header_size=len(header.format(header_size=0).encode())).encode()
    data += struct.pack(f"<{len(samples)}d", *samples)
    for index in range(1, count + 1):
        (directory / f"klatka{index}.stp").write_bytes(data)
    print(f"Zapisano {count} STP, {size} × {size}, {count * len(data) / 1024**2:.1f} MiB: {directory}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--large-dir", type=Path, help="Write a larger series here instead of small fixtures")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()
    if args.count < 1 or args.size < 2:
        parser.error("count must be positive and size must be at least 2")
    if args.large_dir is None:
        write_small_series()
    else:
        write_large_series(args.large_dir, args.count, args.size)


if __name__ == "__main__":
    main()
