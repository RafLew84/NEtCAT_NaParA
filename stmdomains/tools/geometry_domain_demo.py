"""Openable controls with generator references for the experimental method 17."""

import argparse
import json
from pathlib import Path

import numpy as np

from stmdomains.tools.geometry_demo import grid
from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session


def create_domain_geometry_demo(directory: Path) -> dict[str, Path]:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    regular = grid(17.)
    left, right = grid(17), grid(47)
    two = np.vstack((left[left[:, 0] < 128], right[right[:, 0] >= 128]))
    bent = grid(0)
    bent[:, 1] += .004*(bent[:, 0]-128)**2
    phase = grid(0)
    phase[phase[:, 0] > 128, 1] += 7.
    missing = np.delete(regular, [12, 17, 30, 45, 61, 78, 80], axis=0)
    gap = regular[(regular[:, 0] < 116) | (regular[:, 0] > 140)]
    rng = np.random.default_rng(20261104)
    rows = np.array([(x, y) for y in np.arange(25, 240, 14) for x in rng.uniform(15, 240, 23)])
    points = [regular, two, bent, phase, missing, gap,
              np.random.default_rng(42).uniform(5, 250, (120, 2)), rows,
              np.array([(70., 70.), (90., 90.), (110., 110.)])]
    names = ['regular', 'two_orientations', 'gradual_turn', 'phase_jump', 'missing_centers',
             'gap', 'noise', 'rows_1d', 'sparse']
    references = {}
    for i, (name, samples) in enumerate(zip(names, points)):
        labels = np.ones(len(samples), int)
        if name in ('two_orientations', 'phase_jump', 'gap'):
            labels[samples[:, 0] > (128 if name != 'two_orientations' else 127.999)] = 2
        if name in ('gradual_turn', 'sparse'):
            labels[:] = -1  # No sharp physical boundary / no measurable reference.
        if name in ('noise', 'rows_1d'):
            labels[:] = 0  # No intended 2D domain.
        references[str(i+1)] = {'name': name, 'labels': {
            f'frame-{i+1}-molecule-{j+1}': int(label) for j, label in enumerate(labels)},
            'interpretation': 'generator truth; -1 unavailable, 0 no 2D domain, positive domain region'}
    images = np.stack([molecule_image(p)[:256, :384] for p in points])
    source = write_mpp(directory/'domain-geometry.mpp', images[:, ::-1, ::-1])
    session = write_session(directory/'domain-geometry.moltrack.json', source, range(len(points)))
    write_analysis_annotations(session, points, duplicate=False)
    reference = directory/'reference.json'
    reference.write_text(json.dumps(references, indent=2), encoding='utf-8')
    readme = directory/'README.txt'
    readme.write_text('Kontrole SD-V4-17. Otwórz domain-geometry.moltrack.json. Analiza → Geometria.\n'
        + '\n'.join(f'{i+1}: {name}' for i, name in enumerate(names))
        + '\nGranica orientacji i fazy: x=128 px. Luka: pas 116–140 px.\n'
        'Płynna deformacja nie ma narzuconej granicy: badamy rozpiętość pomiarów regionu.\n'
        'Skok fazy ma dwie domeny w referencji; scalenie jest błędem, nawet przy wysokim udziale przypisań.\n'
        'Szare molekuły pozostają odmowami; nie traktuj ich jako potwierdzonej granicy.\n', encoding='utf-8')
    return {'series': session, 'reference': reference, 'readme': readme}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-17/demo'))
    for name, path in create_domain_geometry_demo(parser.parse_args().directory).items():
        print(f'{name}: {path}')


if __name__ == '__main__':
    main()
