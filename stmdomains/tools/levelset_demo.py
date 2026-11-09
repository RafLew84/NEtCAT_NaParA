"""Openable controls for SD-V4-26, including a small island and a scan artefact."""

import argparse
import json
from pathlib import Path

import numpy as np

from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session
from stmdomains.tools.geometry_demo import grid
from stmdomains.tools.geometry_domain_demo import create_domain_geometry_demo


def create_levelset_demo(directory: Path) -> dict[str, Path]:
    paths = create_domain_geometry_demo(directory/'shared')
    directory.mkdir(parents=True, exist_ok=True)
    large = grid(17, (95., 128.))
    small = grid(47, (270., 128.))
    # A compact island, separated from the main field; 25 centres, above minimum 8.
    distance = np.linalg.norm(small-(270., 128.), axis=1)
    small = small[np.argsort(distance, kind='stable')[:25]]
    island = np.vstack((large, small))
    regular = grid(17)
    images = np.stack([molecule_image(island)[:256, :384], molecule_image(regular)[:256, :384]])
    images[1, 126:131] += images[1].max()*2
    source = write_mpp(directory/'extra.mpp', images[:, ::-1, ::-1])
    session = write_session(directory/'extra.moltrack.json', source, range(2))
    write_analysis_annotations(session, [island, regular], duplicate=False)
    reference = directory/'reference.json'
    truth = {'1': {'name': 'small_domain', 'labels': {f'frame-1-molecule-{j+1}': 1 if j < len(large) else 2
                                                   for j in range(len(island))}},
             '2': {'name': 'scan_artifact', 'labels': {f'frame-2-molecule-{j+1}': 1 for j in range(len(regular))}}}
    reference.write_text(json.dumps(truth, indent=2), encoding='utf-8')
    readme = directory/'README.txt'
    readme.write_text('SD-V4-26. Otwórz shared/domain-geometry.moltrack.json: 9 wspólnych kontroli.\n'
        'Otwórz extra.moltrack.json: 1 — duża sieć i osobna mała domena (99 + 25 centrów);\n'
        '2 — jedna sieć z jasnym artefaktem skanu, bez fizycznej granicy domeny.\n'
        'Geometria i Level set: 12°, 16%, jakość 0,75, lokalnie 10, minimum domeny 8, zasięg maski 0,85 NN.\n'
        'Level set: siła 0 / 0,25 / 1, limit 120. Bariery: domyślne lub minimalna długość 100 NN (wyłączenie w tych danych).\n'
        'Oczekiwania z generatora nie są gwarancją detekcji; raport podaje pominięcia.\n', encoding='utf-8')
    return {**paths, 'extra': session, 'extra_reference': reference, 'instructions': readme}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-26/demo'))
    for key, value in create_levelset_demo(parser.parse_args().directory).items():
        print(f'{key}: {value}')


if __name__ == '__main__':
    main()
