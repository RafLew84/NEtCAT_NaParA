from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite, log
from statistics import median

from ._m6_settings_fingerprint import m6_settings_fingerprint
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .orientation_domain_footprint import M6OrientationFootprintPartition
from .orientation_domain_metrics import M6OrientationDomainMetrics
from .sixfold_bond_order_aggregates import (
    SixfoldBondOrderAggregates,
    aggregate_local_sixfold_bond_order,
)


@dataclass(frozen=True)
class M6OrientationFrameAggregates:
    """One-frame population, area, order-quality, and domain summaries."""

    domain_metrics: M6OrientationDomainMetrics
    footprint_partition: M6OrientationFootprintPartition
    local_order_aggregates: SixfoldBondOrderAggregates
    full_domain_count: int
    small_ordered_island_count: int
    ordered_component_count: int
    original_observation_count: int
    valid_representative_count: int
    duplicate_excluded_count: int
    invalid_position_count: int
    valid_fov_area_nm2: float
    supported_area_nm2: float
    full_domain_molecule_fraction: float | None
    small_island_molecule_fraction: float | None
    unassigned_molecule_fraction: float | None
    assigned_molecule_fraction: float | None
    largest_domain_molecule_fraction: float | None
    duplicate_excluded_fraction_of_original: float | None
    invalid_position_fraction_of_original: float | None
    full_domain_footprint_fraction: float | None
    small_island_footprint_fraction: float | None
    unassigned_supported_footprint_fraction: float | None
    unsupported_background_fraction: float | None
    assigned_footprint_fraction: float | None
    largest_domain_footprint_fraction: float | None
    footprint_overlap_error_nm2: float
    non_positive_valid_fov_area_qc: bool
    mean_local_q6_interior: float | None
    global_q6_interior: float | None
    mean_local_q6_all_valid: float | None
    global_q6_all_valid: float | None
    edge_truncated_fraction_of_valid_representatives: float | None
    full_domain_molecule_weighted_coherent_q6: float | None
    full_domain_footprint_weighted_coherent_q6: float | None
    mean_full_domain_footprint_area_nm2: float | None
    median_full_domain_footprint_area_nm2: float | None
    domain_molecule_entropy: float | None
    domain_footprint_entropy: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.domain_metrics, M6OrientationDomainMetrics):
            raise TypeError("domain_metrics must be M6OrientationDomainMetrics.")
        if not isinstance(self.footprint_partition, M6OrientationFootprintPartition):
            raise TypeError(
                "footprint_partition must be M6OrientationFootprintPartition."
            )
        if not isinstance(self.local_order_aggregates, SixfoldBondOrderAggregates):
            raise TypeError("local_order_aggregates must be SixfoldBondOrderAggregates.")
        if self.footprint_partition.domain_metrics != self.domain_metrics:
            raise ValueError("Footprint partition must use domain_metrics.")
        segmentation = self.domain_metrics.segmentation
        expected_counts = (
            segmentation.full_domain_count,
            segmentation.small_ordered_island_count,
            segmentation.ordered_component_count,
            segmentation.point_count,
            self.domain_metrics.valid_representative_count,
            segmentation.assignment_status.count("duplicate_excluded"),
            segmentation.assignment_status.count("invalid_position"),
        )
        count_names = (
            "full_domain_count",
            "small_ordered_island_count",
            "ordered_component_count",
            "original_observation_count",
            "valid_representative_count",
            "duplicate_excluded_count",
            "invalid_position_count",
        )
        actual_counts = tuple(
            _non_negative_int(getattr(self, name), name) for name in count_names
        )
        if actual_counts != expected_counts:
            raise ValueError("Frame counters must follow segmentation populations.")
        if self.original_observation_count != (
            self.valid_representative_count
            + self.duplicate_excluded_count
            + self.invalid_position_count
        ):
            raise ValueError("Original observations must partition into V and rejections.")
        local_context = (
            self.local_order_aggregates.point_count,
            self.local_order_aggregates.duplicate_excluded_count,
            self.local_order_aggregates.invalid_position_count,
            self.local_order_aggregates.coordinate_frame,
            self.local_order_aggregates.orientation_reference,
            self.local_order_aggregates.spatial_calibration_fingerprint,
            self.local_order_aggregates.registration_fingerprint,
        )
        expected_local_context = (
            segmentation.point_count,
            self.duplicate_excluded_count,
            self.invalid_position_count,
            segmentation.coordinate_frame,
            segmentation.orientation_reference,
            segmentation.spatial_calibration_fingerprint,
            segmentation.registration_fingerprint,
        )
        if local_context != expected_local_context:
            raise ValueError("Local-order aggregates must match segmentation context.")

        valid_fov_area = _non_negative_float(
            self.valid_fov_area_nm2,
            "valid_fov_area_nm2",
        )
        supported_area = _non_negative_float(
            self.supported_area_nm2,
            "supported_area_nm2",
        )
        overlap_error = _non_negative_float(
            self.footprint_overlap_error_nm2,
            "footprint_overlap_error_nm2",
        )
        if not isclose(
            valid_fov_area,
            self.footprint_partition.valid_fov_area_nm2,
        ) or not isclose(
            supported_area,
            self.footprint_partition.supported_area_nm2,
        ):
            raise ValueError("Frame areas must come from footprint_partition.")
        if overlap_error != (
            self.footprint_partition.footprint_overlap_error_nm2
        ):
            raise ValueError("Footprint overlap error must come from footprint_partition.")
        if not isinstance(self.non_positive_valid_fov_area_qc, bool):
            raise TypeError("non_positive_valid_fov_area_qc must be a boolean.")
        if self.non_positive_valid_fov_area_qc != (self.valid_fov_area_nm2 <= 0.0):
            raise ValueError("Valid-FOV QC must indicate a non-positive area.")

        molecule_fractions = (
            self.full_domain_molecule_fraction,
            self.small_island_molecule_fraction,
            self.unassigned_molecule_fraction,
        )
        if self.valid_representative_count == 0:
            if any(value is not None for value in molecule_fractions):
                raise ValueError("Empty V requires unavailable molecule fractions.")
            if any(
                value is not None
                for value in (
                    self.assigned_molecule_fraction,
                    self.largest_domain_molecule_fraction,
                    self.edge_truncated_fraction_of_valid_representatives,
                )
            ):
                raise ValueError("Empty V requires unavailable derived fractions.")
        else:
            normalized = tuple(
                _unit_float(value, "molecule fraction")
                for value in molecule_fractions
            )
            if not isclose(fsum(normalized), 1.0, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Molecule fractions must sum to one.")
            if not isclose(
                _unit_float(self.assigned_molecule_fraction, "assigned_molecule_fraction"),
                normalized[0] + normalized[1],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Assigned molecule fraction must sum ordered categories.")
            _unit_float(
                self.largest_domain_molecule_fraction,
                "largest_domain_molecule_fraction",
            )
            _unit_float(
                self.edge_truncated_fraction_of_valid_representatives,
                "edge_truncated_fraction_of_valid_representatives",
            )
            valid_indices = tuple(
                index
                for index, status in enumerate(segmentation.assignment_status)
                if status not in {"duplicate_excluded", "invalid_position"}
            )
            expected_edge_fraction = (
                sum(
                    segmentation.edge_truncated_neighborhood[index]
                    for index in valid_indices
                )
                / self.valid_representative_count
            )
            if not isclose(
                self.edge_truncated_fraction_of_valid_representatives,
                expected_edge_fraction,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Edge-truncated fraction must use all points in V.")
            full_components = tuple(
                component
                for component in self.domain_metrics.components
                if component.component_type == "full_domain"
            )
            small_components = tuple(
                component
                for component in self.domain_metrics.components
                if component.component_type == "small_ordered_island"
            )
            full_count = sum(component.molecule_count for component in full_components)
            small_count = sum(component.molecule_count for component in small_components)
            expected_molecule_fractions = (
                full_count / self.valid_representative_count,
                small_count / self.valid_representative_count,
                (self.valid_representative_count - full_count - small_count)
                / self.valid_representative_count,
            )
            if any(
                not isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
                for actual, expected in zip(normalized, expected_molecule_fractions)
            ):
                raise ValueError("Molecule fractions must use component populations and |V|.")
            expected_largest = (
                max((component.molecule_count for component in full_components), default=0)
                / self.valid_representative_count
            )
            if not isclose(
                self.largest_domain_molecule_fraction,
                expected_largest,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Largest-domain molecule fraction must use |V|.")

        original_fractions = (
            self.duplicate_excluded_fraction_of_original,
            self.invalid_position_fraction_of_original,
        )
        if self.original_observation_count == 0:
            if any(value is not None for value in original_fractions):
                raise ValueError("Empty O requires unavailable rejection fractions.")
        else:
            expected_original_fractions = (
                self.duplicate_excluded_count / self.original_observation_count,
                self.invalid_position_count / self.original_observation_count,
            )
            if any(
                not isclose(
                    _unit_float(value, "original-observation fraction"),
                    expected,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
                for value, expected in zip(
                    original_fractions,
                    expected_original_fractions,
                )
            ):
                raise ValueError("Rejection fractions must use |O|.")

        area_fractions = (
            self.full_domain_footprint_fraction,
            self.small_island_footprint_fraction,
            self.unassigned_supported_footprint_fraction,
            self.unsupported_background_fraction,
        )
        if self.valid_fov_area_nm2 <= 0.0:
            if any(value is not None for value in area_fractions) or any(
                value is not None
                for value in (
                    self.assigned_footprint_fraction,
                    self.largest_domain_footprint_fraction,
                )
            ):
                raise ValueError("Non-positive valid FOV requires unavailable area fractions.")
        else:
            normalized_areas = tuple(
                _unit_float(value, "footprint fraction") for value in area_fractions
            )
            if not isclose(
                fsum(normalized_areas),
                1.0,
                rel_tol=1e-10,
                abs_tol=1e-10,
            ):
                raise ValueError("Footprint fractions must sum to one.")
            if not isclose(
                _unit_float(self.assigned_footprint_fraction, "assigned_footprint_fraction"),
                normalized_areas[0] + normalized_areas[1],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Assigned footprint fraction must sum ordered categories.")
            _unit_float(
                self.largest_domain_footprint_fraction,
                "largest_domain_footprint_fraction",
            )
            expected_area_fractions = (
                self.footprint_partition.full_domain_footprint_fraction,
                self.footprint_partition.small_island_footprint_fraction,
                self.footprint_partition.unassigned_supported_footprint_fraction,
                self.footprint_partition.unsupported_background_fraction,
            )
            if any(
                not isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
                for actual, expected in zip(normalized_areas, expected_area_fractions)
            ):
                raise ValueError("Area fractions must come from footprint_partition.")
            expected_largest_area = (
                max(
                    (
                        component.footprint_area_nm2
                        for component in self.footprint_partition.components
                        if component.component_type == "full_domain"
                    ),
                    default=0.0,
                )
                / self.valid_fov_area_nm2
            )
            if not isclose(
                self.largest_domain_footprint_fraction,
                expected_largest_area,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Largest-domain footprint fraction must use area(W).")

        expected_local_metrics = (
            self.local_order_aggregates.mean_local_q6_interior,
            self.local_order_aggregates.global_q6_interior,
            self.local_order_aggregates.mean_local_q6_all_valid,
            self.local_order_aggregates.global_q6_all_valid,
        )
        if (
            self.mean_local_q6_interior,
            self.global_q6_interior,
            self.mean_local_q6_all_valid,
            self.global_q6_all_valid,
        ) != expected_local_metrics:
            raise ValueError("Local q6 summaries must come from local_order_aggregates.")
        for field_name in (
            "full_domain_molecule_weighted_coherent_q6",
            "full_domain_footprint_weighted_coherent_q6",
            "domain_molecule_entropy",
            "domain_footprint_entropy",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _unit_float(value, field_name)
        for field_name in (
            "mean_full_domain_footprint_area_nm2",
            "median_full_domain_footprint_area_nm2",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _non_negative_float(value, field_name)
        full_components = tuple(
            component
            for component in self.domain_metrics.components
            if component.component_type == "full_domain"
        )
        full_footprints = tuple(
            component
            for component in self.footprint_partition.components
            if component.component_type == "full_domain"
        )
        coherent_q6 = tuple(component.domain_coherent_q6 for component in full_components)
        molecule_weights = tuple(float(component.molecule_count) for component in full_components)
        footprint_weights = tuple(component.footprint_area_nm2 for component in full_footprints)
        footprint_areas = footprint_weights
        expected_domain_values = (
            _weighted_mean(coherent_q6, molecule_weights),
            _weighted_mean(coherent_q6, footprint_weights),
            fsum(footprint_areas) / len(footprint_areas) if footprint_areas else None,
            float(median(footprint_areas)) if footprint_areas else None,
            _normalized_entropy(molecule_weights),
            _normalized_entropy(footprint_weights),
        )
        actual_domain_values = (
            self.full_domain_molecule_weighted_coherent_q6,
            self.full_domain_footprint_weighted_coherent_q6,
            self.mean_full_domain_footprint_area_nm2,
            self.median_full_domain_footprint_area_nm2,
            self.domain_molecule_entropy,
            self.domain_footprint_entropy,
        )
        if any(
            not _optional_close(actual, expected)
            for actual, expected in zip(actual_domain_values, expected_domain_values)
        ):
            raise ValueError("Weighted domain metrics and entropies are inconsistent.")
        for name, value in zip(count_names, actual_counts):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "valid_fov_area_nm2", valid_fov_area)
        object.__setattr__(self, "supported_area_nm2", supported_area)
        object.__setattr__(self, "footprint_overlap_error_nm2", overlap_error)


def aggregate_m6_orientation_frame(
    *,
    local_order: LocalSixfoldBondOrderField,
    domain_metrics: M6OrientationDomainMetrics,
    footprint_partition: M6OrientationFootprintPartition,
) -> M6OrientationFrameAggregates:
    """Aggregate one M6 domain analysis using explicit O, V, and W denominators."""

    _validate_inputs(
        local_order=local_order,
        domain_metrics=domain_metrics,
        footprint_partition=footprint_partition,
    )
    local_aggregates = aggregate_local_sixfold_bond_order(local_order)
    segmentation = domain_metrics.segmentation
    statuses = segmentation.assignment_status
    original_count = segmentation.point_count
    valid_count = domain_metrics.valid_representative_count
    duplicate_count = statuses.count("duplicate_excluded")
    invalid_count = statuses.count("invalid_position")
    full_components = tuple(
        component
        for component in domain_metrics.components
        if component.component_type == "full_domain"
    )
    full_footprints = tuple(
        component
        for component in footprint_partition.components
        if component.component_type == "full_domain"
    )
    full_molecule_count = sum(component.molecule_count for component in full_components)
    small_molecule_count = sum(
        component.molecule_count
        for component in domain_metrics.components
        if component.component_type == "small_ordered_island"
    )
    unassigned_count = valid_count - full_molecule_count - small_molecule_count
    if valid_count:
        molecule_fractions = (
            full_molecule_count / valid_count,
            small_molecule_count / valid_count,
            unassigned_count / valid_count,
        )
        assigned_molecule_fraction = molecule_fractions[0] + molecule_fractions[1]
        largest_domain_molecule_fraction = (
            max((component.molecule_count for component in full_components), default=0)
            / valid_count
        )
        valid_indices = tuple(
            index
            for index, status in enumerate(statuses)
            if status not in {"duplicate_excluded", "invalid_position"}
        )
        edge_fraction = (
            sum(local_order.edge_truncated_neighborhood[index] for index in valid_indices)
            / valid_count
        )
    else:
        molecule_fractions = (None, None, None)
        assigned_molecule_fraction = None
        largest_domain_molecule_fraction = None
        edge_fraction = None
    original_fractions = (
        (duplicate_count / original_count, invalid_count / original_count)
        if original_count
        else (None, None)
    )

    valid_fov_area = footprint_partition.valid_fov_area_nm2
    if valid_fov_area > 0.0:
        assigned_footprint_fraction = (
            footprint_partition.full_domain_footprint_fraction
            + footprint_partition.small_island_footprint_fraction
        )
        largest_domain_footprint_fraction = (
            max((component.footprint_area_nm2 for component in full_footprints), default=0.0)
            / valid_fov_area
        )
    else:
        assigned_footprint_fraction = None
        largest_domain_footprint_fraction = None

    full_molecule_weights = tuple(
        float(component.molecule_count) for component in full_components
    )
    full_footprint_weights = tuple(
        component.footprint_area_nm2 for component in full_footprints
    )
    coherent_q6 = tuple(component.domain_coherent_q6 for component in full_components)
    footprint_areas = tuple(component.footprint_area_nm2 for component in full_footprints)
    return M6OrientationFrameAggregates(
        domain_metrics=domain_metrics,
        footprint_partition=footprint_partition,
        local_order_aggregates=local_aggregates,
        full_domain_count=segmentation.full_domain_count,
        small_ordered_island_count=segmentation.small_ordered_island_count,
        ordered_component_count=segmentation.ordered_component_count,
        original_observation_count=original_count,
        valid_representative_count=valid_count,
        duplicate_excluded_count=duplicate_count,
        invalid_position_count=invalid_count,
        valid_fov_area_nm2=valid_fov_area,
        supported_area_nm2=footprint_partition.supported_area_nm2,
        full_domain_molecule_fraction=molecule_fractions[0],
        small_island_molecule_fraction=molecule_fractions[1],
        unassigned_molecule_fraction=molecule_fractions[2],
        assigned_molecule_fraction=assigned_molecule_fraction,
        largest_domain_molecule_fraction=largest_domain_molecule_fraction,
        duplicate_excluded_fraction_of_original=original_fractions[0],
        invalid_position_fraction_of_original=original_fractions[1],
        full_domain_footprint_fraction=footprint_partition.full_domain_footprint_fraction,
        small_island_footprint_fraction=footprint_partition.small_island_footprint_fraction,
        unassigned_supported_footprint_fraction=(
            footprint_partition.unassigned_supported_footprint_fraction
        ),
        unsupported_background_fraction=(
            footprint_partition.unsupported_background_fraction
        ),
        assigned_footprint_fraction=assigned_footprint_fraction,
        largest_domain_footprint_fraction=largest_domain_footprint_fraction,
        footprint_overlap_error_nm2=footprint_partition.footprint_overlap_error_nm2,
        non_positive_valid_fov_area_qc=valid_fov_area <= 0.0,
        mean_local_q6_interior=local_aggregates.mean_local_q6_interior,
        global_q6_interior=local_aggregates.global_q6_interior,
        mean_local_q6_all_valid=local_aggregates.mean_local_q6_all_valid,
        global_q6_all_valid=local_aggregates.global_q6_all_valid,
        edge_truncated_fraction_of_valid_representatives=edge_fraction,
        full_domain_molecule_weighted_coherent_q6=_weighted_mean(
            coherent_q6,
            full_molecule_weights,
        ),
        full_domain_footprint_weighted_coherent_q6=_weighted_mean(
            coherent_q6,
            full_footprint_weights,
        ),
        mean_full_domain_footprint_area_nm2=(
            fsum(footprint_areas) / len(footprint_areas) if footprint_areas else None
        ),
        median_full_domain_footprint_area_nm2=(
            float(median(footprint_areas)) if footprint_areas else None
        ),
        domain_molecule_entropy=_normalized_entropy(full_molecule_weights),
        domain_footprint_entropy=_normalized_entropy(full_footprint_weights),
    )


def _validate_inputs(
    *,
    local_order: object,
    domain_metrics: object,
    footprint_partition: object,
) -> None:
    if not isinstance(local_order, LocalSixfoldBondOrderField):
        raise TypeError("local_order must be LocalSixfoldBondOrderField.")
    if not isinstance(domain_metrics, M6OrientationDomainMetrics):
        raise TypeError("domain_metrics must be M6OrientationDomainMetrics.")
    if not isinstance(footprint_partition, M6OrientationFootprintPartition):
        raise TypeError("footprint_partition must be M6OrientationFootprintPartition.")
    if footprint_partition.domain_metrics != domain_metrics:
        raise ValueError("footprint_partition must use domain_metrics.")
    segmentation = domain_metrics.segmentation
    if (
        local_order.source_ids != segmentation.source_ids
        or local_order.point_count != segmentation.point_count
        or local_order.physical_duplicate_qc != segmentation.physical_duplicate_qc
        or local_order.geometry_duplicate_qc != segmentation.geometry_duplicate_qc
        or local_order.edge_truncated_neighborhood
        != segmentation.edge_truncated_neighborhood
    ):
        raise ValueError("local_order must match segmentation point state.")
    provenance = (
        local_order.coordinate_frame,
        local_order.orientation_reference,
        local_order.spatial_calibration_fingerprint,
        local_order.registration_fingerprint,
    )
    segmentation_provenance = (
        segmentation.coordinate_frame,
        segmentation.orientation_reference,
        segmentation.spatial_calibration_fingerprint,
        segmentation.registration_fingerprint,
    )
    if provenance != segmentation_provenance:
        raise ValueError("local_order and segmentation provenance must match.")
    if local_order.analysis_settings_fingerprint != m6_settings_fingerprint(
        domain_metrics.settings
    ):
        raise ValueError("local_order must preserve the analysis settings fingerprint.")
    for local_status, assignment_status in zip(
        local_order.computation_status,
        segmentation.assignment_status,
    ):
        if local_status == "valid_order":
            if assignment_status not in {"assigned", "boundary_or_disordered"}:
                raise ValueError("Valid local order requires assigned or boundary status.")
        elif local_status != assignment_status:
            raise ValueError("Non-valid local status must be preserved by segmentation.")
    for component in domain_metrics.components:
        psi_values = tuple(local_order.psi6[index] for index in component.point_indices)
        if any(value is None for value in psi_values):
            raise ValueError("Domain points require local psi6 values.")
        normalized_psi = tuple(complex(value) for value in psi_values if value is not None)
        count = len(normalized_psi)
        expected_mean_local_q6 = fsum(abs(value) for value in normalized_psi) / count
        mean_psi6 = complex(
            fsum(value.real for value in normalized_psi) / count,
            fsum(value.imag for value in normalized_psi) / count,
        )
        if not isclose(
            component.domain_mean_local_q6,
            expected_mean_local_q6,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ) or not isclose(
            component.domain_coherent_q6,
            abs(mean_psi6),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Domain q6 metrics must come from local_order psi6 values.")


def _weighted_mean(
    values: tuple[float, ...],
    weights: tuple[float, ...],
) -> float | None:
    total_weight = fsum(weights)
    if not values or total_weight <= 0.0:
        return None
    return fsum(value * weight for value, weight in zip(values, weights)) / total_weight


def _normalized_entropy(weights: tuple[float, ...]) -> float | None:
    count = len(weights)
    total_weight = fsum(weights)
    if count == 0 or total_weight <= 0.0:
        return None
    if count == 1:
        return 0.0
    probabilities = tuple(weight / total_weight for weight in weights)
    entropy = -fsum(
        probability * log(probability)
        for probability in probabilities
        if probability > 0.0
    ) / log(count)
    if isclose(entropy, 0.0, abs_tol=1e-15):
        return 0.0
    if isclose(entropy, 1.0, abs_tol=1e-15):
        return 1.0
    return entropy


def _optional_close(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not isfinite(numeric) or numeric != normalized or normalized < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized
