"""Versioned contracts for candidate lattice-row assignments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from math import isclose, isfinite
from typing import Literal, Mapping, get_args


LATTICE_ROW_ASSIGNMENT_SCHEMA_VERSION = 1
LATTICE_ROW_ASSIGNMENT_ALGORITHM_VERSION = (
    "moltrack-lattice-row-assignment-v1"
)

LatticeRowAssignmentStatus = Literal[
    "available",
    "ambiguous",
    "unavailable",
]
LatticeRowAssignmentReason = Literal[
    "insufficient_domain_molecules",
    "insufficient_internal_first_shell_bonds",
    "axis_family_unavailable",
    "axis_family_incoherent",
    "row_spacing_unavailable",
    "candidate_score_below_minimum",
    "symmetry_equivalent_axes_not_resolved",
    "unique_best_axis",
]

_STATUSES = set(get_args(LatticeRowAssignmentStatus))
_REASONS = set(get_args(LatticeRowAssignmentReason))


@dataclass(frozen=True)
class LatticeRowAssignmentSettings:
    """Geometry-only thresholds for testing symmetry-equivalent row axes."""

    minimum_domain_molecule_count: int = 3
    minimum_internal_bond_count: int = 2
    axis_cluster_tolerance_deg: float = 15.0
    row_residual_tolerance_fraction: float = 0.25
    minimum_candidate_score: float = 0.5
    minimum_selection_margin: float = 0.05
    minimum_axis_family_coherence: float = 0.25

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_domain_molecule_count",
            _positive_integer(
                self.minimum_domain_molecule_count,
                "minimum_domain_molecule_count",
            ),
        )
        object.__setattr__(
            self,
            "minimum_internal_bond_count",
            _positive_integer(
                self.minimum_internal_bond_count,
                "minimum_internal_bond_count",
            ),
        )
        tolerance = _positive_float(
            self.axis_cluster_tolerance_deg,
            "axis_cluster_tolerance_deg",
        )
        if tolerance >= 30.0:
            raise ValueError(
                "axis_cluster_tolerance_deg must be smaller than 30."
            )
        object.__setattr__(self, "axis_cluster_tolerance_deg", tolerance)
        residual_tolerance = _positive_float(
            self.row_residual_tolerance_fraction,
            "row_residual_tolerance_fraction",
        )
        if residual_tolerance >= 0.5:
            raise ValueError(
                "row_residual_tolerance_fraction must be smaller than 0.5."
            )
        object.__setattr__(
            self,
            "row_residual_tolerance_fraction",
            residual_tolerance,
        )
        for field_name in (
            "minimum_candidate_score",
            "minimum_selection_margin",
            "minimum_axis_family_coherence",
        ):
            object.__setattr__(
                self,
                field_name,
                _unit_float(getattr(self, field_name), field_name),
            )

    def to_dict(self) -> dict[str, int | float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "LatticeRowAssignmentSettings":
        if not isinstance(payload, Mapping):
            raise TypeError(
                "Lattice-row assignment settings must be a mapping."
            )
        names = {field.name for field in fields(cls)}
        if set(payload) != names:
            raise ValueError(
                "Lattice-row assignment settings fields must match the schema."
            )
        return cls(**dict(payload))


def lattice_row_assignment_settings_fingerprint(
    settings: LatticeRowAssignmentSettings,
) -> str:
    if not isinstance(settings, LatticeRowAssignmentSettings):
        raise TypeError(
            "settings must be LatticeRowAssignmentSettings."
        )
    return _fingerprint(
        {
            "algorithm": LATTICE_ROW_ASSIGNMENT_ALGORITHM_VERSION,
            "settings": settings.to_dict(),
        }
    )


@dataclass(frozen=True)
class LatticeRowMemberAssignment:
    """One molecule projected onto one candidate row basis.

    The sign of ``row_index`` is an axial gauge; ``n`` and ``-n`` describe
    the same unoriented row family. Its magnitude and parity are gauge-stable.
    """

    point_index: int
    source_id: str
    row_index: int
    row_parity: int
    along_coordinate_nm: float
    normal_coordinate_nm: float
    row_residual_nm: float

    def __post_init__(self) -> None:
        point_index = _non_negative_integer(
            self.point_index,
            "point_index",
        )
        source_id = _non_empty_string(self.source_id, "source_id")
        row_index = _integer(self.row_index, "row_index")
        row_parity = _non_negative_integer(self.row_parity, "row_parity")
        if row_parity not in (0, 1) or row_parity != row_index % 2:
            raise ValueError(
                "row_parity must equal row_index modulo two."
            )
        object.__setattr__(self, "point_index", point_index)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "row_index", row_index)
        object.__setattr__(self, "row_parity", row_parity)
        for field_name in (
            "along_coordinate_nm",
            "normal_coordinate_nm",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_float(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "row_residual_nm",
            _non_negative_float(
                self.row_residual_nm,
                "row_residual_nm",
            ),
        )


@dataclass(frozen=True)
class LatticeRow:
    """One occupied row for a candidate lattice axis."""

    row_index: int
    parity: int
    point_indices: tuple[int, ...]
    source_ids: tuple[str, ...]
    normal_coordinate_nm: float
    maximum_residual_nm: float

    def __post_init__(self) -> None:
        row_index = _integer(self.row_index, "row_index")
        parity = _non_negative_integer(self.parity, "parity")
        if parity not in (0, 1) or parity != row_index % 2:
            raise ValueError("parity must equal row_index modulo two.")
        point_indices = tuple(self.point_indices)
        source_ids = tuple(self.source_ids)
        if (
            not point_indices
            or len(point_indices) != len(source_ids)
            or len(set(point_indices)) != len(point_indices)
            or len(set(source_ids)) != len(source_ids)
        ):
            raise ValueError(
                "A lattice row requires aligned unique members."
            )
        if any(
            not isinstance(source_id, str) or not source_id
            for source_id in source_ids
        ):
            raise TypeError("source_ids must contain non-empty strings.")
        if tuple(zip(source_ids, point_indices)) != tuple(
            sorted(zip(source_ids, point_indices))
        ):
            raise ValueError(
                "Lattice-row members must be sorted by source_id."
            )
        if any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            for index in point_indices
        ):
            raise ValueError(
                "point_indices must contain non-negative integers."
            )
        object.__setattr__(self, "row_index", row_index)
        object.__setattr__(self, "parity", parity)
        object.__setattr__(self, "point_indices", point_indices)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(
            self,
            "normal_coordinate_nm",
            _finite_float(
                self.normal_coordinate_nm,
                "normal_coordinate_nm",
            ),
        )
        object.__setattr__(
            self,
            "maximum_residual_nm",
            _non_negative_float(
                self.maximum_residual_nm,
                "maximum_residual_nm",
            ),
        )


@dataclass(frozen=True)
class LatticeRowAxisCandidate:
    """One symmetry-equivalent row axis and its complete assignment."""

    candidate_index: int
    axis_angle_deg: float
    row_spacing_nm: float
    row_origin_normal_nm: float
    axis_bond_support_count: int
    axis_bond_support_fraction: float
    assigned_molecule_count: int
    inlier_molecule_count: int
    inlier_fraction: float
    median_residual_nm: float
    median_residual_fraction: float
    score: float
    source_ids: tuple[str, ...]
    member_assignments: tuple[LatticeRowMemberAssignment, ...]
    rows: tuple[LatticeRow, ...]

    def __post_init__(self) -> None:
        candidate_index = _non_negative_integer(
            self.candidate_index,
            "candidate_index",
        )
        axis_angle = _finite_float(
            self.axis_angle_deg,
            "axis_angle_deg",
        ) % 180.0
        row_spacing = _positive_float(
            self.row_spacing_nm,
            "row_spacing_nm",
        )
        support_count = _non_negative_integer(
            self.axis_bond_support_count,
            "axis_bond_support_count",
        )
        assigned_count = _positive_integer(
            self.assigned_molecule_count,
            "assigned_molecule_count",
        )
        inlier_count = _non_negative_integer(
            self.inlier_molecule_count,
            "inlier_molecule_count",
        )
        if inlier_count > assigned_count:
            raise ValueError(
                "inlier_molecule_count cannot exceed assigned_molecule_count."
            )
        source_ids = tuple(self.source_ids)
        assignments = tuple(self.member_assignments)
        rows = tuple(self.rows)
        if (
            len(source_ids) != len(assignments)
            or len(source_ids) != assigned_count
        ):
            raise ValueError(
                "Candidate source IDs and assignments must match its count."
            )
        if source_ids != tuple(sorted(set(source_ids))):
            raise ValueError(
                "Candidate source_ids must be sorted and unique."
            )
        if any(
            not isinstance(value, LatticeRowMemberAssignment)
            for value in assignments
        ):
            raise TypeError(
                "member_assignments must contain row-member assignments."
            )
        if tuple(value.source_id for value in assignments) != source_ids:
            raise ValueError(
                "member_assignments must align with source_ids."
            )
        if any(not isinstance(value, LatticeRow) for value in rows):
            raise TypeError("rows must contain LatticeRow values.")
        if rows != tuple(sorted(rows, key=lambda value: value.row_index)):
            raise ValueError("rows must be sorted by row_index.")
        if len({value.row_index for value in rows}) != len(rows):
            raise ValueError("row_index values must be unique per candidate.")
        flattened_pairs = tuple(
            (source_id, point_index)
            for row in rows
            for source_id, point_index in zip(
                row.source_ids,
                row.point_indices,
            )
        )
        if (
            len(flattened_pairs) != assigned_count
            or len({pair[0] for pair in flattened_pairs})
            != assigned_count
        ):
            raise ValueError(
                "Candidate rows must partition all source_ids exactly once."
            )
        if len({pair[1] for pair in flattened_pairs}) != assigned_count:
            raise ValueError(
                "Candidate rows must use unique point indices."
            )
        expected_pairs = tuple(
            sorted(
                (value.source_id, value.point_index)
                for value in assignments
            )
        )
        if tuple(sorted(flattened_pairs)) != expected_pairs:
            raise ValueError(
                "Candidate row source/index pairs must match assignments."
            )
        row_by_source_id = {
            source_id: row
            for row in rows
            for source_id in row.source_ids
        }
        for assignment in assignments:
            row = row_by_source_id[assignment.source_id]
            if (
                row.row_index != assignment.row_index
                or row.parity != assignment.row_parity
            ):
                raise ValueError(
                    "Candidate row summaries must match member assignments."
                )
        expected_inlier_fraction = inlier_count / assigned_count
        if not isclose(
            float(self.inlier_fraction),
            expected_inlier_fraction,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "inlier_fraction must match molecule counts."
            )
        median_residual = _non_negative_float(
            self.median_residual_nm,
            "median_residual_nm",
        )
        expected_residual_fraction = median_residual / row_spacing
        if not isclose(
            float(self.median_residual_fraction),
            expected_residual_fraction,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "median_residual_fraction must match row spacing."
            )
        object.__setattr__(self, "candidate_index", candidate_index)
        object.__setattr__(self, "axis_angle_deg", axis_angle)
        object.__setattr__(self, "row_spacing_nm", row_spacing)
        object.__setattr__(
            self,
            "row_origin_normal_nm",
            _finite_float(
                self.row_origin_normal_nm,
                "row_origin_normal_nm",
            ),
        )
        object.__setattr__(
            self,
            "axis_bond_support_count",
            support_count,
        )
        object.__setattr__(
            self,
            "axis_bond_support_fraction",
            _unit_float(
                self.axis_bond_support_fraction,
                "axis_bond_support_fraction",
            ),
        )
        object.__setattr__(
            self,
            "assigned_molecule_count",
            assigned_count,
        )
        object.__setattr__(
            self,
            "inlier_molecule_count",
            inlier_count,
        )
        object.__setattr__(
            self,
            "inlier_fraction",
            expected_inlier_fraction,
        )
        object.__setattr__(self, "median_residual_nm", median_residual)
        object.__setattr__(
            self,
            "median_residual_fraction",
            expected_residual_fraction,
        )
        object.__setattr__(self, "score", _unit_float(self.score, "score"))
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "member_assignments", assignments)
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True)
class LatticeDomainRowAssignment:
    """All row-axis hypotheses for one spatial lattice domain."""

    lattice_domain_id: str
    molecule_count: int
    source_ids: tuple[str, ...]
    status: LatticeRowAssignmentStatus
    candidates: tuple[LatticeRowAxisCandidate, ...]
    selected_candidate_index: int | None
    selection_margin: float | None
    axis_family_coherence: float | None
    reason: LatticeRowAssignmentReason

    def __post_init__(self) -> None:
        domain_id = _non_empty_string(
            self.lattice_domain_id,
            "lattice_domain_id",
        )
        molecule_count = _positive_integer(
            self.molecule_count,
            "molecule_count",
        )
        source_ids = tuple(self.source_ids)
        if (
            len(source_ids) != molecule_count
            or source_ids != tuple(sorted(set(source_ids)))
        ):
            raise ValueError(
                "source_ids must contain every domain molecule exactly once."
            )
        if self.status not in _STATUSES:
            raise ValueError(
                f"Unsupported lattice-row status: {self.status!r}."
            )
        candidates = tuple(self.candidates)
        if any(
            not isinstance(value, LatticeRowAxisCandidate)
            for value in candidates
        ):
            raise TypeError(
                "candidates must contain LatticeRowAxisCandidate values."
            )
        if tuple(value.candidate_index for value in candidates) != tuple(
            range(len(candidates))
        ):
            raise ValueError(
                "candidate_index values must be contiguous and ordered."
            )
        if any(
            value.assigned_molecule_count != molecule_count
            or value.source_ids != source_ids
            for value in candidates
        ):
            raise ValueError(
                "Every candidate must assign every domain molecule."
            )
        selected = self.selected_candidate_index
        if selected is not None:
            selected = _non_negative_integer(
                selected,
                "selected_candidate_index",
            )
            if selected >= len(candidates):
                raise IndexError(
                    "selected_candidate_index is out of range."
                )
        margin = (
            None
            if self.selection_margin is None
            else _unit_float(self.selection_margin, "selection_margin")
        )
        coherence = (
            None
            if self.axis_family_coherence is None
            else _unit_float(
                self.axis_family_coherence,
                "axis_family_coherence",
            )
        )
        if self.status == "available":
            if selected is None or margin is None or not candidates:
                raise ValueError(
                    "An available row assignment requires a selected candidate."
                )
        elif self.status == "ambiguous":
            if selected is not None or margin is None or not candidates:
                raise ValueError(
                    "An ambiguous row assignment requires unselected candidates."
                )
        elif selected is not None:
            raise ValueError(
                "Only an available row assignment may select a candidate."
            )
        if candidates and (margin is None or coherence is None):
            raise ValueError(
                "Candidate results require margin and coherence diagnostics."
            )
        if not candidates and (margin is not None or coherence is not None):
            raise ValueError(
                "Unavailable empty results cannot expose candidate diagnostics."
            )
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "molecule_count", molecule_count)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "selected_candidate_index", selected)
        object.__setattr__(self, "selection_margin", margin)
        object.__setattr__(self, "axis_family_coherence", coherence)
        if self.reason not in _REASONS:
            raise ValueError(
                f"Unsupported lattice-row assignment reason: {self.reason!r}."
            )
        expected_reason_by_status = {
            "available": {"unique_best_axis"},
            "ambiguous": {"symmetry_equivalent_axes_not_resolved"},
            "unavailable": _REASONS
            - {
                "unique_best_axis",
                "symmetry_equivalent_axes_not_resolved",
            },
        }
        if self.reason not in expected_reason_by_status[self.status]:
            raise ValueError(
                "Lattice-row assignment reason must match its status."
            )
        if self.status == "unavailable":
            reason_requires_candidates = (
                self.reason == "candidate_score_below_minimum"
            )
            if reason_requires_candidates != bool(candidates):
                raise ValueError(
                    "Unavailable reason must match candidate availability."
                )


@dataclass(frozen=True)
class LatticeRowAssignmentAnalysis:
    """Frame-level row hypotheses derived from final lattice domains."""

    source_ids: tuple[str, ...]
    point_count: int
    domain_assignments: tuple[LatticeDomainRowAssignment, ...]
    settings: LatticeRowAssignmentSettings
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: str
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str
    lattice_domain_analysis_fingerprint: str
    settings_fingerprint: str
    schema_version: int = LATTICE_ROW_ASSIGNMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        point_count = _non_negative_integer(self.point_count, "point_count")
        source_ids = tuple(self.source_ids)
        if (
            len(source_ids) != point_count
            or source_ids != tuple(dict.fromkeys(source_ids))
        ):
            raise ValueError(
                "source_ids must contain one unique value per point."
            )
        if any(not isinstance(value, str) or not value for value in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        assignments = tuple(self.domain_assignments)
        if any(
            not isinstance(value, LatticeDomainRowAssignment)
            for value in assignments
        ):
            raise TypeError(
                "domain_assignments must contain domain row assignments."
            )
        if assignments != tuple(
            sorted(
                assignments,
                key=lambda value: value.lattice_domain_id,
            )
        ):
            raise ValueError(
                "domain_assignments must be sorted by lattice_domain_id."
            )
        if len(
            {value.lattice_domain_id for value in assignments}
        ) != len(assignments):
            raise ValueError(
                "lattice_domain_id values must be unique."
            )
        frame_source_ids = set(source_ids)
        assigned_source_ids: set[str] = set()
        for assignment in assignments:
            domain_source_ids = set(assignment.source_ids)
            if not domain_source_ids.issubset(frame_source_ids):
                raise ValueError(
                    "Domain row assignments must reference frame source_ids."
                )
            if assigned_source_ids.intersection(domain_source_ids):
                raise ValueError(
                    "Domain row assignment memberships must be disjoint."
                )
            assigned_source_ids.update(domain_source_ids)
        if not isinstance(self.settings, LatticeRowAssignmentSettings):
            raise TypeError(
                "settings must be LatticeRowAssignmentSettings."
            )
        if (
            self.settings_fingerprint
            != lattice_row_assignment_settings_fingerprint(self.settings)
        ):
            raise ValueError(
                "settings_fingerprint must match settings."
            )
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.schema_version != LATTICE_ROW_ASSIGNMENT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version: {self.schema_version!r}."
            )
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "domain_assignments", assignments)
        for field_name in (
            "orientation_reference",
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
            "point_coordinate_fingerprint",
            "lattice_domain_analysis_fingerprint",
            "settings_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_empty_string(getattr(self, field_name), field_name),
            )

    def assignment_for_domain(
        self,
        lattice_domain_id: str,
    ) -> LatticeDomainRowAssignment:
        normalized = _non_empty_string(
            lattice_domain_id,
            "lattice_domain_id",
        )
        for assignment in self.domain_assignments:
            if assignment.lattice_domain_id == normalized:
                return assignment
        raise KeyError(f"Unknown lattice_domain_id: {normalized!r}.")


def lattice_row_assignment_analysis_fingerprint(
    analysis: LatticeRowAssignmentAnalysis,
) -> str:
    if not isinstance(analysis, LatticeRowAssignmentAnalysis):
        raise TypeError(
            "analysis must be LatticeRowAssignmentAnalysis."
        )
    return _fingerprint(
        {
            "algorithm": LATTICE_ROW_ASSIGNMENT_ALGORITHM_VERSION,
            "analysis": asdict(analysis),
        }
    )


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    normalized = _integer(value, field_name)
    if normalized < 0:
        raise ValueError(
            f"{field_name} must be a non-negative integer."
        )
    return normalized


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    return value


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
        raise ValueError(f"{field_name} must be between zero and one.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


__all__ = [
    "LATTICE_ROW_ASSIGNMENT_ALGORITHM_VERSION",
    "LATTICE_ROW_ASSIGNMENT_SCHEMA_VERSION",
    "LatticeDomainRowAssignment",
    "LatticeRow",
    "LatticeRowAssignmentAnalysis",
    "LatticeRowAssignmentReason",
    "LatticeRowAssignmentSettings",
    "LatticeRowAssignmentStatus",
    "LatticeRowAxisCandidate",
    "LatticeRowMemberAssignment",
    "lattice_row_assignment_analysis_fingerprint",
    "lattice_row_assignment_settings_fingerprint",
]
