"""Generate image/annotation inputs for manual native-analysis checks.

These are synthetic UI controls, not reference labels or saved model outputs.
Every class and domain must be computed by the application from these inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from stmdomains.tools.demo_inputs import write_mpp, write_session


IMAGE_SHAPE = (512, 512)


def lattice_patches(*, aligned: bool = False) -> NDArray[np.float64]:
    """Five separated patches, each with 81 literal molecular centers."""
    origins = ((90., 90.), (256., 90.), (422., 90.), (166., 390.), (346., 390.))
    ij = np.array([(i, j) for j in range(-4, 5) for i in range(-4, 5)], dtype=float)
    patches = []
    for index, origin in enumerate(origins):
        angle = np.deg2rad(0 if aligned else 18 * index)
        rotation = np.array([[np.cos(angle), -np.sin(angle)],
                             [np.sin(angle), np.cos(angle)]])
        if aligned:
            basis = np.array([[8. + 2 * index, 0.], [0., 12.]])
        else:
            oblique = np.deg2rad(75)
            basis = np.array([[10., 12. * np.cos(oblique)],
                              [0., 12. * np.sin(oblique)]])
        patches.append(ij @ basis.T @ rotation.T + np.asarray(origin))
    return np.vstack(patches)


def molecule_image(points: NDArray[np.float64], *, steps: bool = False) -> NDArray[np.float64]:
    """Render small positive Gaussian spots at the literal centers."""
    image = np.zeros(IMAGE_SHAPE, dtype=float)
    for x, y in points:
        x1, x2 = max(0, int(x) - 7), min(IMAGE_SHAPE[1], int(x) + 8)
        y1, y2 = max(0, int(y) - 7), min(IMAGE_SHAPE[0], int(y) + 8)
        yy, xx = np.mgrid[y1:y2, x1:x2]
        image[y1:y2, x1:x2] += np.exp(-((xx - x)**2 + (yy - y)**2) / (2 * 1.8**2))
    if steps:
        # Deliberately place contrast steps through occupied rows. The order
        # and class computations still see their complete point neighborhoods.
        # The image barrier stage must decide which graph edges remain usable.
        rows = np.unique(np.rint(points[:, 1]).astype(int))
        for row in rows:
            image[row:] += 4.
    return image


def write_analysis_annotations(
    path: Path, points_by_frame: list[NDArray[np.float64]], *, duplicate: bool,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    detections: list[dict[str, Any]] = []
    for frame, points in enumerate(points_by_frame):
        for index, (x, y) in enumerate(points):
            detections.append({
                "frame_index": frame, "detection_id": f"frame-{frame+1}-molecule-{index+1}",
                "bbox_xyxy": [float(x-2), float(y-2), float(x+2), float(y+2)],
                "source_view": "raw", "origin": "manual", "selected": True,
                "confidence": 1.,
            })
    if duplicate:
        x, y = points_by_frame[0][0] + np.array([.1, .1])
        detections.append({
            "frame_index": 0, "detection_id": "duplicate-control",
            "bbox_xyxy": [float(x-2), float(y-2), float(x+2), float(y+2)],
            "source_view": "raw", "origin": "manual", "selected": True,
            "confidence": .8,
        })
    payload["ui"] = {"registration_view_mode": "Show raw"}
    payload["molecular_detections"] = {
        "frame_count": len(points_by_frame), "detections": detections,
    }
    payload["molecular_segmentations"] = {
        "frame_count": len(points_by_frame), "segmentations": [],
    }
    payload["registration"] = {
        "reference_frame_index": 0,
        "results_by_frame": [
            {"frame_index": frame, "shift_xy": [-.25 * frame, .125 * frame],
             "method": "manual", "quality_score": 1., "status": "ok"}
            for frame in range(len(points_by_frame))
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def create_analysis_demo(directory: Path) -> dict[str, Path]:
    """Write genuine MPP/MolTrack files without classes, domains or models."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    patches = lattice_patches()
    barrier_patches = lattice_patches(aligned=True)
    empty = np.empty((0, 2), dtype=float)
    few = np.array([[180., 200.], [192., 200.], [180., 212.], [192., 212.]])
    points = [patches, barrier_patches, empty, few, patches]
    images = np.stack([
        molecule_image(patches), molecule_image(barrier_patches, steps=True),
        molecule_image(patches), molecule_image(few), molecule_image(patches),
    ])
    # The MPP loader rotates by 180 degrees. Store the inverse orientation so
    # each imported Gaussian has the literal raw center used in the JSON.
    source = write_mpp(directory / "analysis.mpp", images[:, ::-1, ::-1])
    series = write_session(directory / "series.moltrack.json", source, range(len(points)))
    write_analysis_annotations(series, points, duplicate=True)
    single_source = write_mpp(directory / "single.mpp", images[:1, ::-1, ::-1])
    single = write_session(directory / "single.moltrack.json", single_source, [0])
    write_analysis_annotations(single, [patches], duplicate=True)
    readme = directory / "README.txt"
    readme.write_text(
        "STM Domains — SD-V4-05, sztuczne wejścia do obliczeń w aplikacji\n\n"
        "Uruchom w netcat: python -m stmdomains.main\n"
        "Otwórz series.moltrack.json i kliknij Analizuj klatkę.\n"
        "Generator zapisuje tylko obrazy i oznaczenia wejściowe; brak modeli, klas i domen.\n"
        "Klatka 1: pięć oddzielonych płatów okresowych, każdy 9×9 centrów; "
        "405 molekuł i jedno dodatkowe oznaczenie w odległości około 0,14 px.\n"
        "Sprawdzony wynik bazowego 05: 357/405 przypisanych, 17 domen, 1 pominięty duplikat. "
        "Pięć geometrycznych płatów zostaje rozdrobnionych; 17 domen nie jest wzorcem trafności.\n"
        "Klatka 2: 405 centrów w pięciu płatach; silne poziome przejścia kontrastu "
        "przechodzą przez zajęte rzędy. Kontrola działania barier obrazu.\n"
        "Oczekiwane: dopasowanie K5 wykonane, 0/405 przypisanych, 0 domen. "
        "To obliczony zerowy wynik, a nie brak analizy lub brak dopasowania.\n"
        "Klatka 3: obraz molekuł, ale zero zapisanych oznaczeń. "
        "Oczekiwane: Brak oznaczeń do analizy. Aplikacja nie wykonuje nowej detekcji molekuł.\n"
        "Klatka 4: cztery oznaczenia, za mało do dopasowania K5; "
        "oczekiwane Brak dopasowania klas wraz z przyczyną.\n"
        "Klatka 5: ten sam obraz i 405 centrów co w klatce 1, bez duplikatu. "
        "Przejście do niej nie uruchamia automatycznie analizy ani nie przenosi wyniku.\n"
        "Przed obliczeniem: Brak analizy tej klatki. Po obliczeniu: 357/405, 17 domen.\n"
        "single.moltrack.json: tylko klatka 1 w osobnym MPP, bez dostępu do innych klatek.\n"
        "Ma dać ten sam wynik co pierwsza klatka serii: 357/405, 17 domen, 1 duplikat.\n"
        "Przełącz Domeny/Klasy, kliknij szarą molekułę i sprawdź powód odmowy "
        "w opisie pod obrazem oraz w Danych oznaczenia. Zmień gamma, zoom i raw/wyrównany.\n"
        "Wszystkie obrazy 512×512 px; jasne plamki odpowiadają centrom oznaczeń. "
        "Geometria wyrównana ma zapisane przesunięcia (-0,25*i; 0,125*i), i od 0.\n"
        "To przykłady techniczne, nie pomiar, etykiety treningowe ani ocena skuteczności detektora.\n",
        encoding="utf-8",
    )
    return {"series": series, "single": single, "source": source,
            "single_source": single_source, "readme": readme}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?",
                        default=Path(".scratch/stmdomains-ui-05/demo"))
    for name, path in create_analysis_demo(parser.parse_args().directory).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
