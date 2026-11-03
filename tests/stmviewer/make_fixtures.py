"""Regenerate the tiny, synthetic STP files used by manual and automated checks."""

from pathlib import Path
import struct


FIXTURES = Path(__file__).parent / "fixtures"


def stp(metadata: str, samples: tuple[float, ...]) -> bytes:
    header = (
        "WSxM file copyright Nanotec Electronica\n"
        "SxM Image file\n"
        "Image header Size: {size:06d}\n"
        "[General Info]\n"
        "Image Data Type: double\n"
        "Number of columns: 4\n"
        "Number of rows: 3\n"
        + metadata + "[Header end]\n"
    )
    size = len(header.format(size=0).encode("utf-8"))
    return header.format(size=size).encode("utf-8") + struct.pack("<12d", *samples)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    # After the STP rotation: white L on the left and bottom, grey markers right.
    asymmetric = stp(
        "Acquisition channel: Topo\nX Amplitude: 8 nm\nY Amplitude: 9 nm\n"
        "Z Amplitude: 99 nm\nX-Offset: 2 nm\nY-Offset: -1 nm\n"
        "Gap Voltage: 0 V\nSetpoint: 0.25 nA\nAngle: 0\n",
        (1.5, 12, 12, 12, 0, 6, 0, 12, 3, 0, 0, 12),
    )
    (FIXTURES / "asymmetric.stp").write_bytes(asymmetric)
    # No calibration: white bar across the upper row (except its leftmost pixel).
    (FIXTURES / "unknown.stp").write_bytes(stp(
        "", (0, 0, 0, 0, 0, 3, 0, 0, 3, 3, 3, 0)
    ))
    (FIXTURES / "truncated.stp").write_bytes(asymmetric[:-8])


if __name__ == "__main__":
    main()
