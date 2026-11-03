"""Validated hierarchy joining lattice geometry and molecular stacking."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Mapping

from .lattice_domain_models import (
    LatticeDomain,
    LatticeDomainAnalysis,
    LatticeDomainDominantSymmetry,
    lattice_domain_analysis_fingerprint,
)
from .lattice_row_models import (
    LatticeRowAssignmentAnalysis,
    lattice_row_assignment_analysis_fingerprint,
)
from .molecular_stacking_models import (
    MolecularStackingAnalysis,
    OrientationalSubdomain,
    StackingOrder,
    StackingPattern,
    molecular_stacking_analysis_fingerprint,
)


MOLECULAR_ORDER_HIERARCHY_SCHEMA_VERSION = 1
MOLECULAR_ORDER_HIERARCHY_ALGORITHM_VERSION = (
    "moltrack-molecular-order-hierarchy-v1"
)

MolecularOrderLatticeDomainKey = tuple[int, str]
MolecularOrderOrientationalSubdomainKey = tuple[int, str, str]
MolecularOrderStackingKey = tuple[int, str, str, str]


@dataclass(frozen=True)
class MolecularOrderStacking:
    """Local stacking evidence attached to one orientational subdomain."""

    frame_index: int
    parent_lattice_domain_id: str
    parent_orientational_subdomain_id: str
    subdomain: OrientationalSubdomain

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        domain_id = _non_empty_string(
            self.parent_lattice_domain_id,
            "parent_lattice_domain_id",
        )
        subdomain_id = _non_empty_string(
            self.parent_orientational_subdomain_id,
            "parent_orientational_subdomain_id",
        )
        if not isinstance(self.subdomain, OrientationalSubdomain):
            raise TypeError("subdomain must be OrientationalSubdomain.")
        if (
            self.subdomain.frame_index != frame_index
            or self.subdomain.parent_lattice_domain_id != domain_id
            or self.subdomain.subdomain_id != subdomain_id
        ):
            raise ValueError(
                "Local stacking evidence must match its hierarchy parents."
            )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(
            self,
            "parent_lattice_domain_id",
            domain_id,
        )
        object.__setattr__(
            self,
            "parent_orientational_subdomain_id",
            subdomain_id,
        )

    @property
    def stable_key(self) -> MolecularOrderStackingKey:
        return (
            self.frame_index,
            self.parent_lattice_domain_id,
            self.parent_orientational_subdomain_id,
            "stacking",
        )

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.subdomain.source_ids

    @property
    def pattern(self) -> str:
        return self.subdomain.pattern


@dataclass(frozen=True)
class MolecularOrderOrientationalSubdomain:
    """One non-overlapping orientational child of a lattice domain."""

    frame_index: int
    parent_lattice_domain_id: str
    orientational_subdomain_id: str
    source_ids: tuple[str, ...]
    stacking_order: MolecularOrderStacking

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        domain_id = _non_empty_string(
            self.parent_lattice_domain_id,
            "parent_lattice_domain_id",
        )
        subdomain_id = _non_empty_string(
            self.orientational_subdomain_id,
            "orientational_subdomain_id",
        )
        source_ids = _sorted_source_ids(
            self.source_ids,
            "source_ids",
            allow_empty=False,
        )
        if not isinstance(self.stacking_order, MolecularOrderStacking):
            raise TypeError(
                "stacking_order must be MolecularOrderStacking."
            )
        stacking = self.stacking_order
        if (
            stacking.frame_index != frame_index
            or stacking.parent_lattice_domain_id != domain_id
            or stacking.parent_orientational_subdomain_id != subdomain_id
        ):
            raise ValueError(
                "Stacking order must preserve its orientational parent key."
            )
        if stacking.source_ids != source_ids:
            raise ValueError(
                "Stacking membership must cover its orientational subdomain."
            )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(
            self,
            "parent_lattice_domain_id",
            domain_id,
        )
        object.__setattr__(
            self,
            "orientational_subdomain_id",
            subdomain_id,
        )
        object.__setattr__(self, "source_ids", source_ids)

    @property
    def stable_key(self) -> MolecularOrderOrientationalSubdomainKey:
        return (
            self.frame_index,
            self.parent_lattice_domain_id,
            self.orientational_subdomain_id,
        )


@dataclass(frozen=True)
class MolecularOrderLatticeDomain:
    """A lattice domain with independent orientational and stacking axes."""

    frame_index: int
    lattice_domain: LatticeDomain
    stacking_order: StackingOrder
    orientational_subdomains: tuple[
        MolecularOrderOrientationalSubdomain,
        ...,
    ]
    unresolved_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        if not isinstance(self.lattice_domain, LatticeDomain):
            raise TypeError("lattice_domain must be LatticeDomain.")
        if not isinstance(self.stacking_order, StackingOrder):
            raise TypeError("stacking_order must be StackingOrder.")
        domain_id = self.lattice_domain.lattice_domain_id
        if (
            self.stacking_order.frame_index != frame_index
            or self.stacking_order.lattice_domain_id != domain_id
        ):
            raise ValueError(
                "Stacking order must match its lattice-domain parent."
            )
        if (
            self.stacking_order.domain_molecule_count
            != self.lattice_domain.molecule_count
        ):
            raise ValueError(
                "Stacking order must preserve lattice-domain molecule count."
            )

        subdomains = tuple(self.orientational_subdomains)
        if any(
            not isinstance(value, MolecularOrderOrientationalSubdomain)
            for value in subdomains
        ):
            raise TypeError(
                "orientational_subdomains must contain hierarchy nodes."
            )
        keys = tuple(value.stable_key for value in subdomains)
        if keys != tuple(sorted(set(keys))):
            raise ValueError(
                "Orientational subdomains require sorted unique stable keys."
            )
        if any(
            value.frame_index != frame_index
            or value.parent_lattice_domain_id != domain_id
            for value in subdomains
        ):
            raise ValueError(
                "Orientational subdomains must preserve lattice parent keys."
            )
        if tuple(value.orientational_subdomain_id for value in subdomains) != (
            self.stacking_order.subdomain_ids
        ):
            raise ValueError(
                "Hierarchy subdomains must match stacking-order children."
            )
        claimed: set[str] = set()
        for subdomain in subdomains:
            if claimed.intersection(subdomain.source_ids):
                raise ValueError(
                    "Orientational sibling memberships cannot overlap."
                )
            claimed.update(subdomain.source_ids)
        if (
            self.stacking_order.pattern
            in {"ABAB", "mixed", "uniform"}
            and len(claimed) != self.stacking_order.ordered_molecule_count
        ):
            raise ValueError(
                "Orientational children must cover ordered molecules exactly."
            )

        unresolved = _sorted_source_ids(
            self.unresolved_source_ids,
            "unresolved_source_ids",
            allow_empty=True,
        )
        domain_members = set(self.lattice_domain.source_ids)
        if not claimed.issubset(domain_members):
            raise ValueError(
                "Orientational members must belong to the lattice domain."
            )
        if claimed.intersection(unresolved):
            raise ValueError(
                "Resolved and unresolved domain memberships cannot overlap."
            )
        if claimed.union(unresolved) != domain_members:
            raise ValueError(
                "Resolved and unresolved memberships must partition the domain."
            )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(
            self,
            "orientational_subdomains",
            subdomains,
        )
        object.__setattr__(self, "unresolved_source_ids", unresolved)

    @property
    def stable_key(self) -> MolecularOrderLatticeDomainKey:
        return (self.frame_index, self.lattice_domain.lattice_domain_id)

    @property
    def dominant_symmetry(self) -> LatticeDomainDominantSymmetry:
        return self.lattice_domain.dominant_symmetry

    @property
    def stacking_pattern(self) -> StackingPattern:
        return self.stacking_order.pattern


@dataclass(frozen=True)
class MolecularOrderFrame:
    """Complete hierarchy partition and provenance for one input frame."""

    frame_index: int
    source_ids: tuple[str, ...]
    lattice_domains: tuple[MolecularOrderLatticeDomain, ...]
    unassigned_source_ids: tuple[str, ...]
    lattice_domain_analysis_fingerprint: str
    row_assignment_fingerprint: str

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        source_ids = _unique_source_ids(self.source_ids, "source_ids")
        domains = tuple(self.lattice_domains)
        if any(
            not isinstance(value, MolecularOrderLatticeDomain)
            for value in domains
        ):
            raise TypeError(
                "lattice_domains must contain hierarchy domain nodes."
            )
        keys = tuple(value.stable_key for value in domains)
        if keys != tuple(sorted(set(keys))):
            raise ValueError(
                "Lattice domains require sorted unique stable keys."
            )
        if any(value.frame_index != frame_index for value in domains):
            raise ValueError(
                "Lattice-domain hierarchy nodes must belong to the frame."
            )

        claimed: set[str] = set()
        for domain in domains:
            members = set(domain.lattice_domain.source_ids)
            if claimed.intersection(members):
                raise ValueError(
                    "Lattice-domain sibling memberships cannot overlap."
                )
            claimed.update(members)
        unassigned = _sorted_source_ids(
            self.unassigned_source_ids,
            "unassigned_source_ids",
            allow_empty=True,
        )
        frame_members = set(source_ids)
        if not claimed.issubset(frame_members):
            raise ValueError("Lattice-domain members must belong to the frame.")
        if claimed.intersection(unassigned):
            raise ValueError(
                "Assigned and unassigned frame memberships cannot overlap."
            )
        if claimed.union(unassigned) != frame_members:
            raise ValueError(
                "Domains and unassigned members must partition the frame."
            )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "lattice_domains", domains)
        object.__setattr__(self, "unassigned_source_ids", unassigned)
        object.__setattr__(
            self,
            "lattice_domain_analysis_fingerprint",
            _sha256_fingerprint(
                self.lattice_domain_analysis_fingerprint,
                "lattice_domain_analysis_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "row_assignment_fingerprint",
            _sha256_fingerprint(
                self.row_assignment_fingerprint,
                "row_assignment_fingerprint",
            ),
        )

    def domain_for_id(
        self,
        lattice_domain_id: str,
    ) -> MolecularOrderLatticeDomain:
        domain_id = _non_empty_string(
            lattice_domain_id,
            "lattice_domain_id",
        )
        for domain in self.lattice_domains:
            if domain.lattice_domain.lattice_domain_id == domain_id:
                return domain
        raise KeyError(f"Unknown lattice_domain_id: {domain_id!r}.")


@dataclass(frozen=True)
class MolecularOrderHierarchy:
    """Versioned per-frame hierarchy with no temporal identity tracking."""

    frames: tuple[MolecularOrderFrame, ...]
    input_frame_indices: tuple[int, ...]
    source_file_sha256: str | None
    source_view: str | None
    prototype_analysis_fingerprint: str
    stacking_analysis_fingerprint: str
    schema_version: int = MOLECULAR_ORDER_HIERARCHY_SCHEMA_VERSION
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        frames = tuple(self.frames)
        if any(not isinstance(value, MolecularOrderFrame) for value in frames):
            raise TypeError("frames must contain MolecularOrderFrame values.")
        frame_indices = tuple(value.frame_index for value in frames)
        if frame_indices != tuple(sorted(set(frame_indices))):
            raise ValueError("frames must be sorted and unique by frame_index.")
        input_indices = tuple(
            _non_negative_integer(value, "input_frame_indices")
            for value in self.input_frame_indices
        )
        if input_indices != frame_indices:
            raise ValueError(
                "input_frame_indices must match hierarchy frames exactly."
            )
        if self.schema_version != MOLECULAR_ORDER_HIERARCHY_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version: {self.schema_version!r}."
            )
        if self.uses_tracking is not False:
            raise ValueError("Molecular order hierarchy cannot use tracking.")
        source_sha = (
            None
            if self.source_file_sha256 is None
            else _sha256_fingerprint(
                self.source_file_sha256,
                "source_file_sha256",
            )
        )
        source_view = (
            None
            if self.source_view is None
            else _non_empty_string(self.source_view, "source_view")
        )
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "input_frame_indices", input_indices)
        object.__setattr__(self, "source_file_sha256", source_sha)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(
            self,
            "prototype_analysis_fingerprint",
            _sha256_fingerprint(
                self.prototype_analysis_fingerprint,
                "prototype_analysis_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "stacking_analysis_fingerprint",
            _sha256_fingerprint(
                self.stacking_analysis_fingerprint,
                "stacking_analysis_fingerprint",
            ),
        )
        object.__setattr__(self, "uses_tracking", False)

    def frame_for_index(self, frame_index: int) -> MolecularOrderFrame:
        normalized = _non_negative_integer(frame_index, "frame_index")
        for frame in self.frames:
            if frame.frame_index == normalized:
                return frame
        raise KeyError(f"Unknown frame_index: {normalized}.")


def build_molecular_order_hierarchy(
    lattice_domain_analyses: Mapping[int, LatticeDomainAnalysis],
    row_assignment_analyses: Mapping[int, LatticeRowAssignmentAnalysis],
    stacking_analysis: MolecularStackingAnalysis,
) -> MolecularOrderHierarchy:
    """Join independently computed results after validating their provenance."""

    lattices = _analysis_mapping(
        lattice_domain_analyses,
        LatticeDomainAnalysis,
        "lattice_domain_analyses",
    )
    rows = _analysis_mapping(
        row_assignment_analyses,
        LatticeRowAssignmentAnalysis,
        "row_assignment_analyses",
    )
    if not isinstance(stacking_analysis, MolecularStackingAnalysis):
        raise TypeError(
            "stacking_analysis must be MolecularStackingAnalysis."
        )
    expected_frames = stacking_analysis.input_frame_indices
    if tuple(sorted(lattices)) != expected_frames:
        raise ValueError(
            "Lattice-domain analyses must cover all stacking input frames."
        )
    if tuple(sorted(rows)) != expected_frames:
        raise ValueError(
            "Row assignments must cover all stacking input frames."
        )

    expected_row_fingerprints = dict(
        stacking_analysis.row_assignment_fingerprints
    )
    order_by_key = {
        (order.frame_index, order.lattice_domain_id): order
        for order in stacking_analysis.orders
    }
    subdomains_by_key: dict[
        tuple[int, str],
        list[OrientationalSubdomain],
    ] = {}
    for subdomain in stacking_analysis.subdomains:
        key = (
            subdomain.frame_index,
            subdomain.parent_lattice_domain_id,
        )
        subdomains_by_key.setdefault(key, []).append(subdomain)

    expected_domain_keys = {
        (frame_index, component.lattice_domain_id)
        for frame_index, analysis in lattices.items()
        for component in analysis.components
    }
    if set(order_by_key) != expected_domain_keys:
        raise ValueError(
            "Stacking orders must cover every lattice component exactly."
        )

    frames = []
    for frame_index in expected_frames:
        lattice = lattices[frame_index]
        row_assignment = rows[frame_index]
        lattice_fingerprint = lattice_domain_analysis_fingerprint(lattice)
        row_fingerprint = lattice_row_assignment_analysis_fingerprint(
            row_assignment
        )
        if row_assignment.lattice_domain_analysis_fingerprint != (
            lattice_fingerprint
        ):
            raise ValueError(
                "Row assignment has mismatched lattice-domain provenance."
            )
        if row_fingerprint != expected_row_fingerprints[frame_index]:
            raise ValueError(
                "Stacking analysis has mismatched row-assignment provenance."
            )
        _validate_frame_provenance(lattice, row_assignment)

        row_by_domain = {
            value.lattice_domain_id: value
            for value in row_assignment.domain_assignments
        }
        component_by_domain = {
            value.lattice_domain_id: value
            for value in lattice.components
        }
        if set(row_by_domain) != set(component_by_domain):
            raise ValueError(
                "Row assignments must cover every lattice component exactly."
            )
        for domain_id, component in component_by_domain.items():
            row_domain = row_by_domain[domain_id]
            if (
                row_domain.source_ids != component.source_ids
                or row_domain.molecule_count != component.molecule_count
            ):
                raise ValueError(
                    "Row membership must match its lattice component."
                )

        hierarchy_domains = []
        for component in sorted(
            lattice.components,
            key=lambda value: value.lattice_domain_id,
        ):
            key = (frame_index, component.lattice_domain_id)
            order = order_by_key[key]
            children = []
            for subdomain in sorted(
                subdomains_by_key.get(key, ()),
                key=lambda value: value.subdomain_id,
            ):
                stacking = MolecularOrderStacking(
                    frame_index=frame_index,
                    parent_lattice_domain_id=component.lattice_domain_id,
                    parent_orientational_subdomain_id=(
                        subdomain.subdomain_id
                    ),
                    subdomain=subdomain,
                )
                children.append(
                    MolecularOrderOrientationalSubdomain(
                        frame_index=frame_index,
                        parent_lattice_domain_id=(
                            component.lattice_domain_id
                        ),
                        orientational_subdomain_id=(
                            subdomain.subdomain_id
                        ),
                        source_ids=subdomain.source_ids,
                        stacking_order=stacking,
                    )
                )
            claimed = {
                source_id
                for child in children
                for source_id in child.source_ids
            }
            unresolved = tuple(
                sorted(set(component.source_ids).difference(claimed))
            )
            hierarchy_domains.append(
                MolecularOrderLatticeDomain(
                    frame_index=frame_index,
                    lattice_domain=component,
                    stacking_order=order,
                    orientational_subdomains=tuple(children),
                    unresolved_source_ids=unresolved,
                )
            )
        assigned = {
            source_id
            for domain in hierarchy_domains
            for source_id in domain.lattice_domain.source_ids
        }
        frames.append(
            MolecularOrderFrame(
                frame_index=frame_index,
                source_ids=lattice.source_ids,
                lattice_domains=tuple(hierarchy_domains),
                unassigned_source_ids=tuple(
                    sorted(set(lattice.source_ids).difference(assigned))
                ),
                lattice_domain_analysis_fingerprint=lattice_fingerprint,
                row_assignment_fingerprint=row_fingerprint,
            )
        )
    return MolecularOrderHierarchy(
        frames=tuple(frames),
        input_frame_indices=expected_frames,
        source_file_sha256=stacking_analysis.source_file_sha256,
        source_view=stacking_analysis.source_view,
        prototype_analysis_fingerprint=(
            stacking_analysis.prototype_analysis_fingerprint
        ),
        stacking_analysis_fingerprint=(
            molecular_stacking_analysis_fingerprint(stacking_analysis)
        ),
    )


def molecular_order_hierarchy_fingerprint(
    hierarchy: MolecularOrderHierarchy,
) -> str:
    """Fingerprint all memberships, independent order axes, and provenance."""

    if not isinstance(hierarchy, MolecularOrderHierarchy):
        raise TypeError("hierarchy must be MolecularOrderHierarchy.")
    return _fingerprint(
        {
            "algorithm": MOLECULAR_ORDER_HIERARCHY_ALGORITHM_VERSION,
            "hierarchy": asdict(hierarchy),
        }
    )


def _validate_frame_provenance(
    lattice: LatticeDomainAnalysis,
    rows: LatticeRowAssignmentAnalysis,
) -> None:
    fields = (
        "source_ids",
        "point_count",
        "coordinate_frame",
        "orientation_reference",
        "spatial_calibration_fingerprint",
        "registration_fingerprint",
        "point_coordinate_fingerprint",
    )
    if any(getattr(lattice, name) != getattr(rows, name) for name in fields):
        raise ValueError(
            "Lattice-domain and row-assignment frame provenance must match."
        )


def _analysis_mapping(
    values: Mapping[int, object],
    expected_type: type,
    field_name: str,
) -> dict[int, object]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping keyed by frame.")
    normalized: dict[int, object] = {}
    for raw_frame_index, analysis in values.items():
        frame_index = _non_negative_integer(
            raw_frame_index,
            f"{field_name} frame index",
        )
        if not isinstance(analysis, expected_type):
            raise TypeError(
                f"{field_name} values must be {expected_type.__name__}."
            )
        normalized[frame_index] = analysis
    return normalized


def _unique_source_ids(
    values: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    normalized = tuple(values)
    if (
        len(set(normalized)) != len(normalized)
        or any(not isinstance(value, str) or not value for value in normalized)
    ):
        raise ValueError(
            f"{field_name} must contain unique non-empty strings."
        )
    return normalized


def _sorted_source_ids(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    normalized = _unique_source_ids(values, field_name)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    if normalized != tuple(sorted(normalized)):
        raise ValueError(f"{field_name} must be deterministically sorted.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _sha256_fingerprint(value: object, field_name: str) -> str:
    normalized = _non_empty_string(value, field_name)
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return normalized


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
