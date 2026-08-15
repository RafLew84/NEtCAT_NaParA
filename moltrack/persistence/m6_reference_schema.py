from __future__ import annotations

from dataclasses import dataclass

from moltrack.analysis.domain_analysis import DomainAnalysisSessionState
from moltrack.analysis.first_shell_geometry_contracts import (
    FirstShellSymmetry,
    first_shell_symmetry,
)

from .reference_dataset import (
    REFERENCE_DATASET_ENVELOPE_VERSION,
    ReferenceDatasetPublication as M6ReferenceDatasetPublication,
    ReferenceDatasetSettings as M6ReferenceDatasetSettings,
)
from .reference_dataset_identity import (
    ReferenceSourceRevision as M6ReferenceSourceRevision,
    ReferenceSplit as M6ReferenceSplit,
    reference_stable_id,
    reference_text,
)


M6_REFERENCE_DATASET_SCHEMA_VERSION = REFERENCE_DATASET_ENVELOPE_VERSION
M6_REFERENCE_DATASET_VERSION = 1


@dataclass(frozen=True)
class M6ReferenceFirstShellFrame:
    """Manual symmetry stratum for first-shell validation of one frame."""

    physical_frame_id: str
    symmetry_class: FirstShellSymmetry

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "physical_frame_id",
            reference_text(self.physical_frame_id, "physical_frame_id"),
        )
        object.__setattr__(
            self,
            "symmetry_class",
            first_shell_symmetry(self.symmetry_class),
        )


@dataclass(frozen=True)
class M6ReferenceFirstShellEdge:
    """One reviewed undirected first-shell relation within a frozen frame."""

    physical_frame_id: str
    source_id_a: str
    source_id_b: str

    def __post_init__(self) -> None:
        frame_id = reference_text(self.physical_frame_id, "physical_frame_id")
        endpoints = tuple(sorted((
            reference_text(self.source_id_a, "source_id_a"),
            reference_text(self.source_id_b, "source_id_b"),
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
    first_shell_frames: tuple[M6ReferenceFirstShellFrame, ...]
    first_shell_edges: tuple[M6ReferenceFirstShellEdge, ...]

    def __post_init__(self) -> None:
        group_id = reference_stable_id(
            self.measurement_group_id,
            "measurement_group_id",
        )
        if self.split not in {"calibration", "validation"}:
            raise ValueError("split must be calibration or validation.")
        if not isinstance(self.source_revision, M6ReferenceSourceRevision):
            raise TypeError("source_revision must be an M6ReferenceSourceRevision.")
        if not isinstance(self.snapshot, DomainAnalysisSessionState):
            raise TypeError("snapshot must be a DomainAnalysisSessionState.")
        frame_values = tuple(self.first_shell_frames)
        if any(
            not isinstance(value, M6ReferenceFirstShellFrame)
            for value in frame_values
        ):
            raise TypeError(
                "first_shell_frames must contain M6ReferenceFirstShellFrame."
            )
        frames = tuple(sorted(
            frame_values,
            key=lambda value: value.physical_frame_id,
        ))
        if len({value.physical_frame_id for value in frames}) != len(frames):
            raise ValueError("first_shell_frames must contain unique frame IDs.")
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
        object.__setattr__(self, "first_shell_frames", frames)
        object.__setattr__(self, "first_shell_edges", edges)

__all__ = [
    "M6_REFERENCE_DATASET_SCHEMA_VERSION",
    "M6ReferenceDatasetPublication",
    "M6ReferenceDatasetSettings",
    "M6ReferenceFirstShellEdge",
    "M6ReferenceFirstShellFrame",
    "M6ReferenceMeasurementGroup",
    "M6ReferenceSourceRevision",
    "M6ReferenceSplit",
]
