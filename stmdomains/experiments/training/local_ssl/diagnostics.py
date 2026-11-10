"""Post-freeze representation diagnostics for issue22; no parameter selection.

The SSL channels are neither molecular angles nor structural classes. Known
control labels are used only here, after prediction freeze, to describe whether
pure interiors have distinguishable descriptors. Actual boundary-edge scoring
belongs to the common evaluator, including windows that cross an interface.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

import numpy as np

from ...bundle import file_hash, write_json
from ..diagnostics import representation_summary
from ..predict import load_features, read_json


FAMILY_LABELS = {
    "fft": "FFT — odniesienie",
    "local_ssl": "Lokalne SSL — po treningu",
    "local_ssl_untrained": "Ten sam encoder — bez treningu",
}
CONTROL_CASES = ("two_orientations", "orientation_8deg", "different_spacing", "phase_boundary")


@contextmanager
def reporting_stage(output: Path, name: str):
    """Account reporting against the same original21+22 CPU ceiling."""
    from .evaluate import PostprocessBudget
    target = output / f"{name}.resources.json"
    if target.exists():
        raise FileExistsError(target)
    budget = PostprocessBudget(output)
    status = "failed"
    try:
        budget.check()
        yield budget
        budget.check()
        status = "completed"
    finally:
        write_json(target, dict(stage=name, status=status, **budget.measurements()))


def pure_support_label(row: dict, truth: dict) -> int:
    """A positive label requires one valid domain over the entire support."""
    if not row["available"]:
        return 0
    x0, y0, x1, y1 = row["support_xyxy"]
    x0, y0, x1, y1 = int(np.floor(x0)), int(np.floor(y0)), int(np.ceil(x1)), int(np.ceil(y1))
    labels = truth["domain_labels"]
    if x0 < 0 or y0 < 0 or x1 > labels.shape[1] or y1 > labels.shape[0] or x0 >= x1 or y0 >= y1:
        return 0
    region = labels[y0:y1, x0:x1]
    if (region[0, 0] <= 0 or not truth["evaluation_valid"][y0:y1, x0:x1].all()
            or not np.all(region == region[0, 0])):
        return 0
    return int(region[0, 0])


def interior_separation(features, labels) -> dict:
    """Describe pure-part separation in the graph's L2 input geometry.

    This does not fit a classifier or optimize a decision threshold. In
    particular a phase boundary may have indistinguishable pure interiors:
    detecting its crossing still requires the separately measured graph edges.
    """
    values = np.asarray(features, dtype=np.float64)
    labels = np.asarray(labels, dtype=int)
    norms = np.linalg.norm(values, axis=1)
    good = np.isfinite(values).all(axis=1) & (norms > 0) & (labels > 0)
    normalized = values[good] / norms[good, None]
    labels = labels[good]
    groups, means, variances = [], [], []
    for label in sorted(set(labels)):
        group = normalized[labels == label]
        mean = group.mean(0)
        variance = float(np.mean(np.sum((group - mean) ** 2, axis=1)))
        groups.append(dict(part=int(label), elements=len(group), mean_squared_radius=variance))
        means.append(mean)
        variances.append(variance)
    distance = float(np.sum((means[0] - means[1]) ** 2)) if len(means) == 2 else None
    dispersion = float(np.mean(variances)) if len(variances) == 2 else None
    ratio = distance / dispersion if dispersion is not None and dispersion > 1e-16 else None
    return dict(parts=groups, squared_centroid_distance=distance,
                mean_within_part_squared_radius=dispersion, separation_ratio=ratio,
                ratio_unavailable_reason="missing_two_parts_or_zero_dispersion" if ratio is None else None,
                scope="Full effective support in one positive truth part; L2 descriptors, no fitted classifier",
                interpretation="Descriptive interior distinction, not boundary accuracy or a physical angle/spacing estimate")


def summarize(output: Path, prepared: Path, evaluation: Path, *, device="cpu"):
    import torch
    from .evaluate import verify_freeze
    from .fit import SSLTrainingData, validate
    from .models import load_model

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    with reporting_stage(output, "diagnostics") as budget:
        verify_freeze(output, check_budget=budget.check)
        groups = [group for group in read_json(output / "cache/index.json")
                  if group["sampler"] == "grid" and group["scale_px"] == 48]
        runs = [dict(run_id=f"{regime}/fft", family="fft", regime=regime, seed=None, latent=0)
                for regime in ("transfer", "transductive")] + read_json(output / "features/index.json")
        records = {record["sample_id"]: record for record in read_json(evaluation / "manifest.json")["controls"]
                   if record["case"] in CONTROL_CASES}
        truths, caches = {}, {}
        for sample_id, record in records.items():
            path = evaluation / record["file"]
            if file_hash(path) != record["sha256"]:
                raise ValueError("Changed control truth: " + sample_id)
            with np.load(path, allow_pickle=False) as archive:
                truths[sample_id] = {key: archive[key] for key in ("domain_labels", "evaluation_valid")}
        for group in groups:
            budget.check()
            folder = output / "cache" / group["group_id"]
            rows = read_json(folder / "rows.json.gz")
            cache = dict(rows=rows, by_regime={})
            for regime in ("transfer", "transductive"):
                with np.load(folder / f"{regime}.npz", allow_pickle=False) as archive:
                    cache["by_regime"][regime] = dict(indices=archive["available_indices"],
                                                   brightness=archive["patches"].mean((1, 2)))
            if group["record"]["sample_id"] in truths:
                truth = truths[group["record"]["sample_id"]]
                cache["pure_labels"] = [pure_support_label(row, truth) for row in rows]
            caches[group["group_id"]] = cache
        features, controls, checkpoints = [], [], []
        validation = SSLTrainingData(prepared, "transfer").validation_batches()
        for run in runs:
            budget.check()
            contents, brightness, frames = [], [], []
            for group in groups:
                budget.check()
                cache = caches[group["group_id"]]
                content = load_features(output, run, group)
                if group["record"]["kind"] == "measurement":
                    values = cache["by_regime"][run["regime"]]
                    contents.append(content[values["indices"]])
                    brightness.extend(values["brightness"])
                    frames.extend([group["record"]["frame_number"]] * len(values["indices"]))
                elif "pure_labels" in cache:
                    record = records[group["record"]["sample_id"]]
                    controls.append(dict(run_id=run["run_id"], family=run["family"], regime=run["regime"],
                                         seed=run["seed"], sample_id=record["sample_id"], case=record["case"],
                                         control_seed=record["seed"], **interior_separation(content, cache["pure_labels"])))
            content = np.concatenate(contents)
            result = representation_summary(content, brightness, frames)
            if run["family"] != "fft":
                channels = content.reshape(-1, run["latent"], 49).transpose(0, 2, 1).reshape(-1, run["latent"])
                std = channels.std(0)
                result["local_channel_std"] = dict(min=float(std.min()), mean=float(std.mean()), max=float(std.max()))
            features.append(dict(run_id=run["run_id"], family=run["family"], regime=run["regime"],
                                 seed=run["seed"], latent=run["latent"], **result,
                                 scope="All available real48grid windows in24fields; descriptive, not held-out generalization"))
            if run["family"] != "fft" and run["regime"] == "transfer":
                initial = run["family"] == "local_ssl_untrained"
                model = load_model(Path(run["directory"]), device=device, step=0 if initial else None)
                budget.check()
                metrics = validate(model, validation, device)
                checkpoints.append(dict(run_id=run["run_id"], family=run["family"], seed=run["seed"],
                                        checkpoint="initial" if initial else "selected", validation=metrics))
                del model
            print("diagnostics " + run["run_id"], flush=True)
        result = dict(schema="stmdomains-issue22-feature-diagnostics-v1",
                      freeze_sha256=file_hash(output / "frozen-predictions.json"), source_sha256=file_hash(Path(__file__)),
                      features=features, control_interiors=controls, checkpoints=checkpoints,
                      orientation=dict(model_angle_available=False, model_spacing_available=False,
                                       reason="SSL emits an orientation-sensitive local map, not a calibrated angle/spacing head",
                                       separate_evidence="Frozen windowed ACF in the prediction evidence; not an SSL angle"),
                      actual_neighbor_edges="See evaluation local relations/boundary metrics, including mixed-support windows",
                      controls_status="Previously viewed development realizations; fixed original20 plan, no parameter tuning",
                      no_checkpoint_or_threshold_selection=True)
        write_json(output / "feature-diagnostics.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--evaluation", type=Path, default=Path(".scratch/training-20/controls/evaluation"))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    result = summarize(args.output, args.prepared, args.evaluation, device=args.device)
    print(json.dumps(dict(features=len(result["features"]), controls=len(result["control_interiors"]),
                          checkpoints=len(result["checkpoints"]))))


if __name__ == "__main__":
    main()
