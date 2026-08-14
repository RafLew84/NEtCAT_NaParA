from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from moltrack import __version__ as moltrack_version
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .m6_reference_payload import M6ReferencePackageTables
from .m6_reference_schema import (
    M6_REFERENCE_DATASET_SCHEMA_VERSION,
    M6_REFERENCE_DATASET_VERSION,
    M6ReferenceDatasetSettings,
)
from .package_io import file_sha256


@dataclass(frozen=True)
class M6ReferenceVersionIdentity:
    version_id: str
    version_fingerprint: str
    validation_epoch_id: str


def write_m6_reference_manifests(
    root: Path,
    tables: M6ReferencePackageTables,
    settings: M6ReferenceDatasetSettings,
    record_counts: tuple[tuple[str, int], ...],
) -> M6ReferenceVersionIdentity:
    file_manifest = _file_manifest(root, record_counts)
    _write_json(root / "file_manifest.json", file_manifest)
    partitions = {
        split: {
            "measurement_group_count": tables.measurement_group_count(split),
            "partition_fingerprint": tables.partition_fingerprint(split),
        }
        for split in ("calibration", "validation")
    }
    epoch = _validation_epoch(partitions["validation"]["partition_fingerprint"])
    identity = _version_identity(settings, partitions, file_manifest, epoch)
    manifest = {
        "schema_version": M6_REFERENCE_DATASET_SCHEMA_VERSION,
        "target": "m6",
        "dataset_id": settings.dataset_id,
        "dataset_version": M6_REFERENCE_DATASET_VERSION,
        "version_id": identity.version_id,
        "parent_version_id": None,
        "version_fingerprint": identity.version_fingerprint,
        "publication_reason": settings.publication_reason,
        "readiness": {"ready": True, "blockers": []},
        "validation_epoch": epoch,
        "partitions": partitions,
        "file_manifest": {
            "path": "file_manifest.json",
            "fingerprint": canonical_sha256(file_manifest),
        },
        "application": {"name": "MolTrack", "version": moltrack_version},
    }
    _write_json(root / "manifest.json", manifest)
    return identity


def _file_manifest(
    root: Path,
    record_counts: tuple[tuple[str, int], ...],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "files": [
            {
                "path": name,
                "record_count": count,
                "sha256": file_sha256(root / name),
            }
            for name, count in sorted(record_counts)
        ],
    }


def _validation_epoch(validation_fingerprint: Any) -> dict[str, str]:
    fingerprint = str(validation_fingerprint)
    identity_fingerprint = canonical_sha256({
        "schema_version": "m6-reference-validation-epoch-v1",
        "validation_partition_fingerprint": fingerprint,
    })
    return {
        "epoch_id": f"m6-validation-epoch-{identity_fingerprint[:24]}",
        "identity_fingerprint": identity_fingerprint,
        "validation_partition_fingerprint": fingerprint,
    }


def _version_identity(
    settings: M6ReferenceDatasetSettings,
    partitions: dict[str, dict[str, Any]],
    file_manifest: dict[str, Any],
    epoch: dict[str, str],
) -> M6ReferenceVersionIdentity:
    body = {
        "schema_version": M6_REFERENCE_DATASET_SCHEMA_VERSION,
        "target": "m6",
        "dataset_id": settings.dataset_id,
        "dataset_version": M6_REFERENCE_DATASET_VERSION,
        "parent_version_id": None,
        "publication_reason": settings.publication_reason,
        "partitions": partitions,
        "validation_epoch": epoch,
        "file_manifest_fingerprint": canonical_sha256(file_manifest),
    }
    fingerprint = canonical_sha256(body)
    return M6ReferenceVersionIdentity(
        version_id=(
            f"{settings.dataset_id}-v{M6_REFERENCE_DATASET_VERSION}-"
            f"{fingerprint[:16]}"
        ),
        version_fingerprint=fingerprint,
        validation_epoch_id=epoch["epoch_id"],
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


__all__ = ["M6ReferenceVersionIdentity", "write_m6_reference_manifests"]
