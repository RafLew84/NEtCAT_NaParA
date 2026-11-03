#!/usr/bin/env python3
"""Run one frame of BBox-prompted SAM2 image segmentation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.sam2.image_batch_contract import (
        empty_sam2_image_batch_output,
        read_sam2_image_batch_input_npz,
        write_sam2_image_batch_output_npz,
    )
    from nanotrack.sam2.image_predictor_kernel import (
        build_sam2_image_predictor_kernel,
    )
    from nanotrack.sam2.run_sam2_subprocess import (
        _configure_cuda_runtime,
        _make_autocast_context,
        _resolve_config_identifier,
        _resolve_torch_device,
        _sam2_import_context,
    )
else:
    from .image_batch_contract import (
        empty_sam2_image_batch_output,
        read_sam2_image_batch_input_npz,
        write_sam2_image_batch_output_npz,
    )
    from .image_predictor_kernel import build_sam2_image_predictor_kernel
    from .run_sam2_subprocess import (
        _configure_cuda_runtime,
        _make_autocast_context,
        _resolve_config_identifier,
        _resolve_torch_device,
        _sam2_import_context,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack SAM2 image batch worker.")
    parser.add_argument("--input-npz", required=True)
    parser.add_argument("--output-npz", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--repo-path", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--apply-postprocessing",
        dest="apply_postprocessing",
        action="store_true",
    )
    parser.add_argument(
        "--disable-postprocessing",
        dest="apply_postprocessing",
        action="store_false",
    )
    parser.set_defaults(apply_postprocessing=True)
    return parser.parse_args()


def _run_worker(args: argparse.Namespace) -> None:
    input_path = Path(args.input_npz).expanduser().resolve()
    output_path = Path(args.output_npz).expanduser().resolve()
    checkpoint_path = Path(args.checkpoint).expanduser()
    repo_path = (
        None
        if args.repo_path is None
        else Path(args.repo_path).expanduser().resolve()
    )
    run_input = read_sam2_image_batch_input_npz(input_path)
    if not run_input.requires_inference:
        write_sam2_image_batch_output_npz(
            output_path,
            empty_sam2_image_batch_output(run_input),
        )
        return

    with _sam2_import_context(repo_path):
        import torch

        config_identifier = _resolve_config_identifier(
            args.config,
            repo_path,
            checkpoint_path,
        )
        device = _resolve_torch_device(torch, args.device)
        _configure_cuda_runtime(torch, device)
        kernel = build_sam2_image_predictor_kernel(
            config_identifier=config_identifier,
            checkpoint_path=checkpoint_path,
            device=str(device),
            apply_postprocessing=bool(args.apply_postprocessing),
        )
        autocast_context = _make_autocast_context(torch, device)
        with torch.inference_mode(), autocast_context:
            run_output = kernel.run(run_input)

    write_sam2_image_batch_output_npz(output_path, run_output)


def main() -> int:
    _run_worker(_parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
