#!/usr/bin/env python3
"""Serve multiple BBox-prompted SAM2 image batches in one process."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
from typing import Any, TextIO


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
    from nanotrack.sam2.memory_budget import (
        current_process_peak_rss_bytes,
        current_process_rss_bytes,
    )
    from nanotrack.sam2.persistent_image_batch_backend import (
        SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION,
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
    from .memory_budget import current_process_peak_rss_bytes, current_process_rss_bytes
    from .persistent_image_batch_backend import (
        SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION,
    )
    from .run_sam2_subprocess import (
        _configure_cuda_runtime,
        _make_autocast_context,
        _resolve_config_identifier,
        _resolve_torch_device,
        _sam2_import_context,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NanoTrack persistent SAM2 image batch worker."
    )
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


def _send_message(output_stream: TextIO, message_type: str, **fields: Any) -> None:
    message = {
        "protocol_version": SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION,
        "type": message_type,
        **fields,
    }
    output_stream.write(json.dumps(message, separators=(",", ":")) + "\n")
    output_stream.flush()


def _reset_peak_vram(torch_module: Any, device: Any) -> None:
    if not str(device).startswith("cuda"):
        return
    reset_peak = getattr(torch_module.cuda, "reset_peak_memory_stats", None)
    if callable(reset_peak):
        reset_peak(device)


def _memory_diagnostics(torch_module: Any, device: Any) -> dict[str, int]:
    current_vram_bytes = 0
    peak_vram_bytes = 0
    if str(device).startswith("cuda"):
        current_memory = getattr(torch_module.cuda, "memory_allocated", None)
        peak_memory = getattr(torch_module.cuda, "max_memory_allocated", None)
        if callable(current_memory):
            current_vram_bytes = max(0, int(current_memory(device)))
        if callable(peak_memory):
            peak_vram_bytes = max(0, int(peak_memory(device)))
    return {
        "host_rss_bytes": current_process_rss_bytes(),
        "peak_host_rss_bytes": current_process_peak_rss_bytes(),
        "current_vram_bytes": current_vram_bytes,
        "peak_vram_bytes": peak_vram_bytes,
    }


def _run_worker(
    args: argparse.Namespace,
    *,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> None:
    checkpoint_path = Path(args.checkpoint).expanduser()
    repo_path = (
        None
        if args.repo_path is None
        else Path(args.repo_path).expanduser().resolve()
    )

    with _sam2_import_context(repo_path):
        import torch

        config_identifier = _resolve_config_identifier(
            args.config,
            repo_path,
            checkpoint_path,
        )
        device = _resolve_torch_device(torch, args.device)
        _configure_cuda_runtime(torch, device)
        with redirect_stdout(sys.stderr):
            kernel = build_sam2_image_predictor_kernel(
                config_identifier=config_identifier,
                checkpoint_path=checkpoint_path,
                device=str(device),
                apply_postprocessing=bool(args.apply_postprocessing),
            )
        _send_message(output_stream, "ready")

        for line in input_stream:
            if not line.strip():
                continue
            request_id: str | None = None
            output_path: Path | None = None
            run_input = None
            run_output = None
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Protocol message must be a JSON object.")
                if (
                    message.get("protocol_version")
                    != SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION
                ):
                    raise ValueError("Unsupported persistent SAM2 protocol version.")
                message_type = message.get("type")
                if message_type == "close":
                    return
                if message_type != "segment_frame":
                    raise ValueError(f"Unsupported message type: {message_type!r}.")

                request_id = str(message.get("request_id", "")).strip()
                if not request_id:
                    raise ValueError("segment_frame requires request_id.")
                input_path = Path(str(message["input_npz"])).expanduser().resolve()
                output_path = Path(str(message["output_npz"])).expanduser().resolve()
                run_input = read_sam2_image_batch_input_npz(input_path)
                _reset_peak_vram(torch, device)
                if run_input.requires_inference:
                    autocast_context = _make_autocast_context(torch, device)
                    with torch.inference_mode(), autocast_context:
                        with redirect_stdout(sys.stderr):
                            run_output = kernel.run(run_input)
                else:
                    run_output = empty_sam2_image_batch_output(run_input)
                write_sam2_image_batch_output_npz(output_path, run_output)
                _send_message(
                    output_stream,
                    "frame_result",
                    request_id=request_id,
                    output_npz=str(output_path),
                    diagnostics=_memory_diagnostics(torch, device),
                )
            except Exception as error:
                if output_path is not None:
                    output_path.unlink(missing_ok=True)
                _send_message(
                    output_stream,
                    "error",
                    request_id=request_id,
                    error_type=type(error).__name__,
                    message=str(error),
                )
            finally:
                run_output = None
                run_input = None


def main() -> int:
    _run_worker(_parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
