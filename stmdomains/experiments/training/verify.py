"""Audit real inputs, replay crops with denied reference access, and ablate centers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from ..bundle import arrays_hash, file_hash, load_sample, write_json
from ..real_input import load_ttmapp
from .data import extract_patch, fit_normalizers, read_windows, verify_split, window_records
from .prepare import prepare


def deny_references(event, args):
    if event != "open" or not isinstance(args[0], (str, bytes)):
        return
    path = str(args[0]).lower()
    if "/evaluation/" in path or "domain_review" in path or "partial-domain-reference" in path:
        raise PermissionError(f"Reference access is forbidden during training preparation: {path}")


def verify(root: Path, source: Path, replay: Path, mpp: Path, session: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    for key in ("split", "normalization", "windows", "gpu_batch"):
        if file_hash(root / manifest[f"{key}_file"]) != manifest[f"{key}_sha256"]:
            raise AssertionError(f"Corrupt prepared {key}")
    raw_samples, _, raw_audit = load_ttmapp(mpp, session)
    original = {r["sample_id"]: arrays for r, arrays in raw_samples}
    original_records = {r["sample_id"]: r for r, _ in raw_samples}
    records = json.loads((root / "analysis/manifest.json").read_text())["samples"]
    samples = [load_sample(root / "analysis", r["sample_id"]) for r in records]
    if any(arrays_hash(arrays) != arrays_hash(original[r["sample_id"]]) for r, arrays in samples):
        raise AssertionError("Prepared inputs differ from the audited raw MPP/session")
    for record, _ in samples:
        for key in ("frame_number", "frame_index", "source_frame_index", "shape_hw",
                    "origin_in_expanded_xy", "expanded_shape_hw", "pixel_spacing_xy",
                    "registration_status", "registration_quality"):
            if record[key] != original_records[record["sample_id"]][key]:
                raise AssertionError(f"Prepared geometry differs from the audited session: {key}")
    rows = read_windows(root / "windows.jsonl")
    split = verify_split(rows)
    normalizers = json.loads((root / "normalization.json").read_text())
    if fit_normalizers(samples) != normalizers:
        raise AssertionError("Normalization replay mismatch")
    lookup = {r["sample_id"]: arrays for r, arrays in samples}
    checked = 0
    for row in rows:
        if row["available"]:
            patch = extract_patch(lookup[row["sample_id"]], row)
            if arrays_hash({"patch": patch}) != row["patch_content_sha256"]:
                raise AssertionError("Patch content replay mismatch")
            checked += 1
    grid_checked = 0
    normalizer_ablated_samples = []
    for record, arrays in samples:
        ablated = dict(arrays, centers_xy=np.empty((0, 2)), boxes_xyxy=np.empty((0, 4)), object_ids=np.empty(0, dtype="U64"))
        full_grid = [r for r in window_records(record, arrays) if r["sampler"] == "grid"]
        empty_grid = window_records(record, ablated)
        if full_grid != empty_grid:
            raise AssertionError("Centers changed grid windows")
        for row in empty_grid:
            if row["available"] and not np.array_equal(extract_patch(arrays, row), extract_patch(ablated, row)):
                raise AssertionError("Centers changed grid pixels")
        grid_checked += len(empty_grid)
        normalizer_ablated_samples.append((record, ablated))
    if fit_normalizers(normalizer_ablated_samples) != normalizers:
        raise AssertionError("Centers changed normalizers")
    # The replay runs after installing an OS-level Python audit hook. No loader
    # for evaluation or manual reference inputs is called by this code path.
    sys.addaudithook(deny_references)
    denied = False
    try:
        (source.parent / "evaluation/manifest.json").read_text()
    except PermissionError:
        denied = True
    if not denied:
        raise AssertionError("Reference access guard did not work")
    replay_manifest = prepare(source, replay)
    replay_keys = ("split_sha256", "normalization_sha256", "windows_sha256", "grid_windows_content_sha256", "gpu_batch_sha256")
    if any(manifest[key] != replay_manifest[key] for key in replay_keys):
        raise AssertionError("Full preparation changed when reference access was denied")
    report = dict(
        schema="stmdomains-training-verification-v1", real_source_arrays_identical=len(samples),
        source_mpp_sha256=raw_audit["source_mpp_sha256"], source_session_sha256=raw_audit["source_session_sha256"],
        patches_recomputed=checked, grid_records_identical_without_centers=grid_checked,
        normalizers_identical_without_centers=True, reference_open_denied=denied,
        complete_replay_identical=list(replay_keys), split_audit=split,
        preparation_manifest_sha256=file_hash(root / "manifest.json"),
        replay_manifest_sha256=file_hash(replay / "manifest.json"),
        source_code_sha256=file_hash(Path(__file__)),
    )
    write_json(root / "verification.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--mpp", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.analysis, args.replay, args.mpp, args.session)
    print(json.dumps({k: v for k, v in result.items() if k != "split_audit"}, indent=2))


if __name__ == "__main__":
    main()
