from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .domain_analysis.classifier_models import ClassifierOutcome
from .domain_analysis.classifier_contract import DomainLabel, DomainLabelSummary
from .domain_analysis.models import M6PublishedComponent
from .domain_analysis.texture_abc_adapter import ABC_ORIENTATION_CLASSIFIER_ID
from .domain_analysis.workspace_controller import (
    DomainAnalysisPublication,
    DomainComponentKey,
)
from .orientation_domain_frame_aggregates import M6OrientationFrameAggregates


M6CurrentFrameQcStatus = Literal[
    "insufficient_bonds_for_length_stats",
    "bond_length_heterogeneity",
    "edge_truncated",
    "footprint_disconnected",
]
DomainClassificationStatus = Literal[
    "available",
    "not_applicable",
    "not_requested",
    "unavailable",
]
DomainRowSelectionKey: TypeAlias = int | DomainComponentKey


@dataclass(frozen=True)
class M6CurrentFrameDomainRow:
    """Presentation-neutral metrics for one ordered M6 component."""

    selection_key: DomainRowSelectionKey
    ordered_component_id: int | None
    m6_orientation_domain_id: int | None
    component_type: str
    molecule_count: int
    molecule_fraction_of_valid_representatives: float | None
    footprint_fraction_of_valid_fov: float | None
    footprint_area_nm2: float
    orientation_deg: float | None
    domain_mean_local_q6: float | None
    domain_coherent_q6: float | None
    domain_median_bond_length_nm: float | None
    domain_bond_length_mad_nm: float | None
    domain_bond_length_iqr_nm: float | None
    domain_bond_length_robust_cv: float | None
    qc_statuses: tuple[str, ...]
    centroid_xy_nm: tuple[float, float] | None = None
    classification_status: DomainClassificationStatus | None = None
    classification_label: DomainLabel | None = None
    classification_error: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.selection_key, DomainComponentKey):
            _validate_domain_analysis_row(self)
            return
        if (
            isinstance(self.selection_key, bool)
            or not isinstance(self.selection_key, int)
            or self.selection_key < 0
            or self.ordered_component_id != self.selection_key
        ):
            raise ValueError("A legacy row requires its non-negative ordered ID.")
        if any((
            self.centroid_xy_nm is not None,
            self.classification_status is not None,
            self.classification_label is not None,
            self.classification_error is not None,
        )):
            raise ValueError("A legacy row cannot contain Domain Analysis fields.")

    @property
    def component_key(self) -> DomainComponentKey | None:
        return (
            self.selection_key
            if isinstance(self.selection_key, DomainComponentKey)
            else None
        )

    @property
    def stable_id(self) -> str:
        if isinstance(self.selection_key, DomainComponentKey):
            return self.selection_key.lattice_domain_id
        if self.m6_orientation_domain_id is not None:
            return str(self.m6_orientation_domain_id)
        return str(self.selection_key)


@dataclass(frozen=True)
class M6CurrentFrameSummary:
    """Frame-level M6 values required for quantitative UI review."""

    mean_local_q6_interior: float | None
    mean_local_q6_all_valid: float | None
    global_q6_interior: float | None
    edge_truncated_fraction_of_valid_representatives: float | None
    full_domain_count: int
    small_ordered_island_count: int
    full_domain_molecule_fraction: float | None
    small_island_molecule_fraction: float | None
    unassigned_molecule_fraction: float | None
    full_domain_footprint_fraction: float | None
    small_island_footprint_fraction: float | None
    unassigned_supported_footprint_fraction: float | None
    unsupported_background_fraction: float | None
    duplicate_excluded_fraction_of_original: float | None
    invalid_position_fraction_of_original: float | None
    full_domain_molecule_weighted_coherent_q6: float | None
    full_domain_footprint_weighted_coherent_q6: float | None
    domain_molecule_entropy: float | None
    domain_footprint_entropy: float | None


@dataclass(frozen=True)
class M6CurrentFrameResults:
    domains: tuple[M6CurrentFrameDomainRow, ...]
    summary: M6CurrentFrameSummary | None
    empty_message: str | None
    presentation_kind: Literal["legacy_m6", "domain_analysis"] = "legacy_m6"

    def __post_init__(self) -> None:
        domains = tuple(self.domains)
        if any(not isinstance(row, M6CurrentFrameDomainRow) for row in domains):
            raise TypeError("domains must contain M6CurrentFrameDomainRow values.")
        object.__setattr__(self, "domains", domains)
        if self.presentation_kind == "legacy_m6":
            if not isinstance(self.summary, M6CurrentFrameSummary) or any(
                row.component_key is not None for row in domains
            ):
                raise ValueError("Legacy M6 results require legacy rows and summary.")
            return
        if self.presentation_kind != "domain_analysis":
            raise ValueError("Unsupported current-frame presentation kind.")
        if self.summary is not None or any(
            row.component_key is None for row in domains
        ):
            raise ValueError(
                "Domain Analysis results require canonical rows without summary."
            )


def build_m6_current_frame_results(
    aggregates: M6OrientationFrameAggregates,
) -> M6CurrentFrameResults:
    """Join component, footprint, and frame metrics without recomputation."""
    if not isinstance(aggregates, M6OrientationFrameAggregates):
        raise TypeError("aggregates must be M6OrientationFrameAggregates.")
    footprints = {
        component.ordered_component_id: component
        for component in aggregates.footprint_partition.components
    }
    rows = []
    for metrics in aggregates.domain_metrics.components:
        footprint = footprints[metrics.ordered_component_id]
        qc_statuses: list[M6CurrentFrameQcStatus] = []
        if metrics.insufficient_bonds_for_length_stats_qc:
            qc_statuses.append("insufficient_bonds_for_length_stats")
        if metrics.bond_length_heterogeneity_qc:
            qc_statuses.append("bond_length_heterogeneity")
        if footprint.edge_truncated:
            qc_statuses.append("edge_truncated")
        if footprint.footprint_disconnected_qc:
            qc_statuses.append("footprint_disconnected")
        rows.append(
            M6CurrentFrameDomainRow(
                selection_key=metrics.ordered_component_id,
                ordered_component_id=metrics.ordered_component_id,
                m6_orientation_domain_id=metrics.m6_orientation_domain_id,
                component_type=metrics.component_type,
                molecule_count=metrics.molecule_count,
                molecule_fraction_of_valid_representatives=(
                    metrics.molecule_fraction_of_valid_representatives
                ),
                footprint_fraction_of_valid_fov=(
                    footprint.footprint_fraction_of_valid_fov
                ),
                footprint_area_nm2=footprint.footprint_area_nm2,
                orientation_deg=metrics.orientation_deg,
                domain_mean_local_q6=metrics.domain_mean_local_q6,
                domain_coherent_q6=metrics.domain_coherent_q6,
                domain_median_bond_length_nm=(
                    metrics.domain_median_bond_length_nm
                ),
                domain_bond_length_mad_nm=metrics.domain_bond_length_mad_nm,
                domain_bond_length_iqr_nm=metrics.domain_bond_length_iqr_nm,
                domain_bond_length_robust_cv=(
                    metrics.domain_bond_length_robust_cv
                ),
                qc_statuses=tuple(qc_statuses),
            )
        )
    summary = M6CurrentFrameSummary(
        mean_local_q6_interior=aggregates.mean_local_q6_interior,
        mean_local_q6_all_valid=aggregates.mean_local_q6_all_valid,
        global_q6_interior=aggregates.global_q6_interior,
        edge_truncated_fraction_of_valid_representatives=(
            aggregates.edge_truncated_fraction_of_valid_representatives
        ),
        full_domain_count=aggregates.full_domain_count,
        small_ordered_island_count=aggregates.small_ordered_island_count,
        full_domain_molecule_fraction=aggregates.full_domain_molecule_fraction,
        small_island_molecule_fraction=aggregates.small_island_molecule_fraction,
        unassigned_molecule_fraction=aggregates.unassigned_molecule_fraction,
        full_domain_footprint_fraction=aggregates.full_domain_footprint_fraction,
        small_island_footprint_fraction=aggregates.small_island_footprint_fraction,
        unassigned_supported_footprint_fraction=(
            aggregates.unassigned_supported_footprint_fraction
        ),
        unsupported_background_fraction=aggregates.unsupported_background_fraction,
        duplicate_excluded_fraction_of_original=(
            aggregates.duplicate_excluded_fraction_of_original
        ),
        invalid_position_fraction_of_original=(
            aggregates.invalid_position_fraction_of_original
        ),
        full_domain_molecule_weighted_coherent_q6=(
            aggregates.full_domain_molecule_weighted_coherent_q6
        ),
        full_domain_footprint_weighted_coherent_q6=(
            aggregates.full_domain_footprint_weighted_coherent_q6
        ),
        domain_molecule_entropy=aggregates.domain_molecule_entropy,
        domain_footprint_entropy=aggregates.domain_footprint_entropy,
    )
    domains = tuple(rows)
    return M6CurrentFrameResults(
        domains=domains,
        summary=summary,
        empty_message=None if domains else "No M6 domains in current frame.",
    )


def build_domain_analysis_current_frame_results(
    publication: DomainAnalysisPublication | None,
    *,
    physical_frame_id: str,
) -> M6CurrentFrameResults:
    """Project one published Domain Analysis frame without recomputation."""

    if publication is not None and not isinstance(
        publication,
        DomainAnalysisPublication,
    ):
        raise TypeError("publication must be a DomainAnalysisPublication or None.")
    if not isinstance(physical_frame_id, str) or not physical_frame_id.strip():
        raise ValueError("physical_frame_id must be a non-empty string.")
    if publication is None:
        return _empty_domain_analysis_results(
            "No published Domain Analysis result."
        )
    gate = publication.result.m6_gate
    if gate is None:
        raise ValueError("A Domain Analysis publication must contain an M6 gate.")
    frame = next(
        (
            value
            for value in gate.frames
            if value.physical_frame_id == physical_frame_id
        ),
        None,
    )
    if frame is None:
        return _empty_domain_analysis_results(
            "No published Domain Analysis result for the current frame."
        )
    outcome = _abc_outcome(publication)
    summaries = {
        summary.lattice_domain_id: summary
        for summary in (() if outcome is None else outcome.domain_summaries)
        if summary.physical_frame_id == physical_frame_id
    }
    components = frame.full_domains + frame.small_ordered_islands
    rows = tuple(
        _domain_analysis_row(
            component,
            physical_frame_id=physical_frame_id,
            outcome=outcome,
            classification=(
                None
                if component.component_type == "small_ordered_island"
                else summaries.get(component.lattice_domain_id)
            ),
        )
        for component in components
    )
    empty_message = None
    if not rows:
        empty_message = "No M6 domains or small ordered islands in current frame."
        if outcome is not None and outcome.status == "failed":
            empty_message += f" M6-Gated A/B/C unavailable: {outcome.error_message}."
    return M6CurrentFrameResults(
        domains=rows,
        summary=None,
        empty_message=empty_message,
        presentation_kind="domain_analysis",
    )


def _empty_domain_analysis_results(message: str) -> M6CurrentFrameResults:
    return M6CurrentFrameResults(
        domains=(),
        summary=None,
        empty_message=message,
        presentation_kind="domain_analysis",
    )


def _abc_outcome(
    publication: DomainAnalysisPublication,
) -> ClassifierOutcome | None:
    return next(
        (
            outcome
            for outcome in (publication.result.classifier_outcomes or ())
            if outcome.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        ),
        None,
    )


def _domain_analysis_row(
    component: M6PublishedComponent,
    *,
    physical_frame_id: str,
    outcome: ClassifierOutcome | None,
    classification: DomainLabelSummary | None,
) -> M6CurrentFrameDomainRow:
    status, label, error = _classification_value(
        component,
        outcome,
        classification,
    )
    return M6CurrentFrameDomainRow(
        selection_key=DomainComponentKey(
            physical_frame_id,
            component.lattice_domain_id,
        ),
        ordered_component_id=None,
        m6_orientation_domain_id=None,
        component_type=component.component_type,
        molecule_count=len(component.members),
        molecule_fraction_of_valid_representatives=None,
        footprint_fraction_of_valid_fov=None,
        footprint_area_nm2=component.footprint_area_nm2,
        orientation_deg=None,
        domain_mean_local_q6=None,
        domain_coherent_q6=None,
        domain_median_bond_length_nm=None,
        domain_bond_length_mad_nm=None,
        domain_bond_length_iqr_nm=None,
        domain_bond_length_robust_cv=None,
        qc_statuses=component.qc_flags,
        centroid_xy_nm=component.centroid_xy_nm,
        classification_status=status,
        classification_label=label,
        classification_error=error,
    )


def _classification_value(
    component: M6PublishedComponent,
    outcome: ClassifierOutcome | None,
    summary: DomainLabelSummary | None,
) -> tuple[DomainClassificationStatus, DomainLabel | None, str | None]:
    if component.component_type == "small_ordered_island":
        return "not_applicable", None, None
    if outcome is None:
        return "not_requested", None, None
    if outcome.status == "failed":
        return "unavailable", None, outcome.error_message
    if summary is None:
        return "unavailable", None, "Missing domain summary."
    return "available", summary.label, None


def _validate_domain_analysis_row(row: M6CurrentFrameDomainRow) -> None:
    if row.ordered_component_id is not None or row.m6_orientation_domain_id is not None:
        raise ValueError("A Domain Analysis row cannot contain legacy IDs.")
    if row.centroid_xy_nm is None or row.classification_status is None:
        raise ValueError("A Domain Analysis row requires centroid and classifier state.")
    valid_statuses = {
        "available",
        "not_applicable",
        "not_requested",
        "unavailable",
    }
    if row.classification_status not in valid_statuses:
        raise ValueError("Unsupported Domain Analysis classifier state.")
    is_island = row.component_type == "small_ordered_island"
    if is_island != (row.classification_status == "not_applicable"):
        raise ValueError("Only small ordered islands are not classifiable.")
    legacy_metrics = (
        row.molecule_fraction_of_valid_representatives,
        row.footprint_fraction_of_valid_fov,
        row.orientation_deg,
        row.domain_mean_local_q6,
        row.domain_coherent_q6,
        row.domain_median_bond_length_nm,
        row.domain_bond_length_mad_nm,
        row.domain_bond_length_iqr_nm,
        row.domain_bond_length_robust_cv,
    )
    if any(value is not None for value in legacy_metrics):
        raise ValueError("A Domain Analysis row cannot contain legacy metrics.")
    if row.classification_status == "available":
        if row.classification_label is None or row.classification_error is not None:
            raise ValueError("Available classification requires only a label.")
    elif row.classification_label is not None:
        raise ValueError("Unavailable classification cannot contain a label.")
    if row.classification_status == "unavailable":
        if not row.classification_error:
            raise ValueError("Unavailable classification requires a diagnosis.")
    elif row.classification_error is not None:
        raise ValueError("Only unavailable classification can contain a diagnosis.")
