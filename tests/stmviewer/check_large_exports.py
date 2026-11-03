"""Opt-in whole-file verification against originals and recomputed real Phase results.

Run one group per process to isolate peak verification memory from the GUI run.
MPP checks every sample bit and metadata field. FFV1 checks every decoded raster;
MJPG checks all frames against the expected raster with explicit lossy tolerances.
"""

import argparse
from dataclasses import fields
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from large_series_probe import Resources, distribution, source_identity
from stmviewer.alignment_metadata import aligned_export_frames
from stmviewer.avi_annotations import AnnotationOptions
from stmviewer.avi_export import prepare_avi
from stmviewer.avi_raster import MoviePresentation, movie_contrast_levels
from stmviewer.avi_sources import aligned_movie_frames
from stmviewer.frame import FrameProvenance, ImageFrame
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series


def check_mpp(row, expected):
    started = perf_counter()
    loaded = open_frame_series([row["file"]])
    assert len(loaded) == len(expected) == row["frames"]
    ignored = {"data", "source", "source_frame_index", "provenance", "metadata_note"}
    for index, (actual, original) in enumerate(zip(loaded, expected, strict=True)):
        assert actual.data.shape == original.data.shape
        assert actual.data.tobytes() == original.data.tobytes(), (
            f"Samples: frame {index}"
        )
        assert "wczytano" in actual.metadata_note
        assert actual.source_frame_index == index
        assert actual.provenance == (
            original.provenance
            or FrameProvenance(str(original.source), original.source_frame_index)
        )
        for field in fields(ImageFrame):
            if field.name not in ignored:
                assert getattr(actual, field.name) == getattr(original, field.name), (
                    index,
                    field.name,
                )
    return dict(
        frames=len(loaded),
        shape=list(loaded[0].data.shape),
        all_sample_bits_equal=True,
        all_metadata_equal=True,
        seconds=perf_counter() - started,
    )


def check_avi(row, frames):
    started = perf_counter()
    plan = prepare_avi(
        frames,
        fps=row["fps"],
        codec=row["codec"],
        presentation=MoviePresentation(
            gamma=row["gamma"], contrast=row["contrast"], background=row["background"]
        ),
        annotations=AnnotationOptions(
            scale_bar=True, frame_number=True, measurement_time=True
        ),
    )
    limits = movie_contrast_levels(frames) if row["contrast"] == "movie" else None
    movie = cv2.VideoCapture(row["file"])
    assert movie.isOpened()
    assert movie.get(cv2.CAP_PROP_FPS) == row["fps"]
    assert int(movie.get(cv2.CAP_PROP_FRAME_COUNT)) == len(frames)
    error_means, error_p99 = [], []
    caption_block_errors = []
    try:
        for index in range(len(frames)):
            ok, actual = movie.read()
            assert ok, index
            expected = plan.render_frame(index, contrast_limits=limits)
            assert actual.shape == expected.shape, (actual.shape, expected.shape)
            if row["codec"] == "FFV1":
                assert np.array_equal(actual, expected), f"FFV1 frame {index}"
            else:
                errors = np.abs(actual.astype(np.int16) - expected)
                # A local bound on the number label catches repeats/reordering
                # that a full-image average could hide in almost identical frames.
                height = 16 + plan.annotations.text_height + 8
                width = (
                    max(
                        cv2.getTextSize(
                            lines[0],
                            cv2.FONT_HERSHEY_SIMPLEX,
                            plan.annotations.font_scale,
                            1,
                        )[0][0]
                        for lines in plan.annotations.labels
                    )
                    + 32
                )
                patch = errors[: height // 4 * 4, : width // 4 * 4, 0]
                block_error = float(
                    patch.reshape(patch.shape[0] // 4, 4, patch.shape[1] // 4, 4)
                    .mean(axis=(1, 3))
                    .max()
                )
                assert block_error < 20, ("MJPG number label", index, block_error)
                caption_block_errors.append(block_error)
                mean, p99 = float(errors.mean()), float(np.percentile(errors, 99))
                # Compression error remains small, including antialiased labels.
                assert mean < 3 and p99 <= 20, (index, mean, p99)
                error_means.append(mean)
                error_p99.append(p99)
        assert not movie.read()[0], "Unexpected extra frame"
    finally:
        movie.release()
    return dict(
        frames=len(frames),
        output_size=plan.geometry.output_size,
        fps=row["fps"],
        all_rasters_equal=row["codec"] == "FFV1",
        mjpg_caption_block_error=distribution(caption_block_errors)
        if caption_block_errors
        else None,
        mjpg_mean_error=distribution(error_means) if error_means else None,
        mjpg_p99_error=distribution(error_p99) if error_p99 else None,
        seconds=perf_counter() - started,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("group", choices=["full", "deleted", "reregistered"])
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    assert report["status"] == "completed"
    assert source_identity(report["input"]["source"]) == report["input"]
    rows = [
        r
        for r in report["exports"]
        if r["group"] == args.group and r["status"] == "saved"
    ]
    assert rows
    resources = Resources()
    results = dict(group=args.group, files=[])
    try:
        originals = open_frame_series([report["input"]["source"]])
        indices = rows[0]["indices"]
        assert all(r["indices"] == indices for r in rows)
        if args.group == "reregistered":
            originals = tuple(originals[i] for i in indices)
            aligned = register_series(originals)
        else:
            aligned = register_series(originals)
            if args.group == "deleted":
                for i in reversed(range(len(originals))):
                    if i not in indices:
                        aligned = aligned.without_frame(i)
                originals = tuple(originals[i] for i in indices)
        for row in rows:
            identity = source_identity(row["file"])
            assert all(row[k] == v for k, v in identity.items())
            if row["kind"] == "mpp":
                assert source_identity(row["sidecar"]["source"]) == row["sidecar"]
                expected = (
                    originals
                    if row["version"] == "original"
                    else aligned_export_frames(aligned, lambda: None)
                )
                result = check_mpp(row, expected)
                del expected
            else:
                frames = (
                    originals
                    if row["version"] == "original"
                    else aligned_movie_frames(originals, aligned)
                )
                result = check_avi(row, frames)
                del frames
            result.update(file=row["file"], kind=row["kind"], codec=row["codec"])
            results["files"].append(result)
            print(json.dumps(result), flush=True)
        results["status"] = "passed"
    finally:
        resources.close()
        results["rss_peak"] = max(v for t, v in resources.samples)
        args.report.with_name(f"verification-{args.group}.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
