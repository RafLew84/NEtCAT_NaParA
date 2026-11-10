"""Prepare issue-20 windows from the immutable issue-14 analysis tree only."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import resource
import shutil
import tempfile
import time

import numpy as np
import scipy

from ..bundle import arrays_hash, file_hash, load_sample, write_json
from ..real_input import PILOT_NUMBERS
from .data import (SPLIT_SPEC, augmented_pair, extract_patch, fit_normalizers,
                   json_hash, verify_split, window_records)


def prepare(analysis: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError(f"Use a fresh output directory: {out}")
    start = time.perf_counter()
    source = json.loads((analysis / "manifest.json").read_text())
    selected = [r for r in source["samples"] if r["kind"] == "measurement"]
    if sorted(r["frame_number"] for r in selected) != list(PILOT_NUMBERS):
        raise ValueError("Expected exactly the audited 24-frame pilot")
    samples = []
    for item in sorted(selected, key=lambda r: r["frame_number"]):
        ident = f'ttmapp-{item["frame_number"]:03}'
        if item["sample_id"] != ident or item["file"] != f"samples/{ident}.npz":
            raise ValueError("Unexpected audited sample identity or relative path")
        record, arrays = load_sample(analysis, item["sample_id"])
        if record["shape_hw"] != [256, 256] or record["expanded_shape_hw"] != [408, 480]:
            raise ValueError("Unexpected original or registered geometry")
        if list(arrays["image"].shape) != record["shape_hw"]:
            raise ValueError("Image shape disagrees with declared geometry")
        if record["coordinate_system"] != "raw_edge_xy" or record["position_unit"] != "px":
            raise ValueError("Unsupported input coordinates")
        if record["pixel_spacing_xy"] != [1., 1.]:
            raise ValueError("Unexpected pixel spacing for the audited measurement")
        origin = np.asarray(record["origin_in_expanded_xy"])
        if origin.shape != (2,) or not np.isfinite(origin).all():
            raise ValueError("Missing registered origin")
        if np.any(origin < 0) or np.any(origin + [256, 256] > [480, 408]):
            raise ValueError("Registered field escapes the declared canvas geometry")
        samples.append((record, arrays))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".training20-", dir=out.parent) as temporary:
        staging = Path(temporary) / "prepared"
        staging.mkdir()
        # The immutable split is written before any extraction or normalization.
        write_json(staging / "split.json", SPLIT_SPEC)
        normalizers = fit_normalizers(samples)
        write_json(staging / "normalization.json", normalizers)
        (staging / "analysis/samples").mkdir(parents=True)
        for record, _ in samples:
            shutil.copyfile(analysis / record["file"], staging / "analysis" / record["file"])
        write_json(staging / "analysis/manifest.json", {**source, "samples": [r for r, _ in samples]})
        rows = []
        grid_digest = []
        available_count = 0
        for record, arrays in samples:
            frame_rows = window_records(record, arrays)
            for row in frame_rows:
                row["patch_content_sha256"] = None
                if row["available"]:
                    patch = extract_patch(arrays, row)
                    row["patch_content_sha256"] = arrays_hash({"patch": patch})
                    available_count += 1
                if row["sampler"] == "grid":
                    grid_digest.append(row)
            rows.extend(frame_rows)
        with (staging / "windows.jsonl").open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        split_audit = verify_split(rows)
        lookup = {r["sample_id"]: arrays for r, arrays in samples}
        eligible = [r for r in rows if r["sampler"] == "grid" and r["scale_raw_px"] == 64 and r["transfer_split"] == "train"]
        if len(eligible) < 2:
            raise ValueError("Insufficient real training windows for the technical probe")
        chosen = [eligible[i] for i in np.linspace(0, len(eligible) - 1, min(128, len(eligible)), dtype=int)]
        batch = np.stack([extract_patch(lookup[r["sample_id"]], r, normalizers["transfer"]) for r in chosen])[:, None]
        np.savez_compressed(staging / "gpu-batch.npz", patches=batch,
                            window_ids=np.array([r["window_id"] for r in chosen]))
        # Check data augmentation reproducibility without touching any reference.
        sample_row = chosen[0]
        first, meta = augmented_pair(lookup[sample_row["sample_id"]], sample_row, normalizers["transfer"], np.random.default_rng(20261101))
        repeated, repeated_meta = augmented_pair(lookup[sample_row["sample_id"]], sample_row, normalizers["transfer"], np.random.default_rng(20261101))
        if not np.array_equal(first, repeated) or meta != repeated_meta:
            raise AssertionError("Augmentation is not reproducible")
        manifest = dict(
            schema="stmdomains-training-preparation-v1",
            source_analysis_manifest_sha256=file_hash(analysis / "manifest.json"),
            analysis_manifest_sha256=file_hash(staging / "analysis/manifest.json"),
            split_file="split.json", split_sha256=file_hash(staging / "split.json"),
            split_content_sha256=json_hash(SPLIT_SPEC),
            normalization_file="normalization.json", normalization_sha256=file_hash(staging / "normalization.json"),
            windows_file="windows.jsonl", windows_sha256=file_hash(staging / "windows.jsonl"),
            grid_windows_content_sha256=json_hash(grid_digest),
            gpu_batch_file="gpu-batch.npz", gpu_batch_sha256=file_hash(staging / "gpu-batch.npz"),
            gpu_batch_content_sha256=arrays_hash({"patches": batch}),
            sample_count=len(samples), window_count=len(rows), available_window_count=available_count,
            counts=dict(Counter(f'{r["sampler"]}/s{r["scale_raw_px"]}/{"available" if r["available"] else "unavailable"}' for r in rows)),
            split_audit=split_audit,
            sampling_policy="grid primary; centers separate; uniform frame then eligible window with replacement; scales are not independent observations",
            normalization_policy="transfer: train spatial and temporal blocks only; transductive: all 24 fields; no per-test fitting",
            synthetic_intensity_adapter="raw_units = low + (high-low)*(0.5+0.4*renderer_signal); then frozen normalizer; fixed convention, no synthetic fit",
            augmentation=dict(translation_raw_px=[-2, 2], gain=[.9, 1.1], offset=[-.1, .1], noise_sigma=[0, .03],
                              rotate=False, rescale=False, flip=False, reference_access=False,
                              correspondence="explicit translation and scale; never assume neighbors share a domain"),
            exclusions="incomplete support and cross-split supports retained as explicit rows; no padding",
            fit_labels="none; no reference files are accepted or read",
            code_sha256={p.name: file_hash(p) for p in (Path(__file__), Path(__file__).with_name("data.py"))},
            environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        )
        write_json(staging / "manifest.json", manifest)
        write_json(staging / "resources.json", dict(elapsed_seconds=time.perf_counter() - start,
                                                     peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                                     rss_scope="single preparation process including imports"))
        staging.rename(out)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.analysis, args.out)
    print(json.dumps({k: result[k] for k in ("sample_count", "window_count", "available_window_count", "split_audit")}, indent=2))


if __name__ == "__main__":
    main()
