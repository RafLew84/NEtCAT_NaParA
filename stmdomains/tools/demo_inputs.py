"""Generate small genuine MPP/MolTrack inputs without checking binary data in."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike


def write_mpp(path: Path, frames: ArrayLike, *, times: Sequence[float] | None = None) -> Path:
    data = np.asarray(frames, dtype="<f8")
    if data.ndim != 3 or min(data.shape) < 1:
        raise ValueError("Expected nonempty [frame, row, column] images.")
    header = (
        "[General Info]\n"
        f"Number of columns: {data.shape[2]}\n"
        f"Number of rows: {data.shape[1]}\n"
        f"Number of Frames: {data.shape[0]}\n"
        "Acquisition channel: Z\n"
    )
    if times is not None:
        if len(times) != data.shape[0]:
            raise ValueError("One time is required per source frame.")
        header += "[Frames Synchronization]\n"
        header += "".join(f"Frame {i}: {time} s\n" for i, time in enumerate(times))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write((header + "[Header end]\n").encode("utf-8"))
        stream.write(data.tobytes())
    return path


def write_session(
    path: Path,
    mpp: Path,
    indices: Sequence[int],
    *,
    schema_version: int = 1,
    active_index: int = 0,
    reverse: bool = False,
) -> Path:
    stat = mpp.stat()
    payload = {
        "schema_version": schema_version,
        "source": {"path": str(mpp.resolve()), "path_relative_to_session": mpp.name,
                   "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        "working_series": {"source_frame_indices": list(indices),
                           "active_frame_index": active_index, "reverse_frame_order": reverse},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def create_demo_inputs(directory: Path) -> dict[str, Path]:
    """Create disposable inputs for the ticket 01 manual acceptance steps."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[:32, :48]
    images = []
    for index in range(4):
        image = (x + y).astype(float) / 3
        image[2:8, 2 + index * 6:8 + index * 6] = 255
        image[20:28, 34:44] = 0
        images.append(image)
    source = write_mpp(directory / "demo.mpp", images, times=[10, 20, 30, 40])
    single_source = write_mpp(directory / "single.mpp", images[:1])
    single = write_session(directory / "single.moltrack.json", single_source, [0])
    reordered = write_session(directory / "reordered.moltrack.json", source, [3, 1], reverse=True)
    changed = write_session(directory / "changed-mtime.moltrack.json", source, range(4))
    changed_payload = json.loads(changed.read_text())
    changed_payload["source"]["mtime_ns"] -= 10_000_000
    changed.write_text(json.dumps(changed_payload, indent=2), encoding="utf-8")

    incompatible = write_mpp(directory / "incompatible.mpp", [[[1, 2]]])
    bad = write_session(directory / "bad-source.moltrack.json", source, range(4))
    bad_payload = json.loads(bad.read_text())
    bad_payload["source"]["path"] = str(incompatible)
    bad_payload["source"]["path_relative_to_session"] = incompatible.name
    bad.write_text(json.dumps(bad_payload, indent=2), encoding="utf-8")
    unknown = write_session(directory / "unknown-version.moltrack.json", source, [0], schema_version=99)
    (directory / "README.txt").write_text(
        "STM Domains — ticket 01, małe dane do ręcznego odbioru\n\n"
        "single.moltrack.json: jedna klatka 48×32 px; jasny kwadrat w prawym dolnym rogu, "
        "ciemny prostokąt w lewym górnym. Nawigacja nieaktywna.\n"
        "reordered.moltrack.json: klatki źródłowe 4, potem 2 (indeksy3,1); "
        "czasy40s,20s, bez ponownego odwracania.\n"
        "changed-mtime.moltrack.json: potwierdzenie innej daty; Odrzuć zachowuje poprzednią serię.\n"
        "bad-source.moltrack.json: niezgodne źródło. Anuluj lub wskaż demo.mpp, aby naprawić.\n"
        "unknown-version.moltrack.json: błąd wersji bez utraty wcześniejszego obrazu.\n"
        "Wszystkie przykłady mają niepotwierdzoną kalibrację; pokazujemy piksele.\n",
        encoding="utf-8",
    )
    return {"single": single, "reordered": reordered, "changed_mtime": changed,
            "bad_source": bad, "unknown_version": unknown, "source": source}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(".scratch/stmdomains-ui-01/demo"))
    paths = create_demo_inputs(parser.parse_args().directory)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
