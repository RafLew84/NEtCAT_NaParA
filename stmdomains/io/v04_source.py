"""Bind exported identities and image coordinates to the already loaded series."""

import hashlib
import io
from math import isclose
from collections.abc import Callable
from typing import Any
from zipfile import ZipFile

import numpy as np

from stmdomains.core.series import Series
from stmdomains.core.registration import parse_registration
from stmdomains.io.annotations import AnnotationStore
from stmdomains.io.moltrack_import import ImportCancelled
from stmdomains.io.v04_package import ResultPackage, V04ImportError


def validate_sources(metadata: dict[str, Any], series: Series, cancelled: Callable[[], bool]) -> None:
    if metadata.get("schema") != "stm-domain-prototype-selected-input-v1":
        raise V04ImportError("Nieobsługiwany schemat metadanych wejściowych wyniku.")
    for role, path in (("mpp", series.source_path), ("session", series.session_path)):
        source = metadata["sources"][role]
        before = path.stat()
        if before.st_size != source["size_bytes"]:
            raise V04ImportError(f"Rozmiar źródła {role} nie odpowiada wynikowi.")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                if cancelled():
                    raise ImportCancelled()
                digest.update(block)
        after = path.stat()
        if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            raise V04ImportError(f"Plik źródłowy {role} zmienił się podczas weryfikacji.")
        if digest.hexdigest() != source["sha256"]:
            raise V04ImportError(f"SHA-256 źródła {role} nie odpowiada wynikowi.")


def validate_images(
    package: ResultPackage, metadata: dict[str, Any], series: Series,
    cancelled: Callable[[], bool],
) -> dict[int, int]:
    source_to_working = {source: i for i, source in enumerate(series.source_frame_indices)}
    indices = metadata["source_frame_indices"]
    if (not isinstance(indices, list) or not indices
            or any(type(index) is not int or index < 0 for index in indices)
            or len(set(indices)) != len(indices)
            or metadata["source_frame_numbers"] != [index + 1 for index in indices]
            or metadata["n_frames"] != len(indices)
            or metadata["source_movie_frame_count"] != len(series.raw_frames)):
        raise V04ImportError("Niespójna mapa klatek w metadanych wyniku.")
    data = package.read("work/expanded/input_selected.npz")
    _validate_array_headers(data, len(indices), series.frame_shape)
    with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
        images = arrays["images"]
        sources = arrays["source_frame_indices"]
        if (sources.dtype.kind not in "iu" or sources.ndim != 1
                or sources.tolist() != indices
                or images.dtype != np.float64
                or images.shape != (len(indices), *series.frame_shape)):
            raise V04ImportError("Mapa albo geometria obrazów NPZ nie odpowiada metadanym.")
        for local, source in enumerate(sources):
            if cancelled():
                raise ImportCancelled()
            if int(source) not in source_to_working:
                raise V04ImportError("Wynik zawiera obraz spoza otwartej serii.")
            raw = series.frame(source_to_working[int(source)]).image
            if not np.array_equal(images[local], raw, equal_nan=True):
                raise V04ImportError(f"Niezgodny obraz źródłowej klatki {int(source) + 1}.")
    return source_to_working


def _validate_array_headers(data: bytes, count: int, frame_shape: tuple[int, int]) -> None:
    """Check bounded numeric geometry before NumPy allocates the exported arrays."""
    with ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        for name, expected_shape in (("images.npy", (count, *frame_shape)),
                                     ("source_frame_indices.npy", (count,))):
            if names.count(name) != 1:
                raise V04ImportError("NPZ nie zawiera jednoznacznych tablic obrazów i indeksów.")
            with archive.open(name) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0):
                    shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
                elif version == (2, 0):
                    shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
                else:
                    raise V04ImportError("Nieobsługiwany nagłówek tablicy NPZ.")
                valid_dtype = dtype == np.float64 if name == "images.npy" else dtype.kind in "iu"
                if shape != expected_shape or not valid_dtype:
                    raise V04ImportError("Geometria albo typ tablicy NPZ nie odpowiada otwartej serii.")
                size = int(np.prod(expected_shape)) * dtype.itemsize
                if archive.getinfo(name).file_size != stream.tell() + size:
                    raise V04ImportError("Długość tablicy NPZ nie odpowiada jej geometrii.")


def validate_annotations(
    rows: list[dict[str, str]], sources: list[int], series: Series,
    source_to_working: dict[int, int], cancelled: Callable[[], bool],
) -> None:
    registration = parse_registration(series.raw_payload.get("registration"), series.frame_count,
                                      series.frame_shape)
    store = AnnotationStore({"molecular_detections": series.raw_payload.get("molecular_detections")},
                            series.frame_count, registration, series.frame_shape)
    grouped: dict[int, dict[str, dict[str, str]]] = {source: {} for source in sources}
    local_indices = {source: local for local, source in enumerate(sources)}
    for row in rows:
        source = int(row["frame_index"])
        identifier = row["detection_id"]
        if source not in grouped or not identifier or identifier in grouped[source]:
            raise V04ImportError("Wynik ma powtórzone ID albo rekord poza zakresem klatek.")
        if (int(row["frame_number"]) != source + 1
                or int(row["local_frame_index"]) != local_indices[source]):
            raise V04ImportError("Niezgodny numer lub lokalny indeks klatki przypisania.")
        grouped[source][identifier] = row
    for source, records in grouped.items():
        if cancelled():
            raise ImportCancelled()
        frame = store.frame(source_to_working[source], "raw")
        if frame.detection_state in ("missing", "invalid", "partial"):
            raise V04ImportError("Nie można jednoznacznie powiązać wyniku z oznaczeniami serii.")
        expected = {item.detection_id: item.center_xy for item in frame.detections}
        if records.keys() != expected.keys():
            raise V04ImportError(f"ID oznaczeń klatki źródłowej {source + 1} nie odpowiadają wynikowi.")
        for identifier, xy in expected.items():
            record = records[identifier]
            if not all(isclose(float(record[key]), coordinate, rel_tol=0, abs_tol=1e-6)
                       for key, coordinate in zip(("x_px", "y_px"), xy)):
                raise V04ImportError(f"Współrzędne oznaczenia {identifier} nie odpowiadają wynikowi.")
