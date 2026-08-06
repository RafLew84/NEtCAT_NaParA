from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isclose, isfinite
from typing import Literal, TypeVar

from .classifier_models import ClassifierOutcome
from .events import (
    ClassifierStatus,
    DomainAnalysisEvent,
    DomainAnalysisEventStatus,
    DomainAnalysisRunStatus,
    validate_domain_analysis_lifecycle,
)
from .fingerprints import canonical_sha256
from .geometry import (
    GeometryMode,
    M6AnalyzedMolecule,
    M6PresentationProvenance,
    M6PublishedMolecule,
)


M6ComponentType = Literal["full_domain", "small_ordered_island"]
_PartitionItem = TypeVar("_PartitionItem")


@dataclass(frozen=True)
class DomainAnalysisRequest:
    """Immutable input snapshot for one Domain Analysis run."""

    frame_range: range
    geometry_mode: GeometryMode = "segmentation_preferred"
    classifier_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, range):
            raise TypeError("frame_range must be a range.")
        if self.frame_range.step != 1 or len(self.frame_range) == 0:
            raise ValueError("frame_range must be a non-empty ascending range.")
        if self.frame_range.start < 0:
            raise ValueError("frame_range cannot contain negative frame indexes.")
        if self.geometry_mode not in {"segmentation_preferred", "bbox_centers"}:
            raise ValueError(f"Unsupported geometry_mode: {self.geometry_mode!r}.")
        classifier_ids = tuple(self.classifier_ids)
        if any(not isinstance(value, str) or not value.strip() for value in classifier_ids):
            raise ValueError("classifier_ids must contain non-empty strings.")
        if len(set(classifier_ids)) != len(classifier_ids):
            raise ValueError("classifier_ids must be unique.")
        object.__setattr__(self, "classifier_ids", classifier_ids)

    @property
    def frame_indices(self) -> tuple[int, ...]:
        return tuple(self.frame_range)


@dataclass(frozen=True)
class M6ComponentMembership:
    """Adapter-owned membership before public geometry is canonicalized."""

    lattice_domain_id: str
    source_ids: tuple[str, ...]
    core_source_ids: tuple[str, ...] = ()
    halo_source_ids: tuple[str, ...] = ()
    qc_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        domain_id = _non_empty_string(self.lattice_domain_id, "lattice_domain_id")
        source_ids = _sorted_unique_ids(self.source_ids, "source_ids", allow_empty=False)
        core_ids = _sorted_unique_ids(self.core_source_ids, "core_source_ids")
        halo_ids = _sorted_unique_ids(self.halo_source_ids, "halo_source_ids")
        if set(core_ids).intersection(halo_ids):
            raise ValueError("Core and halo memberships must be disjoint.")
        if core_ids or halo_ids:
            if set(core_ids).union(halo_ids) != set(source_ids):
                raise ValueError("Core and halo memberships must cover the component.")
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "core_source_ids", core_ids)
        object.__setattr__(self, "halo_source_ids", halo_ids)
        object.__setattr__(
            self,
            "qc_flags",
            _sorted_unique_ids(self.qc_flags, "qc_flags"),
        )


@dataclass(frozen=True)
class M6FrameComputation:
    """Complete one-frame value returned by an injected M6 adapter."""

    frame_index: int
    molecules: tuple[M6AnalyzedMolecule, ...]
    analyzed_pixels_xy: tuple[tuple[int, int], ...]
    pixel_area_nm2: float
    full_domains: tuple[M6ComponentMembership, ...]
    small_ordered_islands: tuple[M6ComponentMembership, ...]
    coordinate_frame: str
    coordinate_transform_fingerprint: str
    m6_settings_fingerprint: str

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(self.frame_index, "frame_index")
        molecules = tuple(sorted(self.molecules, key=lambda value: value.source_id))
        if any(not isinstance(value, M6AnalyzedMolecule) for value in molecules):
            raise TypeError("molecules must contain M6AnalyzedMolecule values.")
        if len({value.source_id for value in molecules}) != len(molecules):
            raise ValueError("M6 adapter molecule source IDs must be unique.")
        analyzed_pixels = _sorted_unique_pixels(
            self.analyzed_pixels_xy,
            "analyzed_pixels_xy",
        )
        _validate_molecule_pixel_coverage(molecules, analyzed_pixels)
        full_domains = _sorted_memberships(self.full_domains, "full_domains")
        islands = _sorted_memberships(
            self.small_ordered_islands,
            "small_ordered_islands",
        )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "molecules", molecules)
        object.__setattr__(self, "analyzed_pixels_xy", analyzed_pixels)
        object.__setattr__(
            self,
            "pixel_area_nm2",
            _positive_float(self.pixel_area_nm2, "pixel_area_nm2"),
        )
        object.__setattr__(self, "full_domains", full_domains)
        object.__setattr__(self, "small_ordered_islands", islands)
        for field_name in (
            "coordinate_frame",
            "coordinate_transform_fingerprint",
            "m6_settings_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_empty_string(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class M6PublishedComponent:
    """Canonical geometry and membership of one published M6 component."""

    lattice_domain_id: str
    component_type: M6ComponentType
    members: tuple[M6PublishedMolecule, ...]
    core_source_ids: tuple[str, ...]
    halo_source_ids: tuple[str, ...]
    footprint_pixels_xy: tuple[tuple[int, int], ...]
    footprint_area_nm2: float
    centroid_xy_nm: tuple[float, float]
    bounds_xyxy_nm: tuple[float, float, float, float]
    qc_flags: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = field(init=False)
    points_xy_nm: tuple[tuple[float, float], ...] = field(init=False)

    def __post_init__(self) -> None:
        if self.component_type not in {"full_domain", "small_ordered_island"}:
            raise ValueError(f"Unsupported component_type: {self.component_type!r}.")
        members = tuple(sorted(self.members, key=lambda value: value.source_id))
        if not members or any(
            not isinstance(value, M6PublishedMolecule) for value in members
        ):
            raise TypeError("members must contain M6PublishedMolecule values.")
        source_ids = tuple(value.source_id for value in members)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Published component source IDs must be unique.")
        core_ids = _sorted_unique_ids(self.core_source_ids, "core_source_ids")
        halo_ids = _sorted_unique_ids(self.halo_source_ids, "halo_source_ids")
        if set(core_ids).intersection(halo_ids):
            raise ValueError("Core and halo memberships must be disjoint.")
        if (core_ids or halo_ids) and set(core_ids).union(halo_ids) != set(
            source_ids
        ):
            raise ValueError("Core and halo memberships must cover the component.")
        footprint_pixels = _sorted_unique_pixels(
            self.footprint_pixels_xy,
            "footprint_pixels_xy",
            allow_empty=False,
        )
        object.__setattr__(self, "lattice_domain_id", _non_empty_string(
            self.lattice_domain_id,
            "lattice_domain_id",
        ))
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(
            self,
            "points_xy_nm",
            tuple(value.point_xy_nm for value in members),
        )
        object.__setattr__(self, "core_source_ids", core_ids)
        object.__setattr__(self, "halo_source_ids", halo_ids)
        object.__setattr__(self, "footprint_pixels_xy", footprint_pixels)
        object.__setattr__(self, "footprint_area_nm2", _non_negative_float(
            self.footprint_area_nm2,
            "footprint_area_nm2",
        ))
        object.__setattr__(self, "centroid_xy_nm", _finite_pair(
            self.centroid_xy_nm,
            "centroid_xy_nm",
        ))
        object.__setattr__(self, "bounds_xyxy_nm", _finite_quad(
            self.bounds_xyxy_nm,
            "bounds_xyxy_nm",
        ))
        object.__setattr__(
            self,
            "qc_flags",
            _sorted_unique_ids(self.qc_flags, "qc_flags"),
        )

@dataclass(frozen=True)
class M6FrameGate:
    """Published disjoint M6 partition for one frame."""

    frame_index: int
    physical_frame_id: str
    coordinate_frame: str
    coordinate_transform_fingerprint: str
    presentation_provenance: M6PresentationProvenance
    source_geometry_fingerprint: str
    m6_settings_fingerprint: str
    m6_algorithm_version: str
    pixel_area_nm2: float
    full_domains: tuple[M6PublishedComponent, ...]
    small_ordered_islands: tuple[M6PublishedComponent, ...]
    outside_members: tuple[M6PublishedMolecule, ...]
    outside_pixels_xy: tuple[tuple[int, int], ...]
    outside_area_nm2: float
    analyzed_source_ids: tuple[str, ...]
    analyzed_pixels_xy: tuple[tuple[int, int], ...]
    analyzed_area_nm2: float
    outside_source_ids: tuple[str, ...] = field(init=False)
    m6_gate_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_index", _non_negative_integer(
            self.frame_index,
            "frame_index",
        ))
        for field_name in (
            "physical_frame_id",
            "coordinate_frame",
            "coordinate_transform_fingerprint",
            "source_geometry_fingerprint",
            "m6_settings_fingerprint",
            "m6_algorithm_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_empty_string(getattr(self, field_name), field_name),
            )
        normalized = _normalized_frame_gate_values(self)
        for field_name, value in normalized.items():
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "m6_gate_fingerprint", "")
        fingerprint_payload = asdict(self)
        fingerprint_payload.pop("presentation_provenance")
        fingerprint_payload.pop("m6_gate_fingerprint")
        fingerprint_payload["schema_version"] = "domain-analysis-m6-gate-v1"
        object.__setattr__(
            self,
            "m6_gate_fingerprint",
            canonical_sha256(fingerprint_payload),
        )

    @property
    def analyzed_molecule_count(self) -> int:
        return len(self.analyzed_source_ids)

    @property
    def full_domain_area_nm2(self) -> float:
        return sum(value.footprint_area_nm2 for value in self.full_domains)

    @property
    def small_ordered_island_area_nm2(self) -> float:
        return sum(
            value.footprint_area_nm2
            for value in self.small_ordered_islands
        )


def _normalized_frame_gate_values(frame: M6FrameGate) -> dict[str, object]:
    if not isinstance(frame.presentation_provenance, M6PresentationProvenance):
        raise TypeError("presentation_provenance must be M6PresentationProvenance.")
    full_domains = _published_components(
        frame.full_domains, "full_domain", "full_domains"
    )
    islands = _published_components(
        frame.small_ordered_islands, "small_ordered_island", "small_ordered_islands"
    )
    outside_members = tuple(
        sorted(frame.outside_members, key=lambda value: value.source_id)
    )
    if any(
        not isinstance(value, M6PublishedMolecule) for value in outside_members
    ):
        raise TypeError("outside_members must contain M6PublishedMolecule values.")
    outside_ids = tuple(value.source_id for value in outside_members)
    if len(set(outside_ids)) != len(outside_ids):
        raise ValueError("Outside source IDs must be unique.")
    analyzed_ids = _sorted_unique_ids(frame.analyzed_source_ids, "analyzed_source_ids")
    _validate_membership_partition(full_domains, islands, outside_ids, analyzed_ids)
    outside_pixels = _sorted_unique_pixels(frame.outside_pixels_xy, "outside_pixels_xy")
    analyzed_pixels = _sorted_unique_pixels(frame.analyzed_pixels_xy, "analyzed_pixels_xy")
    _validate_published_pixel_partition(
        full_domains, islands, outside_pixels, analyzed_pixels
    )
    pixel_area = _positive_float(frame.pixel_area_nm2, "pixel_area_nm2")
    outside_area, analyzed_area = _validated_frame_areas(
        full_domains, islands, outside_pixels, analyzed_pixels, pixel_area,
        frame.outside_area_nm2, frame.analyzed_area_nm2,
    )
    return {
        "full_domains": full_domains, "small_ordered_islands": islands,
        "outside_members": outside_members, "outside_source_ids": outside_ids,
        "outside_pixels_xy": outside_pixels, "analyzed_source_ids": analyzed_ids,
        "analyzed_pixels_xy": analyzed_pixels, "pixel_area_nm2": pixel_area,
        "outside_area_nm2": outside_area, "analyzed_area_nm2": analyzed_area,
    }


@dataclass(frozen=True)
class M6Gate:
    """Atomically published frame collection for an analysis range."""

    frames: tuple[M6FrameGate, ...]

    def __post_init__(self) -> None:
        frames = tuple(sorted(self.frames, key=lambda value: value.frame_index))
        if any(not isinstance(value, M6FrameGate) for value in frames):
            raise TypeError("frames must contain M6FrameGate values.")
        frame_indices = tuple(value.frame_index for value in frames)
        if len(set(frame_indices)) != len(frame_indices):
            raise ValueError("M6 gate frame indexes must be unique.")
        physical_frame_ids = tuple(
            value.physical_frame_id for value in frames
        )
        if len(set(physical_frame_ids)) != len(physical_frame_ids):
            raise ValueError("M6 gate physical_frame_id values must be unique.")
        object.__setattr__(self, "frames", frames)


@dataclass(frozen=True)
class DomainAnalysisFailure:
    """Expected backend failure that prevented atomic M6 publication."""

    stage_id: Literal["m6"]
    frame_index: int
    message: str

    def __post_init__(self) -> None:
        if self.stage_id != "m6":
            raise ValueError("Only the M6 stage can fail in this milestone.")
        object.__setattr__(
            self,
            "frame_index",
            _non_negative_integer(self.frame_index, "frame_index"),
        )
        object.__setattr__(
            self,
            "message",
            _non_empty_string(self.message, "message"),
        )


@dataclass(frozen=True)
class DomainAnalysisResult:
    """Immutable final snapshot returned from DomainAnalysisModule.run."""

    run_status: DomainAnalysisRunStatus
    m6_gate: M6Gate | None
    classifier_status: ClassifierStatus
    classifier_outcomes: tuple[ClassifierOutcome, ...] | None = None
    failure: DomainAnalysisFailure | None = None

    def __post_init__(self) -> None:
        successful = self.run_status in {"completed", "completed_with_errors"}
        if successful and self.m6_gate is None:
            raise ValueError("A successful Domain Analysis must publish its M6 gate.")
        outcomes = (
            None
            if self.classifier_outcomes is None
            else tuple(self.classifier_outcomes)
        )
        if outcomes is not None and any(
            not isinstance(value, ClassifierOutcome) for value in outcomes
        ):
            raise TypeError("classifier_outcomes contain an invalid value.")
        classifier_ids = tuple(value.classifier_id for value in outcomes or ())
        if len(set(classifier_ids)) != len(classifier_ids):
            raise ValueError("Classifier outcomes must have unique classifier IDs.")
        validate_domain_analysis_lifecycle(
            self.run_status,
            m6_published=self.m6_gate is not None,
            classifier_status=self.classifier_status,
            outcome_statuses=(
                None
                if outcomes is None
                else tuple(value.status for value in outcomes)
            ),
        )
        object.__setattr__(self, "classifier_outcomes", outcomes)
        if self.run_status == "failed" and self.m6_gate is not None:
            raise ValueError("A failed run cannot publish an M6 gate.")
        if (self.run_status == "failed") != (self.failure is not None):
            raise ValueError("Only a failed run must contain failure details.")

    @property
    def m6_result_published(self) -> bool:
        return self.m6_gate is not None


def _validated_frame_areas(
    full_domains: tuple[M6PublishedComponent, ...],
    islands: tuple[M6PublishedComponent, ...],
    outside_pixels: tuple[tuple[int, int], ...],
    analyzed_pixels: tuple[tuple[int, int], ...],
    pixel_area: float,
    outside_area: float,
    analyzed_area: float,
) -> tuple[float, float]:
    outside_area = _non_negative_float(outside_area, "outside_area_nm2")
    analyzed_area = _non_negative_float(analyzed_area, "analyzed_area_nm2")
    expected_outside_area = len(outside_pixels) * pixel_area
    expected_analyzed_area = len(analyzed_pixels) * pixel_area
    if not isclose(outside_area, expected_outside_area, abs_tol=1e-12):
        raise ValueError("Outside area must match its canonical pixel footprint.")
    if not isclose(analyzed_area, expected_analyzed_area, abs_tol=1e-12):
        raise ValueError("Analyzed area must match its canonical pixel footprint.")
    for component in full_domains + islands:
        expected_area = len(component.footprint_pixels_xy) * pixel_area
        if not isclose(component.footprint_area_nm2, expected_area, abs_tol=1e-12):
            raise ValueError("M6 component area must match its canonical pixel footprint.")
    category_area = (
        sum(value.footprint_area_nm2 for value in full_domains)
        + sum(value.footprint_area_nm2 for value in islands)
        + outside_area
    )
    if not isclose(category_area, analyzed_area, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("M6 partition category areas must reconstruct analyzed area.")
    return outside_area, analyzed_area


def _validate_membership_partition(
    full_domains: tuple[M6PublishedComponent, ...],
    islands: tuple[M6PublishedComponent, ...],
    outside_ids: tuple[str, ...],
    analyzed_ids: tuple[str, ...],
) -> None:
    components = full_domains + islands
    component_ids = tuple(value.lattice_domain_id for value in components)
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("M6 component IDs must be unique within a frame.")
    member_sets = [set(value.source_ids) for value in components]
    _validate_disjoint_cover(member_sets + [set(outside_ids)], set(analyzed_ids), "molecule")


def _validate_published_pixel_partition(
    full_domains: tuple[M6PublishedComponent, ...],
    islands: tuple[M6PublishedComponent, ...],
    outside_pixels: tuple[tuple[int, int], ...],
    analyzed_pixels: tuple[tuple[int, int], ...],
) -> None:
    footprint_sets = [
        set(value.footprint_pixels_xy)
        for value in full_domains + islands
    ]
    _validate_disjoint_cover(
        footprint_sets + [set(outside_pixels)],
        set(analyzed_pixels),
        "pixel",
    )


def _validate_molecule_pixel_coverage(
    molecules: tuple[M6AnalyzedMolecule, ...],
    analyzed_pixels: tuple[tuple[int, int], ...],
) -> None:
    covered = {
        pixel
        for molecule in molecules
        for pixel in molecule.footprint_pixels_xy
    }
    if covered != set(analyzed_pixels):
        raise ValueError("M6 molecule footprints must cover the analyzed pixel area.")


def _validate_disjoint_cover(
    partitions: list[set[_PartitionItem]],
    expected: set[_PartitionItem],
    label: str,
) -> None:
    combined = set().union(*partitions)
    if sum(len(value) for value in partitions) != len(combined):
        raise ValueError(f"M6 {label} partition categories must be disjoint.")
    if combined != expected:
        raise ValueError(f"M6 {label} partition must cover the analyzed area.")


def _published_components(
    values: tuple[M6PublishedComponent, ...],
    component_type: M6ComponentType,
    field_name: str,
) -> tuple[M6PublishedComponent, ...]:
    normalized = tuple(sorted(values, key=lambda value: value.lattice_domain_id))
    if any(not isinstance(value, M6PublishedComponent) for value in normalized):
        raise TypeError(f"{field_name} must contain M6PublishedComponent values.")
    if any(value.component_type != component_type for value in normalized):
        raise ValueError(f"{field_name} contains an invalid component type.")
    return normalized


def _sorted_memberships(
    values: tuple[M6ComponentMembership, ...],
    field_name: str,
) -> tuple[M6ComponentMembership, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, M6ComponentMembership) for value in normalized):
        raise TypeError(f"{field_name} must contain M6ComponentMembership values.")
    normalized = tuple(sorted(normalized, key=lambda value: value.lattice_domain_id))
    if len({value.lattice_domain_id for value in normalized}) != len(normalized):
        raise ValueError(f"{field_name} component IDs must be unique.")
    return normalized


def _sorted_unique_ids(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    normalized = tuple(sorted(_non_empty_string(value, field_name) for value in values))
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must contain unique values.")
    return normalized


def _sorted_unique_pixels(
    values: tuple[tuple[int, int], ...],
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[tuple[int, int], ...]:
    normalized = tuple(sorted(_pixel_pair(value, field_name) for value in values))
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must contain unique pixels.")
    return normalized


def _pixel_pair(value: tuple[int, int], field_name: str) -> tuple[int, int]:
    pair = tuple(value)
    if len(pair) != 2 or any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in pair
    ):
        raise ValueError(f"{field_name} must contain non-negative integer XY pairs.")
    return pair


def _finite_pair(value: tuple[float, float], field_name: str) -> tuple[float, float]:
    pair = tuple(float(item) for item in value)
    if len(pair) != 2 or not all(isfinite(item) for item in pair):
        raise ValueError(f"{field_name} must be a finite pair.")
    return pair


def _finite_quad(
    value: tuple[float, float, float, float],
    field_name: str,
) -> tuple[float, float, float, float]:
    quad = tuple(float(item) for item in value)
    if len(quad) != 4 or not all(isfinite(item) for item in quad):
        raise ValueError(f"{field_name} must contain four finite values.")
    if quad[0] > quad[2] or quad[1] > quad[3]:
        raise ValueError(f"{field_name} bounds must be ordered.")
    return quad


def _non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _non_negative_float(value: float, field_name: str) -> float:
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative.")
    return normalized


def _positive_float(value: float, field_name: str) -> float:
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{field_name} must be finite and positive.")
    return normalized


def _non_negative_integer(value: int, field_name: str) -> int:
    if isinstance(value, bool) or int(value) != value or int(value) < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return int(value)
