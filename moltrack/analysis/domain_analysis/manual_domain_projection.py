from __future__ import annotations

from collections import Counter

from .domain_correction_models import EffectiveMoleculeOrientation
from .geometry import M6PublishedMolecule
from .manual_domain_models import (
    EffectiveDomainKind,
    EffectiveM6Domain,
    ManualDomainRecord,
)
from .models import M6FrameGate


def active_manual_memberships(
    manual_domains: tuple[ManualDomainRecord, ...],
) -> dict[tuple[str, str], str]:
    memberships: dict[tuple[str, str], str] = {}
    for domain in manual_domains:
        if domain.is_deleted:
            continue
        for source_id in domain.source_ids:
            key = (domain.physical_frame_id, source_id)
            if key in memberships:
                raise ValueError("Effective molecule belongs to multiple manual domains.")
            memberships[key] = domain.manual_domain_id
    return memberships


def project_effective_domains(
    frames: tuple[M6FrameGate, ...],
    manual_domains: tuple[ManualDomainRecord, ...],
    molecules: tuple[EffectiveMoleculeOrientation, ...],
) -> tuple[EffectiveM6Domain, ...]:
    orientations = {
        (value.physical_frame_id, value.source_id): value.effective_orientation
        for value in molecules
    }
    boundaries = {
        (value.physical_frame_id, value.source_id): value.is_boundary
        for value in molecules
    }
    active_manual_memberships(manual_domains)
    effective_molecules = {
        (value.physical_frame_id, value.source_id): value
        for value in molecules
    }
    domains = []
    for frame in frames:
        member_index = _frame_member_index(frame)
        source_footprints = source_footprints_for_frame(frame)
        for component in frame.full_domains:
            source_ids = tuple(
                value
                for value in component.source_ids
                if effective_molecules[(frame.physical_frame_id, value)]
                .effective_domain_id == component.lattice_domain_id
            )
            if source_ids:
                domains.append(_effective_domain(
                    frame,
                    component.lattice_domain_id,
                    "automatic",
                    source_ids,
                    member_index,
                    source_footprints,
                    orientations,
                    boundaries,
                ))
        for record in manual_domains:
            if record.physical_frame_id != frame.physical_frame_id:
                continue
            domains.append(_effective_domain(
                frame,
                record.manual_domain_id,
                "manual",
                () if record.is_deleted else record.source_ids,
                member_index,
                source_footprints,
                orientations,
                boundaries,
                is_tombstone=record.is_deleted,
            ))
    return tuple(sorted(
        domains,
        key=lambda value: (value.physical_frame_id, value.lattice_domain_id),
    ))


def _effective_domain(
    frame: M6FrameGate,
    domain_id: str,
    domain_kind: EffectiveDomainKind,
    source_ids: tuple[str, ...],
    members: dict[str, M6PublishedMolecule],
    source_footprints: dict[str, tuple[tuple[int, int], ...] | None],
    orientations: dict[tuple[str, str], str | None],
    boundaries: dict[tuple[str, str], bool | None],
    *,
    is_tombstone: bool = False,
) -> EffectiveM6Domain:
    points = tuple(members[value].point_xy_nm for value in source_ids)
    footprint = membership_footprint(
        frame,
        source_ids,
        source_footprints=source_footprints,
    )
    composition = Counter(
        label
        for source_id in source_ids
        for label in (orientations.get((frame.physical_frame_id, source_id)),)
        if label is not None and len(label) == 1 and "A" <= label <= "Z"
    )
    return EffectiveM6Domain(
        physical_frame_id=frame.physical_frame_id,
        lattice_domain_id=domain_id,
        domain_kind=domain_kind,
        is_tombstone=is_tombstone,
        source_ids=source_ids,
        molecule_count=len(source_ids),
        centroid_xy_nm=(None if not points else (
            sum(value[0] for value in points) / len(points),
            sum(value[1] for value in points) / len(points),
        )),
        bounds_xyxy_nm=(None if not points else (
            min(value[0] for value in points),
            min(value[1] for value in points),
            max(value[0] for value in points),
            max(value[1] for value in points),
        )),
        footprint_pixels_xy=footprint,
        footprint_area_nm2=len(footprint) * frame.pixel_area_nm2,
        boundary_source_ids=(
            None
            if not any(
                value is not None
                for (frame_id, _), value in boundaries.items()
                if frame_id == frame.physical_frame_id
            )
            else tuple(
                source_id
                for source_id in source_ids
                if boundaries[(frame.physical_frame_id, source_id)]
            )
        ),
        orientation_composition=tuple(sorted(composition.items())),
    )


def _frame_member_index(frame: M6FrameGate) -> dict[str, M6PublishedMolecule]:
    members = {
        member.source_id: member
        for component in frame.full_domains + frame.small_ordered_islands
        for member in component.members
    }
    members.update({value.source_id: value for value in frame.outside_members})
    return members


def source_footprints_for_frame(
    frame: M6FrameGate,
) -> dict[str, tuple[tuple[int, int], ...] | None]:
    footprints: dict[str, tuple[tuple[int, int], ...] | None] = {}
    for component in frame.full_domains + frame.small_ordered_islands:
        footprints.update(_published_source_footprints(
            component.members,
            component.footprint_pixels_xy,
        ))
    footprints.update(_published_source_footprints(
        frame.outside_members,
        frame.outside_pixels_xy,
    ))
    return footprints


def _published_source_footprints(
    members: tuple[M6PublishedMolecule, ...],
    group_footprint: tuple[tuple[int, int], ...],
) -> dict[str, tuple[tuple[int, int], ...] | None]:
    if len(members) == 1 and members[0].footprint_pixels_xy is None:
        return {members[0].source_id: group_footprint}
    return {
        value.source_id: value.footprint_pixels_xy
        for value in members
    }


def membership_footprint(
    frame: M6FrameGate,
    source_ids: tuple[str, ...],
    *,
    source_footprints: (
        dict[str, tuple[tuple[int, int], ...] | None] | None
    ) = None,
) -> tuple[tuple[int, int], ...]:
    footprints_by_source = source_footprints or source_footprints_for_frame(frame)
    unresolved = {
        value for value in source_ids if footprints_by_source[value] is None
    }
    pixels = {
        pixel
        for value in source_ids
        for pixel in footprints_by_source[value] or ()
    }
    groups = tuple(
        (component.source_ids, component.footprint_pixels_xy)
        for component in frame.full_domains + frame.small_ordered_islands
    ) + ((
        tuple(value.source_id for value in frame.outside_members),
        frame.outside_pixels_xy,
    ),)
    for group_source_ids, group_footprint in groups:
        group = set(group_source_ids)
        if group and group.issubset(unresolved):
            pixels.update(group_footprint)
            unresolved.difference_update(group)
    if not unresolved:
        return tuple(sorted(pixels))
    raise ValueError(
        "Manual membership requires preserved per-molecule footprints."
    )


__all__ = [
    "active_manual_memberships",
    "membership_footprint",
    "project_effective_domains",
    "source_footprints_for_frame",
]
