from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from moltrack.analysis.domain_analysis import DomainAnalysisSessionState


M6_REFERENCE_DATASET_SCHEMA_VERSION = 2
M6_REFERENCE_DATASET_VERSION = 1
M6ReferenceSplit = Literal["calibration", "validation"]
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class M6ReferenceSourceRevision:
    """Immutable source bytes and acquisition lineage for one measurement."""

    source_file_name: str
    content_sha256: str
    acquisition_fingerprint: str
    lineage_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_file_name",
            _text(self.source_file_name, "source_file_name"),
        )
        digest = str(self.content_sha256).strip().lower()
        if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
            raise ValueError("content_sha256 must be a SHA-256 hexadecimal digest.")
        object.__setattr__(self, "content_sha256", digest)
        for field_name in ("acquisition_fingerprint", "lineage_fingerprint"):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class M6ReferenceFirstShellEdge:
    """One reviewed undirected first-shell relation within a frozen frame."""

    physical_frame_id: str
    source_id_a: str
    source_id_b: str

    def __post_init__(self) -> None:
        frame_id = _text(self.physical_frame_id, "physical_frame_id")
        endpoints = tuple(sorted((
            _text(self.source_id_a, "source_id_a"),
            _text(self.source_id_b, "source_id_b"),
        )))
        if endpoints[0] == endpoints[1]:
            raise ValueError("A first-shell edge requires two distinct source IDs.")
        object.__setattr__(self, "physical_frame_id", frame_id)
        object.__setattr__(self, "source_id_a", endpoints[0])
        object.__setattr__(self, "source_id_b", endpoints[1])


@dataclass(frozen=True)
class M6ReferenceMeasurementGroup:
    """Indivisible target-specific split input for the M6 publisher."""

    measurement_group_id: str
    split: M6ReferenceSplit
    source_revision: M6ReferenceSourceRevision
    snapshot: DomainAnalysisSessionState
    first_shell_edges: tuple[M6ReferenceFirstShellEdge, ...]

    def __post_init__(self) -> None:
        group_id = _stable_id(self.measurement_group_id, "measurement_group_id")
        if self.split not in {"calibration", "validation"}:
            raise ValueError("split must be calibration or validation.")
        if not isinstance(self.source_revision, M6ReferenceSourceRevision):
            raise TypeError("source_revision must be an M6ReferenceSourceRevision.")
        if not isinstance(self.snapshot, DomainAnalysisSessionState):
            raise TypeError("snapshot must be a DomainAnalysisSessionState.")
        edge_values = tuple(self.first_shell_edges)
        if any(
            not isinstance(value, M6ReferenceFirstShellEdge)
            for value in edge_values
        ):
            raise TypeError("first_shell_edges must contain M6ReferenceFirstShellEdge.")
        edges = tuple(sorted(
            edge_values,
            key=lambda value: (
                value.physical_frame_id,
                value.source_id_a,
                value.source_id_b,
            ),
        ))
        if len(edges) != len(set(edges)):
            raise ValueError("first_shell_edges must not contain duplicates.")
        object.__setattr__(self, "measurement_group_id", group_id)
        object.__setattr__(self, "first_shell_edges", edges)


@dataclass(frozen=True)
class M6ReferenceDatasetSettings:
    """Identity and immutable destination for the first M6 dataset version."""

    destination: Path
    dataset_id: str
    publication_reason: str

    def __post_init__(self) -> None:
        destination = Path(self.destination)
        if not str(destination).strip():
            raise ValueError("M6 Reference Dataset destination must not be empty.")
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "dataset_id", _stable_id(
            self.dataset_id,
            "dataset_id",
        ))
        object.__setattr__(
            self,
            "publication_reason",
            _text(self.publication_reason, "publication_reason"),
        )


@dataclass(frozen=True)
class M6ReferenceDatasetPublication:
    package_path: Path
    dataset_id: str
    version_id: str
    version_fingerprint: str
    validation_epoch_id: str
    relative_files: tuple[str, ...]


def _stable_id(value: object, field_name: str) -> str:
    normalized = _text(value, field_name)
    if _STABLE_ID.fullmatch(normalized) is None:
        raise ValueError(
            f"{field_name} must contain only letters, digits, '.', '_' or '-'."
        )
    return normalized


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "M6_REFERENCE_DATASET_SCHEMA_VERSION",
    "M6ReferenceDatasetPublication",
    "M6ReferenceDatasetSettings",
    "M6ReferenceFirstShellEdge",
    "M6ReferenceMeasurementGroup",
    "M6ReferenceSourceRevision",
    "M6ReferenceSplit",
]
