from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


_BUILT_IN_LABELS = ("A", "B", "C")


@dataclass(frozen=True)
class OrientationClassCatalog:
    """Series-wide A-Z meanings retained independently of current assignments."""

    labels: tuple[str, ...] = _BUILT_IN_LABELS
    revision: int = 0

    def __post_init__(self) -> None:
        labels = tuple(self.labels)
        if labels[:3] != _BUILT_IN_LABELS:
            raise ValueError("Orientation Class Catalog must start with A, B and C.")
        if len(labels) != len(set(labels)):
            raise ValueError("Orientation Class Catalog labels must be unique.")
        if any(
            not isinstance(value, str)
            or len(value) != 1
            or not "A" <= value <= "Z"
            for value in labels
        ):
            raise ValueError("Orientation Class Catalog labels must be A-Z.")
        if labels != tuple(sorted(labels)):
            raise ValueError("Orientation Class Catalog labels must be ordered.")
        if isinstance(self.revision, bool) or self.revision < 0:
            raise ValueError("Orientation Class Catalog revision must be non-negative.")
        object.__setattr__(self, "labels", labels)

    def with_label(self, label: str) -> OrientationClassCatalog:
        normalized = str(label).strip()
        if normalized == "Unresolvable":
            return self
        if len(normalized) != 1 or not "A" <= normalized <= "Z":
            raise ValueError("Orientation class label must be A-Z.")
        if normalized in self.labels:
            return self
        return OrientationClassCatalog(
            labels=tuple(sorted(self.labels + (normalized,))),
            revision=self.revision + 1,
        )

    def validate_assignments(self, labels: Iterable[str]) -> None:
        assigned = {label for label in labels if label != "Unresolvable"}
        if not assigned.issubset(self.labels):
            raise ValueError("Orientation Class Catalog omits a manual assignment.")


__all__ = ["OrientationClassCatalog"]
