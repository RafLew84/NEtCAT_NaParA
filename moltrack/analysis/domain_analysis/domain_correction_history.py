from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from .manual_domain_models import ManualDomainIntent

if TYPE_CHECKING:
    from .domain_correction_models import DomainCorrectionAtom


DomainCorrectionHistoryAction = Literal["apply", "undo", "redo"]


@dataclass(frozen=True)
class DomainCorrectionHistoryRecord:
    record_id: str
    action: DomainCorrectionHistoryAction
    operation_id: str
    physical_frame_id: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("record_id", "operation_id", "physical_frame_id"):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if self.action not in {"apply", "undo", "redo"}:
            raise ValueError(f"Unsupported history action: {self.action!r}.")
        recorded_at = self.recorded_at
        if not isinstance(recorded_at, datetime) or recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be a timezone-aware datetime.")
        object.__setattr__(
            self,
            "recorded_at",
            recorded_at.astimezone(timezone.utc),
        )


@dataclass(frozen=True)
class DomainCorrectionHistoryTarget:
    operation_id: str
    operation_label: str
    source_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_id",
            _text(self.operation_id, "operation_id"),
        )
        object.__setattr__(
            self,
            "operation_label",
            _text(self.operation_label, "operation_label"),
        )
        if (
            isinstance(self.source_count, bool)
            or not isinstance(self.source_count, int)
            or self.source_count <= 0
        ):
            raise ValueError("source_count must be a positive integer.")


@dataclass(frozen=True)
class DomainCorrectionHistoryAvailability:
    undo: DomainCorrectionHistoryTarget | None = None
    redo: DomainCorrectionHistoryTarget | None = None


def active_operation_ids(
    atoms: tuple[DomainCorrectionAtom, ...],
    records: tuple[DomainCorrectionHistoryRecord, ...],
) -> tuple[str, ...]:
    """Derive the active linear branch without mutating its audit records."""

    active_by_frame, _ = _history_stacks(atoms, records)
    active_ids = {
        operation_id
        for frame_active in active_by_frame.values()
        for operation_id in frame_active
    }
    return tuple(
        atom.operation_id for atom in atoms if atom.operation_id in active_ids
    )


def history_availability(
    atoms: tuple[DomainCorrectionAtom, ...],
    records: tuple[DomainCorrectionHistoryRecord, ...],
    physical_frame_id: str,
) -> DomainCorrectionHistoryAvailability:
    frame_id = _text(physical_frame_id, "physical_frame_id")
    active_by_frame, redo_by_frame = _history_stacks(atoms, records)
    active = active_by_frame.get(frame_id, [])
    redo = redo_by_frame.get(frame_id, [])
    atoms_by_id = {atom.operation_id: atom for atom in atoms}
    return DomainCorrectionHistoryAvailability(
        undo=(
            _target(atoms_by_id[active[-1]])
            if active and _is_reversible(atoms_by_id[active[-1]])
            else None
        ),
        redo=_target(atoms_by_id[redo[-1]]) if redo else None,
    )


def validate_history(
    atoms: tuple[DomainCorrectionAtom, ...],
    records: tuple[DomainCorrectionHistoryRecord, ...],
) -> None:
    record_ids = tuple(record.record_id for record in records)
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Correction history record IDs must be unique.")
    active_operation_ids(atoms, records)


def _history_stacks(
    atoms: tuple[DomainCorrectionAtom, ...],
    records: tuple[DomainCorrectionHistoryRecord, ...],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    atoms_by_id = {atom.operation_id: atom for atom in atoms}
    recorded_apply_ids = tuple(
        record.operation_id for record in records if record.action == "apply"
    )
    legacy_count = len(atoms) - len(recorded_apply_ids)
    if legacy_count < 0 or recorded_apply_ids != tuple(
        atom.operation_id for atom in atoms[legacy_count:]
    ):
        raise ValueError(
            "Atoms without apply history records must form a legacy prefix."
        )
    legacy_atoms = atoms[:legacy_count]
    active_by_frame: dict[str, list[str]] = {}
    redo_by_frame: dict[str, list[str]] = {}
    introduced = {atom.operation_id for atom in legacy_atoms}
    for atom in legacy_atoms:
        active_by_frame.setdefault(atom.physical_frame_id, []).append(
            atom.operation_id
        )
    for record in records:
        referenced_atom = atoms_by_id.get(record.operation_id)
        if (
            referenced_atom is None
            or referenced_atom.physical_frame_id != record.physical_frame_id
        ):
            raise ValueError("History record must reference an atom in its frame.")
        active = active_by_frame.setdefault(record.physical_frame_id, [])
        redo = redo_by_frame.setdefault(record.physical_frame_id, [])
        if record.action == "apply":
            if record.operation_id in introduced:
                raise ValueError("An atom can have only one apply history record.")
            introduced.add(record.operation_id)
            active.append(record.operation_id)
            redo.clear()
        elif record.action == "undo":
            if not active or active[-1] != record.operation_id:
                raise ValueError("Undo must reference the last active frame atom.")
            if not _is_reversible(referenced_atom):
                raise ValueError("Legacy boundary corrections cannot be undone.")
            redo.append(active.pop())
        else:
            if not redo or redo[-1] != record.operation_id:
                raise ValueError("Redo must reference the last undone frame atom.")
            active.append(redo.pop())
    return active_by_frame, redo_by_frame


def _is_reversible(atom: DomainCorrectionAtom) -> bool:
    intent = atom.intent
    return not (
        isinstance(intent, ManualDomainIntent)
        and intent.operation == "move"
        and intent.boundary_resolution is not None
        and not atom.effects
    )


def _target(atom: DomainCorrectionAtom) -> DomainCorrectionHistoryTarget:
    labels = {
        "assign": "Assign orientation",
        "reset": "Reset orientation",
        "create": "Create domain",
        "move": "Move to domain",
        "delete": "Delete domain",
        "restore": "Restore domain",
    }
    return DomainCorrectionHistoryTarget(
        operation_id=atom.operation_id,
        operation_label=labels[atom.intent.operation],
        source_count=len(atom.source_ids),
    )


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "DomainCorrectionHistoryAction",
    "DomainCorrectionHistoryAvailability",
    "DomainCorrectionHistoryRecord",
    "DomainCorrectionHistoryTarget",
    "active_operation_ids",
    "history_availability",
    "validate_history",
]
