"""Single integrity boundary for reading published Reference Dataset versions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .package_io import relative_package_files
from .reference_dataset_identity import ReferenceTarget


REFERENCE_DATASET_ENVELOPE_VERSION = 2
_RESERVED_PATHS = {"manifest.json", "file_manifest.json"}


@dataclass(frozen=True)
class ReferenceDatasetPackage:
    package_path: Path
    target: ReferenceTarget
    manifest: dict[str, Any]
    file_manifest: dict[str, Any]
    payloads: dict[str, bytes]

    def json_lines(self, path: str) -> list[dict[str, Any]]:
        try:
            content = self.payloads[path].decode("utf-8")
            rows = [json.loads(line) for line in content.splitlines()]
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"Reference Dataset table is invalid: {path}"
            ) from error
        if any(not isinstance(value, dict) for value in rows):
            raise ValueError(f"Reference Dataset table is invalid: {path}")
        return rows


def load_reference_dataset_package(
    package_path: str | Path,
    *,
    expected_target: ReferenceTarget,
) -> ReferenceDatasetPackage:
    """Verify the complete immutable envelope before exposing any payload."""

    root = Path(package_path)
    manifest = _read_json(root / "manifest.json", "manifest")
    file_manifest = _read_json(root / "file_manifest.json", "file manifest")
    if (
        manifest.get("schema_version") != REFERENCE_DATASET_ENVELOPE_VERSION
        or manifest.get("target") != expected_target
        or manifest.get("readiness") != {"ready": True, "blockers": []}
    ):
        raise ValueError("Reference Dataset envelope is incompatible.")
    payloads = _verified_payloads(root, file_manifest)
    file_fingerprint = canonical_sha256(file_manifest)
    if manifest.get("file_manifest") != {
        "path": "file_manifest.json",
        "fingerprint": file_fingerprint,
    }:
        raise ValueError("Reference Dataset file manifest identity is invalid.")
    fingerprint = canonical_sha256(
        _version_body_from_manifest(manifest, file_fingerprint)
    )
    dataset_id = _text(manifest.get("dataset_id"), "dataset_id")
    dataset_version = manifest.get("dataset_version")
    if (
        isinstance(dataset_version, bool)
        or not isinstance(dataset_version, int)
        or dataset_version < 1
        or manifest.get("version_fingerprint") != fingerprint
        or manifest.get("version_id")
        != f"{dataset_id}-v{dataset_version}-{fingerprint[:16]}"
    ):
        raise ValueError("Reference Dataset version identity is invalid.")
    _verify_validation_epoch(expected_target, manifest)
    return ReferenceDatasetPackage(
        package_path=root,
        target=expected_target,
        manifest=manifest,
        file_manifest=file_manifest,
        payloads=payloads,
    )


def reference_validation_epoch(
    target: ReferenceTarget,
    fingerprint: str,
) -> dict[str, str]:
    identity_fingerprint = canonical_sha256({
        "schema_version": f"{target}-reference-validation-epoch-v1",
        "validation_partition_fingerprint": fingerprint,
    })
    return {
        "epoch_id": f"{target}-validation-epoch-{identity_fingerprint[:24]}",
        "identity_fingerprint": identity_fingerprint,
        "validation_partition_fingerprint": fingerprint,
    }


def _verified_payloads(
    root: Path,
    file_manifest: dict[str, Any],
) -> dict[str, bytes]:
    entries = file_manifest.get("files")
    if file_manifest.get("schema_version") != 1 or not isinstance(entries, list):
        raise ValueError("Reference Dataset file manifest is invalid.")
    payloads: dict[str, bytes] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Reference Dataset file entry is invalid.")
        relative = _safe_relative_path(entry.get("path"))
        try:
            content = (root / PurePosixPath(relative)).read_bytes()
        except OSError as error:
            raise ValueError("Reference Dataset payload is unreadable.") from error
        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            raise ValueError("Reference Dataset payload fingerprint mismatch.")
        if (
            relative.endswith(".jsonl")
            and entry.get("record_count") != len(content.splitlines())
        ):
            raise ValueError("Reference Dataset payload record count mismatch.")
        if relative in payloads:
            raise ValueError("Reference Dataset file manifest has duplicates.")
        payloads[relative] = content
    package_paths = set(relative_package_files(root))
    if package_paths != {*payloads, *_RESERVED_PATHS}:
        raise ValueError("Reference Dataset contains unmanifested payload.")
    return payloads


def _verify_validation_epoch(
    target: ReferenceTarget,
    manifest: dict[str, Any],
) -> None:
    partitions = manifest.get("partitions")
    validation = manifest.get("validation_epoch")
    if not isinstance(partitions, dict) or not isinstance(validation, dict):
        raise ValueError("Reference Dataset Validation epoch is invalid.")
    partition = partitions.get("validation")
    if not isinstance(partition, dict):
        raise ValueError("Reference Dataset Validation epoch is invalid.")
    expected = reference_validation_epoch(
        target,
        _text(
            partition.get("partition_fingerprint"),
            "validation partition fingerprint",
        ),
    )
    if validation != expected:
        raise ValueError("Reference Dataset Validation epoch is invalid.")


def _version_body_from_manifest(
    manifest: dict[str, Any],
    file_manifest_fingerprint: str,
) -> dict[str, Any]:
    keys = (
        "schema_version",
        "target",
        "dataset_id",
        "dataset_version",
        "parent_version_id",
        "publication_reason",
        "partitions",
        "validation_epoch",
    )
    return {
        **{key: manifest.get(key) for key in keys},
        "file_manifest_fingerprint": file_manifest_fingerprint,
    }


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Reference Dataset {label} is unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Reference Dataset {label} must be an object.")
    return value


def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Reference Dataset payload path is invalid.")
    path = PurePosixPath(value.replace("\\", "/"))
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() in _RESERVED_PATHS
        or path.as_posix() in {"", "."}
    ):
        raise ValueError("Reference Dataset payload path is invalid.")
    return path.as_posix()


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Reference Dataset {field_name} is invalid.")
    return value.strip()


__all__ = [
    "REFERENCE_DATASET_ENVELOPE_VERSION",
    "ReferenceDatasetPackage",
    "load_reference_dataset_package",
    "reference_validation_epoch",
]
