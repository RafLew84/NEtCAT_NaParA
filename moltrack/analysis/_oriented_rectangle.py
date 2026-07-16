from __future__ import annotations

from math import isfinite

import numpy as np


OrientedRectangle = tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
]


def normalize_oriented_rectangle(
    vertices: object,
    *,
    side_lengths: tuple[float, float],
    field_name: str,
) -> OrientedRectangle:
    """Validate an ordered rigid rotation/translation of a declared rectangle."""

    try:
        polygon = tuple(_finite_pair(vertex, field_name) for vertex in vertices)  # type: ignore[union-attr]
    except TypeError as exc:
        raise ValueError(f"{field_name} must contain four xy vertices.") from exc
    if len(polygon) != 4:
        raise ValueError(f"{field_name} must contain exactly four vertices.")
    width, height = _positive_pair(side_lengths, "side_lengths")
    points = np.asarray(polygon, dtype=np.float64)
    edges = np.roll(points, -1, axis=0) - points
    scale = max(width, height, 1.0)
    absolute_tolerance = 1e-10 * scale
    actual_lengths = tuple(float(np.linalg.norm(edge)) for edge in edges)
    expected_orders = (
        (width, height, width, height),
        (height, width, height, width),
    )
    if not any(
        all(
            np.isclose(actual, expected, rtol=1e-10, atol=absolute_tolerance)
            for actual, expected in zip(actual_lengths, expected_lengths)
        )
        for expected_lengths in expected_orders
    ):
        raise ValueError(f"{field_name} side lengths must match the declared rectangle.")
    if not np.allclose(edges[0], -edges[2], rtol=1e-10, atol=absolute_tolerance) or not np.allclose(
        edges[1],
        -edges[3],
        rtol=1e-10,
        atol=absolute_tolerance,
    ):
        raise ValueError(f"{field_name} opposite edges must be parallel and equal.")
    dot_tolerance = 1e-10 * max(1.0, width * height)
    if any(
        abs(float(edges[index] @ edges[(index + 1) % 4])) > dot_tolerance
        for index in range(4)
    ):
        raise ValueError(f"{field_name} adjacent edges must be perpendicular.")
    return polygon  # type: ignore[return-value]


def _finite_pair(value: object, field_name: str) -> tuple[float, float]:
    try:
        first, second = (float(item) for item in value)  # type: ignore[union-attr]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} vertices must contain finite xy values.") from exc
    if not isfinite(first) or not isfinite(second):
        raise ValueError(f"{field_name} vertices must contain finite xy values.")
    return first, second


def _positive_pair(value: object, field_name: str) -> tuple[float, float]:
    first, second = _finite_pair(value, field_name)
    if first <= 0.0 or second <= 0.0:
        raise ValueError(f"{field_name} must contain positive values.")
    return first, second
