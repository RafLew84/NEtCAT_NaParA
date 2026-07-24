"""Versioned contracts for molecular stacking and orientational subdomains."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from math import isclose, isfinite
from typing import Literal, Mapping, get_args

from .molecular_orientation_prototype_models import (
    MolecularOrientationPatternMode,
    MolecularOrientationPatternPhase,
)


MOLECULAR_STACKING_SCHEMA_VERSION = 1
MOLECULAR_STACKING_ALGORITHM_VERSION = "moltrack-molecular-stacking-v1"

StackingPattern = Literal[
    "ABAB",
    "uniform",
    "mixed",
    "ambiguous",
    "unavailable",
]
StackingSubdomainPattern = Literal["ABAB", "uniform"]
StackingQCReason = Literal[
    "prototype_states_unavailable",
    "no_axis_evidence",
    "insufficient_domain_coverage",
    "insufficient_subdomain_size",
    "axis_selection_ambiguous",
    "pattern_score_below_threshold",
    "incomplete_coverage",
    "orientation_outliers",
    "phase_boundary",
    "pattern_boundary",
    "spatial_fragmentation",
    "low_confidence",
]

_PATTERNS = set(get_args(StackingPattern))
_SUBDOMAIN_PATTERNS = set(get_args(StackingSubdomainPattern))
_QC_REASONS = set(get_args(StackingQCReason))
_MODES = set(get_args(MolecularOrientationPatternMode))
_PHASES = set(get_args(MolecularOrientationPatternPhase))


@dataclass(frozen=True)
class MolecularStackingSettings:
    """Thresholds for local pattern evidence and spatial components."""

    minimum_domain_coverage: float = 0.6
    minimum_local_score: float = 0.7
    minimum_local_margin: float = 0.05
    minimum_subdomain_size: int = 3
    minimum_ordered_fraction: float = 0.6
    minimum_order_score: float = 0.7
    minimum_axis_margin: float = 0.05
    low_confidence_threshold: float = 0.6

    def __post_init__(self) -> None:
        for field_name in (
            "minimum_domain_coverage",
            "minimum_local_score",
            "minimum_local_margin",
            "minimum_ordered_fraction",
            "minimum_order_score",
            "minimum_axis_margin",
            "low_confidence_threshold",
        ):
            object.__setattr__(
                self,
                field_name,
                _unit_float(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "minimum_subdomain_size",
            _positive_integer(
                self.minimum_subdomain_size,
                "minimum_subdomain_size",
            ),
        )

    def to_dict(self) -> dict[str, int | float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularStackingSettings":
        if not isinstance(payload, Mapping):
            raise TypeError("Stacking settings must be a mapping.")
        names = {field.name for field in fields(cls)}
        if set(payload) != names:
            raise ValueError("Stacking settings fields must match the schema.")
        return cls(**dict(payload))


def molecular_stacking_settings_fingerprint(
    settings: MolecularStackingSettings,
) -> str:
    if not isinstance(settings, MolecularStackingSettings):
        raise TypeError("settings must be MolecularStackingSettings.")
    return _fingerprint(
        {
            "algorithm": MOLECULAR_STACKING_ALGORITHM_VERSION,
            "settings": settings.to_dict(),
        }
    )


@dataclass(frozen=True)
class OrientationalSubdomain:
    """One spatially connected local stacking pattern."""

    subdomain_id: str
    frame_index: int
    parent_lattice_domain_id: str
    pattern: StackingSubdomainPattern
    axis_candidate_index: int | None
    axis_angle_deg: float | None
    mode: MolecularOrientationPatternMode | None
    phase: MolecularOrientationPatternPhase | None
    source_ids: tuple[str, ...]
    molecule_count: int
    parent_molecule_count: int
    coverage_fraction: float
    score: float
    confidence: float
    qc_reasons: tuple[StackingQCReason, ...]

    def __post_init__(self) -> None:
        subdomain_id = _non_empty_string(self.subdomain_id, "subdomain_id")
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        parent_id = _non_empty_string(
            self.parent_lattice_domain_id,
            "parent_lattice_domain_id",
        )
        if self.pattern not in _SUBDOMAIN_PATTERNS:
            raise ValueError(f"Unsupported subdomain pattern: {self.pattern!r}.")
        source_ids = _source_ids(self.source_ids, allow_empty=False)
        molecule_count = _positive_integer(
            self.molecule_count,
            "molecule_count",
        )
        parent_count = _positive_integer(
            self.parent_molecule_count,
            "parent_molecule_count",
        )
        if len(source_ids) != molecule_count or molecule_count > parent_count:
            raise ValueError("Subdomain counts must match source_ids and parent.")
        expected_coverage = molecule_count / parent_count
        if not isclose(
            float(self.coverage_fraction),
            expected_coverage,
            abs_tol=1e-12,
        ):
            raise ValueError("coverage_fraction must match molecule counts.")
        axis_index = _optional_non_negative_integer(
            self.axis_candidate_index,
            "axis_candidate_index",
        )
        axis_angle = _optional_axis_angle(self.axis_angle_deg)
        mode = _optional_member(self.mode, _MODES, "mode")
        phase = _optional_member(self.phase, _PHASES, "phase")
        if self.pattern == "ABAB":
            if None in (axis_index, axis_angle, mode, phase):
                raise ValueError("ABAB subdomain requires axis, mode, and phase.")
        elif any(
            value is not None
            for value in (axis_index, axis_angle, mode, phase)
        ):
            raise ValueError("Uniform subdomain cannot contain A/B geometry.")
        object.__setattr__(self, "subdomain_id", subdomain_id)
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "parent_lattice_domain_id", parent_id)
        object.__setattr__(self, "axis_candidate_index", axis_index)
        object.__setattr__(self, "axis_angle_deg", axis_angle)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "molecule_count", molecule_count)
        object.__setattr__(self, "parent_molecule_count", parent_count)
        object.__setattr__(self, "coverage_fraction", expected_coverage)
        object.__setattr__(self, "score", _unit_float(self.score, "score"))
        object.__setattr__(
            self,
            "confidence",
            _unit_float(self.confidence, "confidence"),
        )
        object.__setattr__(
            self,
            "qc_reasons",
            _qc_reasons(self.qc_reasons),
        )


@dataclass(frozen=True)
class StackingOrder:
    """Auditable stacking result for one parent lattice domain."""

    frame_index: int
    lattice_domain_id: str
    pattern: StackingPattern
    axis_candidate_index: int | None
    axis_angle_deg: float | None
    mode: MolecularOrientationPatternMode | None
    phase: MolecularOrientationPatternPhase | None
    prototype_a_angle_deg: float | None
    prototype_b_angle_deg: float | None
    periodicity_deg: float | None
    score: float | None
    confidence: float
    domain_molecule_count: int
    usable_molecule_count: int
    ordered_molecule_count: int
    coverage_fraction: float
    ordered_fraction: float
    subdomain_ids: tuple[str, ...]
    qc_reasons: tuple[StackingQCReason, ...]

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        domain_id = _non_empty_string(
            self.lattice_domain_id,
            "lattice_domain_id",
        )
        if self.pattern not in _PATTERNS:
            raise ValueError(f"Unsupported stacking pattern: {self.pattern!r}.")
        domain_count = _positive_integer(
            self.domain_molecule_count,
            "domain_molecule_count",
        )
        usable_count = _non_negative_integer(
            self.usable_molecule_count,
            "usable_molecule_count",
        )
        ordered_count = _non_negative_integer(
            self.ordered_molecule_count,
            "ordered_molecule_count",
        )
        if ordered_count > usable_count or usable_count > domain_count:
            raise ValueError("Stacking molecule counts are inconsistent.")
        coverage = usable_count / domain_count
        ordered_fraction = (
            0.0 if usable_count == 0 else ordered_count / usable_count
        )
        if not isclose(float(self.coverage_fraction), coverage, abs_tol=1e-12):
            raise ValueError("coverage_fraction must match molecule counts.")
        if not isclose(
            float(self.ordered_fraction),
            ordered_fraction,
            abs_tol=1e-12,
        ):
            raise ValueError("ordered_fraction must match molecule counts.")
        axis_index = _optional_non_negative_integer(
            self.axis_candidate_index,
            "axis_candidate_index",
        )
        axis_angle = _optional_axis_angle(self.axis_angle_deg)
        mode = _optional_member(self.mode, _MODES, "mode")
        phase = _optional_member(self.phase, _PHASES, "phase")
        periodicity = (
            None
            if self.periodicity_deg is None
            else _positive_float(self.periodicity_deg, "periodicity_deg")
        )
        prototype_a = _optional_periodic_angle(
            self.prototype_a_angle_deg,
            periodicity,
            "prototype_a_angle_deg",
        )
        prototype_b = _optional_periodic_angle(
            self.prototype_b_angle_deg,
            periodicity,
            "prototype_b_angle_deg",
        )
        score = (
            None if self.score is None else _unit_float(self.score, "score")
        )
        subdomain_ids = tuple(self.subdomain_ids)
        if subdomain_ids != tuple(sorted(set(subdomain_ids))):
            raise ValueError("subdomain_ids must be sorted and unique.")
        qc_reasons = _qc_reasons(self.qc_reasons)
        _validate_order_shape(
            self.pattern,
            axis_index=axis_index,
            axis_angle=axis_angle,
            mode=mode,
            phase=phase,
            prototype_a=prototype_a,
            prototype_b=prototype_b,
            periodicity=periodicity,
            score=score,
            confidence=float(self.confidence),
            subdomain_ids=subdomain_ids,
            qc_reasons=qc_reasons,
        )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "axis_candidate_index", axis_index)
        object.__setattr__(self, "axis_angle_deg", axis_angle)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "prototype_a_angle_deg", prototype_a)
        object.__setattr__(self, "prototype_b_angle_deg", prototype_b)
        object.__setattr__(self, "periodicity_deg", periodicity)
        object.__setattr__(self, "score", score)
        object.__setattr__(
            self,
            "confidence",
            _unit_float(self.confidence, "confidence"),
        )
        object.__setattr__(self, "domain_molecule_count", domain_count)
        object.__setattr__(self, "usable_molecule_count", usable_count)
        object.__setattr__(self, "ordered_molecule_count", ordered_count)
        object.__setattr__(self, "coverage_fraction", coverage)
        object.__setattr__(self, "ordered_fraction", ordered_fraction)
        object.__setattr__(self, "subdomain_ids", subdomain_ids)
        object.__setattr__(self, "qc_reasons", qc_reasons)


@dataclass(frozen=True)
class MolecularStackingAnalysis:
    """Stacking orders and non-overlapping subdomains for current frames."""

    orders: tuple[StackingOrder, ...]
    subdomains: tuple[OrientationalSubdomain, ...]
    input_frame_indices: tuple[int, ...]
    source_file_sha256: str | None
    source_view: str | None
    prototype_analysis_fingerprint: str
    row_assignment_fingerprints: tuple[tuple[int, str], ...]
    settings: MolecularStackingSettings
    settings_fingerprint: str
    schema_version: int = MOLECULAR_STACKING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        orders = tuple(self.orders)
        subdomains = tuple(self.subdomains)
        if any(not isinstance(value, StackingOrder) for value in orders):
            raise TypeError("orders must contain StackingOrder values.")
        if any(
            not isinstance(value, OrientationalSubdomain)
            for value in subdomains
        ):
            raise TypeError(
                "subdomains must contain OrientationalSubdomain values."
            )
        order_keys = tuple(
            (value.frame_index, value.lattice_domain_id) for value in orders
        )
        if order_keys != tuple(sorted(set(order_keys))):
            raise ValueError("orders must be sorted and unique by domain key.")
        subdomain_keys = tuple(
            (
                value.frame_index,
                value.parent_lattice_domain_id,
                value.subdomain_id,
            )
            for value in subdomains
        )
        if subdomain_keys != tuple(sorted(set(subdomain_keys))):
            raise ValueError("subdomains must be deterministically sorted.")
        order_by_key = dict(zip(order_keys, orders))
        children_by_key: dict[tuple[int, str], list[OrientationalSubdomain]] = {}
        for value in subdomains:
            key = (value.frame_index, value.parent_lattice_domain_id)
            if key not in order_by_key:
                raise ValueError("Subdomain must reference an existing order.")
            children_by_key.setdefault(key, []).append(value)
        for key, order in order_by_key.items():
            children = tuple(children_by_key.get(key, ()))
            if tuple(sorted(value.subdomain_id for value in children)) != (
                order.subdomain_ids
            ):
                raise ValueError("Order subdomain_ids must match its children.")
            claimed: set[str] = set()
            for child in children:
                if child.parent_molecule_count != order.domain_molecule_count:
                    raise ValueError("Child parent count must match its order.")
                if claimed.intersection(child.source_ids):
                    raise ValueError("Sibling subdomains cannot overlap.")
                claimed.update(child.source_ids)
            if (
                order.pattern in {"ABAB", "mixed", "uniform"}
                and len(claimed) != order.ordered_molecule_count
            ):
                raise ValueError(
                    "Child memberships must cover ordered molecules exactly."
                )
        frame_indices = _frame_indices(self.input_frame_indices)
        if not {value.frame_index for value in orders}.issubset(frame_indices):
            raise ValueError("Order frames must belong to input_frame_indices.")
        row_fingerprints = tuple(self.row_assignment_fingerprints)
        if any(
            not isinstance(value, tuple)
            or len(value) != 2
            or value[0] not in frame_indices
            or not isinstance(value[1], str)
            or not value[1]
            for value in row_fingerprints
        ):
            raise ValueError("Invalid row-assignment fingerprint entry.")
        if tuple(value[0] for value in row_fingerprints) != frame_indices:
            raise ValueError(
                "Row fingerprints must cover every input frame."
            )
        if not isinstance(self.settings, MolecularStackingSettings):
            raise TypeError("settings must be MolecularStackingSettings.")
        if self.settings_fingerprint != (
            molecular_stacking_settings_fingerprint(self.settings)
        ):
            raise ValueError("settings_fingerprint must match settings.")
        if self.schema_version != MOLECULAR_STACKING_SCHEMA_VERSION:
            raise ValueError("Unsupported stacking schema_version.")
        object.__setattr__(self, "orders", orders)
        object.__setattr__(self, "subdomains", subdomains)
        object.__setattr__(self, "input_frame_indices", frame_indices)
        object.__setattr__(
            self,
            "source_file_sha256",
            _optional_sha256(self.source_file_sha256),
        )
        object.__setattr__(
            self,
            "source_view",
            _optional_non_empty_string(self.source_view, "source_view"),
        )
        object.__setattr__(
            self,
            "prototype_analysis_fingerprint",
            _sha256(
                self.prototype_analysis_fingerprint,
                "prototype_analysis_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "row_assignment_fingerprints",
            row_fingerprints,
        )
        object.__setattr__(
            self,
            "settings_fingerprint",
            _sha256(self.settings_fingerprint, "settings_fingerprint"),
        )

    def order_for_domain(
        self,
        frame_index: int,
        lattice_domain_id: str,
    ) -> StackingOrder:
        key = (
            _non_negative_integer(frame_index, "frame_index"),
            _non_empty_string(lattice_domain_id, "lattice_domain_id"),
        )
        for value in self.orders:
            if (value.frame_index, value.lattice_domain_id) == key:
                return value
        raise KeyError(f"Unknown stacking domain key: {key!r}.")


def molecular_stacking_analysis_fingerprint(
    analysis: MolecularStackingAnalysis,
) -> str:
    if not isinstance(analysis, MolecularStackingAnalysis):
        raise TypeError("analysis must be MolecularStackingAnalysis.")
    return _fingerprint(
        {
            "algorithm": MOLECULAR_STACKING_ALGORITHM_VERSION,
            "analysis": asdict(analysis),
        }
    )


def _validate_order_shape(
    pattern: StackingPattern,
    *,
    axis_index: int | None,
    axis_angle: float | None,
    mode: MolecularOrientationPatternMode | None,
    phase: MolecularOrientationPatternPhase | None,
    prototype_a: float | None,
    prototype_b: float | None,
    periodicity: float | None,
    score: float | None,
    confidence: float,
    subdomain_ids: tuple[str, ...],
    qc_reasons: tuple[StackingQCReason, ...],
) -> None:
    geometry = (axis_index, axis_angle, mode, phase)
    if pattern == "ABAB":
        if None in geometry or None in (
            prototype_a,
            prototype_b,
            periodicity,
            score,
        ):
            raise ValueError("ABAB order requires complete A/B evidence.")
        if len(subdomain_ids) < 1:
            raise ValueError("ABAB order requires a subdomain.")
    elif pattern == "mixed":
        if axis_index is None or axis_angle is None or None in (
            prototype_a,
            prototype_b,
            periodicity,
            score,
        ):
            raise ValueError("Mixed order requires axis and A/B prototypes.")
        if len(subdomain_ids) < 2:
            raise ValueError("Mixed order requires multiple subdomains.")
    elif pattern == "uniform":
        if any(value is not None for value in geometry):
            raise ValueError("Uniform order cannot contain A/B geometry.")
        if prototype_a is None or prototype_b is not None:
            raise ValueError("Uniform order requires one prototype.")
        if periodicity is None or score is None or len(subdomain_ids) != 1:
            raise ValueError("Uniform order requires one complete subdomain.")
    elif pattern == "ambiguous":
        if any(value is not None for value in geometry) or subdomain_ids:
            raise ValueError("Ambiguous order cannot select geometry.")
        if score is None or prototype_a is None or prototype_b is None:
            raise ValueError("Ambiguous order requires measured A/B evidence.")
    else:
        if (
            any(value is not None for value in geometry)
            or prototype_a is not None
            or prototype_b is not None
            or periodicity is not None
            or score is not None
            or subdomain_ids
            or confidence != 0.0
        ):
            raise ValueError("Unavailable order cannot contain a result.")
    if pattern in {"ambiguous", "unavailable"} and not qc_reasons:
        raise ValueError(f"{pattern} order requires a QC reason.")


def _qc_reasons(
    values: tuple[StackingQCReason, ...],
) -> tuple[StackingQCReason, ...]:
    normalized = tuple(values)
    if any(value not in _QC_REASONS for value in normalized):
        raise ValueError("Unsupported stacking QC reason.")
    if normalized != tuple(sorted(set(normalized))):
        raise ValueError("qc_reasons must be sorted and unique.")
    return normalized


def _source_ids(
    values: tuple[str, ...],
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    normalized = tuple(values)
    if (
        (not allow_empty and not normalized)
        or normalized != tuple(sorted(set(normalized)))
        or any(not isinstance(value, str) or not value for value in normalized)
    ):
        raise ValueError("source_ids must be sorted unique non-empty strings.")
    return normalized


def _frame_indices(values: tuple[int, ...]) -> tuple[int, ...]:
    normalized = tuple(values)
    if (
        not normalized
        or normalized != tuple(sorted(set(normalized)))
        or any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            for value in normalized
        )
    ):
        raise ValueError("input_frame_indices must be sorted and unique.")
    return normalized


def _optional_member(value, allowed: set, field_name: str):
    if value is not None and value not in allowed:
        raise ValueError(f"Unsupported {field_name}: {value!r}.")
    return value


def _optional_axis_angle(value: object) -> float | None:
    return (
        None
        if value is None
        else _finite_float(value, "axis_angle_deg") % 180.0
    )


def _optional_periodic_angle(
    value: object,
    periodicity: float | None,
    field_name: str,
) -> float | None:
    if value is None:
        return None
    if periodicity is None:
        raise ValueError(f"{field_name} requires periodicity_deg.")
    return _finite_float(value, field_name) % periodicity


def _optional_non_negative_integer(
    value: object,
    field_name: str,
) -> int | None:
    return (
        None
        if value is None
        else _non_negative_integer(value, field_name)
    )


def _optional_non_empty_string(
    value: object,
    field_name: str,
) -> str | None:
    return None if value is None else _non_empty_string(value, field_name)


def _optional_sha256(value: object) -> str | None:
    return None if value is None else _sha256(value, "source_file_sha256")


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _sha256(value: object, field_name: str) -> str:
    normalized = _non_empty_string(value, field_name)
    if len(normalized) != 64:
        raise ValueError(f"{field_name} must be a SHA-256 digest.")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a SHA-256 digest.") from exc
    return normalized.lower()


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between zero and one.")
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
    "MOLECULAR_STACKING_ALGORITHM_VERSION",
    "MOLECULAR_STACKING_SCHEMA_VERSION",
    "MolecularStackingAnalysis",
    "MolecularStackingSettings",
    "OrientationalSubdomain",
    "StackingOrder",
    "StackingPattern",
    "StackingQCReason",
    "StackingSubdomainPattern",
    "molecular_stacking_analysis_fingerprint",
    "molecular_stacking_settings_fingerprint",
]
