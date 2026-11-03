from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from moltrack.analysis import MolecularSampleCoordinates
from moltrack.analysis.domain_analysis import DomainAnalysisSessionState
from moltrack.core import MolTrackImageSeries

from .reference_dataset import (
    REFERENCE_DATASET_ENVELOPE_VERSION,
    ReferenceDatasetPublication as OrientationReferenceDatasetPublication,
    ReferenceDatasetSettings as OrientationReferenceDatasetSettings,
)
from .reference_dataset_identity import (
    ReferenceSourceRevision as OrientationReferenceSourceRevision,
    ReferenceSplit as OrientationReferenceSplit,
    reference_stable_id,
)


ORIENTATION_REFERENCE_DATASET_SCHEMA_VERSION = REFERENCE_DATASET_ENVELOPE_VERSION
ORIENTATION_REFERENCE_DATASET_VERSION = 1


@dataclass(frozen=True)
class OrientationReferenceMeasurementGroup:
    """One indivisible Orientation split input with its source image series."""

    measurement_group_id: str
    split: OrientationReferenceSplit
    source_revision: OrientationReferenceSourceRevision
    snapshot: DomainAnalysisSessionState
    series: MolTrackImageSeries
    sample_coordinates: tuple[MolecularSampleCoordinates, ...]

    def __post_init__(self) -> None:
        group_id = reference_stable_id(
            self.measurement_group_id,
            "measurement_group_id",
        )
        if self.split not in {"calibration", "validation"}:
            raise ValueError("split must be calibration or validation.")
        if not isinstance(self.source_revision, OrientationReferenceSourceRevision):
            raise TypeError(
                "source_revision must be an OrientationReferenceSourceRevision."
            )
        if not isinstance(self.snapshot, DomainAnalysisSessionState):
            raise TypeError("snapshot must be a DomainAnalysisSessionState.")
        if not isinstance(self.series, MolTrackImageSeries):
            raise TypeError("series must be a MolTrackImageSeries.")
        if Path(self.series.source_path).resolve() != self.source_revision.source_path.resolve():
            raise ValueError("series and source_revision must identify the same source.")
        coordinates = tuple(self.sample_coordinates)
        if not coordinates or any(
            not isinstance(value, MolecularSampleCoordinates)
            for value in coordinates
        ):
            raise ValueError(
                "sample_coordinates must contain MolecularSampleCoordinates."
            )
        frame_indices = tuple(value.frame_index for value in coordinates)
        if len(frame_indices) != len(set(frame_indices)):
            raise ValueError("sample_coordinates must contain one value per frame.")
        object.__setattr__(self, "measurement_group_id", group_id)
        object.__setattr__(
            self,
            "sample_coordinates",
            tuple(sorted(coordinates, key=lambda value: value.frame_index)),
        )


__all__ = [
    "ORIENTATION_REFERENCE_DATASET_SCHEMA_VERSION",
    "OrientationReferenceDatasetPublication",
    "OrientationReferenceDatasetSettings",
    "OrientationReferenceMeasurementGroup",
    "OrientationReferenceSourceRevision",
    "OrientationReferenceSplit",
]
