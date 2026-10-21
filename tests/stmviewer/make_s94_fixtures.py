"""Small, deterministic S94 patterns and a corresponding calibrated STP."""

from pathlib import Path
import struct

from make_fixtures import stp

FIXTURES = Path(__file__).parent / "fixtures" / "s94"
SAMPLES = (16384, 0, 0, 4096, 16384, 0, 8192, 0, 16384, 16384, 16384, 2048)


def s94(*, swapped=0, mode=0, gain=2, x_size=8.0, y_size=9.0, samples=SAMPLES):
    header = struct.pack(
        "<hhhhiffffffhhffffhh",
        4, 3, swapped, mode, 42, x_size, y_size, 2.0, -1.0, 100.0, -200.0,
        gain, 2, 0.0, 0.0, 0.0, 1.0, 37, 0,
    )
    return header + struct.pack("<12h", *samples)


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "frame2.s94").write_bytes(s94())
    (FIXTURES / "frame10.S94").write_bytes(s94(mode=1, x_size=16.0, y_size=12.0))
    (FIXTURES / "unknown-gain.s94").write_bytes(s94(gain=99))
    (FIXTURES / "unknown-mode.s94").write_bytes(s94(mode=7))
    (FIXTURES / "swapped.s94").write_bytes(s94(swapped=1))
    (FIXTURES / "truncated.s94").write_bytes(s94()[:-1])
    # STP stores the same calibrated image in reversed row/column order.
    (FIXTURES / "frame1.stp").write_bytes(stp(
        "Acquisition channel: Topo\nX Amplitude: 8 nm\nY Amplitude: 9 nm\n"
        "Z Amplitude: 5 nm\nX-Offset: 2 nm\nY-Offset: -1 nm\n",
        (0.6875, 5.5, 5.5, 5.5, 0.0, 2.75, 0.0, 5.5, 1.375, 0.0, 0.0, 5.5),
    ))


if __name__ == "__main__":
    main()
