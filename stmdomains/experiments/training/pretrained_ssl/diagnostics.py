"""Post-freeze DINO26 descriptor diagnostics; no new fit or model inference.

Teacher/student/base validation snapshots already use fixed, hashed input
views. The moving self-distillation CE and head entropies describe training;
they neither select checkpoints nor establish domain accuracy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ...bundle import file_hash, write_json
from ..diagnostics import representation_summary
from ..predict import load_features, read_json
from ..masked_ae.evaluate import verify_freeze
from .common import reporting_stage


COLORS = {20261101: "tab:blue", 20261102: "tab:orange", 20261103: "tab:green"}
ROLES = ("base", "student", "teacher")


def plot_training(path, runs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for run in runs:
        col = ("transfer", "transductive").index(run["regime"])
        color = COLORS[run["seed"]]
        history = run.get("loss_history", [])
        chunks = [history[i:i+100] for i in range(0, len(history), 100)]
        if chunks:
            axes[0, col].plot([c[-1]["step"] for c in chunks], [np.mean([r["loss"] for r in c]) for c in chunks],
                              color=color, linestyle="--", alpha=.5, label=f"{run['seed']} trening")
        validation = run.get("validation_history", [])
        if validation:
            steps = [r["step"] for r in validation]
            axes[0, col].plot(steps, [r["loss"] for r in validation], color=color, label=f"{run['seed']} stałe wejścia")
            axes[1, col].plot(steps, [r["head_mutual_information"] for r in validation], color=color,
                              label=f"{run['seed']} MI całej próbki")
            axes[1, col].plot(steps, [r["head_position_conditional_information"] for r in validation], color=color,
                              linestyle=":", label=f"{run['seed']} MI przy stałej pozycji")
        if run["status"] != "completed":
            axes[0, col].annotate(f"{run['seed']}: próba nieukończona", (0.02, .96-.06*(run["seed"]-20261101)),
                                  xycoords="axes fraction", fontsize=8, color=color)
    for col, regime in enumerate(("transfer", "transductive")):
        axes[0, col].set_title(regime)
        axes[0, col].set_ylabel("CE ruchomego nauczyciela (diagnostyka)")
        axes[1, col].set_ylabel("H(średnie p) − średnie H(p), naty")
        for row in (0, 1):
            axes[row, col].set_xlabel("Krok; główny checkpoint zawsze 1000")
            axes[row, col].grid(alpha=.2)
            if axes[row, col].lines:
                axes[row, col].legend(fontsize=7)
    fig.suptitle("Samodestylacja26: krzywe nie wybierają checkpointu\nWysoka MI lub niska CE nie potwierdzają wykrywania domen", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(path, dpi=140)
    plt.close(fig)


def final_snapshots(runs):
    result = []
    for run in runs:
        history = run.get("validation_history", [])
        selected = next((r for r in history if r["step"] == 1000), None) if run["status"] == "completed" else None
        diagnostic = selected or (history[-1] if history else None)
        result.append(dict(run_id=run["run_id"], regime=run["regime"], seed=run["seed"], status=run["status"],
            primary_checkpoint_available=selected is not None, diagnostic_step=None if diagnostic is None else diagnostic["step"],
            validation_inputs=run.get("validation"), metrics=diagnostic,
            unavailable_reason=None if selected is not None else run.get("stop_reason", "adaptation_incomplete"),
            scope="Fixed validation views from20" if run["regime"] == "transfer" else "The same fixed windows, part of transductive training data"))
    return result


def plot_descriptors(path, snapshots):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    role_colors = {"base": "gray", "student": "tab:orange", "teacher": "tab:blue"}
    x = np.arange(len(snapshots))
    labels = [f"{r['regime']}\n{r['seed']}" + ("*" if not r["primary_checkpoint_available"] else "") for r in snapshots]
    for i, role in enumerate(ROLES):
        values = [(r["metrics"] or {}).get(role + "_descriptor", {}) for r in snapshots]
        for axis, field in ((axes[0, 0], "std_mean"), (axes[0, 1], "effective_rank")):
            axis.bar(x+(i-1)*.23, [v.get(field, np.nan) for v in values], width=.22, color=role_colors[role], label=role)
        if role != "base":
            axes[1, 0].bar(x+(i-1.5)*.25, [v.get("l2_mse_to_frozen", np.nan) for v in values], width=.24, color=role_colors[role], label=role)
    for r in snapshots:
        per_scale = (r["metrics"] or {}).get("teacher_descriptor", {}).get("per_scale", {})
        if per_scale:
            scales = sorted(per_scale, key=int)
            axes[1, 1].plot([int(s) for s in scales], [per_scale[s]["effective_rank"] for s in scales], marker="o",
                color=COLORS[r["seed"]], linestyle="-" if r["regime"] == "transfer" else "--",
                label=f"{r['regime']} {r['seed']}" + ("*" if not r["primary_checkpoint_available"] else ""))
    for axis in (axes[0, 0], axes[0, 1], axes[1, 0]):
        axis.set_xticks(x, labels, fontsize=8)
        axis.legend(fontsize=8)
        axis.grid(axis="y", alpha=.2)
    axes[0, 0].set_ylabel("Średnie STD deskryptora mean384 po wejściach")
    axes[0, 1].set_ylabel("Ranga efektywna wycentrowanych opisów")
    axes[1, 0].set_ylabel("MSE wektorów L2 względem frozen")
    axes[1, 1].set_xlabel("Rozmiar surowego okna, px")
    axes[1, 1].set_ylabel("Teacher: ranga osobno dla każdej skali")
    axes[1, 1].grid(alpha=.2)
    if axes[1, 1].lines:
        axes[1, 1].legend(fontsize=7)
    fig.suptitle("Opisy na tych samych stałych wejściach; zmiana wektora nie oznacza poprawy domen\n* Ostatnia dostępna diagnostyka nieukończonej próby, bez zastępczej predykcji", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(path, dpi=140)
    plt.close(fig)


def summarize(output):
    output = Path(output).resolve()
    with reporting_stage(output, "diagnostics") as budget:
        frozen = verify_freeze(output, check_budget=budget.check)
        reports = {}
        for path in sorted((output / "training").glob("*/dino_adapted/seed-*/run.json")):
            if file_hash(path) != frozen["files"][str(path.relative_to(output))]:
                raise ValueError("Training diagnostic report changed after freeze")
            run = read_json(path)
            reports[run["run_id"]] = run
        registry = read_json(output / "training/registry.json")
        outcomes = {r["run_id"]: r for r in registry["outcomes"]}
        specs = read_json(output / "plan.json")["run_specs"]
        if len(specs) != 6 or set(outcomes) != {r["run_id"] for r in specs} or not registry["suite_finished"]:
            raise ValueError("Every planned adaptation needs a terminal recorded outcome")
        runs = []
        for spec in specs:
            outcome = outcomes[spec["run_id"]]
            reported = reports.get(spec["run_id"], {})
            runs.append(dict(reported, run_id=spec["run_id"], regime=spec["regime"], seed=spec["seed"],
                reported_fit_status=reported.get("status"), status=outcome["status"],
                stop_reason=outcome.get("reason") or reported.get("stop_reason"),
                loss_history=reported.get("loss_history", []), validation_history=reported.get("validation_history", [])))
        # Existing encoded descriptors only; one run at a time, no checkpoint inference.
        groups = [r for r in read_json(output / "cache/index.json") if r["sampler"] == "grid" and r["scale_px"] == 48 and r["record"]["kind"] == "measurement"]
        cache = {}
        for group in budget.checked(groups):
            cache[group["group_id"]] = {}
            for regime in ("transfer", "transductive"):
                with np.load(output / "cache" / group["group_id"] / (regime + ".npz"), allow_pickle=False) as data:
                    cache[group["group_id"]][regime] = dict(indices=data["available_indices"], brightness=data["patches"].mean((1, 2)))
        features = []
        for run in budget.checked(read_json(output / "features/index.json")):
            values, brightness, frames = [], [], []
            for group in budget.checked(groups):
                content = load_features(output, run, group)
                selected = cache[group["group_id"]][run["regime"]]
                values.append(content[selected["indices"]])
                brightness.extend(selected["brightness"])
                frames.extend([group["record"]["frame_number"]] * len(selected["indices"]))
            stats = representation_summary(np.concatenate(values), brightness, frames)
            features.append(dict(run_id=run["run_id"], family=run["family"], regime=run["regime"], seed=run["seed"], **stats,
                scope="All available real grid48 descriptors; descriptive statistics, not held-out validation or a domain score"))
        snapshots = final_snapshots(runs)
        figures = output / "figures"
        figures.mkdir(exist_ok=True)
        names = ("training-curves.png", "descriptor-diagnostics.png")
        for name in names:
            if (figures / name).exists():
                raise FileExistsError(figures / name)
        plot_training(figures / names[0], runs)
        plot_descriptors(figures / names[1], snapshots)
        result = dict(schema="stmdomains-pretrained-ssl26-diagnostics-v1", freeze_sha256=file_hash(output / "frozen-predictions.json"),
            snapshots=snapshots, cached_representation_statistics=features, new_model_forward_calls=0, new_optimizer_steps=0,
            figures_sha256={name: file_hash(figures / name) for name in names}, source_sha256=file_hash(Path(__file__)),
            model_angle_available=False, model_spacing_available=False,
            limitations=["Mean384 variability/rank, feature drift, head entropy and SSL loss are not domain-detection accuracy",
                "Layer normalization across channels does not establish variability across images; per-scale diagnostics are retained",
                "Global head diversity may come from token positions; position-conditional information is reported separately",
                "Frozen and adapted descriptors use pipeline26; this is not numerical reproduction of the different extraction pipeline18/19",
                "Failed runs have no primary replacement; last diagnostic snapshots are explicitly marked",
                "Transductive fixed-window diagnostics reuse training observations; TTMAPP is one previously studied acquisition"],
            resources=budget.measurements())
        write_json(output / "feature-diagnostics.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.output)
    print(json.dumps(dict(snapshots=len(result["snapshots"]), feature_records=len(result["cached_representation_statistics"]), new_model_forward_calls=0)))


if __name__ == "__main__":
    main()
