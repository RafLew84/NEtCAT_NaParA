"""Opt-in pair diagnostics; never saves aligned images or changes source files.

Continues after pair failures to aid investigation. The application aborts the
whole registration at its first failed pair. Estimates are not ground truth.
"""

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
from stmviewer.registration import CPU_METHODS, create_shift_backend
from stmviewer.series import open_frame_series


def summarize(rows, shape, complete):
    good = [row for row in rows if "result" in row]
    failures = [row for row in rows if "error" in row]
    summary = dict(
        processed_pairs=len(rows),
        failures=failures,
        statuses=dict(Counter(row["result"]["status"] for row in good)),
        estimated_canvas_yx=None,
        all_pairs_processed=complete,
    )
    if good:
        shifts = np.array([row["result"]["shift_xy"] for row in good])
        summary["shift_norm_p50_p95_max"] = np.percentile(
            np.linalg.norm(shifts, axis=1), [50, 95, 100]
        ).tolist()
        # A failed or partial run is not a result the application could display.
        if complete and not failures:
            cumulative = np.vstack(([0.0, 0.0], np.cumsum(shifts, axis=0)))
            summary["estimated_canvas_yx"] = [
                shape[axis]
                + math.ceil(max(0, cumulative[:, coordinate].max()))
                + math.ceil(max(0, -cumulative[:, coordinate].min()))
                for axis, coordinate in ((0, 1), (1, 0))
            ]
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="New diagnostic directory")
    parser.add_argument(
        "--method",
        action="append",
        choices=[*CPU_METHODS, "phase_no_normalization", "deep_matcher_translation"],
    )
    parser.add_argument(
        "--weights",
        type=Path,
        help="Existing local LoFTR outdoor weights; never downloaded",
    )
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument(
        "--max-pairs", type=int, help="Smoke only; report explicitly marks partial runs"
    )
    args = parser.parse_args()
    if args.max_pairs is not None and args.max_pairs < 1:
        parser.error("--max-pairs must be positive")
    methods = args.method or list(CPU_METHODS)
    if "deep_matcher_translation" in methods and args.weights is None:
        parser.error("Deep Matcher requires --weights")
    args.output.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve()
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    frames = open_frame_series([source])
    report = dict(
        source=str(source), source_bytes=source.stat().st_size, source_sha256=digest
    )
    report.update(
        frame_count=len(frames),
        shape_yx=frames[0].data.shape,
        nonfinite_frames=[
            i + 1 for i, frame in enumerate(frames) if not np.isfinite(frame.data).all()
        ],
        metadata={
            name: getattr(frames[0], name)
            for name in (
                "size_x_nm",
                "size_y_nm",
                "channel",
                "signal_unit",
                "measurement_time_s",
            )
        },
        methods={},
    )

    def save():
        (args.output / "baseline.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )

    save()
    for method in methods:
        started = perf_counter()
        if method == "deep_matcher_translation":
            loaded = load_deep_backend(DeepMatcherOptions(args.weights, args.device))
            backend, device = loaded.backend, loaded.device
        elif method == "phase_no_normalization":
            from nanotrack.registration.phase_correlation import (
                PhaseCorrelationShiftBackend,
                PhaseCorrelationShiftConfig,
            )

            backend = PhaseCorrelationShiftBackend(
                PhaseCorrelationShiftConfig(normalization=None)
            )
            device = "CPU"
        else:
            backend, device = create_shift_backend(method), "CPU"
        setup_seconds = perf_counter() - started
        started = perf_counter()
        count = (
            min(len(frames) - 1, args.max_pairs) if args.max_pairs else len(frames) - 1
        )
        rows = []
        for i in range(1, count + 1):
            began = perf_counter()
            try:
                result = backend.estimate(
                    frames[i - 1].data, frames[i].data, moving_frame_index=i
                )
                row = dict(pair_1based=[i, i + 1], result=asdict(result))
            except Exception as error:
                row = dict(
                    pair_1based=[i, i + 1], error=f"{type(error).__name__}: {error}"
                )
            row["seconds"] = perf_counter() - began
            rows.append(row)
        summary = summarize(rows, frames[0].data.shape, count == len(frames) - 1)
        summary.update(
            seconds=perf_counter() - started, setup_seconds=setup_seconds, device=device
        )
        if method == "phase_no_normalization":
            summary["quality_note"] = (
                "Existing backend still computes quality/status using the phase-normalized peak ratio."
            )
        report["methods"][method] = dict(summary=summary, pairs=rows)
        save()
        print(method, json.dumps(summary), flush=True)
        # Release native/GPU resources before constructing another backend.
        if method == "deep_matcher_translation":
            del loaded
        del backend


if __name__ == "__main__":
    main()
