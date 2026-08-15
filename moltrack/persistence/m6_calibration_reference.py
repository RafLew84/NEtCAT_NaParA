"""Calibration projection of a verified immutable M6 Reference Dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from moltrack.analysis.lattice_domain_validation import LatticeDomainPartitionLabels
from moltrack.analysis.m6_calibration_campaign_models import (
    M6CalibrationReferenceGroup,
)

from .m6_reference_payload import M6_REFERENCE_TABLE_FILES
from .reference_dataset_identity import (
    ReferenceSplit,
    reference_partition_fingerprint,
)
from .reference_dataset_reader import load_reference_dataset_package


@dataclass(frozen=True)
class M6CalibrationReference:
    package_path: Path
    dataset_id: str
    version_id: str
    version_fingerprint: str
    validation_epoch_id: str
    groups: tuple[M6CalibrationReferenceGroup, ...]


def load_m6_calibration_reference(
    package_path: str | Path,
) -> M6CalibrationReference:
    package = load_reference_dataset_package(
        package_path,
        expected_target="m6",
    )
    if set(package.payloads) != set(M6_REFERENCE_TABLE_FILES):
        raise ValueError("M6 Reference Dataset payload table set is invalid.")
    tables = {
        name: package.json_lines(name)
        for name in M6_REFERENCE_TABLE_FILES
    }
    _verify_table_identity(package.manifest, tables)
    manifest = package.manifest
    version_id = _text(manifest.get("version_id"), "version_id")
    return M6CalibrationReference(
        package_path=package.package_path,
        dataset_id=_text(manifest.get("dataset_id"), "dataset_id"),
        version_id=version_id,
        version_fingerprint=_text(
            manifest.get("version_fingerprint"),
            "version_fingerprint",
        ),
        validation_epoch_id=_text(
            _mapping(manifest.get("validation_epoch"), "validation_epoch").get(
                "epoch_id"
            ),
            "validation_epoch.epoch_id",
        ),
        groups=_calibration_groups(tables, version_id),
    )


def _verify_table_identity(
    manifest: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    for rows in tables.values():
        if any(row.get("split") not in {"calibration", "validation"} for row in rows):
            raise ValueError("M6 Reference Dataset table split is invalid.")
    measurements: dict[str, str] = {}
    for row in tables["measurements.jsonl"]:
        group_id = _text(row.get("measurement_group_id"), "measurement_group_id")
        split = _text(row.get("split"), "split")
        if group_id in measurements:
            raise ValueError("M6 Reference Dataset measurement groups are duplicated.")
        measurements[group_id] = split
    if set(measurements.values()) != {"calibration", "validation"}:
        raise ValueError("M6 Reference Dataset requires both dataset splits.")
    for row in tables["m6_assignments.jsonl"]:
        group_id = _text(row.get("measurement_group_id"), "measurement_group_id")
        if measurements.get(group_id) != row.get("split"):
            raise ValueError("M6 Reference Dataset assignment group identity is invalid.")
    partitions = _mapping(manifest.get("partitions"), "partitions")
    splits: tuple[ReferenceSplit, ...] = ("calibration", "validation")
    for split in splits:
        partition = _mapping(partitions.get(split), f"{split} partition")
        actual_count = sum(value == split for value in measurements.values())
        if partition.get("measurement_group_count") != actual_count:
            raise ValueError(
                f"M6 Reference Dataset {split} measurement count mismatch."
            )
        if partition.get("partition_fingerprint") != (
            reference_partition_fingerprint("m6", split, tables)
        ):
            raise ValueError(
                f"M6 Reference Dataset {split} partition fingerprint mismatch."
            )


def _calibration_groups(
    tables: dict[str, list[dict[str, Any]]],
    version_id: str,
) -> tuple[M6CalibrationReferenceGroup, ...]:
    calibration_ids = tuple(sorted(
        _text(row.get("measurement_group_id"), "measurement_group_id")
        for row in tables["measurements.jsonl"]
        if row.get("split") == "calibration"
    ))
    assignments = tables["m6_assignments.jsonl"]
    groups = []
    for group_id in calibration_ids:
        rows = [
            row
            for row in assignments
            if row.get("split") == "calibration"
            and row.get("measurement_group_id") == group_id
        ]
        if not rows:
            raise ValueError("M6 Reference Dataset Calibration group has no labels.")
        groups.append(_reference_group(version_id, group_id, rows))
    return tuple(groups)


def _reference_group(
    version_id: str,
    group_id: str,
    rows: list[dict[str, Any]],
) -> M6CalibrationReferenceGroup:
    resolved = [
        row
        for row in rows
        if row.get("review_eligibility") == "eligible"
        and row.get("review_abstention") is None
    ]
    excluded = tuple(sorted(
        _source_key(row)
        for row in rows
        if row not in resolved
    ))
    if not resolved:
        raise ValueError("M6 Calibration group has no resolved reference labels.")
    source_ids = tuple(_source_key(row) for row in resolved)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("M6 Calibration group contains duplicate source IDs.")
    labels: list[str | None] = []
    boundaries = []
    boundary_available = True
    for row in resolved:
        partition = row.get("effective_m6_partition")
        domain_id = row.get("effective_domain_id")
        frame_id = _text(row.get("physical_frame_id"), "physical_frame_id")
        if partition == "full_domain":
            labels.append(f"{frame_id}::{_text(domain_id, 'effective_domain_id')}")
        elif partition in {"small_ordered_island", "outside"}:
            if domain_id is not None:
                raise ValueError("Non-domain M6 assignment carries a domain ID.")
            labels.append(None)
        else:
            raise ValueError("M6 Reference Dataset assignment partition is invalid.")
        boundary = row.get("effective_boundary")
        if boundary is None:
            boundary_available = False
            boundaries.append(False)
        elif isinstance(boundary, bool):
            boundaries.append(boundary)
        else:
            raise ValueError("M6 Reference Dataset boundary value is invalid.")
    return M6CalibrationReferenceGroup(
        dataset_version_id=version_id,
        measurement_group_id=group_id,
        reference_labels=LatticeDomainPartitionLabels(
            source_ids=source_ids,
            domain_labels=tuple(labels),
            boundary=tuple(boundaries),
            confidence=tuple(None for _ in source_ids),
        ),
        reference_boundary_available=boundary_available,
        abstention_count=sum(row.get("review_abstention") is not None for row in rows),
        excluded_source_ids=excluded,
    )


def _source_key(row: dict[str, Any]) -> str:
    return (
        f"{_text(row.get('physical_frame_id'), 'physical_frame_id')}::"
        f"{_text(row.get('source_id'), 'source_id')}"
    )


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"M6 Reference Dataset {field_name} is invalid.")
    return value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"M6 Reference Dataset {field_name} is invalid.")
    return value.strip()


__all__ = ["M6CalibrationReference", "load_m6_calibration_reference"]
