from __future__ import annotations

from math import isfinite
from typing import Sequence


def normalize_boundary_distances(
    values: Sequence[float | None],
    *,
    point_count: int,
) -> tuple[float | None, ...]:
    try:
        raw_values = tuple(values)
    except TypeError as exc:
        raise TypeError(
            "distance_to_valid_fov_boundary_nm must be an iterable."
        ) from exc
    if len(raw_values) != point_count:
        raise ValueError(
            "distance_to_valid_fov_boundary_nm must contain one value per point."
        )
    normalized: list[float | None] = []
    for index, value in enumerate(raw_values):
        if value is None:
            normalized.append(None)
            continue
        if isinstance(value, bool):
            raise TypeError(
                f"distance_to_valid_fov_boundary_nm[{index}] must be a number or None."
            )
        try:
            distance = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(
                f"distance_to_valid_fov_boundary_nm[{index}] must be a number or None."
            ) from exc
        if not isfinite(distance) or distance < 0.0:
            raise ValueError(
                "distance_to_valid_fov_boundary_nm values must be finite and non-negative."
            )
        normalized.append(distance)
    return tuple(normalized)
