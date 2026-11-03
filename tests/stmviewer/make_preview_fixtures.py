"""Small display patterns with genuine zeros, gaps and constant frames."""

from pathlib import Path

from make_fixtures import stp


# Display row order; STP stores these samples rotated by 180 degrees.
PATTERN = (0, 0.25, 1, float('nan'), float('nan'), float('nan'), 0.5, 1,
           0, float('nan'), 1, float('nan'))


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name, samples, metadata in (
        ('pattern1.stp', PATTERN, ''),
        ('pattern2.stp', tuple(value + 10 for value in PATTERN), ''),
        ('constant.stp', (7,) * 12, ''),
        ('missing.stp', (float('nan'),) * 12, ''),
        ('physical.stp', PATTERN, 'X Amplitude: 8 nm\nY Amplitude: 9 nm\n'),
        ('placeholder.stp', PATTERN, 'X Amplitude: 1000 nm\nY Amplitude: 1000 nm\n'),
    ):
        (destination / name).write_bytes(stp(metadata, tuple(reversed(samples))))


if __name__ == '__main__':
    generate(Path(__file__).parent / 'fixtures' / 'preview')
