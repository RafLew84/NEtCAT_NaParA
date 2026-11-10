"""Small evidence manifest and a geometry figure, without domain predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ..bundle import file_hash, load_sample, write_json
from .data import read_windows, spatial_band, temporal_split


def geometry_figure(data: Path, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    rows = read_windows(data / "windows.jsonl")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), constrained_layout=True)
    for ax, number in zip(axes, (1, 150, 250)):
        ident = f"ttmapp-{number:03}"
        record, arrays = load_sample(data / "analysis", ident)
        image = arrays["image"]
        low, high = np.quantile(image, [.02, .98])
        ax.imshow(image, cmap="gray", vmin=low, vmax=high, extent=[0, 256, 256, 0])
        split = temporal_split(number)
        left, right = np.array(spatial_band(split)) - record["origin_in_expanded_xy"][0]
        left, right = max(0, left), min(256, right)
        ax.add_patch(Rectangle((left, 0), right - left, 256, fill=False, edgecolor="#40dce6", linewidth=2))
        selected = [r for r in rows if r["sample_id"] == ident and r["sampler"] == "grid" and r["scale_raw_px"] == 48 and r["transfer_split"] == split]
        xy = np.array([r["raw_edge_xy"] for r in selected]).reshape(-1, 2)
        ax.scatter(xy[:, 0], xy[:, 1], s=8, color="#40dce6")
        if selected:
            x0, y0, x1, y1 = selected[len(selected) // 2]["support_xyxy"]
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#ffcc55", linewidth=1.5))
        ax.set(title=f"Frame {number}: {split}\n{len(selected)} grid windows at 48 px", xlabel="raw x [px]", ylabel="raw y [px]", xlim=(0, 256), ylim=(256, 0))
    fig.suptitle("Issue 20: held-out geometry, not domain predictions\nCyan: allowed band / centers; yellow: one window including augmentation support")
    fig.savefig(out, dpi=140)
    plt.close(fig)


def summarize(root: Path) -> dict:
    data = json.loads((root / "data/manifest.json").read_text())
    verified = json.loads((root / "data/verification.json").read_text())
    controls = json.loads((root / "controls/audit.json").read_text())
    gpu = json.loads((root / "gpu/gpu-probe.json").read_text())
    if not gpu["gpu_requirement_met"]:
        raise ValueError("GPU requirement was not satisfied")
    if gpu["input_sha256"] != data["gpu_batch_sha256"]:
        raise ValueError("GPU report refers to a different batch")
    geometry_figure(root / "data", root / "geometry.png")
    files = ("data/manifest.json", "data/verification.json", "data/normalization.json",
             "data/split.json", "controls/audit.json", "gpu/gpu-probe.json", "geometry.png")
    per_batch = {}
    for batch in (32, 64, 128):
        measurements = [row for row in gpu["measurements"] if row["batch_size"] == batch]
        per_batch[str(batch)] = dict(
            seconds_per_step_min=min(r["seconds_per_step"] for r in measurements),
            seconds_per_step_max=max(r["seconds_per_step"] for r in measurements),
            max_cuda_allocated_bytes=max(r["cuda_peak_allocated_bytes"] for r in measurements),
            max_cuda_reserved_bytes=max(r["cuda_peak_reserved_bytes"] for r in measurements),
            max_rss_bytes=max(r["rss_peak_bytes"] for r in measurements),
        )
    package = Path(__file__).parent
    evidence = dict(
        schema="stmdomains-training20-evidence-v1", preparation_complete=True,
        domain_models_trained=False, detector_selected=False,
        local_artifact_root=str(root.resolve()), artifacts_sha256={name: file_hash(root / name) for name in files},
        source_mpp_sha256=verified["source_mpp_sha256"], source_session_sha256=verified["source_session_sha256"],
        code_sha256={p.name: file_hash(p) for p in sorted(package.iterdir()) if p.suffix in (".py", ".json", ".sh")},
        data=dict(samples=data["sample_count"], windows=data["window_count"], available=data["available_window_count"],
                  counts=data["counts"], normalizers=json.loads((root / "data/normalization.json").read_text()), split_audit=data["split_audit"]),
        verification={k: verified[k] for k in ("real_source_arrays_identical", "patches_recomputed", "grid_records_identical_without_centers", "reference_open_denied", "complete_replay_identical")},
        controls=dict(sample_count=controls["sample_count"], case_count=controls["case_count"], seeds=controls["seeds"],
                      analysis_manifest_sha256=controls["analysis_manifest_sha256"], evaluation_manifest_sha256=controls["evaluation_manifest_sha256"]),
        gpu=dict(device=gpu["gpu"], torch=gpu["torch"], cuda_runtime=gpu["cuda_runtime"],
                 resume_all_passed=all(r["passed"] for r in gpu["resume"]), seeds=gpu["seeds"],
                 resume_comparisons=[dict(seed=r["seed"], comparison=r["comparison"]) for r in gpu["resume"]],
                 operations=gpu["operations"], per_batch=per_batch,
                 total_wall_seconds=gpu["total_wall_seconds_including_workers"]),
    )
    write_json(root / "evidence.json", evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.root)
    print(json.dumps(dict(data=result["data"]["windows"], controls=result["controls"]["sample_count"], gpu=result["gpu"]["resume_all_passed"])))


if __name__ == "__main__":
    main()
