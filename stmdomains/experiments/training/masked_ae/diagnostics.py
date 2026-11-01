"""Post-freeze issue25 diagnostics, never a model or threshold selector.

All decoder comparisons use the same masked validation input, including AE21.
The validation data also selected checkpoints, so these are descriptive loss
checks, not held-out reconstruction or molecular-domain generalization.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from ...bundle import file_hash, write_json
from ..diagnostics import representation_summary
from ..local_ssl.diagnostics import CONTROL_CASES, interior_separation, pure_support_label
from ..predict import load_features, read_json
from .common import reporting_stage
from .evaluate import verify_freeze


EXAMPLE_SEED = 20261101
EXAMPLE_SCALES = (32, 48, 64)
RECONSTRUCTION_FAMILIES = ("ae", "ae_untrained", "mask25", "mask50")


def validation_examples(data):
    """First canonical validation ID at each frozen scale, independent of loss."""
    return [next(row for row in data.validation if row["scale_raw_px"] == scale)
            for scale in EXAMPLE_SCALES]


def reconstruction_diagnostics(runs, data, device, budget):
    import torch
    from ..models import load_model as load_ae
    from .fit import validation_batches, validation_identity
    from .models import MASK_RATIOS, apply_mask, load_model as load_masked, masked_losses

    examples = validation_examples(data)
    example_ids = {row["window_id"] for row in examples}
    batches = {family: validation_batches(data, family) for family in MASK_RATIOS}
    identities = {family: validation_identity(values) for family, values in batches.items()}
    if identities["mask25"]["image_content_sha256"] != identities["mask50"]["image_content_sha256"] or identities["mask25"]["mask_order_sha256"] != identities["mask50"]["mask_order_sha256"]:
        raise ValueError("Validation images or nested mask permutations differ")
    images, metrics = {}, []
    for run in budget.checked(runs):
        if run["regime"] != "transfer" or run["family"] not in RECONSTRUCTION_FAMILIES:
            continue
        initial = run["family"] == "ae_untrained"
        model = (load_ae(Path(run["directory"]), device=device) if run["family"] == "ae"
                 else load_masked(Path(run["directory"]), device=device, initial=initial))
        model.eval().requires_grad_(False)
        for task, values in batches.items():
            totals = dict(masked_squared_error=0., visible_squared_error=0., full_squared_error=0.,
                          masked_pixels=0, measured_pixels=0, windows=0)
            for batch in budget.checked(values):
                tensors = {name: batch[name].to(device) for name in ("inputs", "target", "mask", "measured")}
                with torch.inference_mode():
                    masked = apply_mask(tensors["inputs"], tensors["mask"], tensors["measured"])
                    prediction = model.predict(masked)
                    terms = masked_losses(prediction, tensors["target"], tensors["mask"], tensors["measured"])
                n_masked, n_measured = int(terms["masked_pixels"]), int(terms["measured_pixels"])
                totals["masked_squared_error"] += float(terms["masked_mse"]) * n_masked
                totals["visible_squared_error"] += float(terms["visible_mse"]) * (n_measured - n_masked)
                totals["full_squared_error"] += float(terms["full_mse"]) * n_measured
                totals["masked_pixels"] += n_masked
                totals["measured_pixels"] += n_measured
                totals["windows"] += len(masked)
                if run["seed"] == EXAMPLE_SEED:
                    for i, ident in enumerate(batch["window_ids"]):
                        if ident not in example_ids:
                            continue
                        per_example = masked_losses(prediction[i:i+1], tensors["target"][i:i+1],
                                                    tensors["mask"][i:i+1], tensors["measured"][i:i+1])
                        images[task, ident, run["family"]] = dict(
                            target=tensors["target"][i, 0].cpu().numpy(),
                            masked=masked[i, 0].cpu().numpy(), reconstruction=prediction[i, 0].cpu().numpy(),
                            masked_mse=float(per_example["masked_mse"]), full_mse=float(per_example["full_mse"]))
            metrics.append(dict(run_id=run["run_id"], family=run["family"], seed=run["seed"],
                checkpoint="initial" if initial else "selected", validation_task=task,
                artificial_mask_fraction=MASK_RATIOS[task], input="Same masked noisy image for every model",
                masked_mse=totals["masked_squared_error"] / totals["masked_pixels"],
                visible_mse=totals["visible_squared_error"] / (totals["measured_pixels"] - totals["masked_pixels"]),
                full_mse=totals["full_squared_error"] / totals["measured_pixels"], **totals))
        del model
        print("reconstruction diagnostics " + run["run_id"], flush=True)
    return metrics, identities, examples, images


def plot_reconstruction(target, examples, images):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    columns = ("target", "masked", "ae", "ae_untrained", "mask25", "mask50")
    names = ("Czysty cel", "Zakryte wejście", "AE21", "Wspólna inicjalizacja", "Maskowanie 25%", "Maskowanie 50%")
    fig, axes = plt.subplots(6, 6, figsize=(14, 15))
    for y, (task, row) in enumerate((task, row) for task in ("mask25", "mask50") for row in examples):
        ident = row["window_id"]
        reference = images[task, ident, "mask50"]
        for x, column in enumerate(columns):
            ax = axes[y, x]
            value = reference[column] if column in {"target", "masked"} else images[task, ident, column]["reconstruction"]
            ax.imshow(value, cmap="gray", vmin=0., vmax=1., interpolation="nearest")
            ax.set_xticks([])
            ax.set_yticks([])
            if column not in {"target", "masked"}:
                loss = images[task, ident, column]
                ax.set_xlabel(f"MSE mask: {loss['masked_mse']:.4f}\nMSE full: {loss['full_mse']:.4f}", fontsize=8)
            if y == 0:
                ax.set_title(names[x], fontsize=10)
        axes[y, 0].set_ylabel(f"{task}; okno {row['scale_raw_px']} px", fontsize=10)
    fig.suptitle("Stałe przykłady walidacyjne, ziarno 20261101\nIdentyczne maski i wejścia; rekonstrukcja nie jest oceną wykrywania domen", fontsize=12)
    fig.tight_layout(rect=(0., 0., 1., .96))
    fig.savefig(target, dpi=140)
    plt.close(fig)


def plot_curves(target, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=False)
    colors = {20261101: "tab:blue", 20261102: "tab:orange", 20261103: "tab:green"}
    records = []
    for path in sorted((output / "training").glob("*/*/z32/seed-*/run.json")):
        run = read_json(path)
        ax = axes[("mask25", "mask50").index(run["family"]), ("transfer", "transductive").index(run["regime"])]
        color = colors[run["seed"]]
        history = run["loss_history"]
        # Bin fixed consecutive100 optimization steps only for readable plotting.
        groups = [history[i:i+100] for i in range(0, len(history), 100)]
        ax.plot([g[-1]["step"] for g in groups], [np.mean([r["masked_mse"] for r in g]) for g in groups],
                color=color, alpha=.45, linestyle="--", label=f"{run['seed']} trening")
        validation = run.get("validation_history", [])
        if validation:
            ax.plot([r["step"] for r in validation], [r["masked_mse"] for r in validation],
                    color=color, label=f"{run['seed']} stała walidacja")
        if run.get("selected_step") is not None:
            ax.axvline(run["selected_step"], color=color, alpha=.25)
        ax.set_title(f"{run['family']} / {run['regime']}")
        ax.set_xlabel("Krok optymalizacji")
        ax.set_ylabel("MSE na zakrytych pikselach")
        ax.grid(alpha=.2)
        records.append(dict(file=str(path.relative_to(output)), sha256=file_hash(path),
                            selected_step=run.get("selected_step"), status=run["status"]))
    for ax in axes.flat:
        ax.legend(fontsize=7)
    fig.suptitle("Krzywe celu rekonstrukcji; każda proporcja maski ma własne zadanie\nWalidacja wybiera punkt transferu; transdukcja ma z góry ustaloną liczbę kroków", fontsize=12)
    fig.tight_layout(rect=(0., 0., 1., .93))
    fig.savefig(target, dpi=140)
    plt.close(fig)
    return records


def summarize(output, prepared, evaluation, *, device="cpu"):
    import torch
    from .fit import TrainingData

    output = Path(output).resolve()
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    with reporting_stage(output, "diagnostics") as budget:
        verify_freeze(output, check_budget=budget.check)
        plan = read_json(output / "plan.json")
        if file_hash(evaluation / "manifest.json") != plan["controls_evaluation_manifest_sha256"]:
            raise ValueError("Diagnostic control references differ from the frozen plan")
        groups = [r for r in read_json(output / "cache/index.json") if r["sampler"] == "grid" and r["scale_px"] == 48]
        runs = read_json(output / "features/index.json")
        runs += [dict(run_id=regime+"/fft", regime=regime, family="fft", seed=None, latent=0)
                 for regime in ("transfer", "transductive")]
        records = {r["sample_id"]: r for r in read_json(evaluation / "manifest.json")["controls"] if r["case"] in CONTROL_CASES}
        truths, caches = {}, {}
        for sid, record in records.items():
            path = evaluation / record["file"]
            if file_hash(path) != record["sha256"]:
                raise ValueError("Changed control truth: " + sid)
            with np.load(path, allow_pickle=False) as archive:
                truths[sid] = {name: archive[name] for name in ("domain_labels", "evaluation_valid")}
        for group in budget.checked(groups):
            folder = output / "cache" / group["group_id"]
            rows = read_json(folder / "rows.json.gz")
            cache = dict(rows=rows, by_regime={})
            for regime in ("transfer", "transductive"):
                with np.load(folder / (regime + ".npz"), allow_pickle=False) as archive:
                    cache["by_regime"][regime] = dict(indices=archive["available_indices"], brightness=archive["patches"].mean((1, 2)))
            sid = group["record"]["sample_id"]
            if sid in truths:
                cache["pure_labels"] = [pure_support_label(row, truths[sid]) for row in rows]
            caches[group["group_id"]] = cache
        feature_records, controls = [], []
        for run in budget.checked(runs):
            contents, brightness, frames = [], [], []
            for group in budget.checked(groups):
                cache = caches[group["group_id"]]
                content = load_features(output, run, group)
                if group["record"]["kind"] == "measurement":
                    value = cache["by_regime"][run["regime"]]
                    contents.append(content[value["indices"]])
                    brightness.extend(value["brightness"])
                    frames.extend([group["record"]["frame_number"]] * len(value["indices"]))
                elif "pure_labels" in cache:
                    truth_meta = records[group["record"]["sample_id"]]
                    controls.append(dict(run_id=run["run_id"], family=run["family"], regime=run["regime"], seed=run["seed"],
                        sample_id=truth_meta["sample_id"], case=truth_meta["case"], control_seed=truth_meta["seed"],
                        **interior_separation(content, cache["pure_labels"])))
            content = np.concatenate(contents)
            metrics = representation_summary(content, brightness, frames)
            if run["family"] == "local_ssl":
                channels = content.reshape(-1, 32, 49).transpose(0, 2, 1).reshape(-1, 32)
                std = channels.std(0)
                metrics["local_channel_std"] = dict(min=float(std.min()), mean=float(std.mean()), max=float(std.max()))
            feature_records.append(dict(run_id=run["run_id"], family=run["family"], regime=run["regime"], seed=run["seed"],
                **metrics, scope="All available real48grid windows of24fields; descriptive, not held-out generalization"))
            print("feature diagnostics " + run["run_id"], flush=True)
        validation, identities, examples, images = reconstruction_diagnostics(runs, TrainingData(prepared, "transfer"), device, budget)
        figures = output / "figures"
        figures.mkdir(exist_ok=True)
        for name in ("masked-reconstruction.png", "validation-curves.png"):
            if (figures / name).exists():
                raise FileExistsError(figures / name)
        plot_reconstruction(figures / "masked-reconstruction.png", examples, images)
        curves = plot_curves(figures / "validation-curves.png", output)
        result = dict(schema="stmdomains-masked-ae25-diagnostics-v1", freeze_sha256=file_hash(output / "frozen-predictions.json"),
            source_sha256=file_hash(Path(__file__)), features=feature_records, control_interiors=controls,
            reconstruction_validation=validation, validation_inputs=identities,
            reconstruction_examples=dict(seed=EXAMPLE_SEED, selection="First canonical validation window at each32/48/64 scale; fixed before loss access",
                windows=[{key: row[key] for key in ("window_id", "sample_id", "scale_raw_px")} for row in examples],
                display="Fixed gray[0,1] range; metrics use original unclipped output tensors"),
            training_curves=curves, figure_sha256={p.name: file_hash(p) for p in figures.glob("*.png")},
            calibration=dict(model_angle_available=False, model_spacing_available=False,
                reason="AE/SSL emit descriptors, not calibrated physical angles, spacing or material labels"),
            limitations=["Reconstruction uses checkpoint-selection validation data, not new held-out observations",
                "AE21, both masked tasks and initial models see identical masked inputs for each validation task",
                "MSE on masked/visible/full measured pixels is reported separately and does not measure domain detection",
                "Pure-support interior separation omits mixed windows and does not establish boundary accuracy",
                "Feature brightness/frame correlations are descriptive and do not establish causality"],
            resources=budget.measurements())
        write_json(output / "feature-diagnostics.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    result = summarize(args.output, args.prepared, args.evaluation or args.output / "controls/evaluation", device=args.device)
    print(json.dumps(dict(features=len(result["features"]), reconstruction_comparisons=len(result["reconstruction_validation"]))))


if __name__ == "__main__":
    main()
