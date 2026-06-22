#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moltrack.core import MolecularDetection
from moltrack.diagnostics.sam_environment import (
    build_sam_environment_report,
    probe_python_executable,
    run_fast_sam_contract_smoke,
)
from moltrack.sam2 import MolTrackSam2Segmenter
from moltrack.sam3 import MolTrackSam3BoxPrompt, MolTrackSam3ConceptAdapter


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MolTrack SAM2/SAM3 environment diagnostics.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON reports.")
    parser.add_argument("--probe-python", action="store_true", help="Run python.exe --version probes.")
    parser.add_argument(
        "--output-dir",
        default=".tmp/sam_environment_smoke",
        help="Directory for fast contract smoke NPZ files.",
    )
    parser.add_argument(
        "--real-sam2",
        action="store_true",
        help="Run a tiny real SAM2 inference. This may use GPU and is not part of fast tests.",
    )
    parser.add_argument(
        "--real-sam3",
        action="store_true",
        help="Run a tiny real SAM3 inference. This may use GPU/network cache and is not part of fast tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    reports = [
        build_sam_environment_report(),
        run_fast_sam_contract_smoke(args.output_dir),
    ]
    if args.probe_python:
        env_report = reports[0]
        python_paths = [result.path for result in env_report.results if result.name.endswith("python.exe")]
        for python_path in python_paths:
            reports.append(type(env_report)("Python executable probe", (probe_python_executable(python_path),)))

    for report in reports:
        print(report.to_json() if args.json else report.to_text())
        print()

    exit_code = 0 if all(report.ok for report in reports) else 1
    if args.real_sam2:
        exit_code = max(exit_code, _run_real_sam2_smoke())
    if args.real_sam3:
        exit_code = max(exit_code, _run_real_sam3_smoke())
    if not (args.real_sam2 or args.real_sam3):
        print("Real SAM2/SAM3 inference smoke tests were skipped. Use --real-sam2 or --real-sam3 to run them manually.")
    return exit_code


def _run_real_sam2_smoke() -> int:
    print("Running real SAM2 smoke on a 16x16 frame...")
    frame = np.arange(16 * 16, dtype=np.float32).reshape(16, 16)
    detection = MolecularDetection(
        frame_index=0,
        bbox_xyxy=(4, 4, 12, 12),
        confidence=1.0,
        source_view="raw",
        detection_id="real-sam2-smoke",
        origin="manual",
    )
    try:
        segmentation = MolTrackSam2Segmenter().segment_detection(frame, detection)
    except Exception as exc:
        print(f"REAL SAM2 ERROR: {exc}")
        return 1
    print(
        "REAL SAM2 OK: "
        f"segmentation_id={segmentation.segmentation_id}, "
        f"score={segmentation.score}, "
        f"model={segmentation.model_name}"
    )
    return 0


def _run_real_sam3_smoke() -> int:
    print("Running real SAM3 smoke on a 16x16 frame...")
    frame = np.arange(16 * 16, dtype=np.float32).reshape(16, 16)
    prompts = (
        MolTrackSam3BoxPrompt(
            bbox_xyxy=(4, 4, 12, 12),
            label=1,
            detection_id="real-sam3-smoke",
        ),
    )
    try:
        proposals = MolTrackSam3ConceptAdapter().segment_prompts(
            frame,
            prompts,
            frame_index=0,
            source_view="raw",
            model_id="facebook/sam3",
            score_threshold=0.1,
            mask_threshold=0.5,
            max_results=10,
        )
    except Exception as exc:
        print(f"REAL SAM3 ERROR: {exc}")
        return 1
    print(f"REAL SAM3 OK: {len(proposals)} proposal(s)")
    for index, proposal in enumerate(proposals[:5], start=1):
        print(f"  {index}. score={proposal.score:.3f}, bbox={proposal.bbox_xyxy}, model={proposal.model_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
