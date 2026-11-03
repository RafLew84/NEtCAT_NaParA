"""Write image/centre controls for order tuning, without classes or saved models."""

import argparse
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session


def create_order_demo(directory: Path) -> Path:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261103)
    lattice = np.array([(x, y) for y in range(-5, 6) for x in range(-5, 6)], float) * 12.
    regular = lattice @ (np.array([[1., 1.], [-1., 1.]]) / np.sqrt(2)) + (128., 128.)
    random = rng.uniform(32., 224., (121, 2))
    rows = np.column_stack((rng.uniform(32., 224., 121), np.repeat(48. + 16. * np.arange(11), 11)))
    sparse = np.array([[80., 80.], [92., 80.], [80., 92.], [92., 92.]])
    points = [regular, random, rows, sparse]
    images = np.stack([molecule_image(p)[:256, :256] for p in points])
    # Four narrow spots occupy less than the viewer's 2% contrast tail. Broaden
    # this sparse control so its actual centres remain visible in the browser.
    images[-1] = gaussian_filter(images[-1], 2.)
    source = write_mpp(directory / "order-controls.mpp", images[:, ::-1, ::-1])
    session = write_session(directory / "order-controls.moltrack.json", source, range(len(points)))
    write_analysis_annotations(session, points, duplicate=False)
    (directory / "README.txt").write_text(
        "STM Domains — SD-V4-10, kontrole porządku\n\n"
        "Uruchom w netcat: python -m stmdomains.main\n"
        "Otwórz order-controls.moltrack.json. Analiza → Analiza serii…:\n"
        "analizuj klatki 1–4, K1, odkrywanie: Inny wybrany zakres, klatka 1–1.\n"
        "Wspólny katalog pozwala ocenić pozostałe układy, nawet bez próbek do nowego dopasowania.\n"
        "1: regularna siatka 11×11 obrócona o 45°.\n"
        "2: losowe centra, ziarno 20261103; możliwe pojedyncze przypadkowe pozytywy.\n"
        "3: poziome rzędy z losowym położeniem wzdłuż rzędów. Metoda może potwierdzić periodyczność "
        "mimo braku sieci 2D; to ograniczenie, nie wzorzec poprawnych domen.\n"
        "4: cztery centra; przy wspólnym katalogu test odmawia przez niewystarczające wsparcie.\n"
        "Analiza → Test porządku…: porównaj kwantyle 0,950 i 0,925 oraz pary "
        "promień/sigma 3 i 1,333333 (bazowo dokładnie 4/3) oraz 2 i 1.\n"
        "Wartości są mnożnikami odstępu d wyznaczonego z każdej klatki, nie nm.\n"
        "Sprawdź osobny licznik porządku, wynik domen i Dane oznaczenia… dla szarych molekuł.\n"
        "Zmiana pola nie przelicza; użyj Kalibruj i przelicz klatkę. Przywróć bazowe też wymaga przeliczenia.\n"
        "Wyniki techniczne i dokładne liczby: docs/stmdomains/implementation/interactive-v04/acceptance-10.md.\n"
        "To syntetyczne wejścia do testu działania, bez zapisanych klas, domen ani oceny skuteczności detektora.\n",
        encoding="utf-8",
    )
    return session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".scratch/stmdomains-ui-10/demo"))
    print(create_order_demo(parser.parse_args().output))


if __name__ == "__main__":
    main()
