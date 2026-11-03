from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal


@dataclass(frozen=True)
class SourceInputEvidence:
    evidence_kind: ClassVar[str] = "source_input_v1"
    source_kind: str
    raw_centroid_x: float | None
    raw_centroid_y: float | None


@dataclass(frozen=True)
class CentroidEvidence:
    evidence_kind: ClassVar[str] = "centroid_v1"
    centroid_x_nm: float
    centroid_y_nm: float
    coordinate_frame: str


@dataclass(frozen=True)
class SampleCoordinatesEvidence:
    evidence_kind: ClassVar[str] = "sample_coordinates_v1"
    sample_x_nm: float
    sample_y_nm: float
    transform_fingerprint: str


@dataclass(frozen=True)
class FirstShellEvidence:
    evidence_kind: ClassVar[str] = "classic_m6_first_shell_v1"
    neighbor_count: int


@dataclass(frozen=True)
class LocalOrderEvidence:
    evidence_kind: ClassVar[str] = "classic_m6_local_order_v1"
    q6: float | None
    orientation_deg: float | None
    computation_status: str | None
    m3_availability: Literal["unavailable"] = "unavailable"


@dataclass(frozen=True)
class SeedGrowthEvidence:
    evidence_kind: ClassVar[str] = "classic_m6_seed_growth_v1"
    native_assignment_status: str
    core_halo_role: None = None
    core_halo_availability: Literal["unavailable"] = "unavailable"
    explicit_boundary: None = None
    explicit_boundary_availability: Literal["unavailable"] = "unavailable"


@dataclass(frozen=True)
class DomainPartitionEvidence:
    evidence_kind: ClassVar[str] = "m6_partition_v1"
    partition: str
    lattice_domain_id: str | None
    native_component_type: str | None
    explicit_boundary: None = None
    explicit_boundary_availability: Literal["unavailable"] = "unavailable"


@dataclass(frozen=True)
class DomainSizeEvidence:
    evidence_kind: ClassVar[str] = "m6_domain_size_v1"
    component_type: str
    molecule_count: int
