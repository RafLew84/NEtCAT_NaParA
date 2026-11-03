"""Calibration-only geometry projection of a verified M6 Reference Dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from moltrack.analysis.first_shell_geometry_contracts import (
    FirstShellSymmetry,
    first_shell_symmetry,
)

from .m6_calibration_reference import load_m6_calibration_tables


@dataclass(frozen=True)
class M6FirstShellReferenceFrame:
    physical_frame_id: str
    working_frame_index: int
    symmetry_class: FirstShellSymmetry
    source_ids: tuple[str, ...]
    points_xy_nm: tuple[tuple[float, float], ...]
    manual_edges: tuple[tuple[str, str], ...]
    spatial_calibration_fingerprint: str
    registration_fingerprint: str


@dataclass(frozen=True)
class M6FirstShellReferenceGroup:
    measurement_group_id: str
    frames: tuple[M6FirstShellReferenceFrame, ...]


@dataclass(frozen=True)
class M6FirstShellCalibrationReference:
    package_path: Path
    dataset_id: str
    version_id: str
    version_fingerprint: str
    validation_epoch_id: str
    groups: tuple[M6FirstShellReferenceGroup, ...]


def load_m6_first_shell_calibration_reference(
    package_path: str | Path,
) -> M6FirstShellCalibrationReference:
    verified = load_m6_calibration_tables(package_path)
    tables = verified.tables
    calibration_groups = tuple(sorted(
        _text(row.get("measurement_group_id"), "measurement_group_id")
        for row in tables["measurements.jsonl"]
    ))
    groups = tuple(
        _group(group_id, tables)
        for group_id in calibration_groups
    )
    if not groups:
        raise ValueError("M6 Reference Dataset Calibration has no geometry groups.")
    return M6FirstShellCalibrationReference(
        package_path=verified.package_path,
        dataset_id=verified.dataset_id,
        version_id=verified.version_id,
        version_fingerprint=verified.version_fingerprint,
        validation_epoch_id=verified.validation_epoch_id,
        groups=groups,
    )


def _group(
    group_id: str,
    tables: dict[str, list[dict[str, Any]]],
) -> M6FirstShellReferenceGroup:
    frame_rows = [
        row
        for row in tables["frames.jsonl"]
        if row.get("measurement_group_id") == group_id
    ]
    if not frame_rows:
        raise ValueError("M6 Calibration geometry group has no frames.")
    frames = tuple(
        _frame(group_id, row, tables)
        for row in sorted(
            frame_rows,
            key=lambda value: (
                _integer(value.get("working_frame_index"), "working_frame_index"),
                _text(value.get("physical_frame_id"), "physical_frame_id"),
            ),
        )
    )
    frame_ids = tuple(value.physical_frame_id for value in frames)
    if len(frame_ids) != len(set(frame_ids)):
        raise ValueError("M6 Calibration geometry frames are duplicated.")
    return M6FirstShellReferenceGroup(group_id, frames)


def _frame(
    group_id: str,
    frame_row: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
) -> M6FirstShellReferenceFrame:
    frame_id = _text(frame_row.get("physical_frame_id"), "physical_frame_id")
    symmetry = _symmetry(frame_row.get("first_shell_symmetry_class"))
    geometry_rows = _matching_rows(
        tables["source_geometry.jsonl"],
        group_id,
        frame_id,
    )
    if not geometry_rows:
        raise ValueError("M6 Calibration geometry frame has no source positions.")
    points = tuple(sorted(
        (
            _text(row.get("source_id"), "source_id"),
            _point(row.get("point_xy_nm")),
        )
        for row in geometry_rows
    ))
    source_ids = tuple(value[0] for value in points)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("M6 Calibration geometry source IDs are duplicated.")
    edge_rows = _matching_rows(
        tables["m6_first_shell_edges.jsonl"],
        group_id,
        frame_id,
    )
    manual_edges = tuple(sorted(
        _edge(row.get("source_id_a"), row.get("source_id_b"), source_ids)
        for row in edge_rows
    ))
    if len(manual_edges) != len(set(manual_edges)):
        raise ValueError("M6 Calibration first-shell edges are duplicated.")
    calibration_fingerprints = {
        str(row.get("coordinate_transform_fingerprint", "unspecified_calibration"))
        for row in geometry_rows
    }
    registration_fingerprints = {
        str(row.get("registration_fingerprint", "unregistered"))
        for row in geometry_rows
    }
    if len(calibration_fingerprints) != 1 or len(registration_fingerprints) != 1:
        raise ValueError("M6 Calibration frame geometry provenance is inconsistent.")
    return M6FirstShellReferenceFrame(
        physical_frame_id=frame_id,
        working_frame_index=_integer(
            frame_row.get("working_frame_index"),
            "working_frame_index",
        ),
        symmetry_class=symmetry,
        source_ids=source_ids,
        points_xy_nm=tuple(value[1] for value in points),
        manual_edges=manual_edges,
        spatial_calibration_fingerprint=calibration_fingerprints.pop(),
        registration_fingerprint=registration_fingerprints.pop(),
    )


def _matching_rows(
    rows: list[dict[str, Any]],
    group_id: str,
    frame_id: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("measurement_group_id") == group_id
        and row.get("physical_frame_id") == frame_id
    ]


def _edge(left: object, right: object, source_ids: tuple[str, ...]) -> tuple[str, str]:
    values = sorted((_text(left, "source_id_a"), _text(right, "source_id_b")))
    edge = (values[0], values[1])
    if edge[0] == edge[1] or any(value not in source_ids for value in edge):
        raise ValueError("M6 Calibration first-shell edge is invalid.")
    return edge


def _symmetry(value: object) -> FirstShellSymmetry:
    try:
        return first_shell_symmetry(value)
    except ValueError as error:
        raise ValueError(
            "M6 Calibration frame first-shell symmetry is invalid."
        ) from error


def _point(value: object) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("M6 Calibration point_xy_nm is invalid.")
    try:
        point = (float(value[0]), float(value[1]))
    except (TypeError, ValueError) as error:
        raise ValueError("M6 Calibration point_xy_nm is invalid.") from error
    return point


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"M6 Calibration {field_name} is invalid.")
    return value


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"M6 Reference Dataset {field_name} is invalid.")
    return value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"M6 Reference Dataset {field_name} is invalid.")
    return value.strip()


__all__ = [
    "M6FirstShellCalibrationReference",
    "M6FirstShellReferenceFrame",
    "M6FirstShellReferenceGroup",
    "load_m6_first_shell_calibration_reference",
]
