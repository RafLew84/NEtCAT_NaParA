#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter as default_perf_counter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moltrack.persistence import load_moltrack_session, restore_moltrack_image_series_from_session
from moltrack.sam2 import (
    MolTrackSam2Segmenter,
    benchmark_legacy_sam2,
    build_sam2_baseline_tasks,
    discover_sam2_checkpoints,
    select_default_sam2_checkpoint,
    write_sam2_baseline_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the current legacy MolTrack SAM2 path. The legacy backend starts "
            "and loads SAM2 once per BBox, so use --max-bboxes for a quick sample."
        )
    )
    parser.add_argument("session", help="Path to a .moltrack.json state containing BBoxes.")
    parser.add_argument("--start-frame", type=int, help="First frame, numbered from 1 (inclusive).")
    parser.add_argument("--end-frame", type=int, help="Last frame, numbered from 1 (inclusive).")
    parser.add_argument(
        "--source-view",
        choices=("auto", "raw", "expanded_aligned"),
        default="auto",
        help="BBox source view. Auto follows the saved registration view.",
    )
    parser.add_argument("--checkpoint", help="SAM2 checkpoint path. Defaults to normal discovery.")
    parser.add_argument("--mask-threshold", type=float, default=0.5)
    parser.add_argument(
        "--max-bboxes",
        type=int,
        help="Optional sampling cap for this benchmark only; it is not a backend limit.",
    )
    parser.add_argument("--output", help="Output JSON path.")
    return parser


def main(
    argv=None,
    *,
    session_loader=load_moltrack_session,
    series_restorer=restore_moltrack_image_series_from_session,
    checkpoint_discovery=discover_sam2_checkpoints,
    segmenter_factory=MolTrackSam2Segmenter,
    perf_counter=default_perf_counter,
) -> int:
    args = _build_parser().parse_args(argv)
    session_path = Path(args.session)
    try:
        session = session_loader(session_path)
        series = series_restorer(session)
        start_frame_number = int(args.start_frame or (session.active_frame_index + 1))
        end_frame_number = int(args.end_frame or start_frame_number)
        source_view = _resolve_source_view(args.source_view, session.registration_view_mode)
        checkpoint_path = _resolve_checkpoint_path(args.checkpoint, checkpoint_discovery)
        tasks = build_sam2_baseline_tasks(
            series,
            start_frame_index=start_frame_number - 1,
            end_frame_index=end_frame_number - 1,
            source_view=source_view,
            max_bbox_count=args.max_bboxes,
        )
        report = benchmark_legacy_sam2(
            tasks,
            segmenter=segmenter_factory(),
            checkpoint_path=checkpoint_path,
            mask_probability_threshold=float(args.mask_threshold),
            perf_counter=perf_counter,
            progress_callback=_print_progress,
        )
        output_path = (
            Path(args.output)
            if args.output
            else session_path.with_name(f"{session_path.stem}.sam2-baseline.json")
        )
        write_sam2_baseline_report(output_path, report)
    except Exception as exc:
        print(f"SAM2 baseline failed: {str(exc) or exc.__class__.__name__}", file=sys.stderr)
        return 1

    print()
    print(report.to_text())
    print(f"- Report: {output_path}")
    return 0


def _resolve_source_view(requested_source_view: str, registration_view_mode: str) -> str:
    if requested_source_view != "auto":
        return requested_source_view
    if str(registration_view_mode) == "Show expanded aligned":
        return "expanded_aligned"
    return "raw"


def _resolve_checkpoint_path(checkpoint, checkpoint_discovery) -> Path:
    if checkpoint:
        return Path(checkpoint)
    selected = select_default_sam2_checkpoint(checkpoint_discovery())
    if selected is None:
        raise RuntimeError("No SAM2 checkpoints found. Pass --checkpoint explicitly.")
    return Path(getattr(selected, "path", selected))


def _print_progress(completed, total, task, duration_seconds) -> None:
    print(
        f"[{completed}/{total}] frame {task.detection.frame_index + 1}, "
        f"BBox {task.detection.detection_id}: {duration_seconds:.3f} s",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
