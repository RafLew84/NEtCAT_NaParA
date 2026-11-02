"""Create a short real MPP series for manual playback and gamma checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from stmdomains.tools.demo_inputs import write_mpp, write_session


def _detection(index: int) -> dict[str, Any]:
    return {
        "frame_index": index, "detection_id": f"frame-{index + 1}",
        "bbox_xyxy": [4 + 4 * index, 8, 12 + 4 * index, 14],
        "source_view": "raw", "origin": "manual", "selected": True,
        "confidence": 1.0,
    }


def create_browsing_demo(directory: Path) -> dict[str, Path]:
    """Generate disposable images, annotations and saved global translations."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[:32, :48]
    images = []
    for index in range(8):
        image = (x + 2 * y).astype(float)
        image[8:14, 4 + 4 * index:12 + 4 * index] = 255
        image[24:29, 2:5] = 0
        if index == 2:
            image[:] = np.nan
            image[0, 0], image[-1, -1] = np.inf, -np.inf
        elif index == 3:
            image[:] = 20
        images.append(image)
    # Undo the loader's 180-degree rotation so raw coordinates match this demo.
    raw = np.stack(images)
    source = write_mpp(directory / "browsing.mpp", raw[:, ::-1, ::-1],
                       times=[10 * (index + 1) for index in range(8)])
    series = write_session(directory / "series.moltrack.json", source, range(8))
    payload = json.loads(series.read_text(encoding="utf-8"))
    payload["ui"] = {"registration_view_mode": "Show raw"}
    payload["molecular_detections"] = {
        "frame_count": 8,
        "detections": [_detection(index) for index in range(8) if index not in (2, 3)],
    }
    payload["molecular_segmentations"] = {"frame_count": 8, "segmentations": []}
    payload["registration"] = {
        "reference_frame_index": 0,
        "results_by_frame": [
            {"frame_index": index, "shift_xy": [-0.25 * index, 0.125 * index],
             "method": "manual", "quality_score": 1.0, "status": "ok"}
            for index in range(8)
        ],
    }
    series.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    single = write_session(directory / "single.moltrack.json", source, [0])
    one = json.loads(single.read_text(encoding="utf-8"))
    one["ui"] = {"registration_view_mode": "Show raw"}
    one["molecular_detections"] = {"frame_count": 1, "detections": [_detection(0)]}
    one["molecular_segmentations"] = {"frame_count": 1, "segmentations": []}
    one["registration"] = {
        "reference_frame_index": 0,
        "results_by_frame": [payload["registration"]["results_by_frame"][0]],
    }
    single.write_text(json.dumps(one, indent=2), encoding="utf-8")
    (directory / "README.txt").write_text(
        "STM Domains — SD-V4-03: miniatury, odtwarzanie i gamma\n\n"
        "series.moltrack.json: osiem klatek 48×32 px, źródłowe 1–8, czasy 10–80 s.\n"
        "Klatki 1, 2, 5, 6, 7, 8: gradient, jasny prostokąt przesuwający się w prawo, "
        "czarny znacznik na dole po lewej. ID frame-N odpowiada numerowi klatki N.\n"
        "Centra prostokąta w oryginale: klatka 1 (8,11), 2 (12,11), 5 (24,11), "
        "6 (28,11), 7 (32,11), 8 (36,11). Bbox ma 8×6 px; nie jest ponownie obracany.\n"
        "Klatka 3: tylko NaN/+inf/-inf, jawny brak obrazu pomiarowego i brak oznaczeń. "
        "Nie może pokazywać obrazu ani nakładek z klatki 2.\n"
        "Klatka 4: stała wartość 20, bez detekcji; przy gamma 1 jednolity szary 128, "
        "przy gamma 2 szary 180. Zmiana gamma nie zmienia danych pomiarowych.\n"
        "Wyrównanie: zapisane globalne przesunięcia (-0.25*i,0.125*i), indeks i od 0. "
        "Płótno 50×33 px, origin pierwszej klatki (2,0), ostatniej (0.25,0.875).\n"
        "Miniatury pozostają przy gamma 1 i pokazują oryginały; gamma dużego obrazu "
        "ich nie zmienia. Sprawdź zgodność miniatury, suwaka i numeru.\n"
        "Uruchom play 1 i 20 kl./s: każda klatka ma być pokazana po kolei, pauza "
        "zachowuje bieżący numer, koniec zatrzymuje. Od początku wraca do klatki 1.\n"
        "single.moltrack.json: ta sama pierwsza klatka MPP jako seria jednoklatkowa; "
        "zbędna nawigacja i odtwarzanie nieaktywne, gamma i podgląd pozostają dostępne.\n"
        "To dane kontrolne, nie pomiar i nie ocena detektora. Skala fizyczna niepotwierdzona.\n",
        encoding="utf-8",
    )
    return {"series": series, "single": single, "source": source}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path,
                        default=Path(".scratch/stmdomains-ui-03/demo"))
    for name, path in create_browsing_demo(parser.parse_args().directory).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
