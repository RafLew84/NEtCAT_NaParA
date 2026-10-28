"""Reproduce Phase's misalignment of three visible structures in MOVIE_8 1->2.

The three independently matched patches are a local reference for this pair.
They are NOT full-film ground truth or evidence that one shift fits all rows.
Run from any directory with the Viewer repository on PYTHONPATH. Expected RED
on base 26f5538: current full-frame Phase is ~0px while these structures move
by ~14px. The optional --normalization none probes one configuration change; it is not a
production fix or a general acceptance test. No image filtering is performed.
"""

import argparse
import hashlib
from pathlib import Path
from time import perf_counter
import json

import cv2
import numpy as np

from stmviewer.registration import create_shift_backend
from stmviewer.series import open_frame_series


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="Original MOVIE_8.mpp used in this investigation"
    )
    parser.add_argument("--normalization", choices=["phase", "none"], default="phase")
    args = parser.parse_args()
    source = args.source
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    assert (
        digest == "a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7"
    ), ("This local reference was defined for a different MOVIE_8.mpp", digest)
    frames = open_frame_series([source])
    reference, moving = (np.asarray(f.data, dtype=np.float32) for f in frames[:2])
    rectangles = ((180, 160, 260, 240), (350, 320, 430, 400), (90, 330, 170, 410))
    landmarks = []
    for x0, y0, x1, y1 in rectangles:
        template = reference[y0:y1, x0:x1]
        search = moving[y0 - 40 : y1 + 40, x0 - 40 : x1 + 40]
        correlation = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
        _, peak, _, position = cv2.minMaxLoc(correlation)
        shift = np.array((40 - position[0], 40 - position[1]), dtype=float)
        zero = float(correlation[40, 40])
        assert peak - zero > 0.15, (shift, peak, zero)
        assert np.linalg.norm(shift - (14, 0)) <= 2, shift
        landmarks.append(
            dict(
                rect_xyxy=[x0, y0, x1, y1],
                shift_xy=shift.tolist(),
                peak_ncc=peak,
                zero_ncc=zero,
            )
        )
    consensus = np.median([r["shift_xy"] for r in landmarks], axis=0)
    backend = create_shift_backend("phase_correlation")
    if args.normalization == "none":
        from nanotrack.registration.phase_correlation import (
            PhaseCorrelationShiftBackend,
            PhaseCorrelationShiftConfig,
        )

        backend = PhaseCorrelationShiftBackend(
            PhaseCorrelationShiftConfig(normalization=None)
        )
    estimate = backend.estimate(frames[0].data, frames[1].data, moving_frame_index=1)
    error = float(np.linalg.norm(np.asarray(estimate.shift_xy) - consensus))
    print(
        json.dumps(
            dict(
                pair_1based=[1, 2],
                landmarks=landmarks,
                consensus_xy=consensus.tolist(),
                phase_xy=list(estimate.shift_xy),
                phase_status=estimate.status,
                disagreement_px=error,
                seconds=perf_counter() - started,
            ),
            indent=2,
        ),
        flush=True,
    )
    assert error <= 3.0, (
        f"Phase misaligns the three visible structures by {error:.3f} px (>3 px)"
    )


if __name__ == "__main__":
    main()
