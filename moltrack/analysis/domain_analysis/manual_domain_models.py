from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


ManualDomainOperation = Literal["create", "move", "delete", "restore"]
EffectiveDomainKind = Literal["automatic", "manual"]


@dataclass(frozen=True)
class ManualDomainIntent:
    physical_frame_id: str
    operation: ManualDomainOperation
    source_ids: tuple[str, ...] = ()
    manual_domain_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        physical_frame_id: str,
        source_ids: tuple[str, ...],
    ) -> ManualDomainIntent:
        return cls(physical_frame_id, "create", source_ids)

    @classmethod
    def move(
        cls,
        *,
        physical_frame_id: str,
        source_ids: tuple[str, ...],
        manual_domain_id: str,
    ) -> ManualDomainIntent:
        return cls(physical_frame_id, "move", source_ids, manual_domain_id)

    @classmethod
    def delete(
        cls,
        *,
        physical_frame_id: str,
        manual_domain_id: str,
    ) -> ManualDomainIntent:
        return cls(physical_frame_id, "delete", manual_domain_id=manual_domain_id)

    @classmethod
    def restore(
        cls,
        *,
        physical_frame_id: str,
        manual_domain_id: str,
    ) -> ManualDomainIntent:
        return cls(physical_frame_id, "restore", manual_domain_id=manual_domain_id)

    def __post_init__(self) -> None:
        object.__setattr__(self, "physical_frame_id", _text(
            self.physical_frame_id,
            "physical_frame_id",
        ))
        if self.operation not in {"create", "move", "delete", "restore"}:
            raise ValueError(f"Unsupported manual-domain operation: {self.operation!r}.")
        source_ids = tuple(sorted({_text(value, "source_id") for value in self.source_ids}))
        domain_id = None if self.manual_domain_id is None else _uuid_text(
            self.manual_domain_id,
            "manual_domain_id",
        )
        if self.operation in {"create", "move"} and not source_ids:
            raise ValueError(f"{self.operation} requires source_ids.")
        if self.operation in {"move", "delete", "restore"} and domain_id is None:
            raise ValueError(f"{self.operation} requires manual_domain_id.")
        if self.operation in {"delete", "restore"} and source_ids:
            raise ValueError(f"{self.operation} cannot carry source_ids.")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "manual_domain_id", domain_id)


@dataclass(frozen=True)
class ManualDomainRecord:
    physical_frame_id: str
    manual_domain_id: str
    source_ids: tuple[str, ...]
    restore_source_ids: tuple[str, ...]
    is_deleted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "physical_frame_id", _text(
            self.physical_frame_id,
            "physical_frame_id",
        ))
        object.__setattr__(self, "manual_domain_id", _uuid_text(
            self.manual_domain_id,
            "manual_domain_id",
        ))
        source_ids = _source_ids(self.source_ids)
        restore_ids = _source_ids(self.restore_source_ids)
        if not isinstance(self.is_deleted, bool):
            raise TypeError("is_deleted must be a bool.")
        if self.is_deleted and source_ids:
            raise ValueError("Deleted manual domain must be a tombstone.")
        if not restore_ids:
            raise ValueError("Manual domain must preserve restore_source_ids.")
        if not self.is_deleted and source_ids != restore_ids:
            raise ValueError(
                "Active manual domain restore_source_ids must match its membership."
            )
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "restore_source_ids", restore_ids)


@dataclass(frozen=True)
class EffectiveM6Domain:
    physical_frame_id: str
    lattice_domain_id: str
    domain_kind: EffectiveDomainKind
    is_tombstone: bool
    source_ids: tuple[str, ...]
    molecule_count: int
    centroid_xy_nm: tuple[float, float] | None
    bounds_xyxy_nm: tuple[float, float, float, float] | None
    footprint_pixels_xy: tuple[tuple[int, int], ...]
    footprint_area_nm2: float
    boundary_source_ids: tuple[str, ...] | None
    orientation_composition: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        for field_name in ("physical_frame_id", "lattice_domain_id"):
            object.__setattr__(self, field_name, _text(
                getattr(self, field_name),
                field_name,
            ))
        if self.domain_kind not in {"automatic", "manual"}:
            raise ValueError(f"Unsupported effective domain kind: {self.domain_kind!r}.")
        source_ids = _source_ids(self.source_ids)
        boundary_ids = (
            None
            if self.boundary_source_ids is None
            else _source_ids(self.boundary_source_ids)
        )
        if boundary_ids is not None and not set(boundary_ids).issubset(source_ids):
            raise ValueError("Boundary molecules must belong to the effective domain.")
        if self.molecule_count != len(source_ids):
            raise ValueError("molecule_count must match source_ids.")
        if self.footprint_area_nm2 < 0:
            raise ValueError("footprint_area_nm2 must be non-negative.")
        if self.is_tombstone != (self.domain_kind == "manual" and not source_ids):
            raise ValueError("Only an empty manual domain is a tombstone.")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "boundary_source_ids", boundary_ids)


def _source_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, "source_id") for value in values}))


def _uuid_text(value: object, field_name: str) -> str:
    text = _text(value, field_name)
    try:
        return str(UUID(text))
    except ValueError as error:
        raise ValueError(f"{field_name} must be a UUID.") from error


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "EffectiveM6Domain",
    "ManualDomainIntent",
    "ManualDomainRecord",
]
