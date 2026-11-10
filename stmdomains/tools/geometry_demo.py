"""Ready-to-open geometry controls: genuine images/centers, no fitted results."""

import argparse
from pathlib import Path
import numpy as np
from stmdomains.tools.demo_inputs import write_mpp, write_session
from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations


def grid(angle: float, origin=(128., 128.), scale=(1., 1.)) -> np.ndarray:
    points = np.array([(10*x, 14*y) for y in range(-4, 5) for x in range(-5, 6)], float)
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    return (points @ rotation.T)*(1., -1.)/scale + origin


def create_geometry_demo(directory: Path) -> dict[str, Path]:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261104)
    regular = grid(17)
    two = np.vstack((grid(17, (78., 128.)), grid(47, (275., 128.))))
    phase = grid(0)
    phase[phase[:, 0] > 128] += (0., 7.)
    missing = np.delete(regular, [12, 17, 30, 45, 61, 78, 80], axis=0)
    gap = regular[(regular[:, 0] < 116) | (regular[:, 0] > 140)]
    rows = np.array([(x, y) for y in np.arange(25, 240, 14) for x in rng.uniform(15, 240, 23)])
    points = [regular, grid(47), two, phase, missing, gap,
              np.random.default_rng(42).uniform(5, 250, (120, 2)), rows,
              np.array([(70., 70.), (90., 90.), (110., 110.)])]
    images = np.stack([molecule_image(p)[:256, :384] for p in points])
    source = write_mpp(directory/'geometry.mpp', images[:, ::-1, ::-1])
    session = write_session(directory/'geometry.moltrack.json', source, range(len(points)))
    write_analysis_annotations(session, points, duplicate=False)
    anisotropic = [grid(17, (128., 128.), (.6, 1.2))]
    image = molecule_image(anisotropic[0])[:256, :256]
    calibrated = write_mpp(directory/'anisotropic.mpp', image[None, ::-1, ::-1])
    # Explicit physical scan extents; written before session source size/mtime.
    contents = calibrated.read_bytes().replace(b'[Header end]',
        b'[Control]\nX Amplitude: 153.6 nm\nY Amplitude: 307.2 nm\n[Header end]')
    calibrated.write_bytes(contents)
    calibrated_session = write_session(directory/'anisotropic.moltrack.json', calibrated, [0])
    write_analysis_annotations(calibrated_session, anisotropic, duplicate=False)
    readme = directory/'README.txt'
    readme.write_text('''Kontrole SD-V4-16. Otwórz MolTrack w STM Domains, Analiza → Geometria… → Pomierz geometrię.
Nie ma zapisanych klas/domen ani modelu. Do geometrii nie potrzeba analizy klas.
Klatka 1: 17°, rozstawy poprzeczne 14 i 10 px; środkowa molekuła 50.
Klatka 2: obrót do 47°, te same rozstawy.
Klatka 3: dwa oddzielne pola 17° i 47°; orientacja nie oznacza typu.
Klatka 4: przesunięcie połowy sieci o 7 px. Daleko od granicy te same 0°/90° i 14/10 px.
Klatka 5: brakujące centra; lokalne wsparcie może spadać.
Klatka 6: rzeczywista przerwa; pomiar może odmówić blisko przerwy.
Klatka 7: losowe centra, brak dominującego stabilnego kierunku.
Klatka 8: rzędy o rozstawie 14 px, losowe położenia wzdłuż nich; jeden kierunek.
Klatka 9: trzy centra, niewystarczające dane, bez kierunków.
anisotropic.moltrack.json: X=0,6 nm/px, Y=1,2 nm/px; fizyczny kąt 17°, 14/10 nm.
Kąt kreski na ekranie różni się od kąta w metryce fizycznej przy nierównej skali X/Y.
Te kontrole sprawdzają pomiar; nie wymagają poprawnej segmentacji ani detekcji granicy fazy.
''', encoding='utf-8')
    return {'series': session, 'anisotropic': calibrated_session, 'readme': readme}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-16/demo'))
    for name, path in create_geometry_demo(parser.parse_args().directory).items():
        print(f'{name}: {path}')


if __name__ == '__main__':
    main()
