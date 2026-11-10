"""Fixed correspondence and optimization figures for the issue22 prototype."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ...bundle import file_hash, write_json
from ..predict import read_json
from .diagnostics import FAMILY_LABELS, reporting_stage


SEEDS = (20261101, 20261102, 20261103)


def make_figures(output: Path, prepared: Path):
    import torch
    from .evaluate import verify_freeze
    from .fit import SSLTrainingData
    from .models import aligned_tokens, load_model
    torch.set_num_threads(1)
    target = output / "figures"
    target.mkdir(exist_ok=True)
    with reporting_stage(output, "figures") as budget:
        verify_freeze(output, check_budget=budget.check)
        fig, axes = plt.subplots(2, 4, figsize=(16, 7), constrained_layout=True, sharex=True, sharey="col")
        for row_number, latent in enumerate((16, 32)):
            for seed in SEEDS:
                budget.check()
                path = output / "training/transfer/local_ssl" / f"z{latent}" / f"seed-{seed}" / "run.json"
                if not path.exists():
                    continue
                run = read_json(path)
                history = run["validation_history"]
                steps = [row["step"] for row in history]
                for column, (key, multiplier) in enumerate((("loss", 1), ("invariance", 25), ("variance", 25), ("covariance", 1))):
                    values = [multiplier * row[key] for row in history]
                    ax = axes[row_number, column]
                    ax.plot(steps, values, label=str(seed), linewidth=1.1)
                    if run.get("selected_step") in steps:
                        index = steps.index(run["selected_step"])
                        ax.scatter([steps[index]], [values[index]], s=23)
            for ax, title in zip(axes[row_number], ("Cała funkcja celu", "25 × zgodność pozycji", "25 × niedobór wariancji", "Kowariancja")):
                ax.set_title(f"z{latent} · {title}", fontsize=10)
                ax.set_xlabel("Krok optymalizatora")
                ax.grid(alpha=.25)
            axes[row_number, 0].legend(title="Ziarno", fontsize=8)
        fig.suptitle("Stała walidacja bez etykiet domen · punkty oznaczają wybrany checkpoint\nSkładniki celu nie mierzą wykrywalności domen", fontsize=12)
        fig.savefig(target / "validation-curves.png", dpi=150)
        plt.close(fig)

        data = SSLTrainingData(prepared, "transfer")
        index = next(index for index, row in enumerate(data.validation) if row["scale_raw_px"] == 48)
        batch = data.batch([index], np.random.default_rng(740022), validation=True)
        views, shifts, scales = batch["views"], batch["shifts"], batch["scales"]
        fig, axes = plt.subplots(2, 6, figsize=(16, 6), constrained_layout=True)
        records = []
        directory = output / "training/transfer/local_ssl/z32/seed-20261101"
        for row_number, step in enumerate((0, None)):
            budget.check()
            model = load_model(directory, device="cpu", step=step)
            with torch.inference_mode():
                maps = [model.encode(views[:, i])["local_map"] for i in range(2)]
                aligned = [aligned_tokens(maps[i], shifts[:, i], scales) for i in range(2)]
            images = [views[0, i, 0].numpy() for i in range(2)]
            images += [maps[i][0, 0].numpy() for i in range(2)]
            images += [aligned[i][0, :, 0].reshape(5, 5).numpy() for i in range(2)]
            low, high = min(float(image.min()) for image in images[2:]), max(float(image.max()) for image in images[2:])
            titles = ("Widok 1 + pozycje", "Widok 2 + pozycje", "Kanał 0 · mapa 1", "Kanał 0 · mapa 2", "Kanał 0 · zgodne 1", "Kanał 0 · zgodne 2")
            for column, (ax, image, title) in enumerate(zip(axes[row_number], images, titles)):
                ax.imshow(image, cmap="gray" if column < 2 else "viridis", origin="upper",
                          vmin=0 if column < 2 else low, vmax=1 if column < 2 else high, interpolation="nearest")
                ax.set_title(("Przed treningiem" if step == 0 else "Wybrany checkpoint") + "\n" + title, fontsize=8)
                if column < 2:
                    axis = 7. + 8. * np.arange(1, 6)
                    xx, yy = np.meshgrid(axis, axis)
                    shift = shifts[0, column].numpy() * 64. / float(scales[0])
                    ax.scatter(xx.ravel() - shift[0], yy.ravel() - shift[1], color="#ff7567", s=8, marker="+")
                ax.axis("off")
            records.append(dict(checkpoint="initial" if step == 0 else "selected", fixed_channel=0,
                                map_color_range=[low, high],
                                aligned_feature_mse=float((aligned[0] - aligned[1]).square().mean()),
                                scope="One fixed displayed patch; not a validation loss or a collapse assessment"))
            del model
        fig.suptitle("Dwa przekształcenia jednego ustalonego wycinka · z32, ziarno20261101\nKońcowe mapy porównują te same pozycje pomiaru. Kolor oznacza aktywację kanału, bez klas i kąta.", fontsize=11)
        fig.savefig(target / "local-correspondence.png", dpi=165)
        plt.close(fig)

        diagnostic = read_json(output / "feature-diagnostics.json")
        rows = [row for row in diagnostic["features"] if row["regime"] == "transfer"]
        labels = ["FFT" if row["family"] == "fft" else
                  f"{'SSL' if row['family'] == 'local_ssl' else 'Losowy'} z{row['latent']}\n{row['seed']}" for row in rows]
        colors = ["#9286c8" if row["family"] == "fft" else "#258c84" if row["family"] == "local_ssl" else "#b98951" for row in rows]
        fig, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
        axes[0].bar(range(len(rows)), [row["effective_rank"] for row in rows], color=colors)
        axes[0].set_ylabel("Efektywny rząd deskryptorów")
        axes[1].bar(range(len(rows)), [row["max_absolute_dimension_correlation"]["brightness"] for row in rows], color=colors)
        axes[1].set_ylabel("Maks. |korelacja kanału z jasnością|")
        axes[1].set_ylim(0, 1.02)
        for ax in axes:
            ax.set_xticks(range(len(rows)), labels, rotation=65, ha="right", fontsize=8)
            ax.grid(axis="y", alpha=.25)
        fig.suptitle("Deskryptory wszystkich dostępnych okien48px w24klatkach TTMAPP\nDiagnostyka opisowa; większy rząd i mniejsza korelacja nie dowodzą domen", fontsize=12)
        fig.savefig(target / "representation-diagnostics.png", dpi=150)
        plt.close(fig)

        result = dict(schema="stmdomains-issue22-figures-v1", source_sha256=file_hash(Path(__file__)),
                      files={str(path.relative_to(output)): file_hash(path) for path in sorted(target.glob("*.png"))},
                      fixed_example=dict(window_id=data.validation[index]["window_id"], scale_px=48,
                                         augmentation_seed=740022, model_seed=20261101, channel=0,
                                         shifts_xy=shifts.numpy().tolist(),
                                         rule="First sorted validation window of scale48; independent fixed augmentation seed; first model seed/channel"),
                      correspondence=records, no_model_or_example_selection=True)
        write_json(target / "manifest.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, default=Path(".scratch/training-20"))
    args = parser.parse_args()
    make_figures(args.output, args.prepared)
    print(args.output / "figures")


if __name__ == "__main__":
    main()
