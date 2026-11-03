"""Same-canvas overlays from saved graph measurements; no new model computation."""
import argparse
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from stmviewer.session_archive import load_session


def overlay(reference, moving, shift):
    low = min(float(reference.min()), float(moving.min()))
    high = max(float(reference.max()), float(moving.max()))
    scale = high - low or 1.
    a, b = (reference-low)/scale, (moving-low)/scale
    matrix = np.array([[1., 0., shift[0]], [0., 1., shift[1]]])
    b = cv2.warpAffine(b.astype(np.float32), matrix, (a.shape[1], a.shape[0]),
                       flags=cv2.INTER_LINEAR, borderValue=float('nan'))
    rgb = np.stack([a, b, b], axis=-1)
    rgb[~np.isfinite(rgb).all(axis=-1)] = 1.
    return np.clip(rgb, 0., 1.)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('efficient', type=Path)
    parser.add_argument('matchanything', type=Path)
    parser.add_argument('--pairs', nargs='+', required=True, help='Current 1-based pairs, e.g. 29:30')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    states = [load_session(path) for path in (args.efficient, args.matchanything)]
    assert states[0].graph.sources == states[1].graph.sources
    edges = [{(e.i, e.j): e for e in state.graph.edges} for state in states]
    pairs = [tuple(int(value)-1 for value in pair.split(':')) for pair in args.pairs]
    fig, axes = plt.subplots(len(pairs), 4, figsize=(16, 3.2*len(pairs)), squeeze=False)
    for row, (i, j) in enumerate(pairs):
        reference, moving = states[0].frames[i].data, states[0].frames[j].data
        axes[row, 0].imshow(reference, cmap='gray', origin='upper')
        axes[row, 0].set_title(f'Klatka bazowa {i+1}; para {i+1}→{j+1}')
        axes[row, 1].imshow(overlay(reference, moving, (0., 0.)), origin='upper')
        axes[row, 1].set_title('Przed dopasowaniem')
        for col, (label, measured) in enumerate(zip(('EfficientLoFTR', 'MatchAnything-ELoFTR'), edges), 2):
            edge = measured[(i, j)]
            if edge.shift_xy is not None:
                axes[row, col].imshow(overlay(reference, moving, edge.shift_xy), origin='upper')
                axes[row, col].set_title(f'{label}\nXY=({edge.shift_xy[0]:.2f}, {edge.shift_xy[1]:.2f}); {edge.status}')
            else:
                axes[row, col].text(.5, .5, f'{label}\nBrak pomiaru', ha='center', va='center')
        for ax in axes[row]:
            ax.set_axis_off()
    fig.suptitle('Bazowa: czerwony; przesuwana: turkusowy. XY surowej pary, wspólny zakres jasności.\n'
                 'Brak niezależnej prawdy STM; zgodność fragmentów wymaga oceny.', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .96))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=120)
    plt.close(fig)


if __name__ == '__main__':
    main()
