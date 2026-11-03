from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from moltrack import __version__ as moltrack_version
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .correction_aware_export_payload import CorrectionAwarePackagePayload
from .correction_aware_export_schema import (
    CORRECTION_AWARE_EXPORT_SCHEMA_VERSION,
    CorrectionAwareExportSettings,
)
from .package_io import file_sha256


def write_correction_aware_manifest(
    root: Path,
    settings: CorrectionAwareExportSettings,
    package: CorrectionAwarePackagePayload,
    record_counts: tuple[tuple[str, int], ...],
) -> None:
    source_identity = settings.source_identity.to_dict()
    manifest = {
        "export_schema_version": CORRECTION_AWARE_EXPORT_SCHEMA_VERSION,
        "package_kind": "moltrack_correction_aware_analysis",
        "export_mode": settings.export_mode,
        "activation_status": package.activation_status,
        "correction_status": package.correction_status,
        "application": {"name": "MolTrack", "version": moltrack_version},
        "compatibility": {
            "based_on_automatic_export_schema": 9,
            "readable_as_schema_v9": False,
        },
        "source": {
            "identity": source_identity,
            "identity_fingerprint": canonical_sha256(source_identity),
        },
        "anchors": package.anchors,
        "readiness": package.readiness,
        "files": _file_entries(root, record_counts),
    }
    (root / "manifest.json").write_text(
        json.dumps(
            manifest,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _file_entries(
    root: Path,
    record_counts: tuple[tuple[str, int], ...],
) -> list[dict[str, Any]]:
    return [
        {
            "path": name,
            "record_count": count,
            "sha256": file_sha256(root / name),
        }
        for name, count in sorted(record_counts)
    ]


__all__ = ["write_correction_aware_manifest"]
