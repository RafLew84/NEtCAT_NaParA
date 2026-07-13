#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)
from moltrack.sam2 import (
    MolTrackSam2Segmenter,
    Sam2OptimizationGateError,
    benchmark_sam2_optimization,
    build_sam2_baseline_tasks,
    discover_sam2_checkpoints,
    select_default_sam2_checkpoint,
    write_sam2_optimization_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare legacy and persistent MolTrack SAM2 backends."
    )
    parser.add_argument("session", help="Path to a .moltrack.json state containing BBoxes.")
    parser.add_argument("--start-frame", type=int, help="First frame, numbered from 1.")
    parser.add_argument("--end-frame", type=int, help="Last frame, numbered from 1.")
    parser.add_argument(
        "--source-view",
        choices=("auto", "raw", "expanded_aligned"),
        default="auto",
    )
    parser.add_argument("--checkpoint", help="SAM2 checkpoint path.")
    parser.add_argument("--mask-threshold", type=float, default=0.5)
    parser.add_argument(
        "--max-bboxes",
        type=int,
        help="Optional benchmark sampling cap; this is not a backend limit.",
    )
    parser.add_argument("--output", help="Output JSON report path.")
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    session_path = Path(args.session)
    try:
        saved_session = load_moltrack_session(session_path)
        series = restore_moltrack_image_series_from_session(saved_session)
        start_frame = int(args.start_frame or (saved_session.active_frame_index + 1))
        end_frame = int(args.end_frame or start_frame)
        source_view = _resolve_source_view(
            args.source_view,
            saved_session.registration_view_mode,
        )
        checkpoint_path = _resolve_checkpoint_path(args.checkpoint)
        tasks = build_sam2_baseline_tasks(
            series,
            start_frame_index=start_frame - 1,
            end_frame_index=end_frame - 1,
            source_view=source_view,
            max_bbox_count=args.max_bboxes,
        )
        report = benchmark_sam2_optimization(
            tasks,
            legacy_segmenter=MolTrackSam2Segmenter(),
            persistent_segmenter=MolTrackSam2Segmenter(),
            checkpoint_path=checkpoint_path,
            mask_probability_threshold=float(args.mask_threshold),
        )
        output_path = (
            Path(args.output)
            if args.output
            else session_path.with_name(f"{session_path.stem}.sam2-optimization.json")
        )
        write_sam2_optimization_report(output_path, report)
    except Exception as error:
        print(
            f"SAM2 optimization benchmark failed: {str(error) or error.__class__.__name__}",
            file=sys.stderr,
        )
        return 1

    print(report.to_text())
    print(f"- Report: {output_path}")
    try:
        report.require_pass()
    except Sam2OptimizationGateError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


def _resolve_source_view(requested: str, registration_view_mode: str) -> str:
    if requested != "auto":
        return requested
    return (
        "expanded_aligned"
        if str(registration_view_mode) == "Show expanded aligned"
        else "raw"
    )


def _resolve_checkpoint_path(checkpoint) -> Path:
    if checkpoint:
        return Path(checkpoint)
    selected = select_default_sam2_checkpoint(discover_sam2_checkpoints())
    if selected is None:
        raise RuntimeError("No SAM2 checkpoints found. Pass --checkpoint explicitly.")
    return Path(getattr(selected, "path", selected))


if __name__ == "__main__":
    raise SystemExit(main())
