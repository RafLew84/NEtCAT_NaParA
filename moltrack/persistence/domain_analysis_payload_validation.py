from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, cast


def required(payload: Mapping[str, Any], field_name: str, path: str) -> Any:
    if field_name not in payload:
        raise ValueError(f"{path}.{field_name} is required.")
    return payload[field_name]


def mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object.")
    return value


def list_value(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list.")
    return value


def list_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> list[Any]:
    return list_value(required(payload, field_name, path), f"{path}.{field_name}")


def text_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> str:
    value = required(payload, field_name, path)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{field_name} must be a non-empty string.")
    return value


def optional_text_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> str | None:
    value = required(payload, field_name, path)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{field_name} must be null or non-empty text.")
    return value


def integer_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> int:
    value = required(payload, field_name, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}.{field_name} must be an integer.")
    return value


def optional_integer_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> int | None:
    value = required(payload, field_name, path)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}.{field_name} must be null or an integer.")
    return value


def number_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> float:
    value = required(payload, field_name, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}.{field_name} must be numeric.")
    return float(value)


def boolean_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> bool:
    value = required(payload, field_name, path)
    if not isinstance(value, bool):
        raise ValueError(f"{path}.{field_name} must be a bool.")
    return value


def text_list_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> list[str]:
    values = list_field(payload, field_name, path)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{path}.{field_name} must contain non-empty strings.")
    return cast(list[str], values)


def float_pair_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[float, float]:
    values = list_field(payload, field_name, path)
    if len(values) != 2 or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise ValueError(f"{path}.{field_name} must be a numeric pair.")
    return float(values[0]), float(values[1])


def integer_pair_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[int, int]:
    values = list_field(payload, field_name, path)
    if len(values) != 2 or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in values
    ):
        raise ValueError(f"{path}.{field_name} must be an integer pair.")
    return values[0], values[1]


def float_quad_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[float, float, float, float]:
    values = list_field(payload, field_name, path)
    if len(values) != 4 or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise ValueError(f"{path}.{field_name} must contain 4 numeric values.")
    return cast(tuple[float, float, float, float], tuple(map(float, values)))


def integer_pairs_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[tuple[int, int], ...]:
    values = list_field(payload, field_name, path)
    pairs: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        if not isinstance(value, list) or len(value) != 2 or any(
            isinstance(item, bool) or not isinstance(item, int)
            for item in value
        ):
            raise ValueError(
                f"{path}.{field_name}[{index}] must be an integer pair."
            )
        pairs.append((value[0], value[1]))
    return tuple(pairs)


def float_pairs_field(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[tuple[float, float], ...]:
    values = list_field(payload, field_name, path)
    pairs: list[tuple[float, float]] = []
    for index, value in enumerate(values):
        if not isinstance(value, list) or len(value) != 2 or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value
        ):
            raise ValueError(
                f"{path}.{field_name}[{index}] must be a numeric pair."
            )
        pairs.append((float(value[0]), float(value[1])))
    return tuple(pairs)


def pairs_to_lists(
    values: tuple[tuple[Any, Any], ...],
) -> list[list[Any]]:
    return [[first, second] for first, second in values]


def json_compatible_value(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))
