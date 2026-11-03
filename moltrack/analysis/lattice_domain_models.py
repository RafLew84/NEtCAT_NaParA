"""Versioned final lattice-domain contracts for one molecular frame."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from math import atan2, degrees, fsum, hypot, isclose, isfinite
from typing import Literal, Mapping, get_args

import numpy as np

from ._coordinate_fingerprint import point_coordinate_fingerprint
from .first_shell_graph import OrientationReference
from .lattice_domain_seed_growth_models import (
    LatticeDomainBoundaryReason,
    LatticeDomainPointRole,
)
from .m6_settings import MolecularM6OrientationAnalysisSettings


LATTICE_DOMAIN_ANALYSIS_SCHEMA_VERSION = 1
LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION = "moltrack-lattice-domain-analysis-v1"

LatticeDomainComponentType = Literal["full_domain", "small_ordered_island"]
LatticeDomainDominantSymmetry = Literal[
    "trifold",
    "sixfold",
    "mixed",
    "ambiguous",
]
LatticeDomainOrientationReferenceChannel = Literal[
    "m3_lattice",
    "m6",
    "joint",
    "unavailable",
]
M3M6OrientationRelationStatus = Literal[
    "available",
    "not_applicable",
    "unavailable",
    "symmetry_alias_unresolvable_from_centroids",
]


_COMPONENT_TYPES = set(get_args(LatticeDomainComponentType))
_SYMMETRIES = set(get_args(LatticeDomainDominantSymmetry))
_REFERENCE_CHANNELS = set(get_args(LatticeDomainOrientationReferenceChannel))
_RELATION_STATUSES = set(get_args(M3M6OrientationRelationStatus))
_POINT_ROLES = set(get_args(LatticeDomainPointRole))
_BOUNDARY_REASONS = set(get_args(LatticeDomainBoundaryReason))
_ORIENTATION_REFERENCES = {"+x_sample_axis", "scan_x_axis_assumed_sample_x"}


@dataclass(frozen=True)
class LatticeDomainAnalysisSettings:
    """Thresholds used only when materializing final lattice domains."""

    min_domain_size: int = 8
    min_bonds_for_length_stats: int = 5
    bond_length_robust_cv_qc_threshold: float = 0.2

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "min_domain_size",
            _positive_integer(self.min_domain_size, "min_domain_size"),
        )
        object.__setattr__(
            self,
            "min_bonds_for_length_stats",
            _positive_integer(
                self.min_bonds_for_length_stats,
                "min_bonds_for_length_stats",
            ),
        )
        threshold = _non_negative_float(
            self.bond_length_robust_cv_qc_threshold,
            "bond_length_robust_cv_qc_threshold",
        )
        object.__setattr__(self, "bond_length_robust_cv_qc_threshold", threshold)

    def to_dict(self) -> dict[str, int | float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "LatticeDomainAnalysisSettings":
        if not isinstance(payload, Mapping):
            raise TypeError("Lattice-domain analysis settings must be a mapping.")
        names = {field.name for field in fields(cls)}
        if set(payload) != names:
            raise ValueError("Lattice-domain analysis settings fields must match the schema.")
        return cls(**dict(payload))


def lattice_domain_analysis_settings_from_m6(
    settings: MolecularM6OrientationAnalysisSettings,
) -> LatticeDomainAnalysisSettings:
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    return LatticeDomainAnalysisSettings(
        min_domain_size=settings.min_domain_size,
        min_bonds_for_length_stats=settings.min_bonds_for_domain_length_stats,
        bond_length_robust_cv_qc_threshold=(
            settings.domain_bond_length_robust_cv_qc_threshold
        ),
    )


def lattice_domain_analysis_settings_fingerprint(
    settings: LatticeDomainAnalysisSettings,
) -> str:
    if not isinstance(settings, LatticeDomainAnalysisSettings):
        raise TypeError("settings must be LatticeDomainAnalysisSettings.")
    return _fingerprint(
        {
            "algorithm": LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
            "settings": settings.to_dict(),
        }
    )


@dataclass(frozen=True)
class LatticeDomainInternalBond:
    """One canonical internal first-shell bond in sample coordinates."""

    source_ids: tuple[str, str]
    distance_nm: float
    axial_angle_deg: float

    def __post_init__(self) -> None:
        source_ids = tuple(self.source_ids)
        if (
            len(source_ids) != 2
            or source_ids != tuple(sorted(source_ids))
            or source_ids[0] == source_ids[1]
            or any(not isinstance(value, str) or not value for value in source_ids)
        ):
            raise ValueError("Internal bond source_ids must be two sorted unique IDs.")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(
            self,
            "distance_nm",
            _positive_float(self.distance_nm, "distance_nm"),
        )
        object.__setattr__(
            self,
            "axial_angle_deg",
            _finite_float(self.axial_angle_deg, "axial_angle_deg") % 180.0,
        )


@dataclass(frozen=True)
class LatticeDomainGeometry:
    """Spatial and first-shell geometry for one lattice component."""

    centroid_x_nm: float
    centroid_y_nm: float
    min_x_nm: float
    min_y_nm: float
    max_x_nm: float
    max_y_nm: float
    internal_first_shell_bond_count: int
    internal_first_shell_bonds: tuple[LatticeDomainInternalBond, ...]
    median_bond_length_nm: float | None
    bond_length_mad_nm: float | None
    bond_length_iqr_nm: float | None
    bond_length_robust_cv: float | None
    footprint_area_nm2: float | None
    footprint_fraction_of_valid_fov: float | None

    def __post_init__(self) -> None:
        for field_name in (
            "centroid_x_nm",
            "centroid_y_nm",
            "min_x_nm",
            "min_y_nm",
            "max_x_nm",
            "max_y_nm",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_float(getattr(self, field_name), field_name),
            )
        if self.min_x_nm > self.max_x_nm or self.min_y_nm > self.max_y_nm:
            raise ValueError("Lattice-domain bounds must be ordered.")
        if not (
            self.min_x_nm <= self.centroid_x_nm <= self.max_x_nm
            and self.min_y_nm <= self.centroid_y_nm <= self.max_y_nm
        ):
            raise ValueError("Lattice-domain centroid must lie within its bounds.")
        object.__setattr__(
            self,
            "internal_first_shell_bond_count",
            _non_negative_integer(
                self.internal_first_shell_bond_count,
                "internal_first_shell_bond_count",
            ),
        )
        bonds = tuple(self.internal_first_shell_bonds)
        if any(not isinstance(value, LatticeDomainInternalBond) for value in bonds):
            raise TypeError(
                "internal_first_shell_bonds must contain LatticeDomainInternalBond values."
            )
        if len(bonds) != self.internal_first_shell_bond_count:
            raise ValueError("Internal bond count must match internal_first_shell_bonds.")
        if bonds != tuple(sorted(bonds, key=lambda value: value.source_ids)):
            raise ValueError("Internal first-shell bonds must be sorted by source IDs.")
        if len({value.source_ids for value in bonds}) != len(bonds):
            raise ValueError("Internal first-shell bonds must be unique.")
        object.__setattr__(self, "internal_first_shell_bonds", bonds)
        bond_values = (
            self.median_bond_length_nm,
            self.bond_length_mad_nm,
            self.bond_length_iqr_nm,
            self.bond_length_robust_cv,
        )
        if any(value is None for value in bond_values) and not all(
            value is None for value in bond_values
        ):
            raise ValueError("Bond-length statistics must be all present or all absent.")
        if all(value is not None for value in bond_values):
            object.__setattr__(
                self,
                "median_bond_length_nm",
                _positive_float(self.median_bond_length_nm, "median_bond_length_nm"),
            )
            for field_name in (
                "bond_length_mad_nm",
                "bond_length_iqr_nm",
                "bond_length_robust_cv",
            ):
                object.__setattr__(
                    self,
                    field_name,
                    _non_negative_float(getattr(self, field_name), field_name),
                )
        if self.footprint_area_nm2 is not None:
            object.__setattr__(
                self,
                "footprint_area_nm2",
                _non_negative_float(self.footprint_area_nm2, "footprint_area_nm2"),
            )
        if self.footprint_fraction_of_valid_fov is not None:
            if self.footprint_area_nm2 is None:
                raise ValueError("A footprint fraction requires a footprint area.")
            object.__setattr__(
                self,
                "footprint_fraction_of_valid_fov",
                _unit_float(
                    self.footprint_fraction_of_valid_fov,
                    "footprint_fraction_of_valid_fov",
                ),
            )


@dataclass(frozen=True)
class LatticeDomainQc:
    """Independent quality flags; valid measurements may coexist with QC flags."""

    edge_truncated_neighborhood: bool
    graph_disconnected: bool
    insufficient_bonds_for_length_stats: bool
    bond_length_heterogeneity: bool
    footprint_unavailable: bool
    footprint_clipped_by_fov: bool
    symmetry_alias_unresolvable_from_centroids: bool

    def __post_init__(self) -> None:
        if any(
            not isinstance(getattr(self, field.name), bool)
            for field in fields(self)
        ):
            raise TypeError("Lattice-domain QC values must be booleans.")
        if self.insufficient_bonds_for_length_stats and self.bond_length_heterogeneity:
            raise ValueError("Unavailable bond statistics cannot be heterogeneous.")


@dataclass(frozen=True)
class LatticeDomain:
    """One spatially connected trifold, sixfold, mixed, or ambiguous component."""

    lattice_domain_id: str
    source_component_id: int
    component_type: LatticeDomainComponentType
    point_indices: tuple[int, ...]
    source_ids: tuple[str, ...]
    core_point_indices: tuple[int, ...]
    core_source_ids: tuple[str, ...]
    halo_point_indices: tuple[int, ...]
    halo_source_ids: tuple[str, ...]
    molecule_count: int
    core_size: int
    halo_size: int
    molecule_fraction_of_valid_representatives: float
    adjacent_boundary_point_count: int
    adjacent_boundary_source_ids: tuple[str, ...]
    adjacent_boundary_point_fraction: float
    theta3_lattice_prototype_deg: float | None
    theta6_prototype_deg: float | None
    theta3_lattice_spread_deg: float | None
    theta6_spread_deg: float | None
    dominant_symmetry: LatticeDomainDominantSymmetry
    orientation_reference_channel: LatticeDomainOrientationReferenceChannel
    m3_m6_orientation_relation_status: M3M6OrientationRelationStatus
    m3_m6_orientation_offset_deg: float | None
    confidence: float
    geometry: LatticeDomainGeometry
    qc: LatticeDomainQc

    def __post_init__(self) -> None:
        domain_id = _non_empty_string(self.lattice_domain_id, "lattice_domain_id")
        if not domain_id.startswith("lattice-"):
            raise ValueError("lattice_domain_id must use the 'lattice-' prefix.")
        object.__setattr__(
            self,
            "source_component_id",
            _non_negative_integer(self.source_component_id, "source_component_id"),
        )
        if self.component_type not in _COMPONENT_TYPES:
            raise ValueError(f"Unsupported component_type: {self.component_type!r}.")
        point_indices, source_ids = _member_pairs(
            self.point_indices,
            self.source_ids,
            field_prefix="member",
            require_non_empty=True,
        )
        core_indices, core_ids = _member_pairs(
            self.core_point_indices,
            self.core_source_ids,
            field_prefix="core",
            require_non_empty=True,
        )
        halo_indices, halo_ids = _member_pairs(
            self.halo_point_indices,
            self.halo_source_ids,
            field_prefix="halo",
            require_non_empty=False,
        )
        if set(core_indices).intersection(halo_indices):
            raise ValueError("Core and halo members must be disjoint.")
        if set(point_indices) != set(core_indices + halo_indices):
            raise ValueError("Domain members must equal the union of core and halo.")
        member_id_by_index = dict(zip(point_indices, source_ids))
        if any(
            member_id_by_index.get(index) != source_id
            for index, source_id in zip(
                core_indices + halo_indices,
                core_ids + halo_ids,
            )
        ):
            raise ValueError("Core and halo source IDs must preserve member identity.")
        molecule_count = _positive_integer(self.molecule_count, "molecule_count")
        core_size = _positive_integer(self.core_size, "core_size")
        halo_size = _non_negative_integer(self.halo_size, "halo_size")
        if (
            molecule_count != len(point_indices)
            or core_size != len(core_indices)
            or halo_size != len(halo_indices)
            or molecule_count != core_size + halo_size
        ):
            raise ValueError("Lattice-domain size fields must match memberships.")
        molecule_fraction = _unit_float(
            self.molecule_fraction_of_valid_representatives,
            "molecule_fraction_of_valid_representatives",
        )
        boundary_count = _non_negative_integer(
            self.adjacent_boundary_point_count,
            "adjacent_boundary_point_count",
        )
        boundary_ids = tuple(self.adjacent_boundary_source_ids)
        if (
            boundary_ids != tuple(sorted(set(boundary_ids)))
            or any(not isinstance(value, str) or not value for value in boundary_ids)
            or len(boundary_ids) != boundary_count
        ):
            raise ValueError(
                "adjacent_boundary_source_ids must match the sorted unique boundary count."
            )
        boundary_fraction = _unit_float(
            self.adjacent_boundary_point_fraction,
            "adjacent_boundary_point_fraction",
        )
        theta3 = _optional_periodic_angle(
            self.theta3_lattice_prototype_deg,
            "theta3_lattice_prototype_deg",
        )
        theta6 = _optional_periodic_angle(
            self.theta6_prototype_deg,
            "theta6_prototype_deg",
        )
        spread3 = _optional_spread(
            self.theta3_lattice_spread_deg,
            "theta3_lattice_spread_deg",
        )
        spread6 = _optional_spread(self.theta6_spread_deg, "theta6_spread_deg")
        if (theta3 is None) != (spread3 is None) or (theta6 is None) != (spread6 is None):
            raise ValueError("Each orientation prototype and spread must be present together.")
        if self.dominant_symmetry not in _SYMMETRIES:
            raise ValueError(f"Unsupported dominant_symmetry: {self.dominant_symmetry!r}.")
        if self.orientation_reference_channel not in _REFERENCE_CHANNELS:
            raise ValueError("Unsupported orientation_reference_channel.")
        if self.m3_m6_orientation_relation_status not in _RELATION_STATUSES:
            raise ValueError("Unsupported M3/M6 orientation relation status.")
        offset = _optional_spread(
            self.m3_m6_orientation_offset_deg,
            "m3_m6_orientation_offset_deg",
        )
        _validate_orientation_contract(
            self.dominant_symmetry,
            self.orientation_reference_channel,
            self.m3_m6_orientation_relation_status,
            theta3=theta3,
            theta6=theta6,
            relation_offset=offset,
        )
        confidence = _unit_float(self.confidence, "confidence")
        if not isinstance(self.geometry, LatticeDomainGeometry):
            raise TypeError("geometry must be LatticeDomainGeometry.")
        if not isinstance(self.qc, LatticeDomainQc):
            raise TypeError("qc must be LatticeDomainQc.")
        if (
            self.dominant_symmetry == "ambiguous"
            and not self.qc.symmetry_alias_unresolvable_from_centroids
        ):
            raise ValueError("Ambiguous symmetry requires centroid-alias QC.")
        member_ids = set(source_ids)
        if any(
            not set(bond.source_ids).issubset(member_ids)
            for bond in self.geometry.internal_first_shell_bonds
        ):
            raise ValueError("Internal bonds must reference domain members.")
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "point_indices", point_indices)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "core_point_indices", core_indices)
        object.__setattr__(self, "core_source_ids", core_ids)
        object.__setattr__(self, "halo_point_indices", halo_indices)
        object.__setattr__(self, "halo_source_ids", halo_ids)
        object.__setattr__(self, "molecule_count", molecule_count)
        object.__setattr__(self, "core_size", core_size)
        object.__setattr__(self, "halo_size", halo_size)
        object.__setattr__(
            self,
            "molecule_fraction_of_valid_representatives",
            molecule_fraction,
        )
        object.__setattr__(self, "adjacent_boundary_point_count", boundary_count)
        object.__setattr__(self, "adjacent_boundary_source_ids", boundary_ids)
        object.__setattr__(self, "adjacent_boundary_point_fraction", boundary_fraction)
        object.__setattr__(self, "theta3_lattice_prototype_deg", theta3)
        object.__setattr__(self, "theta6_prototype_deg", theta6)
        object.__setattr__(self, "theta3_lattice_spread_deg", spread3)
        object.__setattr__(self, "theta6_spread_deg", spread6)
        object.__setattr__(self, "m3_m6_orientation_offset_deg", offset)
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class LatticeDomainAnalysis:
    """Independent, auditable lattice-domain result for one frame."""

    source_ids: tuple[str, ...]
    point_count: int
    points_xy_nm: tuple[tuple[float, float], ...]
    valid_representative: tuple[bool, ...]
    point_role: tuple[LatticeDomainPointRole, ...]
    boundary_reason: tuple[LatticeDomainBoundaryReason | None, ...]
    point_lattice_domain_id: tuple[str | None, ...]
    first_shell_bonds: tuple[LatticeDomainInternalBond, ...]
    domains: tuple[LatticeDomain, ...]
    small_ordered_islands: tuple[LatticeDomain, ...]
    valid_representative_count: int
    classified_molecule_count: int
    classified_molecule_fraction: float
    boundary_point_count: int
    boundary_point_fraction: float
    settings: LatticeDomainAnalysisSettings
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str
    first_shell_graph_fingerprint: str
    local_order_analysis_fingerprint: str
    local_symmetry_evidence_settings_fingerprint: str
    local_symmetry_bond_evidence_fingerprint: str
    seed_growth_settings_fingerprint: str
    seed_growth_result_fingerprint: str
    settings_fingerprint: str
    schema_version: int = LATTICE_DOMAIN_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        point_count = _non_negative_integer(self.point_count, "point_count")
        source_ids = tuple(self.source_ids)
        if len(source_ids) != point_count or len(set(source_ids)) != point_count:
            raise ValueError("source_ids must contain one unique value per point.")
        if any(not isinstance(value, str) or not value for value in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        points = tuple(_finite_pair(value, "points_xy_nm") for value in self.points_xy_nm)
        valid_representatives = tuple(self.valid_representative)
        roles = tuple(self.point_role)
        reasons = tuple(self.boundary_reason)
        assignments = tuple(self.point_lattice_domain_id)
        if not (
            len(points)
            == len(valid_representatives)
            == len(roles)
            == len(reasons)
            == len(assignments)
            == point_count
        ):
            raise ValueError("Point lattice-domain fields must align with source_ids.")
        if any(not isinstance(value, bool) for value in valid_representatives):
            raise TypeError("valid_representative must contain booleans.")
        if any(role not in _POINT_ROLES for role in roles):
            raise ValueError("point_role contains an unsupported role.")
        if any(reason is not None and reason not in _BOUNDARY_REASONS for reason in reasons):
            raise ValueError("boundary_reason contains an unsupported reason.")
        if any(
            (role == "boundary") != (reason is not None)
            for role, reason in zip(roles, reasons)
        ):
            raise ValueError("Only boundary points require a boundary_reason.")
        first_shell_bonds = tuple(self.first_shell_bonds)
        if any(
            not isinstance(value, LatticeDomainInternalBond)
            for value in first_shell_bonds
        ):
            raise TypeError("first_shell_bonds must contain lattice-domain bonds.")
        if first_shell_bonds != tuple(
            sorted(first_shell_bonds, key=lambda value: value.source_ids)
        ) or len({value.source_ids for value in first_shell_bonds}) != len(
            first_shell_bonds
        ):
            raise ValueError("first_shell_bonds must be sorted and unique.")
        point_by_source_id = dict(zip(source_ids, points))
        if any(
            not set(bond.source_ids).issubset(point_by_source_id)
            for bond in first_shell_bonds
        ):
            raise ValueError("First-shell bonds must reference frame source IDs.")
        for bond in first_shell_bonds:
            _validate_bond_geometry(bond, point_by_source_id=point_by_source_id)
        domains = tuple(self.domains)
        islands = tuple(self.small_ordered_islands)
        components = domains + islands
        if any(not isinstance(value, LatticeDomain) for value in components):
            raise TypeError("Domain collections must contain LatticeDomain values.")
        if any(value.component_type != "full_domain" for value in domains):
            raise ValueError("domains may contain only full_domain components.")
        if any(value.component_type != "small_ordered_island" for value in islands):
            raise ValueError("small_ordered_islands contains an invalid component.")
        component_ids = tuple(value.lattice_domain_id for value in components)
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("lattice_domain_id values must be unique within a frame.")
        if domains != tuple(sorted(domains, key=lambda value: value.lattice_domain_id)):
            raise ValueError("domains must be sorted by lattice_domain_id.")
        if islands != tuple(sorted(islands, key=lambda value: value.lattice_domain_id)):
            raise ValueError("small_ordered_islands must be sorted by lattice_domain_id.")
        expected_assignments: list[str | None] = [None] * point_count
        for component in components:
            for point_index, source_id in zip(component.point_indices, component.source_ids):
                if point_index >= point_count or source_ids[point_index] != source_id:
                    raise ValueError("Domain members must preserve frame point identity.")
                if expected_assignments[point_index] is not None:
                    raise ValueError("Lattice-domain memberships must be disjoint.")
                if not valid_representatives[point_index]:
                    raise ValueError("Domain members must be valid representatives.")
                expected_assignments[point_index] = component.lattice_domain_id
            if any(roles[index] != "core" for index in component.core_point_indices):
                raise ValueError("Domain core members must preserve core point roles.")
            if any(roles[index] != "halo" for index in component.halo_point_indices):
                raise ValueError("Domain halo members must preserve halo point roles.")
            component_points = tuple(points[index] for index in component.point_indices)
            expected_centroid_x = fsum(
                point[0]
                for _source_id, point in sorted(
                    zip(component.source_ids, component_points)
                )
            ) / component.molecule_count
            expected_centroid_y = fsum(
                point[1]
                for _source_id, point in sorted(
                    zip(component.source_ids, component_points)
                )
            ) / component.molecule_count
            if not (
                isclose(component.geometry.centroid_x_nm, expected_centroid_x, abs_tol=1e-12)
                and isclose(component.geometry.centroid_y_nm, expected_centroid_y, abs_tol=1e-12)
                and component.geometry.min_x_nm == min(point[0] for point in component_points)
                and component.geometry.min_y_nm == min(point[1] for point in component_points)
                and component.geometry.max_x_nm == max(point[0] for point in component_points)
                and component.geometry.max_y_nm == max(point[1] for point in component_points)
            ):
                raise ValueError("Domain geometry must match stored sample coordinates.")
        if assignments != tuple(expected_assignments):
            raise ValueError("point_lattice_domain_id must match domain memberships.")
        valid_count = _non_negative_integer(
            self.valid_representative_count,
            "valid_representative_count",
        )
        if valid_count != sum(valid_representatives):
            raise ValueError("valid_representative_count must match point flags.")
        classified_count = _non_negative_integer(
            self.classified_molecule_count,
            "classified_molecule_count",
        )
        if classified_count != sum(value.molecule_count for value in components):
            raise ValueError("classified_molecule_count must match final components.")
        boundary_count = _non_negative_integer(
            self.boundary_point_count,
            "boundary_point_count",
        )
        classified_fraction = _unit_float(
            self.classified_molecule_fraction,
            "classified_molecule_fraction",
        )
        boundary_fraction = _unit_float(
            self.boundary_point_fraction,
            "boundary_point_fraction",
        )
        if classified_count > valid_count or boundary_count > valid_count:
            raise ValueError("Classified and boundary counts cannot exceed valid points.")
        if classified_count + boundary_count > valid_count:
            raise ValueError("Classified and boundary point sets must be disjoint.")
        if boundary_count != sum(
            role == "boundary" and valid
            for role, valid in zip(roles, valid_representatives)
        ):
            raise ValueError("boundary_point_count must match point roles.")
        if valid_count == 0 and components:
            raise ValueError("A frame without valid representatives cannot contain domains.")
        expected_classified_fraction = classified_count / valid_count if valid_count else 0.0
        expected_boundary_fraction = boundary_count / valid_count if valid_count else 0.0
        if not isclose(classified_fraction, expected_classified_fraction, abs_tol=1e-12):
            raise ValueError("classified_molecule_fraction has an invalid denominator.")
        if not isclose(boundary_fraction, expected_boundary_fraction, abs_tol=1e-12):
            raise ValueError("boundary_point_fraction has an invalid denominator.")
        if not isclose(
            fsum(value.molecule_fraction_of_valid_representatives for value in components),
            classified_fraction,
            abs_tol=1e-12,
        ):
            raise ValueError("Component molecule fractions must match the frame fraction.")
        if not isinstance(self.settings, LatticeDomainAnalysisSettings):
            raise TypeError("settings must be LatticeDomainAnalysisSettings.")
        if self.settings_fingerprint != lattice_domain_analysis_settings_fingerprint(
            self.settings
        ):
            raise ValueError("settings_fingerprint must match settings.")
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.orientation_reference not in _ORIENTATION_REFERENCES:
            raise ValueError("Unsupported orientation_reference.")
        if self.schema_version != LATTICE_DOMAIN_ANALYSIS_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {self.schema_version!r}.")
        for field_name in (
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
            "point_coordinate_fingerprint",
            "first_shell_graph_fingerprint",
            "local_order_analysis_fingerprint",
            "local_symmetry_evidence_settings_fingerprint",
            "local_symmetry_bond_evidence_fingerprint",
            "seed_growth_settings_fingerprint",
            "seed_growth_result_fingerprint",
            "settings_fingerprint",
        ):
            _non_empty_string(getattr(self, field_name), field_name)
        point_array = np.asarray(points, dtype=np.float64).reshape((-1, 2))
        if (
            point_coordinate_fingerprint(point_array, source_ids)
            != self.point_coordinate_fingerprint
        ):
            raise ValueError(
                "Stored sample coordinates must match point_coordinate_fingerprint."
            )
        role_by_source_id = dict(zip(source_ids, roles))
        for component in components:
            _validate_component_metrics(
                component,
                valid_representative_count=valid_count,
                point_by_source_id=point_by_source_id,
                role_by_source_id=role_by_source_id,
                first_shell_bonds=first_shell_bonds,
                settings=self.settings,
            )
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "points_xy_nm", points)
        object.__setattr__(self, "valid_representative", valid_representatives)
        object.__setattr__(self, "point_role", roles)
        object.__setattr__(self, "boundary_reason", reasons)
        object.__setattr__(self, "point_lattice_domain_id", assignments)
        object.__setattr__(self, "first_shell_bonds", first_shell_bonds)
        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "small_ordered_islands", islands)
        object.__setattr__(self, "valid_representative_count", valid_count)
        object.__setattr__(self, "classified_molecule_count", classified_count)
        object.__setattr__(self, "classified_molecule_fraction", classified_fraction)
        object.__setattr__(self, "boundary_point_count", boundary_count)
        object.__setattr__(self, "boundary_point_fraction", boundary_fraction)

    @property
    def components(self) -> tuple[LatticeDomain, ...]:
        return self.domains + self.small_ordered_islands

    def component_for_id(self, lattice_domain_id: str) -> LatticeDomain:
        normalized = _non_empty_string(lattice_domain_id, "lattice_domain_id")
        for component in self.components:
            if component.lattice_domain_id == normalized:
                return component
        raise KeyError(f"Unknown lattice_domain_id: {normalized!r}.")


def lattice_domain_analysis_fingerprint(analysis: LatticeDomainAnalysis) -> str:
    """Fingerprint the complete final partition, metrics, QC, and provenance."""

    if not isinstance(analysis, LatticeDomainAnalysis):
        raise TypeError("analysis must be LatticeDomainAnalysis.")
    return _fingerprint(
        {
            "algorithm": LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
            "analysis": asdict(analysis),
        }
    )


def _validate_component_metrics(
    component: LatticeDomain,
    *,
    valid_representative_count: int,
    point_by_source_id: dict[str, tuple[float, float]],
    role_by_source_id: dict[str, LatticeDomainPointRole],
    first_shell_bonds: tuple[LatticeDomainInternalBond, ...],
    settings: LatticeDomainAnalysisSettings,
) -> None:
    expected_molecule_fraction = (
        component.molecule_count / valid_representative_count
        if valid_representative_count
        else 0.0
    )
    if not isclose(
        component.molecule_fraction_of_valid_representatives,
        expected_molecule_fraction,
        abs_tol=1e-12,
    ):
        raise ValueError("Domain molecule fraction has an invalid denominator.")
    expected_boundary_fraction = (
        component.adjacent_boundary_point_count
        / (component.molecule_count + component.adjacent_boundary_point_count)
        if component.adjacent_boundary_point_count
        else 0.0
    )
    if not isclose(
        component.adjacent_boundary_point_fraction,
        expected_boundary_fraction,
        abs_tol=1e-12,
    ):
        raise ValueError("Domain boundary fraction has an invalid local denominator.")
    member_ids = set(component.source_ids)
    expected_boundary_ids = tuple(
        sorted(
            {
                endpoint
                for bond in first_shell_bonds
                if bool(set(bond.source_ids).intersection(member_ids))
                and not set(bond.source_ids).issubset(member_ids)
                for endpoint in bond.source_ids
                if endpoint not in member_ids
                and role_by_source_id.get(endpoint) == "boundary"
            }
        )
    )
    if component.adjacent_boundary_source_ids != expected_boundary_ids:
        raise ValueError("Adjacent boundary IDs must match first-shell graph adjacency.")
    expected_id = lattice_domain_id_from_members(
        tuple(
            (source_id, *point_by_source_id[source_id])
            for source_id in component.source_ids
        ),
        coordinate_frame="sample_nm",
    )
    if component.lattice_domain_id != expected_id:
        raise ValueError("lattice_domain_id must match stored member geometry.")
    expected_internal_bonds = tuple(
        bond for bond in first_shell_bonds if set(bond.source_ids).issubset(member_ids)
    )
    if component.geometry.internal_first_shell_bonds != expected_internal_bonds:
        raise ValueError("Domain internal bonds must match the first-shell graph subset.")
    distances: list[float] = []
    adjacency = {source_id: set() for source_id in component.source_ids}
    for bond in component.geometry.internal_first_shell_bonds:
        left, right = bond.source_ids
        distances.append(bond.distance_nm)
        adjacency[left].add(right)
        adjacency[right].add(left)
    expected_statistics = _bond_statistics(
        tuple(sorted(distances)),
        minimum_count=settings.min_bonds_for_length_stats,
    )
    actual_statistics = (
        component.geometry.median_bond_length_nm,
        component.geometry.bond_length_mad_nm,
        component.geometry.bond_length_iqr_nm,
        component.geometry.bond_length_robust_cv,
    )
    if not _optional_float_tuples_close(actual_statistics, expected_statistics):
        raise ValueError("Domain bond statistics must match internal first-shell bonds.")
    expected_disconnected = not _source_graph_is_connected(adjacency)
    if component.qc.graph_disconnected != expected_disconnected:
        raise ValueError("graph_disconnected QC must match internal first-shell bonds.")
    expected_insufficient = expected_statistics[0] is None
    if component.qc.insufficient_bonds_for_length_stats != expected_insufficient:
        raise ValueError("Bond-statistics availability QC is inconsistent.")
    robust_cv = expected_statistics[3]
    expected_heterogeneity = (
        robust_cv is not None
        and robust_cv >= settings.bond_length_robust_cv_qc_threshold
    )
    if component.qc.bond_length_heterogeneity != expected_heterogeneity:
        raise ValueError("Bond-length heterogeneity QC is inconsistent.")
    if component.qc.footprint_unavailable != (
        component.geometry.footprint_area_nm2 is None
    ):
        raise ValueError("Footprint availability QC is inconsistent.")


def _validate_bond_geometry(
    bond: LatticeDomainInternalBond,
    *,
    point_by_source_id: dict[str, tuple[float, float]],
) -> None:
    left_point = point_by_source_id[bond.source_ids[0]]
    right_point = point_by_source_id[bond.source_ids[1]]
    delta_x = right_point[0] - left_point[0]
    delta_y = right_point[1] - left_point[1]
    expected_distance = hypot(delta_x, delta_y)
    expected_angle = degrees(atan2(delta_y, delta_x)) % 180.0
    if not isclose(bond.distance_nm, expected_distance, abs_tol=1e-10):
        raise ValueError("First-shell bond distance must match stored coordinates.")
    if _axial_angle_distance_deg(bond.axial_angle_deg, expected_angle) > 1e-10:
        raise ValueError("First-shell bond angle must match stored coordinates.")


def lattice_domain_id_from_members(
    member_geometry: tuple[tuple[str, float, float], ...],
    *,
    coordinate_frame: str,
) -> str:
    """Create a permutation-invariant ID from canonical member geometry."""

    records = tuple(
        sorted(
            (
                _non_empty_string(source_id, "source_id"),
                _finite_float(x_nm, "x_nm"),
                _finite_float(y_nm, "y_nm"),
            )
            for source_id, x_nm, y_nm in member_geometry
        )
    )
    if not records or len({record[0] for record in records}) != len(records):
        raise ValueError("Lattice-domain ID requires unique, non-empty members.")
    digest = _fingerprint(
        {
            "schema": "moltrack-lattice-domain-id-v1",
            "coordinate_frame": _non_empty_string(coordinate_frame, "coordinate_frame"),
            "members": records,
        }
    )
    return f"lattice-{digest}"


def _validate_orientation_contract(
    symmetry: str,
    reference_channel: str,
    relation_status: str,
    *,
    theta3: float | None,
    theta6: float | None,
    relation_offset: float | None,
) -> None:
    if symmetry == "trifold":
        expected = ("m3_lattice", theta3 is not None, theta6 is None, "not_applicable")
    elif symmetry == "sixfold":
        expected = ("m6", theta3 is None, theta6 is not None, "not_applicable")
    elif symmetry == "mixed":
        expected = ("joint", theta3 is not None, theta6 is not None, "available")
    else:
        if reference_channel != "unavailable":
            raise ValueError("Ambiguous symmetry requires an unavailable reference channel.")
        if relation_status not in {
            "unavailable",
            "symmetry_alias_unresolvable_from_centroids",
        }:
            raise ValueError("Ambiguous symmetry requires an unresolved relation status.")
        if relation_offset is not None:
            raise ValueError("Ambiguous symmetry cannot report a resolved M3/M6 offset.")
        return
    expected_channel, first_condition, second_condition, expected_relation = expected
    if reference_channel != expected_channel or not first_condition or not second_condition:
        raise ValueError("Orientation channels do not match dominant_symmetry.")
    if relation_status != expected_relation:
        raise ValueError("M3/M6 relation status does not match dominant_symmetry.")
    if (symmetry == "mixed") != (relation_offset is not None):
        raise ValueError("Only a mixed domain has an M3/M6 orientation offset.")


def _member_pairs(
    point_indices: tuple[int, ...],
    source_ids: tuple[str, ...],
    *,
    field_prefix: str,
    require_non_empty: bool,
) -> tuple[tuple[int, ...], tuple[str, ...]]:
    indices = tuple(
        _non_negative_integer(value, f"{field_prefix}_point_indices")
        for value in point_indices
    )
    ids = tuple(_non_empty_string(value, f"{field_prefix}_source_ids") for value in source_ids)
    if len(indices) != len(ids) or len(set(indices)) != len(indices) or len(set(ids)) != len(ids):
        raise ValueError(f"{field_prefix} members must be aligned and unique.")
    if require_non_empty and not indices:
        raise ValueError(f"{field_prefix} members must not be empty.")
    if ids != tuple(sorted(ids)):
        raise ValueError(f"{field_prefix} members must be ordered by source ID.")
    return indices, ids


def _optional_periodic_angle(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _finite_float(value, field_name) % 60.0


def _finite_pair(value: object, field_name: str) -> tuple[float, float]:
    try:
        pair = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} values must contain two numbers.") from exc
    if len(pair) != 2:
        raise ValueError(f"{field_name} values must contain two numbers.")
    return (
        _finite_float(pair[0], field_name),
        _finite_float(pair[1], field_name),
    )


def _optional_spread(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 30.0:
        raise ValueError(f"{field_name} must be between 0 and 30 degrees.")
    return normalized


def _bond_statistics(
    distances_nm: tuple[float, ...],
    *,
    minimum_count: int,
) -> tuple[float | None, float | None, float | None, float | None]:
    if len(distances_nm) < minimum_count:
        return None, None, None, None
    distances = np.asarray(distances_nm, dtype=np.float64)
    median = float(np.median(distances))
    mad = float(np.median(np.abs(distances - median)))
    q25, q75 = np.percentile(distances, (25.0, 75.0))
    return median, mad, float(q75 - q25), 1.4826 * mad / median


def _optional_float_tuples_close(
    first: tuple[float | None, ...],
    second: tuple[float | None, ...],
) -> bool:
    return all(
        (left is None and right is None)
        or (
            left is not None
            and right is not None
            and isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        )
        for left, right in zip(first, second)
    )


def _source_graph_is_connected(adjacency: dict[str, set[str]]) -> bool:
    if len(adjacency) <= 1:
        return True
    reached: set[str] = set()
    stack = [min(adjacency)]
    while stack:
        current = stack.pop()
        if current in reached:
            continue
        reached.add(current)
        stack.extend(adjacency[current] - reached)
    return len(reached) == len(adjacency)


def _axial_angle_distance_deg(first: float, second: float) -> float:
    difference = abs((first % 180.0) - (second % 180.0))
    return min(difference, 180.0 - difference)


def _fingerprint(payload: object) -> str:
    return sha256(
        json.dumps(
            payload,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value


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


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized
