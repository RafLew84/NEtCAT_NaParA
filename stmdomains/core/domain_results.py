"""Immutable molecule assignments from a saved analysis, separate from annotations."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ResultClass:
    class_id: str
    color: str


@dataclass(frozen=True)
class MoleculeAssignment:
    detection_id: str
    domain_local_id: int
    class_id: str
    provisional_class_id: str
    status: str
    rejection_reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class FrameResult:
    analyzed: bool
    assignments: Mapping[str, MoleculeAssignment]
    classes: tuple[ResultClass, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", MappingProxyType(dict(self.assignments)))

    @property
    def total_count(self) -> int:
        return len(self.assignments)

    @property
    def suppressed_count(self) -> int:
        return sum(item.status == "suppressed_duplicate" for item in self.assignments.values())

    @property
    def active_count(self) -> int:
        return self.total_count - self.suppressed_count

    @property
    def assigned_count(self) -> int:
        return sum(item.domain_local_id > 0 for item in self.assignments.values())

    @property
    def domain_count(self) -> int:
        return len({item.domain_local_id for item in self.assignments.values() if item.domain_local_id > 0})

    @property
    def class_counts(self) -> Mapping[str, int]:
        counts = Counter(item.class_id for item in self.assignments.values() if item.domain_local_id > 0)
        return MappingProxyType({item.class_id: counts[item.class_id] for item in self.classes})


@dataclass(frozen=True)
class DomainResult:
    series_id: str
    package_path: Path
    frames: Mapping[int, FrameResult]
    classes: tuple[ResultClass, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", MappingProxyType(dict(self.frames)))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def frame(self, index: int) -> FrameResult:
        return self.frames.get(index, FrameResult(False, {}, self.classes))

    @property
    def frame_count(self) -> int:
        return len(self.frames)
