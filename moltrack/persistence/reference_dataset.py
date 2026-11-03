from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from moltrack import __version__ as moltrack_version
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .package_io import path_exists, publish_path, relative_package_files
from .reference_dataset_identity import (
    ReferenceMeasurementIdentity,
    ReferenceSourceRevision,
    ReferenceSplit,
    ReferenceTarget,
    reference_measurement_group_fingerprint,
    reference_partition_fingerprint,
    reference_source_identity,
    reference_source_revision_row,
    reference_stable_id,
    reference_text,
    validate_reference_split_integrity,
    validated_reference_measurements,
)
from .reference_dataset_reader import (
    REFERENCE_DATASET_ENVELOPE_VERSION,
    load_reference_dataset_package,
    reference_validation_epoch,
)


_RESERVED_PATHS = {"manifest.json", "file_manifest.json"}


@dataclass(frozen=True)
class ReferenceDatasetSettings:
    destination: Path
    dataset_id: str
    publication_reason: str
    parent_package: Path | None = None

    def __post_init__(self) -> None:
        destination = Path(self.destination)
        if not str(destination).strip():
            raise ValueError("Reference Dataset destination must not be empty.")
        object.__setattr__(self, "destination", destination)
        object.__setattr__(
            self,
            "dataset_id",
            reference_stable_id(self.dataset_id, "dataset_id"),
        )
        object.__setattr__(
            self,
            "publication_reason",
            reference_text(self.publication_reason, "publication_reason"),
        )
        if self.parent_package is not None:
            parent_package = Path(self.parent_package)
            if destination.resolve().is_relative_to(parent_package.resolve()):
                raise ValueError(
                    "A child Reference Dataset destination must be outside its "
                    "parent package."
                )
            object.__setattr__(self, "parent_package", parent_package)


@dataclass(frozen=True)
class ReferencePayloadFile:
    path: str
    content: bytes
    record_count: int

    def __post_init__(self) -> None:
        normalized = PurePosixPath(str(self.path).replace("\\", "/"))
        if (
            normalized.is_absolute()
            or ".." in normalized.parts
            or normalized.as_posix() in _RESERVED_PATHS
            or normalized.as_posix() in {"", "."}
        ):
            raise ValueError("Reference payload path must be safe and relative.")
        if not isinstance(self.content, bytes):
            raise TypeError("Reference payload content must be bytes.")
        if not isinstance(self.record_count, int) or self.record_count < 0:
            raise ValueError("Reference payload record_count must be non-negative.")
        object.__setattr__(self, "path", normalized.as_posix())


@dataclass(frozen=True)
class ReferencePartitionIdentity:
    split: ReferenceSplit
    measurement_group_count: int
    partition_fingerprint: str

    def __post_init__(self) -> None:
        if self.split not in {"calibration", "validation"}:
            raise ValueError("Reference partition split is invalid.")
        if (
            not isinstance(self.measurement_group_count, int)
            or self.measurement_group_count < 1
        ):
            raise ValueError("Reference partition must contain measurement groups.")
        object.__setattr__(
            self,
            "partition_fingerprint",
            reference_text(
                self.partition_fingerprint,
                "partition_fingerprint",
            ),
        )


@dataclass(frozen=True)
class ReferenceDatasetDraft:
    target: ReferenceTarget
    settings: ReferenceDatasetSettings
    initial_dataset_version: int
    payload_files: tuple[ReferencePayloadFile, ...]
    partitions: tuple[ReferencePartitionIdentity, ...]
    source_revisions: tuple[ReferenceSourceRevision, ...] = ()

    def __post_init__(self) -> None:
        if self.target not in {"m6", "orientation"}:
            raise ValueError("Reference Dataset target is invalid.")
        if not isinstance(self.settings, ReferenceDatasetSettings):
            raise TypeError("settings must be ReferenceDatasetSettings.")
        if self.initial_dataset_version < 1:
            raise ValueError("initial_dataset_version must be positive.")
        files = tuple(self.payload_files)
        if any(not isinstance(value, ReferencePayloadFile) for value in files):
            raise TypeError("Reference Dataset payload files are invalid.")
        files = tuple(sorted(files, key=lambda value: value.path))
        if not files or len(files) != len({value.path for value in files}):
            raise ValueError("Reference Dataset payload paths must be non-empty and unique.")
        partitions = tuple(self.partitions)
        if any(
            not isinstance(value, ReferencePartitionIdentity)
            for value in partitions
        ):
            raise TypeError("Reference Dataset partition identities are invalid.")
        partitions = tuple(sorted(partitions, key=lambda value: value.split))
        if (
            len(partitions) != 2
            or {value.split for value in partitions}
            != {"calibration", "validation"}
        ):
            raise ValueError("Reference Dataset requires both partition identities.")
        source_revisions = tuple(self.source_revisions)
        if any(
            not isinstance(value, ReferenceSourceRevision)
            for value in source_revisions
        ):
            raise TypeError("Reference Dataset source revisions are invalid.")
        object.__setattr__(self, "payload_files", files)
        object.__setattr__(self, "partitions", partitions)
        object.__setattr__(self, "source_revisions", source_revisions)


@dataclass(frozen=True)
class ReferenceDatasetPublication:
    package_path: Path
    dataset_id: str
    version_id: str
    version_fingerprint: str
    validation_epoch_id: str
    relative_files: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceDatasetPublicationPlan:
    """Verified operator preview of one immutable publication."""

    target: ReferenceTarget
    dataset_id: str
    dataset_version: int
    parent_version_id: str | None
    source_revision_ids: tuple[str, ...]
    partitions: tuple[ReferencePartitionIdentity, ...]
    validation_epoch_id: str
    validation_epoch_action: Literal["preserve", "new"]

    def operator_summary(self) -> str:
        parent = self.parent_version_id or "none (new dataset root)"
        sources = "\n".join(
            f"  - {value}" for value in self.source_revision_ids
        ) or "  - none supplied"
        partitions = "\n".join(
            f"  - {value.split}: {value.partition_fingerprint}"
            for value in self.partitions
        )
        return (
            f"Target: {self.target}\n"
            f"Dataset ID: {self.dataset_id}\n"
            f"Ancestry: {parent} -> version {self.dataset_version}\n"
            f"Parent version: {parent}\n"
            f"Source revisions:\n{sources}\n"
            f"Split fingerprints:\n{partitions}\n"
            f"Validation epoch: {self.validation_epoch_action} "
            f"{self.validation_epoch_id}"
        )


@dataclass(frozen=True)
class ReferenceDatasetPublicationCandidate:
    """Freeze a verified preview and publish only if it still matches."""

    plan: ReferenceDatasetPublicationPlan
    _draft: ReferenceDatasetDraft = field(repr=False)

    def publish(self) -> ReferenceDatasetPublication:
        return _publish_reference_dataset(self._draft, self.plan)


@dataclass(frozen=True)
class _ParentVersion:
    version_id: str
    dataset_version: int
    validation_epoch_id: str
    validation_partition_fingerprint: str


def publish_reference_dataset(
    draft: ReferenceDatasetDraft,
) -> ReferenceDatasetPublication:
    """Verify ancestry and atomically publish one immutable dataset envelope."""

    return prepare_reference_dataset(draft).publish()


def prepare_reference_dataset(
    draft: ReferenceDatasetDraft,
) -> ReferenceDatasetPublicationCandidate:
    """Prepare the same verified identity plan consumed by publication."""

    if not isinstance(draft, ReferenceDatasetDraft):
        raise TypeError("draft must be a ReferenceDatasetDraft.")
    plan = _publication_plan(draft, _load_parent(draft))
    return ReferenceDatasetPublicationCandidate(plan, draft)


def _publish_reference_dataset(
    draft: ReferenceDatasetDraft,
    expected_plan: ReferenceDatasetPublicationPlan,
) -> ReferenceDatasetPublication:
    current_plan = _publication_plan(draft, _load_parent(draft))
    if current_plan != expected_plan:
        raise ValueError(
            "Reference Dataset publication inputs changed after preview."
        )

    settings = draft.settings
    if path_exists(settings.destination):
        raise FileExistsError(
            f"Reference Dataset version already exists: {settings.destination}"
        )
    settings.destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{settings.destination.name}.",
        suffix=".tmp",
        dir=settings.destination.parent,
    ))
    try:
        file_manifest = _write_payload(staging, draft.payload_files)
        _write_json(staging / "file_manifest.json", file_manifest)
        manifest = _manifest(draft, file_manifest, current_plan)
        _write_json(staging / "manifest.json", manifest)
        relative_files = relative_package_files(staging)
        publish_path(staging, settings.destination, overwrite=False)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return ReferenceDatasetPublication(
        package_path=settings.destination,
        dataset_id=settings.dataset_id,
        version_id=manifest["version_id"],
        version_fingerprint=manifest["version_fingerprint"],
        validation_epoch_id=manifest["validation_epoch"]["epoch_id"],
        relative_files=relative_files,
    )


def reference_json_lines_file(
    path: str,
    rows: list[dict[str, Any]],
) -> ReferencePayloadFile:
    content = "".join(
        json.dumps(
            row,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
        for row in rows
    ).encode("utf-8")
    return ReferencePayloadFile(path, content, len(rows))


def _load_parent(draft: ReferenceDatasetDraft) -> _ParentVersion | None:
    package_path = draft.settings.parent_package
    if package_path is None:
        return None
    package = load_reference_dataset_package(
        package_path,
        expected_target=draft.target,
    )
    manifest = package.manifest
    dataset_version = manifest.get("dataset_version")
    if (
        manifest.get("dataset_id") != draft.settings.dataset_id
        or not isinstance(dataset_version, int)
        or dataset_version < draft.initial_dataset_version
    ):
        raise ValueError("Reference Dataset parent envelope is incompatible.")
    validation = manifest["validation_epoch"]
    return _ParentVersion(
        version_id=manifest["version_id"],
        dataset_version=dataset_version,
        validation_epoch_id=validation["epoch_id"],
        validation_partition_fingerprint=(
            validation["validation_partition_fingerprint"]
        ),
    )


def _write_payload(
    root: Path,
    files: tuple[ReferencePayloadFile, ...],
) -> dict[str, Any]:
    entries = []
    for value in files:
        destination = root / PurePosixPath(value.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value.content)
        entries.append({
            "path": value.path,
            "record_count": value.record_count,
            "sha256": hashlib.sha256(value.content).hexdigest(),
        })
    return {"schema_version": 1, "files": entries}


def _publication_plan(
    draft: ReferenceDatasetDraft,
    parent: _ParentVersion | None,
) -> ReferenceDatasetPublicationPlan:
    validation_fingerprint = next(
        value.partition_fingerprint
        for value in draft.partitions
        if value.split == "validation"
    )
    epoch = reference_validation_epoch(draft.target, validation_fingerprint)
    action: Literal["preserve", "new"] = "new"
    if parent is not None and (
        parent.validation_partition_fingerprint == validation_fingerprint
    ):
        epoch["epoch_id"] = parent.validation_epoch_id
        action = "preserve"
    source_revision_ids = tuple(sorted({
        reference_source_identity(draft.target, value)[0]
        for value in draft.source_revisions
    }))
    return ReferenceDatasetPublicationPlan(
        target=draft.target,
        dataset_id=draft.settings.dataset_id,
        dataset_version=(
            draft.initial_dataset_version
            if parent is None
            else parent.dataset_version + 1
        ),
        parent_version_id=None if parent is None else parent.version_id,
        source_revision_ids=source_revision_ids,
        partitions=draft.partitions,
        validation_epoch_id=epoch["epoch_id"],
        validation_epoch_action=action,
    )


def _manifest(
    draft: ReferenceDatasetDraft,
    file_manifest: dict[str, Any],
    plan: ReferenceDatasetPublicationPlan,
) -> dict[str, Any]:
    settings = draft.settings
    partitions = {
        value.split: {
            "measurement_group_count": value.measurement_group_count,
            "partition_fingerprint": value.partition_fingerprint,
        }
        for value in draft.partitions
    }
    validation_fingerprint = str(
        partitions["validation"]["partition_fingerprint"]
    )
    epoch = reference_validation_epoch(draft.target, validation_fingerprint)
    epoch["epoch_id"] = plan.validation_epoch_id
    file_fingerprint = canonical_sha256(file_manifest)
    body = {
        "schema_version": REFERENCE_DATASET_ENVELOPE_VERSION,
        "target": draft.target,
        "dataset_id": settings.dataset_id,
        "dataset_version": plan.dataset_version,
        "parent_version_id": plan.parent_version_id,
        "publication_reason": settings.publication_reason,
        "partitions": partitions,
        "validation_epoch": epoch,
        "file_manifest_fingerprint": file_fingerprint,
    }
    fingerprint = canonical_sha256(body)
    return {
        **{key: value for key, value in body.items() if key != "file_manifest_fingerprint"},
        "version_id": (
            f"{settings.dataset_id}-v{plan.dataset_version}-{fingerprint[:16]}"
        ),
        "version_fingerprint": fingerprint,
        "readiness": {"ready": True, "blockers": []},
        "file_manifest": {
            "path": "file_manifest.json",
            "fingerprint": file_fingerprint,
        },
        "application": {"name": "MolTrack", "version": moltrack_version},
    }


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


__all__ = [
    "ReferenceDatasetDraft",
    "ReferenceDatasetPublicationCandidate",
    "ReferenceDatasetPublicationPlan",
    "ReferenceDatasetPublication",
    "ReferenceDatasetSettings",
    "ReferenceMeasurementIdentity",
    "ReferencePartitionIdentity",
    "ReferencePayloadFile",
    "ReferenceSourceRevision",
    "ReferenceSplit",
    "ReferenceTarget",
    "publish_reference_dataset",
    "prepare_reference_dataset",
    "reference_json_lines_file",
    "reference_measurement_group_fingerprint",
    "reference_partition_fingerprint",
    "reference_source_identity",
    "reference_source_revision_row",
    "validate_reference_split_integrity",
    "validated_reference_measurements",
]
