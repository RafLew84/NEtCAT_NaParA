from __future__ import annotations

from math import atan2, isfinite, sqrt

import numpy as np


Point = tuple[float, float]
Polygon = tuple[Point, ...]
Rectangle = tuple[float, float, float, float]


def rectangular_window(
    size_nm: object,
    origin_nm: object,
) -> tuple[Rectangle, ...]:
    width, height = _finite_pair(size_nm, "window_size_nm")
    origin_x, origin_y = _finite_pair(origin_nm, "window_origin_nm")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("window_size_nm values must be positive.")
    return ((origin_x, origin_y, origin_x + width, origin_y + height),)


def masked_window(
    mask_value: object,
    pixel_size_nm: object,
    origin_nm: object,
) -> tuple[Rectangle, ...]:
    mask = np.asarray(mask_value)
    if mask.ndim != 2:
        raise ValueError("valid_fov_mask must be a two-dimensional array.")
    if mask.dtype != np.bool_:
        if not bool(np.all((mask == 0) | (mask == 1))):
            raise ValueError("valid_fov_mask must contain only boolean values.")
        mask = mask.astype(bool)
    pixel_width, pixel_height = _finite_pair(
        pixel_size_nm,
        "valid_fov_pixel_size_nm",
    )
    origin_x, origin_y = _finite_pair(origin_nm, "window_origin_nm")
    if pixel_width <= 0.0 or pixel_height <= 0.0:
        raise ValueError("valid_fov_pixel_size_nm values must be positive.")

    active: dict[tuple[int, int], list[int]] = {}
    rectangles: list[Rectangle] = []
    for row_index, row in enumerate(mask):
        runs = _true_runs(row)
        next_active: dict[tuple[int, int], list[int]] = {}
        for run in runs:
            start_row = active.get(run, [row_index])[0]
            next_active[run] = [start_row]
        for run, (start_row,) in active.items():
            if run not in next_active:
                rectangles.append(
                    _pixel_rectangle(
                        run,
                        start_row,
                        row_index,
                        pixel_width,
                        pixel_height,
                        origin_x,
                        origin_y,
                    )
                )
        active = next_active
    row_count = int(mask.shape[0])
    for run, (start_row,) in active.items():
        rectangles.append(
            _pixel_rectangle(
                run,
                start_row,
                row_count,
                pixel_width,
                pixel_height,
                origin_x,
                origin_y,
            )
        )
    return tuple(rectangles)


def rectangle_polygon(rectangle: Rectangle) -> Polygon:
    min_x, min_y, max_x, max_y = rectangle
    return (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    )


def point_in_window(
    point: np.ndarray,
    rectangles: tuple[Rectangle, ...],
    *,
    tolerance: float,
) -> bool:
    x, y = float(point[0]), float(point[1])
    return any(
        min_x - tolerance <= x <= max_x + tolerance
        and min_y - tolerance <= y <= max_y + tolerance
        for min_x, min_y, max_x, max_y in rectangles
    )


def clip_polygon_halfplane(
    polygon: Polygon,
    *,
    normal: np.ndarray,
    offset: float,
    tolerance: float,
) -> Polygon:
    if not polygon:
        return ()
    output: list[Point] = []
    previous = np.asarray(polygon[-1], dtype=np.float64)
    previous_value = float(previous @ normal - offset)
    previous_inside = previous_value <= tolerance
    for current_point in polygon:
        current = np.asarray(current_point, dtype=np.float64)
        current_value = float(current @ normal - offset)
        current_inside = current_value <= tolerance
        if current_inside != previous_inside:
            denominator = previous_value - current_value
            if abs(denominator) > tolerance:
                fraction = previous_value / denominator
                intersection = previous + fraction * (current - previous)
                output.append((float(intersection[0]), float(intersection[1])))
        if current_inside:
            output.append((float(current[0]), float(current[1])))
        previous = current
        previous_value = current_value
        previous_inside = current_inside
    return _remove_adjacent_duplicates(tuple(output), tolerance=tolerance)


def polygon_area(polygon: Polygon) -> float:
    if len(polygon) < 3:
        return 0.0
    return abs(
        sum(
            left[0] * right[1] - left[1] * right[0]
            for left, right in zip(polygon, polygon[1:] + polygon[:1])
        )
    ) * 0.5


def convex_polygon_intersection(
    left: Polygon,
    right: Polygon,
    *,
    tolerance: float,
) -> Polygon:
    """Return the convex intersection, retaining zero-area contact segments."""

    clipped = left
    if len(right) < 3:
        return ()
    orientation = 1.0 if _signed_polygon_area(right) >= 0.0 else -1.0
    for start, end in zip(right, right[1:] + right[:1]):
        edge_x = end[0] - start[0]
        edge_y = end[1] - start[1]
        normal = orientation * np.asarray((edge_y, -edge_x), dtype=np.float64)
        offset = float(normal @ np.asarray(start, dtype=np.float64))
        clipped = clip_polygon_halfplane(
            clipped,
            normal=normal,
            offset=offset,
            tolerance=tolerance,
        )
        if not clipped:
            break
    return clipped


def circle_polygon_intersection_area(
    polygon: Polygon,
    *,
    center: np.ndarray,
    radius: float,
    tolerance: float,
) -> float:
    if len(polygon) < 3:
        return 0.0
    translated = tuple(
        np.asarray(point, dtype=np.float64) - center for point in polygon
    )
    signed_area = sum(
        _circle_segment_area(left, right, radius, tolerance)
        for left, right in zip(translated, translated[1:] + translated[:1])
    )
    return abs(float(signed_area))


def _circle_segment_area(
    left: np.ndarray,
    right: np.ndarray,
    radius: float,
    tolerance: float,
) -> float:
    direction = right - left
    a = float(direction @ direction)
    split_values = [0.0, 1.0]
    if a > tolerance * tolerance:
        b = 2.0 * float(left @ direction)
        c = float(left @ left) - radius * radius
        discriminant = b * b - 4.0 * a * c
        length_scale = max(
            radius,
            float(np.linalg.norm(left)),
            float(np.linalg.norm(right)),
            sqrt(a),
            tolerance,
        )
        discriminant_tolerance = (tolerance * length_scale) ** 2
        if discriminant > discriminant_tolerance:
            root = sqrt(discriminant)
            parameter_tolerance = min(0.25, tolerance / sqrt(a))
            for value in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)):
                if parameter_tolerance < value < 1.0 - parameter_tolerance:
                    split_values.append(value)
    split_values.sort()
    contribution = 0.0
    for start, end in zip(split_values, split_values[1:]):
        first = left + start * direction
        second = left + end * direction
        midpoint = (first + second) * 0.5
        cross = float(first[0] * second[1] - first[1] * second[0])
        if float(midpoint @ midpoint) <= (radius + tolerance) ** 2:
            contribution += 0.5 * cross
        else:
            dot = float(first @ second)
            contribution += 0.5 * radius * radius * atan2(cross, dot)
    return contribution


def _signed_polygon_area(polygon: Polygon) -> float:
    return 0.5 * sum(
        left[0] * right[1] - left[1] * right[0]
        for left, right in zip(polygon, polygon[1:] + polygon[:1])
    )


def _true_runs(row: np.ndarray) -> tuple[tuple[int, int], ...]:
    runs = []
    start: int | None = None
    for column, enabled in enumerate(row):
        if bool(enabled) and start is None:
            start = column
        elif not bool(enabled) and start is not None:
            runs.append((start, column))
            start = None
    if start is not None:
        runs.append((start, len(row)))
    return tuple(runs)


def _pixel_rectangle(
    run: tuple[int, int],
    first_row: int,
    end_row: int,
    pixel_width: float,
    pixel_height: float,
    origin_x: float,
    origin_y: float,
) -> Rectangle:
    return (
        origin_x + run[0] * pixel_width,
        origin_y + first_row * pixel_height,
        origin_x + run[1] * pixel_width,
        origin_y + end_row * pixel_height,
    )


def _finite_pair(value: object, field_name: str) -> tuple[float, float]:
    try:
        normalized = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must contain two numbers.") from exc
    if len(normalized) != 2:
        raise ValueError(f"{field_name} must contain two numbers.")
    try:
        pair = float(normalized[0]), float(normalized[1])
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must contain two numbers.") from exc
    if not all(isfinite(component) for component in pair):
        raise ValueError(f"{field_name} must contain finite numbers.")
    return pair


def _remove_adjacent_duplicates(polygon: Polygon, *, tolerance: float) -> Polygon:
    result: list[Point] = []
    for point in polygon:
        if not result or np.linalg.norm(np.subtract(point, result[-1])) > tolerance:
            result.append(point)
    if len(result) > 1 and np.linalg.norm(np.subtract(result[0], result[-1])) <= tolerance:
        result.pop()
    return tuple(result)
