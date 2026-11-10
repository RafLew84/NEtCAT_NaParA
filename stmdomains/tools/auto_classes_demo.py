"""Generate raw-image/centre controls for Auto, without class or domain results."""

import argparse
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter

from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session


def lattice(angle: float, center: tuple[float, float]) -> NDArray[np.float64]:
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), np.sin(theta)], [-np.sin(theta), np.cos(theta)]])
    grid = np.array([(x, y) for y in range(-5, 6) for x in range(-5, 6)], float)
    return grid * 10 @ rotation + center


def control_points() -> list[NDArray[np.float64]]:
    return [lattice(45, (128, 128)),
            np.vstack([lattice(45, (100, 128)), lattice(0, (330, 128))]),
            np.random.default_rng(20261103).uniform(32, 224, (121, 2)),
            np.array([[80., 80.], [128., 80.], [80., 128.], [128., 128.]]),
            np.empty((0, 2))]


def create_auto_demo(directory: Path) -> Path:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    points = control_points()
    images = np.stack([molecule_image(p)[:256, :448] for p in points])
    images[3] = gaussian_filter(images[3], 2.)
    source = write_mpp(directory / "auto-controls.mpp", images[:, ::-1, ::-1])
    session = write_session(directory / "auto-controls.moltrack.json", source, range(len(points)))
    write_analysis_annotations(session, points, duplicate=False)
    (directory / "README.txt").write_text(
        "SD-V4-12 — wejścia kontrolne Auto, bez zapisanych klas/domen.\n"
        "netcat: python -m stmdomains.main; otwórz auto-controls.moltrack.json.\n"
        "Analiza → Analiza… → Klasy: Dopasuj nowe klasy, Auto, maksimum 8.\n"
        "Zakres: Bieżąca klatka; odkrywanie: Ten sam zakres co analiza.\n"
        "1: jedna sieć (K1); 2: dwie orientacje otoczeń (K2); 3: losowe centra; "
        "4: cztery centra; 5: brak oznaczeń. Ostatnie trzy: nierozstrzygnięcie, bez katalogu.\n"
        "Sprawdź Ranking Auto, maksimum 1 dla klatki 2, porównanie z ręcznym K5.\n"
        "Dla wspólnej analizy wybierz Zakres 1–2 i ten sam zakres odkrywania. "
        "Klasy są wspólne, domeny lokalne. Cała seria ma też klatki kontrolne bez wsparcia.\n"
        "Auto to ograniczona reguła dla opisów otoczeń, nie liczba fizycznych faz.\n",
        encoding="utf-8",
    )
    return session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".scratch/stmdomains-ui-12/demo"))
    print(create_auto_demo(parser.parse_args().output))


if __name__ == "__main__":
    main()
