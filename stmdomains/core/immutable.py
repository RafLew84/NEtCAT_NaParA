"""Immutable metadata snapshots and JSON-compatible values for content identities."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


class _FrozenMapping(Mapping):
    """Owned snapshot: only this type can safely skip recursive copying."""

    def __init__(self, values: Mapping) -> None:
        self._values = MappingProxyType({key: freeze_metadata(item) for key, item in values.items()})

    def __getitem__(self, key: Any) -> Any:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def freeze_metadata(value: Any) -> Any:
    if isinstance(value, _FrozenMapping):
        return value
    if isinstance(value, Mapping):
        return _FrozenMapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_metadata(item) for item in value)
    return value


def plain_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: plain_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain_metadata(item) for item in value]
    return value
