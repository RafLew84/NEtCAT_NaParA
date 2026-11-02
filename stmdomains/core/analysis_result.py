"""One-frame analysis inputs and immutable molecule memberships, independent of Qt."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from stmdomains.core.annotations import FrameAnnotations
from stmdomains.core.series import FrameData


class AnalysisCancelled(Exception):
    """Cooperative cancellation leaves the previous completed result available."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class AnalysisInput:
    series_id: str
    frame: FrameData
    annotations: FrameAnnotations


@dataclass(frozen=True)
class ResultClass:
    class_id: str
    color: str


@dataclass(frozen=True)
class MoleculeAssignment:
    detection_id: str
    domain_local_id: int = 0
    class_id: str = ""
    provisional_class_id: str = ""
    status: str = "unassigned"
    rejection_reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class FrameAnalysis:
    series_id: str
    working_index: int
    source_index: int
    status: Literal["complete", "no_annotations", "insufficient_data"]
    message: str = ""
    assignments: Mapping[str, MoleculeAssignment] = field(default_factory=dict)
    classes: tuple[ResultClass, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False)
    domain_labels: NDArray[np.int32] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", MappingProxyType(dict(self.assignments)))
        object.__setattr__(self, "parameters", _freeze(self.parameters))
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.domain_labels is not None:
            labels = np.asarray(self.domain_labels, dtype=np.int32)
            if labels.ndim != 2 or np.any(labels < 0):
                raise ValueError("Mapa domen musi być nieujemnym obrazem 2D.")
            # Own immutable backing storage; callers cannot re-enable writes.
            frozen = np.frombuffer(labels.tobytes(), dtype=np.int32).reshape(labels.shape)
            object.__setattr__(self, "domain_labels", frozen)

    @property
    def total_count(self) -> int:
        return len(self.assignments)

    @property
    def suppressed_count(self) -> int:
        return sum(item.status == "suppressed_duplicate" for item in self.assignments.values())

    @property
    def outside_count(self) -> int:
        return sum(item.status == "outside_field" for item in self.assignments.values())

    @property
    def active_count(self) -> int:
        return self.total_count - self.suppressed_count - self.outside_count

    @property
    def assigned_count(self) -> int:
        return sum(item.domain_local_id > 0 for item in self.assignments.values())

    @property
    def unassigned_count(self) -> int:
        return self.active_count - self.assigned_count

    @property
    def domain_count(self) -> int:
        return len({item.domain_local_id for item in self.assignments.values()
                    if item.domain_local_id > 0})

    @property
    def class_counts(self) -> dict[str, int]:
        counts = Counter(item.class_id for item in self.assignments.values()
                         if item.domain_local_id > 0)
        return {item.class_id: counts[item.class_id] for item in self.classes}
