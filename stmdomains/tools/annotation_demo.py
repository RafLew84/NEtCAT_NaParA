"""Create small real MPP inputs for reviewing molecule layers and geometry."""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
from typing import Any
import zlib

import numpy as np

from stmdomains.tools.demo_inputs import write_mpp, write_session


def _mask(shape: tuple[int, int], bbox: tuple[int, int, int, int]) -> dict[str, Any]:
    pixels = np.zeros(shape, dtype=bool)
    x1, y1, x2, y2 = bbox
    pixels[y1:y2, x1:x2] = True
    packed = np.packbits(pixels.reshape(-1)).tobytes()
    return {
        "encoding": "packbits-zlib-base64",
        "shape": list(shape),
        "data": base64.b64encode(zlib.compress(packed)).decode("ascii"),
    }


def _detection(
    identity: str, frame: int, bbox: tuple[float, float, float, float], view: str,
) -> dict[str, Any]:
    return {
        "detection_id": identity, "frame_index": frame, "bbox_xyxy": list(bbox),
        "original_bbox_xyxy": list(bbox), "source_view": view,
        "confidence": 0.95, "selected": identity != "aligned-B",
        "origin": "manual", "model_name": "kontrola geometrii",
    }


def _segmentation(
    detection: dict[str, Any], mask: dict[str, Any], *, origin: list[float] | None = None,
) -> dict[str, Any]:
    x1, y1, x2, y2 = detection["bbox_xyxy"]
    return {
        "segmentation_id": f"mask-{detection['detection_id']}",
        "frame_index": detection["frame_index"],
        "source_view": detection["source_view"],
        "bbox_xyxy": detection["bbox_xyxy"].copy(),
        "polygon_xy": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        "mask": mask, "original_mask": {"encoding": "same-as-mask"},
        "prompt_detection_ids": [detection["detection_id"]],
        "origin": "manual", "score": 0.9,
        "metadata": {} if origin is None else {"registered_frame_origin_xy": origin},
    }


def create_annotation_demo(directory: Path) -> dict[str, Path]:
    """Make inspectable fixtures; no measurement inputs or models are required."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[:32, :48]
    first = (x + 2 * y).astype(float)
    first[6:12, 8:16] = 255
    first[20:26, 30:38] = 180
    first[24:29, 3:7] = 0
    second = first.copy()
    second[1:4, 38:44] = 255
    # The MPP loader rotates its matrices by 180 degrees. Store the inverse
    # orientation so the coordinates above are literal imported raw positions.
    raw = np.stack([first, second])
    source = write_mpp(directory / "molecules.mpp", raw[:, ::-1, ::-1], times=[10, 20])
    registered = write_session(directory / "registered.moltrack.json", source, [0, 1])
    payload = json.loads(registered.read_text(encoding="utf-8"))
    payload["registration"] = {
        "settings": {"backend": "phase_correlation", "reference_strategy": "first",
                     "registration_view": "raw", "backend_params": {}},
        "reference_frame_index": 0,
        "results_by_frame": [
            {"frame_index": 0, "shift_xy": [0, 0], "method": "identity",
             "quality_score": 1.0, "status": "ok"},
            {"frame_index": 1, "shift_xy": [-2.5, 1.25], "method": "phase_correlation",
             "quality_score": 0.2, "status": "low_confidence"},
        ],
    }
    detections = [
        _detection("raw-A", 0, (8, 6, 16, 12), "raw"),
        _detection("aligned-B", 0, (33, 20, 41, 26), "expanded_aligned"),
        _detection("fractional-A", 1, (8.5, 7.25, 16.5, 13.25), "expanded_aligned"),
        _detection("raw-B", 1, (30, 20, 38, 26), "raw"),
    ]
    detections[0]["original_bbox_xyxy"] = [7, 5, 17, 13]
    payload["molecular_detections"] = {"frame_count": 2, "detections": detections}
    payload["molecular_segmentations"] = {
        "frame_count": 2,
        "segmentations": [
            _segmentation(detections[0], _mask((32, 48), (8, 6, 16, 12))),
            _segmentation(detections[1], _mask((34, 51), (33, 20, 41, 26)), origin=[3, 0]),
            _segmentation(detections[3], _mask((32, 48), (30, 20, 38, 26))),
        ],
    }
    variants = {"registered": payload}
    bad_mask = deepcopy(payload)
    bad_mask["molecular_segmentations"]["segmentations"][0]["mask"]["data"] = "not-base64!"
    variants["bad_mask"] = bad_mask
    no_registration = deepcopy(payload)
    del no_registration["registration"]
    variants["no_registration"] = no_registration
    empty = deepcopy(payload)
    empty["molecular_detections"]["detections"] = []
    empty["molecular_segmentations"]["segmentations"] = []
    variants["empty"] = empty
    missing = deepcopy(payload)
    del missing["molecular_detections"], missing["molecular_segmentations"]
    variants["missing"] = missing
    paths = {"source": source}
    for name, data in variants.items():
        path = directory / f"{name.replace('_', '-')}.moltrack.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        paths[name] = path
    (directory / "README.txt").write_text(
        "STM Domains — SD-V4-02: molekuły i geometria\n\n"
        "registered.moltrack.json: 2 klatki 48×32 px, źródłowe 1 i 2; czasy 10 i 20 s.\n"
        "W obu oryginałach A: biały prostokąt bbox (8,6,16,12), środek (12,9); "
        "B: szary prostokąt bbox (30,20,38,26), środek (34,23). "
        "Czarny znacznik jest na dole po lewej. Klatka 2 ma dodatkowy biały znacznik u góry po prawej.\n"
        "Klatka 1: ID raw-A i aligned-B, obie maski dostępne. Kliknięcie raw-A pokazuje "
        "historyczny bbox (7,5,17,13), lecz ramka bieżąca jest (8,6,16,12). "
        "aligned-B ma selected=false i nadal jest widoczna.\n"
        "Klatka 2: ID fractional-A i raw-B; tylko B ma maskę. "
        "Wyrównanie ma niską pewność 0.2, ale pozostaje dostępne.\n"
        "Płótno wyrównane: 51×34 px. Początek pola klatki 1: (3,0), klatki 2: (0.5,1.25). "
        "Centra A po wyrównaniu: (15,9), następnie (12.5,10.25). "
        "Dopełnienie poza polem nie jest pomiarem.\n"
        "bad-mask.moltrack.json: uszkodzona maska raw-A; poprawny bbox i polygon pozostają, "
        "maska B nadal działa.\n"
        "no-registration.moltrack.json: wyrównanie niedostępne. W klatce 1 widoczna raw-A, "
        "w klatce 2 raw-B; oznaczeń expanded_aligned nie można poprawnie umieścić.\n"
        "empty.moltrack.json: dostępne, jawnie puste listy oznaczeń. "
        "missing.moltrack.json: brak obu sekcji, oznaczenia niedostępne. "
        "Żaden z tych przypadków nie dowodzi braku molekuł na obrazie.\n"
        "Przełączaj widoki, zoom/pan, ramki, centra, maski i krycie; oznaczenia mają "
        "pozostawać na tych samych prostokątach. Skala fizyczna jest niepotwierdzona.\n",
        encoding="utf-8",
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path,
                        default=Path(".scratch/stmdomains-ui-02/demo"))
    for name, path in create_annotation_demo(parser.parse_args().directory).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
