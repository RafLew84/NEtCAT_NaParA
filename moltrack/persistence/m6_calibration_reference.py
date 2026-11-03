"""Calibration adapter for the neutral verified M6 reference projection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from moltrack.analysis.m6_calibration_campaign_models import (
    M6CalibrationReferenceGroup,
)

from .m6_reference_projection import (
    M6ReferenceTables,
    m6_reference_groups,
    project_verified_m6_tables,
)
from .reference_dataset_reader import load_reference_dataset_package


M6CalibrationTables = M6ReferenceTables


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
    verified = load_m6_calibration_tables(package_path)
    return M6CalibrationReference(
        package_path=verified.package_path,
        dataset_id=verified.dataset_id,
        version_id=verified.version_id,
        version_fingerprint=verified.version_fingerprint,
        validation_epoch_id=verified.validation_epoch_id,
        groups=m6_reference_groups(verified.tables, verified.version_id),
    )


def load_m6_calibration_tables(
    package_path: str | Path,
) -> M6ReferenceTables:
    package = load_reference_dataset_package(package_path, expected_target="m6")
    return project_verified_m6_tables(package, "calibration")


__all__ = [
    "M6CalibrationReference",
    "M6CalibrationTables",
    "load_m6_calibration_reference",
    "load_m6_calibration_tables",
]
