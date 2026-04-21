#!/usr/bin/env python3
"""Run deterministic DexiNed stub inference for NanoTrack in a dedicated interpreter."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.edges.contract import DexiNedRunInput, DexiNedRunOutput
else:
    from .contract import DexiNedRunInput, DexiNedRunOutput


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack DexiNed subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--checkpoint", required=True, help="Path to a DexiNed checkpoint.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local DexiNed repo.")
    parser.add_argument("--device", default="auto", help="Torch device, e.g. auto, cuda, cuda:0, cpu.")
    return parser.parse_args()


def _load_input(path: Path) -> DexiNedRunInput:
    with np.load(path, allow_pickle=False) as payload:
        input_payload = {key: payload[key] for key in payload.files}
    return DexiNedRunInput.from_npz_payload(input_payload)


def _compute_polygon_edge_mask(polygon_mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(polygon_mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("polygon_mask must have shape [H, W].")
    if mask.shape[0] < 2 or mask.shape[1] < 2:
        return mask.copy()

    interior = mask.copy()
    interior &= np.roll(mask, 1, axis=0)
    interior &= np.roll(mask, -1, axis=0)
    interior &= np.roll(mask, 1, axis=1)
    interior &= np.roll(mask, -1, axis=1)

    interior[0, :] = False
    interior[-1, :] = False
    interior[:, 0] = False
    interior[:, -1] = False
    return mask & ~interior


def _build_stub_output(run_input: DexiNedRunInput, checkpoint_path: str | Path) -> DexiNedRunOutput:
    frame_count = int(run_input.frames.shape[0])
    polygon_mask = np.asarray(run_input.polygon_mask, dtype=bool)
    edge_binary_2d = _compute_polygon_edge_mask(polygon_mask)

    edge_prob_2d = np.zeros(polygon_mask.shape, dtype=np.float32)
    edge_prob_2d[polygon_mask] = 0.15
    edge_prob_2d[edge_binary_2d] = 0.95

    edge_prob = np.repeat(edge_prob_2d[None, :, :], frame_count, axis=0)
    effective_threshold = 0.5 if run_input.threshold is None else float(run_input.threshold)
    edge_binary = edge_prob >= effective_threshold

    return DexiNedRunOutput(
        edge_prob=edge_prob,
        edge_binary=edge_binary,
        model_name="dexined_stub",
        checkpoint_name=Path(checkpoint_path).name,
    )


def main() -> int:
    args = _parse_args()
    run_input = _load_input(Path(args.input_npz))
    run_output = _build_stub_output(run_input, args.checkpoint)
    Path(args.output_npz).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_npz, **run_output.to_npz_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
