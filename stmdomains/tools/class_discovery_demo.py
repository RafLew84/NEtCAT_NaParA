"""Small genuine MPP inputs for manual class-discovery acceptance, with no models."""

import argparse
from pathlib import Path

import numpy as np

from stmdomains.tools.analysis_demo import lattice_patches, molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session


def create_class_discovery_demo(directory: Path) -> dict[str, Path]:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    patches = lattice_patches()
    different = lattice_patches(aligned=True)
    # A 45-degree lattice keeps this K1 control separate from the method's
    # near-horizontal image-barrier control (provided by analysis_demo).
    small = (np.array([(12. * x, 12. * y) for y in range(4) for x in range(4)])
             @ (np.array([[1., 1.], [-1., 1.]]) / np.sqrt(2)) + (200., 200.))
    empty = np.empty((0, 2))
    cases = {"single": [small], "pair_a": [patches, patches, patches],
             "pair_b": [patches, different, empty], "empty": [empty]}
    paths = {}
    for name, points in cases.items():
        images = np.stack([molecule_image(p) for p in points])
        source = write_mpp(directory / f"{name}.mpp", images[:, ::-1, ::-1])
        session = write_session(directory / f"{name}.moltrack.json", source, range(len(points)))
        write_analysis_annotations(session, points, duplicate=False)
        paths[name] = session
    (directory / "README.txt").write_text(
        "STM Domains — SD-V4-07, syntetyczne wejścia do ręcznego odbioru\n\n"
        "Uruchom w netcat: python -m stmdomains.main\n"
        "Menu Analiza → Klasy i zakres…, Bieżąca klatka.\n"
        "single.moltrack.json: jedna klatka, 16 centrów w siatce 4×4 obróconej o 45°. "
        "K1 daje 12/16 i jedną domenę; K8 odmawia dopasowania z powodu zbyt małej "
        "liczby różnych użytecznych otoczeń. Zachowaj i obejrzyj poprzedni wynik K1.\n"
        "pair_a / pair_b: pierwsza klatka jest identyczna, pozostałe się różnią. "
        "Lokalne K5 na pierwszej klatce daje te same przypisania i tę samą wersję katalogu. "
        "Wybór Cała seria korzysta również z pozostałych klatek, więc katalog może się zmienić.\n"
        "empty.moltrack.json: brak oznaczeń, dopasowanie wyjaśnia brak danych.\n"
        "Generator zapisuje tylko obrazy i oznaczenia. Bez modeli i etykiet wynikowych. "
        "Kontrole sprawdzają działanie programu, nie trafność fizyczną detektora.\n",
        encoding="utf-8",
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".scratch/stmdomains-ui-07/demo"))
    arguments = parser.parse_args()
    for name, path in create_class_discovery_demo(arguments.output).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
