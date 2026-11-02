"""Reconstruct saved translations without registering or modifying source images."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import affine_transform


@dataclass(frozen=True)
class Registration:
    raw_shape: tuple[int, int]
    frame_count: int
    expanded_shape: tuple[int, int]
    origins_xy: tuple[tuple[float, float], ...]
    reason: str = ""
    descriptions: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return not self.reason

    def describe(self, index: int) -> str:
        self._check_index(index)
        if not self.available:
            return "Wyrównanie niedostępne: " + self.reason
        return self.descriptions[index]

    def origin(self, index: int) -> tuple[float, float]:
        self._check_index(index)
        if not self.available:
            raise ValueError(self.reason)
        return self.origins_xy[index]

    def field_rect(self, index: int, view: str) -> tuple[float, float, float, float]:
        self._check_index(index)
        self._check_view(view)
        x, y = self.origin(index) if view == "expanded_aligned" else (0., 0.)
        height, width = self.raw_shape
        return x, y, float(width), float(height)

    def image(self, raw: NDArray[np.float64], index: int, view: str) -> NDArray[np.float64]:
        self._check_index(index)
        self._check_view(view)
        if raw.shape != self.raw_shape:
            raise ValueError("Wymiary obrazu nie odpowiadają geometrii serii.")
        if view == "raw":
            return raw
        x, y = self.origin(index)
        result = affine_transform(
            raw, matrix=np.eye(2), offset=(-y, -x), output_shape=self.expanded_shape,
            order=1, mode="constant", cval=np.nan, prefilter=False,
        )
        return np.asarray(result, dtype=np.float64)

    def transform_mask(
        self, mask: NDArray[np.bool_], index: int, source_view: str, target_view: str,
    ) -> NDArray[np.bool_]:
        """Translate a source mask once; padding never counts as a positive sample."""
        self._check_index(index)
        self._check_view(source_view)
        self._check_view(target_view)
        source_shape = self.expanded_shape if source_view == "expanded_aligned" else self.raw_shape
        if mask.shape != source_shape:
            raise ValueError("Wymiary maski nie odpowiadają jej układowi współrzędnych.")
        if "expanded_aligned" in (source_view, target_view):
            x, y = self.origin(index)
        else:
            x, y = 0., 0.
        if source_view == target_view:
            return mask
        shape = self.expanded_shape if target_view == "expanded_aligned" else self.raw_shape
        offset = (-y, -x) if target_view == "expanded_aligned" else (y, x)
        result = affine_transform(mask, matrix=np.eye(2), offset=offset, output_shape=shape,
                                  order=0, mode="constant", cval=False, prefilter=False)
        return np.asarray(result, dtype=bool)

    def _check_index(self, index: int) -> None:
        if not 0 <= index < self.frame_count:
            raise IndexError("Indeks klatki poza zakresem rejestracji.")

    @staticmethod
    def _check_view(view: str) -> None:
        if view not in ("raw", "expanded_aligned"):
            raise ValueError("Nieznany układ współrzędnych obrazu.")


def parse_registration(
    payload: object, frame_count: int, raw_shape: tuple[int, int],
) -> Registration:
    """Parse the registration section; coordinates belong to working frame indices."""
    if payload is None:
        return Registration(raw_shape, frame_count, raw_shape, (), "Brak zapisanej rejestracji.")
    try:
        records = _validated_records(payload, frame_count)
    except ValueError as exc:
        return Registration(raw_shape, frame_count, raw_shape, (), str(exc))
    shifts = [tuple(record["shift_xy"]) for record in records]
    left = ceil(max(0, -min(dx for dx, dy in shifts)))
    right = ceil(max(0, max(dx for dx, dy in shifts)))
    top = ceil(max(0, -min(dy for dx, dy in shifts)))
    bottom = ceil(max(0, max(dy for dx, dy in shifts)))
    origins = tuple((left + shifts[i][0], top + shifts[i][1]) for i in range(frame_count))
    height, width = raw_shape
    assert isinstance(payload, dict)
    descriptions = tuple(_description(record, payload.get("reference_frame_index"), frame_count)
                         for record in records)
    return Registration(raw_shape, frame_count, (height + top + bottom, width + left + right),
                        origins, descriptions=descriptions)


def _description(record: dict[str, Any], reference: object, frame_count: int) -> str:
    status = record.get("status")
    status_labels = {"ok": "OK", "low_confidence": "niska pewność", "manual_review": "wymaga oceny"}
    label = status_labels.get(status, f"status nieznany ({status})") if isinstance(status, str) else "status nieznany"
    quality = record.get("quality_score")
    score = (f"jakość {quality:g}" if isinstance(quality, (int, float))
             and not isinstance(quality, bool) and isfinite(quality)
             else "jakość nieznana")
    method = record.get("method")
    method = method if isinstance(method, str) and method else "nieznana"
    ref = (f"klatka {reference + 1}" if type(reference) is int and 0 <= reference < frame_count
           else "nieznana")
    return f"Rejestracja: {label} · {score} · metoda {method} · referencja: {ref}"


def _validated_records(payload: object, frame_count: int) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Uszkodzona sekcja rejestracji.")
    if "frame_count" in payload and (
        type(payload["frame_count"]) is not int or payload["frame_count"] != frame_count
    ):
        raise ValueError("Liczba klatek rejestracji nie odpowiada serii.")
    items = payload.get("results_by_frame")
    if not isinstance(items, list):
        raise ValueError("Brak poprawnej listy wyników rejestracji.")
    indexed: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Uszkodzony wynik rejestracji.")
        index = item.get("frame_index")
        if type(index) is not int or not 0 <= index < frame_count:
            raise ValueError("Niepoprawny indeks klatki rejestracji.")
        if index in indexed:
            raise ValueError(f"Powtórzony wynik rejestracji klatki {index + 1}.")
        shift = item.get("shift_xy")
        if not isinstance(shift, (list, tuple)) or len(shift) != 2 or not all(
            type(value) in (int, float) and isfinite(value) for value in shift
        ):
            raise ValueError(f"Niepoprawne przesunięcie klatki {index + 1}.")
        if item.get("status") == "failed":
            raise ValueError(f"Rejestracja klatki {index + 1} zakończona niepowodzeniem.")
        indexed[index] = item
    if len(indexed) != frame_count:
        raise ValueError("Niepełna rejestracja: brakuje wyników dla części klatek.")
    return [indexed[index] for index in range(frame_count)]
