"""Fixed scientific reconstruction and validation figures for issue21a."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ...bundle import file_hash, write_json
from ..predict import read_json
from .diagnostics import FAMILIES, FAMILY_LABELS, reporting_stage


def model_directory(output, baseline, family, seed=20261101):
    root = baseline if family in ("ae", "rvae") else output
    return root / "training/transfer" / family / "z32" / f"seed-{seed}"


def make_figures(output: Path, baseline: Path):
    from .evaluate import verify_freeze
    from .models import load_model
    import torch
    torch.set_num_threads(1)
    target = output / "figures"
    target.mkdir(exist_ok=True)
    with reporting_stage(output, "figures") as budget:
        verify_freeze(output, check_budget=budget.check)
        fig, axes = plt.subplots(4, 2, figsize=(12, 12), constrained_layout=True, sharex=True, sharey="col")
        for row_number, family in enumerate(FAMILIES):
            for seed in (20261101, 20261102, 20261103):
                budget.check()
                run = read_json(model_directory(output, baseline, family, seed) / "run.json")
                history = run["validation_history"]
                steps = [row["step"] for row in history]
                beta = .0001 if family.endswith("lowkl") else .001
                values = ([row["mse"] for row in history], [beta * row["kl"] for row in history])
                for ax, series in zip(axes[row_number], values):
                    ax.plot(steps, series, label=str(seed), linewidth=1.2)
                    if run.get("selected_step") in steps:
                        index = steps.index(run["selected_step"])
                        ax.scatter([steps[index]], [series[index]], s=25)
            for ax, title in zip(axes[row_number], ("MSE rekonstrukcji", "Ważona kara β·KL")):
                ax.set_title(f"{FAMILY_LABELS[family]}\n{title}", fontsize=10)
                ax.grid(alpha=.25)
                ax.set_xlabel("Krok optymalizatora")
            if row_number == 0:
                axes[row_number, 0].legend(title="Ziarno", fontsize=8)
        fig.suptitle("Stała walidacja bez etykiet domen · punkty: checkpointy wybrane przez MSE + β·KL\nSkładniki pokazano oddzielnie; zmiana β zmienia także regułę wyboru modelu", fontsize=11)
        fig.savefig(target / "validation-curves.png", dpi=150)
        plt.close(fig)

        folder = output / "cache/ttmapp-250/grid/s48"
        with np.load(folder / "transfer.npz", allow_pickle=False) as archive:
            available, patches = archive["available_indices"], archive["patches"]
        rows = read_json(folder / "rows.json.gz")
        selected = min(range(len(available)), key=lambda i: (np.linalg.norm(np.array(rows[available[i]]["raw_edge_xy"]) - [128, 128]), rows[available[i]]["element_id"]))
        patch = patches[selected]
        families = ("ae", *FAMILIES)
        fig, axes = plt.subplots(2, 6, figsize=(15, 5.5), constrained_layout=True)
        reconstruction_records = []
        for row_number, step in enumerate((None, 2000)):
            images = [patch]
            for family in families:
                budget.check()
                directory = model_directory(output, baseline, family)
                if step and not (directory / f"step-{step:04}.pt").exists():
                    images.append(None)
                    continue
                model = load_model(directory, device="cpu", step=step)
                with torch.inference_mode():
                    predicted = model.predict(torch.from_numpy(patch[None, None])).numpy()[0, 0]
                images.append(predicted)
                reconstruction_records.append(dict(family=family, checkpoint="selected" if step is None else step,
                                                   mse=float(np.mean((predicted - patch) ** 2))))
                del model
            titles = ("Wejście", *(FAMILY_LABELS[family].replace(" — ", "\n") for family in families))
            for column, (image, title) in enumerate(zip(images, titles)):
                ax = axes[row_number, column]
                if image is not None:
                    ax.imshow(image, cmap="gray", vmin=0, vmax=1, origin="upper")
                else:
                    ax.text(.5, .5, "Brak checkpointu", ha="center", va="center")
                ax.set_title(("Wybrany checkpoint" if step is None else "Krok2000") + "\n" + title, fontsize=8)
                ax.axis("off")
        fig.suptitle("TTMAPP250 · okno48px najbliższe (128,128) · ziarno20261101\nPrzykład ustalony przed oceną; rekonstrukcja nie jest rozpoznaniem domeny", fontsize=11)
        fig.savefig(target / "reconstruction-examples.png", dpi=170)
        plt.close(fig)

        with np.load(output / "diagnostic-inputs.npz", allow_pickle=False) as archive:
            images = archive["images"]
        predicted = []
        diagnostic_runs = []
        for label in ("beta-1e-3", "beta-0"):
            budget.check()
            directory = output / "diagnostic" / label
            metadata = read_json(directory / "run.json")
            if not (directory / "step-2000.pt").exists():
                predicted.append(None)
                diagnostic_runs.append(dict(label=label, available=False, status=metadata["status"]))
                continue
            model = load_model(directory, device="cpu", step=2000)
            with torch.inference_mode():
                reconstructed = model.predict(torch.from_numpy(images)).numpy()
            predicted.append(reconstructed)
            diagnostic_runs.append(dict(label=label, available=True, step=2000,
                                        mse=float(np.mean((images - reconstructed) ** 2))))
            del model
        fig, axes = plt.subplots(4, 4, figsize=(18, 8), constrained_layout=True)
        for index, ax in enumerate(axes.flat):
            pieces = [images[index, 0]] + [p[index, 0] if p is not None else np.full((64, 64), np.nan) for p in predicted]
            ax.imshow(np.concatenate(pieces, axis=1), cmap="gray", vmin=0, vmax=1, origin="upper")
            ax.axvline(63.5, color="#e79c40", linewidth=.5); ax.axvline(127.5, color="#e79c40", linewidth=.5)
            ax.set_title(f"Wycinek {index + 1}: wejście | β=0,001 | β=0", fontsize=9)
            ax.axis("off")
        fig.suptitle("Próba zapamiętania16 ustalonych wycinków treningowych · krok2000\nBez augmentacji, ten sam losowany posterior; nie jest to wynik walidacji ani domen", fontsize=12)
        fig.savefig(target / "diagnostic-reconstruction.png", dpi=150)
        plt.close(fig)
        files = {str(path.relative_to(output)): file_hash(path) for path in sorted(target.glob("*.png"))}
        result = dict(schema="stmdomains-issue21a-figures-v1", files=files, seed=20261101,
                      real_example=dict(sample_id="ttmapp-250", target_center=[128, 128],
                                        selected_window_id=rows[available[selected]]["window_id"],
                                        selected_center=rows[available[selected]]["raw_edge_xy"], scale_px=48),
                      reconstructions=reconstruction_records, diagnostic=diagnostic_runs,
                      source_sha256=file_hash(Path(__file__)), no_model_or_example_selection=True)
        write_json(target / "manifest.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=Path(".scratch/autoencoder-21"))
    args = parser.parse_args()
    make_figures(args.output, args.baseline)
    print(args.output / "figures")


if __name__ == "__main__":
    main()
