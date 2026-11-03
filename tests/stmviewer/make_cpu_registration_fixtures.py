"""Deterministic textured translations shared by the CPU integration and GUI trial."""

from pathlib import Path

import numpy as np

from make_registration_fixtures import write_movie


def cpu_frames():
    y, x = np.mgrid[:80, :80]
    frame = 0.25 * np.sin(x / 4) + 0.2 * np.cos(y / 6) + 0.1 * np.sin((x + y) / 8)
    frame[12:27, 17:36] += 2.1
    frame[39:58, 44:66] -= 1.4
    frame[57:73, 11:29] += 1.2
    frame += np.random.default_rng(29).normal(0, 0.02, frame.shape)
    return frame, np.roll(frame, (1, -2), (0, 1)), np.roll(frame, (-1, 1), (0, 1))


if __name__ == '__main__':
    write_movie(Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp', cpu_frames())
