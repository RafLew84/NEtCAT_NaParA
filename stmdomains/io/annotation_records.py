"""Validate optional record sections while keeping failures local to annotations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from typing import Any

from stmdomains.core.annotations import BBox


def bbox(value: object) -> BBox:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("Niepoprawna ramka oznaczenia.")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in value):
        raise ValueError("Ramka musi zawierać liczby.")
    x1, y1, x2, y2 = (float(x) for x in value)
    if not all(isfinite(x) for x in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
        raise ValueError("Ramka musi mieć skończone współrzędne i dodatni rozmiar.")
    return x1, y1, x2, y2


@dataclass
class RecordSection:
    frames: dict[int, list[tuple[str, dict[str, Any]]]]
    state: str
    diagnostics: tuple[str, ...]


def read_section(payload: object, kind: str, frame_count: int) -> RecordSection:
    label = "Oznaczenia" if kind == "detections" else "Segmentacje"
    if payload is None:
        return RecordSection({}, "missing", (f"{label}: brak zapisanej sekcji.",))
    if not isinstance(payload, dict):
        return RecordSection({}, "invalid", (f"{label}: niepoprawna sekcja.",))
    count = payload.get("frame_count")
    if type(count) is not int or count != frame_count:
        return RecordSection({}, "invalid", (f"{label}: liczba klatek niezgodna z serią.",))
    records = payload.get(kind)
    if not isinstance(records, list):
        return RecordSection({}, "invalid", (f"{label}: brak poprawnej listy rekordów.",))
    id_key = "detection_id" if kind == "detections" else "segmentation_id"
    ids = Counter(record[id_key] for record in records if isinstance(record, dict)
                  and isinstance(record.get(id_key), str) and record[id_key])
    frames: dict[int, list[tuple[str, dict[str, Any]]]] = {}
    diagnostics = []
    for position, record in enumerate(records):
        try:
            if not isinstance(record, dict):
                raise ValueError("niepoprawny rekord")
            index = record.get("frame_index")
            if type(index) is not int or not 0 <= index < frame_count:
                raise ValueError("niepoprawny indeks klatki")
            identifier = record.get(id_key)
            if identifier is None or identifier == "":
                identifier = f"local-{kind}-{position}"
                while identifier in ids:
                    identifier += "-local"
            elif not isinstance(identifier, str):
                raise ValueError("niepoprawny identyfikator")
            elif ids[identifier] > 1:
                raise ValueError(f"powtórzony identyfikator {identifier}")
            if record.get("source_view", "raw") not in ("raw", "expanded_aligned"):
                raise ValueError("nieznany układ współrzędnych")
            if kind == "detections":
                bbox(record.get("bbox_xyxy"))
            frames.setdefault(index, []).append((identifier, record))
        except ValueError as exc:
            diagnostics.append(f"{label}, rekord {position + 1}: {exc}.")
    state = "partial" if diagnostics else ("empty" if not records else "available")
    return RecordSection(frames, state, tuple(diagnostics))


def section_message(state: str, count: int, *, masks: bool = False) -> str:
    label = "Segmentacje" if masks else "Oznaczenia"
    if state == "missing":
        return f"{label}: brak danych."
    if state == "invalid":
        return f"{label}: dane niedostępne."
    if state == "empty":
        return f"{label}: zapisana pusta lista (nie oznacza braku molekuł)."
    if not count and state == "available":
        return "Brak zapisanych segmentacji na tej klatce." if masks else (
            "Brak zapisanych oznaczeń na tej klatce."
        )
    return f"{label}: {count}" + (" · część danych niedostępna" if state == "partial" else "")
