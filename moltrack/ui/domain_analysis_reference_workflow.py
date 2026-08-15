from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, overload

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QWidget

from moltrack.analysis import build_molecular_sample_coordinates
from moltrack.analysis.domain_analysis import (
    DomainAnalysisSeries,
    DomainAnalysisSessionState,
    M6FrameGate,
    M6PresetLibrary,
)
from moltrack.persistence.reference_dataset_identity import ReferenceSourceRevision
from moltrack.core import MolecularCentroid, MolTrackImageSeries
from moltrack.persistence import (
    M6ReferenceDatasetPublication,
    M6ReferenceDatasetSettings,
    M6ReferenceFirstShellEdge,
    M6ReferenceFirstShellFrame,
    M6ReferenceMeasurementGroup,
    M6ReferenceSourceRevision,
    OrientationReferenceDatasetPublication,
    OrientationReferenceDatasetSettings,
    OrientationReferenceMeasurementGroup,
    OrientationReferenceSourceRevision,
    publish_m6_reference_dataset,
    publish_orientation_reference_dataset,
)


CurrentDomainAnalysisWorkspace = Callable[
    [],
    tuple[
        DomainAnalysisSessionState,
        MolTrackImageSeries,
        DomainAnalysisSeries,
        M6PresetLibrary,
    ],
]
ReferenceSplit = Literal["calibration", "validation"]


@dataclass(frozen=True)
class StagedReferenceMeasurement:
    measurement_group_id: str
    split: ReferenceSplit
    state: DomainAnalysisSessionState
    series: MolTrackImageSeries
    analysis_series: DomainAnalysisSeries
    acquisition_fingerprint: str
    lineage_fingerprint: str


class DomainAnalysisReferenceWorkflow:
    """Stage reviewed measurements and publish both reference targets."""

    def __init__(self, owner: QWidget) -> None:
        if not isinstance(owner, QWidget):
            raise TypeError("owner must be a QWidget.")
        self._owner = owner
        self._m6_groups: dict[ReferenceSplit, StagedReferenceMeasurement] = {}
        self._orientation_groups: dict[
            ReferenceSplit,
            StagedReferenceMeasurement,
        ] = {}
        self._m6_first_shell_frames: dict[
            str,
            tuple[M6ReferenceFirstShellFrame, ...],
        ] = {}
        self._m6_publication: M6ReferenceDatasetPublication | None = None
        self._orientation_publication: (
            OrientationReferenceDatasetPublication | None
        ) = None

    @property
    def m6_publication(self) -> M6ReferenceDatasetPublication:
        publication = self._m6_publication
        if publication is None:
            raise ValueError("Publish the M6 Reference Dataset before calibration.")
        return publication

    @property
    def orientation_publication(self) -> OrientationReferenceDatasetPublication:
        publication = self._orientation_publication
        if publication is None:
            raise RuntimeError("No Orientation Reference Dataset was published.")
        return publication

    @property
    def m6_groups(self) -> tuple[StagedReferenceMeasurement, ...]:
        if set(self._m6_groups) != {"calibration", "validation"}:
            raise ValueError("M6 reference staging requires both data splits.")
        return tuple(
            self._m6_groups[split]
            for split in ("calibration", "validation")
        )

    def first_shell_symmetries(
        self,
        measurement_group_id: str,
    ) -> tuple[Literal["trifold", "sixfold"], ...]:
        frames = self._m6_first_shell_frames[measurement_group_id]
        return tuple(sorted({value.symmetry_class for value in frames}))

    def publish_m6_reference(
        self,
        current: CurrentDomainAnalysisWorkspace,
    ) -> object:
        if self._m6_publication is not None:
            raise RuntimeError(
                "The published M6 reference is immutable; start a new release "
                "workflow to stage another version."
            )
        group = self._stage_current(current)
        self._m6_groups[group.split] = group
        if set(self._m6_groups) != {"calibration", "validation"}:
            return f"Staged {group.split}; stage the other split before publication."
        settings = self._reference_settings("m6")
        if settings is None:
            return "Publication cancelled; staged groups were preserved."
        measurements = tuple(
            self._m6_measurement(value) for value in self.m6_groups
        )
        self._m6_first_shell_frames = {
            value.measurement_group_id: value.first_shell_frames
            for value in measurements
        }
        publication = publish_m6_reference_dataset(measurements, settings)
        self._m6_publication = publication
        return publication.package_path

    def publish_orientation_reference(
        self,
        current: CurrentDomainAnalysisWorkspace,
    ) -> object:
        if self._orientation_publication is not None:
            raise RuntimeError(
                "The published Orientation reference is immutable; start a new "
                "release workflow to stage another version."
            )
        group = self._stage_current(current)
        self._orientation_groups[group.split] = group
        if set(self._orientation_groups) != {"calibration", "validation"}:
            return f"Staged {group.split}; stage the other split before publication."
        settings = self._reference_settings("orientation")
        if settings is None:
            return "Publication cancelled; staged groups were preserved."
        measurements = tuple(
            self._orientation_measurement(self._orientation_groups[split])
            for split in ("calibration", "validation")
        )
        publication = publish_orientation_reference_dataset(
            measurements,
            settings,
        )
        self._orientation_publication = publication
        return publication.package_path

    def _stage_current(
        self,
        current: CurrentDomainAnalysisWorkspace,
    ) -> StagedReferenceMeasurement:
        state, series, analysis_series, _library = current()
        if state.draft is None or state.published_result is None:
            raise ValueError("Reference staging requires a published analysis.")
        split, accepted = QInputDialog.getItem(
            self._owner,
            "Reference split",
            "Whole measurement group split",
            ("calibration", "validation"),
            -1,
            False,
        )
        if not accepted or split not in {"calibration", "validation"}:
            raise ValueError("Reference split selection was cancelled.")
        default_id = f"{Path(series.source_path).stem}-{split}"
        group_id, accepted = QInputDialog.getText(
            self._owner,
            "Measurement group",
            "Stable measurement_group_id",
            text=default_id,
        )
        if not accepted:
            raise ValueError("Measurement group staging was cancelled.")
        acquisition_fingerprint = self._source_identity(
            "Stable acquisition fingerprint",
        )
        lineage_fingerprint = self._source_identity(
            "Stable sample/condition lineage fingerprint",
        )
        normalized_split: ReferenceSplit = (
            "calibration" if split == "calibration" else "validation"
        )
        return StagedReferenceMeasurement(
            group_id.strip(),
            normalized_split,
            state,
            series,
            analysis_series,
            acquisition_fingerprint,
            lineage_fingerprint,
        )

    def _source_identity(self, label: str) -> str:
        value, accepted = QInputDialog.getText(
            self._owner,
            "Measurement source identity",
            label,
        )
        normalized = value.strip()
        if not accepted or not normalized:
            raise ValueError(f"{label} entry was cancelled or empty.")
        return normalized

    @overload
    def _reference_settings(
        self,
        target: Literal["m6"],
    ) -> M6ReferenceDatasetSettings | None: ...

    @overload
    def _reference_settings(
        self,
        target: Literal["orientation"],
    ) -> OrientationReferenceDatasetSettings | None: ...

    def _reference_settings(
        self,
        target: Literal["m6", "orientation"],
    ) -> M6ReferenceDatasetSettings | OrientationReferenceDatasetSettings | None:
        dataset_id, accepted = QInputDialog.getText(
            self._owner,
            f"Publish {target} reference",
            "Stable dataset_id",
        )
        if not accepted or not dataset_id.strip():
            return None
        directory = QFileDialog.getExistingDirectory(
            self._owner,
            f"Publish {target} Reference Dataset v2",
        )
        if not directory:
            return None
        settings_type = (
            M6ReferenceDatasetSettings
            if target == "m6"
            else OrientationReferenceDatasetSettings
        )
        return settings_type(
            destination=Path(directory) / f"{dataset_id.strip()}-reference-v2",
            dataset_id=dataset_id.strip(),
            publication_reason="Operator publication from Domain Analysis",
        )

    def _m6_measurement(
        self,
        group: StagedReferenceMeasurement,
    ) -> M6ReferenceMeasurementGroup:
        publication = group.state.published_result
        assert publication is not None and publication.result.m6_gate is not None
        first_shell_frames, first_shell_edges = self._first_shell_reference(
            group,
            publication.result.m6_gate.frames,
        )
        return M6ReferenceMeasurementGroup(
            measurement_group_id=group.measurement_group_id,
            split=group.split,
            source_revision=self._source_revision(group, M6ReferenceSourceRevision),
            snapshot=group.state,
            first_shell_frames=first_shell_frames,
            first_shell_edges=first_shell_edges,
        )

    def _first_shell_reference(
        self,
        group: StagedReferenceMeasurement,
        frames: tuple[M6FrameGate, ...],
    ) -> tuple[
        tuple[M6ReferenceFirstShellFrame, ...],
        tuple[M6ReferenceFirstShellEdge, ...],
    ]:
        first_shell_frames: list[M6ReferenceFirstShellFrame] = []
        first_shell_edges: list[M6ReferenceFirstShellEdge] = []
        for frame in frames:
            symmetry, accepted = QInputDialog.getItem(
                self._owner,
                f"First-shell reference: {group.measurement_group_id}",
                f"Symmetry for {frame.physical_frame_id}",
                ("trifold", "sixfold"),
                -1,
                False,
            )
            if not accepted or symmetry not in {"trifold", "sixfold"}:
                raise ValueError("First-shell symmetry selection was cancelled.")
            first_shell_frames.append(M6ReferenceFirstShellFrame(
                frame.physical_frame_id,
                "trifold" if symmetry == "trifold" else "sixfold",
            ))
            edge_text, accepted = QInputDialog.getMultiLineText(
                self._owner,
                f"First-shell reference: {group.measurement_group_id}",
                (
                    f"Reviewed edges for {frame.physical_frame_id}; "
                    "one source_id_a,source_id_b pair per line"
                ),
            )
            if not accepted:
                raise ValueError("First-shell edge entry was cancelled.")
            first_shell_edges.extend(
                self._first_shell_edges(frame.physical_frame_id, edge_text)
            )
        return tuple(first_shell_frames), tuple(first_shell_edges)

    @staticmethod
    def _first_shell_edges(
        physical_frame_id: str,
        edge_text: str,
    ) -> tuple[M6ReferenceFirstShellEdge, ...]:
        edges = []
        for line in edge_text.splitlines():
            if not line.strip():
                continue
            source_ids = tuple(value.strip() for value in line.split(","))
            if len(source_ids) != 2 or not all(source_ids):
                raise ValueError(
                    "Each reviewed first-shell edge must contain exactly two "
                    "comma-separated source IDs."
                )
            edges.append(M6ReferenceFirstShellEdge(
                physical_frame_id,
                source_ids[0],
                source_ids[1],
            ))
        return tuple(edges)

    def _orientation_measurement(
        self,
        group: StagedReferenceMeasurement,
    ) -> OrientationReferenceMeasurementGroup:
        segmentations = group.series.molecular_segmentations
        if segmentations is None:
            raise ValueError("Orientation reference publication requires masks.")
        draft = group.state.draft
        assert draft is not None
        coordinates = []
        for frame_index in draft.frame_indices:
            centroids = tuple(
                MolecularCentroid.from_segmentation(
                    value,
                    frame_shape=group.series.frame_shape,
                )
                for value in segmentations.get_segmentations(
                    frame_index,
                    source_view="raw",
                )
            )
            coordinates.append(build_molecular_sample_coordinates(
                group.series,
                centroids,
                frame_index=frame_index,
                source_view="raw",
            ))
        return OrientationReferenceMeasurementGroup(
            measurement_group_id=group.measurement_group_id,
            split=group.split,
            source_revision=self._source_revision(
                group,
                OrientationReferenceSourceRevision,
            ),
            snapshot=group.state,
            series=group.series,
            sample_coordinates=tuple(coordinates),
        )

    @staticmethod
    def _source_revision(
        group: StagedReferenceMeasurement,
        revision_type: type[ReferenceSourceRevision],
    ) -> ReferenceSourceRevision:
        source_path = Path(group.series.source_path).resolve()
        return revision_type.from_path(
            source_path,
            source_file_name=source_path.name,
            acquisition_fingerprint=group.acquisition_fingerprint,
            lineage_fingerprint=group.lineage_fingerprint,
        )


__all__ = [
    "CurrentDomainAnalysisWorkspace",
    "DomainAnalysisReferenceWorkflow",
    "StagedReferenceMeasurement",
]
