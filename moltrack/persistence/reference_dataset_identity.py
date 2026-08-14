from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .package_io import file_sha256


ReferenceSplit = Literal["calibration", "validation"]
ReferenceTarget = Literal["m6", "orientation"]
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class ReferenceSourceRevision:
    """Immutable, verified source bytes and acquisition lineage."""

    source_path: Path
    source_file_name: str
    acquisition_fingerprint: str
    lineage_fingerprint: str
    content_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        source_path = Path(self.source_path)
        if not source_path.is_file():
            raise ValueError("Reference source_path must identify a readable file.")
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(
            self,
            "source_file_name",
            reference_text(self.source_file_name, "source_file_name"),
        )
        object.__setattr__(self, "content_sha256", file_sha256(source_path))
        for field_name in ("acquisition_fingerprint", "lineage_fingerprint"):
            object.__setattr__(
                self,
                field_name,
                reference_text(getattr(self, field_name), field_name),
            )

    @classmethod
    def from_path(
        cls,
        source_path: Path,
        *,
        source_file_name: str,
        acquisition_fingerprint: str,
        lineage_fingerprint: str,
    ) -> ReferenceSourceRevision:
        return cls(
            source_path=source_path,
            source_file_name=source_file_name,
            acquisition_fingerprint=acquisition_fingerprint,
            lineage_fingerprint=lineage_fingerprint,
        )

    def verify_current_bytes(self) -> None:
        try:
            current_sha256 = file_sha256(self.source_path)
        except OSError as error:
            raise ValueError("Reference source drift: source is unreadable.") from error
        if current_sha256 != self.content_sha256:
            raise ValueError(
                "Reference source drift: source bytes changed after revision capture."
            )


@dataclass(frozen=True)
class ReferenceMeasurementIdentity:
    measurement_group_id: str
    split: ReferenceSplit
    source_revision: ReferenceSourceRevision


def reference_source_identity(
    target: ReferenceTarget,
    source: ReferenceSourceRevision,
) -> tuple[str, str]:
    source.verify_current_bytes()
    fingerprint = canonical_sha256({
        "schema_version": f"{target}-reference-source-revision-v1",
        "content_sha256": source.content_sha256,
        "acquisition_fingerprint": source.acquisition_fingerprint,
        "lineage_fingerprint": source.lineage_fingerprint,
    })
    return f"source-revision-{fingerprint[:24]}", fingerprint


def reference_measurement_group_fingerprint(
    target: ReferenceTarget,
    body: dict[str, Any],
) -> str:
    identity_body = {
        key: value
        for key, value in body.items()
        if key != "source_file_name"
    }
    return canonical_sha256({
        "schema_version": f"{target}-reference-measurement-group-v2",
        **identity_body,
    })


def reference_partition_fingerprint(
    target: ReferenceTarget,
    split: ReferenceSplit,
    tables: dict[str, list[dict[str, Any]]],
) -> str:
    return canonical_sha256({
        "schema_version": f"{target}-reference-partition-v2",
        "split": split,
        "tables": {
            name: [
                {key: value for key, value in row.items() if key != "source_file_name"}
                for row in rows
                if row["split"] == split
            ]
            for name, rows in sorted(tables.items())
        },
    })


def validate_reference_split_integrity(
    measurements: tuple[ReferenceMeasurementIdentity, ...],
) -> None:
    identity_fields = {
        "measurement_group_id": lambda value: value.measurement_group_id,
        "content_sha256": lambda value: value.source_revision.content_sha256,
        "acquisition_fingerprint": (
            lambda value: value.source_revision.acquisition_fingerprint
        ),
        "lineage_fingerprint": (
            lambda value: value.source_revision.lineage_fingerprint
        ),
    }
    for field_name, identity in identity_fields.items():
        splits_by_identity: dict[str, set[str]] = {}
        for measurement in measurements:
            splits_by_identity.setdefault(identity(measurement), set()).add(
                measurement.split
            )
        leaked = sorted(
            value
            for value, splits in splits_by_identity.items()
            if splits == {"calibration", "validation"}
        )
        if leaked:
            raise ValueError(
                f"Reference Dataset split leakage through {field_name}: {leaked[0]}"
            )


def reference_stable_id(value: object, field_name: str) -> str:
    normalized = reference_text(value, field_name)
    if _STABLE_ID.fullmatch(normalized) is None:
        raise ValueError(
            f"{field_name} must contain only letters, digits, '.', '_' or '-'."
        )
    return normalized


def reference_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "ReferenceMeasurementIdentity",
    "ReferenceSourceRevision",
    "ReferenceSplit",
    "ReferenceTarget",
    "reference_measurement_group_fingerprint",
    "reference_partition_fingerprint",
    "reference_source_identity",
    "reference_stable_id",
    "reference_text",
    "validate_reference_split_integrity",
]
