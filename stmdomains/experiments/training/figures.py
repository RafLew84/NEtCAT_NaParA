"""Fixed scientific figures from completed runs; no model/example selection."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .predict import read_json


def make_figures(output):
    if not (output/'frozen-predictions.json').exists():
        raise ValueError('Freeze the predictions before reporting')
    target = output/'figures'
    target.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, family in zip(axes, ('ae', 'rvae')):
        for seed in (20261101, 20261102, 20261103):
            path = output/'training'/'transfer'/family/'z32'/f'seed-{seed}'/'run.json'
            run = read_json(path)
            steps = [row['step'] for row in run['validation_history']]
            losses = [row['loss'] for row in run['validation_history']]
            ax.plot(steps, losses, label=str(seed))
            chosen = run['selected_step']
            if chosen in steps:
                ax.scatter([chosen], [losses[steps.index(chosen)]], s=28)
        ax.set(title=f'{family.upper()}, z32 — walidacja bez etykiet', xlabel='Krok optymalizatora',
               ylabel='MSE' if family == 'ae' else 'MSE + 0,001 KL')
        ax.grid(alpha=.25)
        ax.legend(title='Ziarno')
    fig.suptitle('Punkty oznaczają wybrane checkpointy; wykres nie mierzy jakości domen')
    fig.savefig(target/'validation-curves.png', dpi=160)
    plt.close(fig)

    import torch
    from .models import load_model
    torch.set_num_threads(1)
    fig, axes = plt.subplots(2, 3, figsize=(8, 6), constrained_layout=True)
    for row_number, regime in enumerate(('transfer', 'transductive')):
        path = output/'cache'/'ttmapp-250/grid/s48'/f'{regime}.npz'
        with np.load(path, allow_pickle=False) as data:
            indices, patches = data['available_indices'], data['patches']
        rows = read_json(output/'cache'/'ttmapp-250/grid/s48/rows.json.gz')
        # The field center is fixed in advance; no error/label criterion picks a patch.
        selected = min(range(len(indices)), key=lambda i: (np.linalg.norm(np.array(rows[indices[i]]['raw_edge_xy'])-[128, 128]), rows[indices[i]]['element_id']))
        patch = patches[selected]
        images = [patch]
        with torch.inference_mode():
            for family in ('ae', 'rvae'):
                model = load_model(output/'training'/regime/family/'z32'/'seed-20261101', device='cpu')
                images.append(model.predict(torch.from_numpy(patch[None, None])).numpy()[0, 0])
        for column, (image, label) in enumerate(zip(images, ('Wejście', 'AE z32', 'rVAE z32'))):
            ax = axes[row_number, column]
            ax.imshow(image, cmap='gray', vmin=0, vmax=1, origin='upper')
            ax.set_title(f'{regime}\n{label}')
            ax.axis('off')
    fig.suptitle('TTMAPP 250, środek pola, skala 48 px; ustalone ziarno 20261101\nRekonstrukcja nie jest rozpoznaniem domeny')
    fig.savefig(target/'reconstruction-examples.png', dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/autoencoder-21'))
    args = parser.parse_args()
    make_figures(args.output)
    print(args.output/'figures')


if __name__ == '__main__':
    main()
