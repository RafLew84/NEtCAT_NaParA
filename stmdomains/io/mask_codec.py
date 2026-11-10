"""Decode one optional mask, validating its entire coordinate-system shape."""

from __future__ import annotations

import base64
from math import ceil, floor
import zlib

import numpy as np
from numpy.typing import NDArray

from stmdomains.io.annotation_records import bbox


def decode_mask(
    payload: object, expected_shape: tuple[int, int], *,
    reference_mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.bool_] | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Niepoprawny zapis maski.")
    encoding = payload.get("encoding")
    if encoding == "same-as-mask":
        if reference_mask is None or reference_mask.shape != expected_shape:
            raise ValueError("Maska historyczna nie ma poprawnej maski odniesienia.")
        return reference_mask
    shape = payload.get("shape")
    if (not isinstance(shape, (list, tuple)) or len(shape) != 2
            or any(type(x) is not int or x <= 0 for x in shape)
            or tuple(shape) != expected_shape):
        raise ValueError("Wymiary maski niezgodne z jej układem współrzędnych.")
    if encoding in ("packbits-zlib-base64", "bbox-packbits-zlib-base64"):
        result = _packed_mask(payload, expected_shape)
        result.setflags(write=False)
        return result
    if encoding != "rle":
        raise ValueError(f"Nieobsługiwane kodowanie maski: {encoding}.")
    counts = payload.get("counts")
    total = expected_shape[0] * expected_shape[1]
    if (not isinstance(counts, list) or any(type(x) is not int or x < 0 for x in counts)
            or sum(counts) != total):
        raise ValueError("Liczby przebiegów maski niezgodne z wymiarami.")
    decoded = np.repeat(np.arange(len(counts), dtype=np.uint64) % 2, counts)
    result = decoded.astype(bool).reshape(expected_shape)
    result.setflags(write=False)
    return result


def _packed_mask(payload: dict, shape: tuple[int, int]) -> NDArray[np.bool_]:
    height, width = shape
    x0, y0, x1, y1 = 0, 0, width, height
    if payload["encoding"] == "bbox-packbits-zlib-base64":
        left, top, right, bottom = bbox(payload.get("bbox_xyxy"))
        x0, y0 = max(0, floor(left)), max(0, floor(top))
        x1, y1 = min(width, ceil(right)), min(height, ceil(bottom))
        if x1 <= x0 or y1 <= y0:
            raise ValueError("Wycięta maska leży poza zadeklarowanym obrazem.")
    pixels = (y1 - y0) * (x1 - x0)
    expected_bytes = (pixels + 7) // 8
    try:
        compressed = base64.b64decode(payload.get("data", ""), validate=True)
        inflater = zlib.decompressobj()
        packed = inflater.decompress(compressed, expected_bytes + 1)
        if len(packed) != expected_bytes or not inflater.eof or inflater.unused_data:
            raise ValueError("Długość danych maski niezgodna z wymiarami.")
    except (TypeError, ValueError, zlib.error) as exc:
        raise ValueError("Uszkodzone skompresowane dane maski.") from exc
    bits = np.unpackbits(np.frombuffer(packed, dtype=np.uint8), count=pixels, bitorder="little")
    result = np.zeros(shape, dtype=bool)
    result[y0:y1, x0:x1] = bits.reshape(y1 - y0, x1 - x0)
    return result
