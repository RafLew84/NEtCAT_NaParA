"""Immutable metadata snapshots and JSON-compatible values for content identities."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_metadata(item) for item in value)
    return value


def plain_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: plain_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain_metadata(item) for item in value]
    return value
