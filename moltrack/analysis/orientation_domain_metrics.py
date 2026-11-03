from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite
from typing import Literal

import numpy as np

from ._orientation_domain_common import (
    component_m6_orientation_deg,
    m6_orientation_distance_deg,
    validate_m6_domain_analysis_inputs,
)
from ._m6_settings_fingerprint import m6_settings_fingerprint
from .first_shell_graph import FirstShellGraph, OrientationReference
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .orientation_domain_models import (
    LatticeOrientationDomain,
    M6OrientationDomainSegmentation,
)


@dataclass(frozen=True)
class M6OrientationComponentMetrics:
    """Population, M6-quality, geometry, and bond metrics for one component."""

    component: LatticeOrientationDomain
    molecule_fraction_of_valid_representatives: float
    domain_mean_local_q6: float
    domain_coherent_q6: float
    min_x_nm: float
    min_y_nm: float
    max_x_nm: float
    max_y_nm: float
    internal_first_shell_bond_count: int
    domain_median_bond_length_nm: float | None
    domain_bond_length_mad_nm: float | None
    domain_bond_length_iqr_nm: float | None
    domain_bond_length_robust_cv: float | None
    insufficient_bonds_for_length_stats_qc: bool
    bond_length_heterogeneity_qc: bool

    def __post_init__(self) -> None:
        if not isinstance(self.component, LatticeOrientationDomain):
            raise TypeError("component must be a LatticeOrientationDomain.")

        molecule_fraction = _unit_float(
            self.molecule_fraction_of_valid_representatives,
            "molecule_fraction_of_valid_representatives",
        )
        mean_local_q6 = _unit_float(self.domain_mean_local_q6, "domain_mean_local_q6")
        coherent_q6 = _unit_float(self.domain_coherent_q6, "domain_coherent_q6")
        if coherent_q6 > mean_local_q6 and not isclose(
            coherent_q6,
            mean_local_q6,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("domain_coherent_q6 cannot exceed domain_mean_local_q6.")

        min_x = _finite_float(self.min_x_nm, "min_x_nm")
        min_y = _finite_float(self.min_y_nm, "min_y_nm")
        max_x = _finite_float(self.max_x_nm, "max_x_nm")
        max_y = _finite_float(self.max_y_nm, "max_y_nm")
        centroid_within_bounds = (
            min_x <= self.centroid_x_nm <= max_x
            and min_y <= self.centroid_y_nm <= max_y
        )
        if not centroid_within_bounds:
            raise ValueError("Domain centroid must lie within its axis-aligned bounds.")

        bond_count = _non_negative_int(
            self.internal_first_shell_bond_count,
            "internal_first_shell_bond_count",
        )
        bond_statistics = _normalize_bond_statistics(
            self.domain_median_bond_length_nm,
            self.domain_bond_length_mad_nm,
            self.domain_bond_length_iqr_nm,
            self.domain_bond_length_robust_cv,
        )
        if not isinstance(self.insufficient_bonds_for_length_stats_qc, bool):
            raise TypeError("insufficient_bonds_for_length_stats_qc must be a boolean.")
        if not isinstance(self.bond_length_heterogeneity_qc, bool):
            raise TypeError("bond_length_heterogeneity_qc must be a boolean.")
        if self.insufficient_bonds_for_length_stats_qc != (bond_statistics[0] is None):
            raise ValueError(
                "insufficient_bonds_for_length_stats_qc must indicate unavailable statistics."
            )
        if bond_statistics[0] is None and self.bond_length_heterogeneity_qc:
            raise ValueError("Unavailable bond statistics cannot be heterogeneous.")

        object.__setattr__(
            self,
            "molecule_fraction_of_valid_representatives",
            molecule_fraction,
        )
        object.__setattr__(self, "domain_mean_local_q6", mean_local_q6)
        object.__setattr__(self, "domain_coherent_q6", coherent_q6)
        object.__setattr__(self, "min_x_nm", min_x)
        object.__setattr__(self, "min_y_nm", min_y)
        object.__setattr__(self, "max_x_nm", max_x)
        object.__setattr__(self, "max_y_nm", max_y)
        object.__setattr__(self, "internal_first_shell_bond_count", bond_count)
        object.__setattr__(self, "domain_median_bond_length_nm", bond_statistics[0])
        object.__setattr__(self, "domain_bond_length_mad_nm", bond_statistics[1])
        object.__setattr__(self, "domain_bond_length_iqr_nm", bond_statistics[2])
        object.__setattr__(self, "domain_bond_length_robust_cv", bond_statistics[3])

    @property
    def ordered_component_id(self) -> int:
        return self.component.ordered_component_id

    @property
    def m6_orientation_domain_id(self) -> int | None:
        return self.component.m6_orientation_domain_id

    @property
    def component_type(self) -> Literal["full_domain", "small_ordered_island"]:
        return self.component.component_type

    @property
    def point_indices(self) -> tuple[int, ...]:
        return self.component.point_indices

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.component.source_ids

    @property
    def molecule_count(self) -> int:
        return self.component.molecule_count

    @property
    def orientation_deg(self) -> float:
        return self.component.orientation_deg

    @property
    def centroid_x_nm(self) -> float:
        return self.component.centroid_x_nm

    @property
    def centroid_y_nm(self) -> float:
        return self.component.centroid_y_nm


@dataclass(frozen=True)
class M6OrientationDomainMetrics:
    """Basic metrics for every final M6 component in one point field."""

    segmentation: M6OrientationDomainSegmentation
    valid_representative_count: int
    components: tuple[M6OrientationComponentMetrics, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.segmentation, M6OrientationDomainSegmentation):
            raise TypeError("segmentation must be an M6OrientationDomainSegmentation.")
        valid_count = _non_negative_int(
            self.valid_representative_count,
            "valid_representative_count",
        )
        expected_valid_count = sum(
            status not in {"duplicate_excluded", "invalid_position"}
            for status in self.segmentation.assignment_status
        )
        if valid_count != expected_valid_count:
            raise ValueError(
                "valid_representative_count must follow segmentation assignment statuses."
            )

        components = tuple(self.components)
        if any(not isinstance(value, M6OrientationComponentMetrics) for value in components):
            raise TypeError(
                "components must contain M6OrientationComponentMetrics values."
            )
        if tuple(value.component for value in components) != self.segmentation.components:
            raise ValueError("Metrics must describe the segmentation components in order.")

        for component in components:
            expected_fraction = component.molecule_count / valid_count
            if not isclose(
                component.molecule_fraction_of_valid_representatives,
                expected_fraction,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "molecule_fraction_of_valid_representatives must use valid representatives."
                )
            has_enough_bonds = (
                component.internal_first_shell_bond_count
                >= self.segmentation.settings.min_bonds_for_domain_length_stats
            )
            if has_enough_bonds == component.insufficient_bonds_for_length_stats_qc:
                raise ValueError(
                    "Bond-statistics QC must use min_bonds_for_domain_length_stats."
                )
            expected_heterogeneity = (
                component.domain_bond_length_robust_cv is not None
                and component.domain_bond_length_robust_cv
                >= self.segmentation.settings.domain_bond_length_robust_cv_qc_threshold
            )
            if component.bond_length_heterogeneity_qc != expected_heterogeneity:
                raise ValueError(
                    "bond_length_heterogeneity_qc must use the configured robust-CV threshold."
                )
        object.__setattr__(self, "valid_representative_count", valid_count)
        object.__setattr__(self, "components", components)

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.segmentation.source_ids

    @property
    def point_count(self) -> int:
        return self.segmentation.point_count

    @property
    def settings(self) -> MolecularM6OrientationAnalysisSettings:
        return self.segmentation.settings

    @property
    def coordinate_frame(self) -> Literal["sample_nm"]:
        return self.segmentation.coordinate_frame

    @property
    def orientation_reference(self) -> OrientationReference:
        return self.segmentation.orientation_reference

    @property
    def spatial_calibration_fingerprint(self) -> str:
        return self.segmentation.spatial_calibration_fingerprint

    @property
    def registration_fingerprint(self) -> str:
        return self.segmentation.registration_fingerprint

    @property
    def point_coordinate_fingerprint(self) -> str:
        return self.segmentation.point_coordinate_fingerprint

    def component_for_ordered_id(
        self,
        ordered_component_id: int,
    ) -> M6OrientationComponentMetrics:
        component_id = _non_negative_int(ordered_component_id, "ordered_component_id")
        try:
            return self.components[component_id]
        except IndexError as exc:
            raise KeyError(f"Unknown ordered_component_id: {component_id}.") from exc


def compute_m6_orientation_domain_metrics(
    points_xy_nm: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    segmentation: M6OrientationDomainSegmentation,
    settings: MolecularM6OrientationAnalysisSettings,
) -> M6OrientationDomainMetrics:
    """Measure final components from unique internal first-shell bonds."""

    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    points = validate_m6_domain_analysis_inputs(
        points_xy_nm,
        first_shell_graph=first_shell_graph,
        local_order=local_order,
        settings=settings,
    )
    expected_settings_fingerprint = m6_settings_fingerprint(settings)
    if (
        first_shell_graph.analysis_settings_fingerprint
        != expected_settings_fingerprint
        or local_order.analysis_settings_fingerprint
        != expected_settings_fingerprint
    ):
        raise ValueError("Graph and local order must preserve the settings fingerprint.")
    _validate_segmentation_context(
        segmentation,
        first_shell_graph=first_shell_graph,
        local_order=local_order,
        settings=settings,
    )
    valid_count = sum(
        status not in {"duplicate_excluded", "invalid_position"}
        for status in segmentation.assignment_status
    )
    components = tuple(
        _measure_component(
            component,
            points=points,
            graph=first_shell_graph,
            local_order=local_order,
            valid_representative_count=valid_count,
            settings=settings,
        )
        for component in segmentation.components
    )
    return M6OrientationDomainMetrics(
        segmentation=segmentation,
        valid_representative_count=valid_count,
        components=components,
    )


def _measure_component(
    component: LatticeOrientationDomain,
    *,
    points: np.ndarray,
    graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    valid_representative_count: int,
    settings: MolecularM6OrientationAnalysisSettings,
) -> M6OrientationComponentMetrics:
    member_indices = component.point_indices
    ordered_members = tuple(
        sorted(member_indices, key=lambda index: local_order.source_ids[index])
    )
    psi_values = tuple(local_order.psi6[index] for index in ordered_members)
    if any(value is None for value in psi_values):
        raise ValueError("Domain points require valid psi6 values.")
    normalized_psi = tuple(complex(value) for value in psi_values if value is not None)
    count = component.molecule_count
    mean_local_q6 = fsum(abs(value) for value in normalized_psi) / count
    mean_psi = complex(
        fsum(value.real for value in normalized_psi) / count,
        fsum(value.imag for value in normalized_psi) / count,
    )

    member_set = set(member_indices)
    internal_distances = tuple(
        sorted(
            distance_nm
            for (left, right), distance_nm in zip(
                graph.edges_ij,
                graph.distances_nm,
            )
            if left in member_set and right in member_set and distance_nm > 0.0
        )
    )
    bond_statistics = _compute_bond_statistics(
        internal_distances,
        minimum_count=settings.min_bonds_for_domain_length_stats,
    )
    coordinates = points[np.asarray(member_indices, dtype=np.int64)]
    centroid_x = fsum(float(points[index, 0]) for index in ordered_members) / count
    centroid_y = fsum(float(points[index, 1]) for index in ordered_members) / count
    orientation_deg = component_m6_orientation_deg(member_indices, local_order)
    if not isclose(
        component.centroid_x_nm,
        centroid_x,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("Component centroid_x_nm must match points_xy_nm.")
    if not isclose(
        component.centroid_y_nm,
        centroid_y,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("Component centroid_y_nm must match points_xy_nm.")
    if m6_orientation_distance_deg(component.orientation_deg, orientation_deg) > 1e-10:
        raise ValueError("Component orientation_deg must match local_order psi6 values.")
    robust_cv = bond_statistics[3]
    return M6OrientationComponentMetrics(
        component=component,
        molecule_fraction_of_valid_representatives=count / valid_representative_count,
        domain_mean_local_q6=mean_local_q6,
        domain_coherent_q6=abs(mean_psi),
        min_x_nm=float(np.min(coordinates[:, 0])),
        min_y_nm=float(np.min(coordinates[:, 1])),
        max_x_nm=float(np.max(coordinates[:, 0])),
        max_y_nm=float(np.max(coordinates[:, 1])),
        internal_first_shell_bond_count=len(internal_distances),
        domain_median_bond_length_nm=bond_statistics[0],
        domain_bond_length_mad_nm=bond_statistics[1],
        domain_bond_length_iqr_nm=bond_statistics[2],
        domain_bond_length_robust_cv=robust_cv,
        insufficient_bonds_for_length_stats_qc=bond_statistics[0] is None,
        bond_length_heterogeneity_qc=(
            robust_cv is not None
            and robust_cv >= settings.domain_bond_length_robust_cv_qc_threshold
        ),
    )


def _validate_segmentation_context(
    segmentation: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    if not isinstance(segmentation, M6OrientationDomainSegmentation):
        raise TypeError("segmentation must be an M6OrientationDomainSegmentation.")
    if segmentation.settings != settings:
        raise ValueError("segmentation must use the supplied settings.")
    if (
        segmentation.source_ids != first_shell_graph.point_ids
        or segmentation.point_count != first_shell_graph.point_count
        or segmentation.physical_duplicate_qc != local_order.physical_duplicate_qc
        or segmentation.geometry_duplicate_qc != local_order.geometry_duplicate_qc
        or segmentation.edge_truncated_neighborhood
        != local_order.edge_truncated_neighborhood
    ):
        raise ValueError("segmentation must match graph and local-order point state.")
    segmentation_context = (
        segmentation.coordinate_frame,
        segmentation.orientation_reference,
        segmentation.spatial_calibration_fingerprint,
        segmentation.registration_fingerprint,
        segmentation.point_coordinate_fingerprint,
    )
    graph_context = (
        first_shell_graph.coordinate_frame,
        first_shell_graph.orientation_reference,
        first_shell_graph.spatial_calibration_fingerprint,
        first_shell_graph.registration_fingerprint,
        first_shell_graph.point_coordinate_fingerprint,
    )
    if segmentation_context != graph_context:
        raise ValueError("segmentation coordinate provenance must match first_shell_graph.")


def _compute_bond_statistics(
    distances_nm: tuple[float, ...],
    *,
    minimum_count: int,
) -> tuple[float | None, float | None, float | None, float | None]:
    if len(distances_nm) < minimum_count:
        return None, None, None, None
    distances = np.asarray(distances_nm, dtype=np.float64)
    median = float(np.median(distances))
    if median <= 0.0:
        return None, None, None, None
    mad = float(np.median(np.abs(distances - median)))
    quartile_25, quartile_75 = np.percentile(distances, (25.0, 75.0))
    return median, mad, float(quartile_75 - quartile_25), 1.4826 * mad / median


def _normalize_bond_statistics(
    median: object,
    mad: object,
    iqr: object,
    robust_cv: object,
) -> tuple[float | None, float | None, float | None, float | None]:
    values = (median, mad, iqr, robust_cv)
    if all(value is None for value in values):
        return None, None, None, None
    if any(value is None for value in values):
        raise ValueError("Bond-length statistics must be all present or all None.")
    normalized_median = _positive_float(median, "domain_median_bond_length_nm")
    normalized_mad = _non_negative_float(mad, "domain_bond_length_mad_nm")
    normalized_iqr = _non_negative_float(iqr, "domain_bond_length_iqr_nm")
    normalized_cv = _non_negative_float(robust_cv, "domain_bond_length_robust_cv")
    if not isclose(
        normalized_cv,
        1.4826 * normalized_mad / normalized_median,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("domain_bond_length_robust_cv must equal 1.4826*MAD/median.")
    return normalized_median, normalized_mad, normalized_iqr, normalized_cv


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


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized
