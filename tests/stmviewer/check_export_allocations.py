"""Opt-in allocation evidence; separate from export timing because tracing costs time."""

import argparse
import json
from pathlib import Path
import tracemalloc

import numpy as np

from large_series_probe import source_identity
from stmviewer.avi_annotations import AnnotationOptions
from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.avi_sources import aligned_movie_frames
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series


def live_numpy_bytes():
    snapshot = tracemalloc.take_snapshot().filter_traces(
        [tracemalloc.DomainFilter(True, np.lib.tracemalloc_domain)]
    )
    return sum(trace.size for trace in snapshot.traces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    originals = open_frame_series([args.source.resolve()])
    aligned = register_series(originals)
    frames = aligned_movie_frames(originals, aligned)
    plan = prepare_avi(
        frames,
        fps=30,
        codec="FFV1",
        presentation=MoviePresentation(gamma=2, background=128, contrast="movie"),
        annotations=AnnotationOptions(True, True, True),
    )
    report = dict(input=source_identity(args.source), frames=len(frames), operations=[])
    # Trace new export allocations, not already loaded original/aligned buffers.
    tracemalloc.start()
    try:
        for kind in ("avi", "mpp", "avi", "mpp"):
            samples = []

            def progress(done, total, description):
                if done % 100 == 0 or done == total:
                    samples.append(live_numpy_bytes())

            tracemalloc.reset_peak()
            path = args.destination / f"{len(report['operations'])}.{kind}"
            if kind == "avi":
                save_avi(path, plan, progress=progress)
            else:
                save_aligned_mpp(path, aligned, wsxm_compatible=True, progress=progress)
            current, peak = tracemalloc.get_traced_memory()
            live = live_numpy_bytes()
            row = dict(
                kind=kind,
                numpy_live_after=live,
                numpy_peak_at_progress=max(samples),
                all_traced_current=current,
                all_traced_peak=peak,
            )
            report["operations"].append(row)
            print(json.dumps(row), flush=True)
            # Reject retaining a rendered movie; no forced GC or allocator trimming.
            assert live < 1024 * 1024, row
            assert max(samples) < 64 * 1024 * 1024, row
        report["status"] = "passed"
    finally:
        tracemalloc.stop()
        (args.destination / "allocations.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
