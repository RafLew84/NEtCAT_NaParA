from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .m6_reference_manifest import (
    M6ReferenceVersionIdentity,
    write_m6_reference_manifests,
)
from .m6_reference_payload import (
    M6_REFERENCE_TABLE_FILES,
    M6ReferencePackageTables,
    build_m6_reference_tables,
)
from .m6_reference_schema import (
    M6ReferenceDatasetPublication,
    M6ReferenceDatasetSettings,
    M6ReferenceMeasurementGroup,
)
from .package_io import path_exists, publish_path, relative_package_files


def publish_m6_reference_dataset(
    measurements: tuple[M6ReferenceMeasurementGroup, ...],
    settings: M6ReferenceDatasetSettings,
) -> M6ReferenceDatasetPublication:
    """Validate and atomically publish the first immutable M6 dataset version."""

    if not isinstance(settings, M6ReferenceDatasetSettings):
        raise TypeError("settings must be M6ReferenceDatasetSettings.")
    tables = build_m6_reference_tables(tuple(measurements))
    destination = settings.destination
    if path_exists(destination):
        raise FileExistsError(
            f"M6 Reference Dataset version already exists: {destination}"
        )
    identity, relative_files = _publish_new_version(
        tables,
        settings,
        destination,
    )
    return M6ReferenceDatasetPublication(
        package_path=destination,
        dataset_id=settings.dataset_id,
        version_id=identity.version_id,
        version_fingerprint=identity.version_fingerprint,
        validation_epoch_id=identity.validation_epoch_id,
        relative_files=relative_files,
    )


def _publish_new_version(
    tables: M6ReferencePackageTables,
    settings: M6ReferenceDatasetSettings,
    destination: Path,
) -> tuple[M6ReferenceVersionIdentity, tuple[str, ...]]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    ))
    try:
        counts = _write_tables(staging, tables)
        identity = write_m6_reference_manifests(
            staging,
            tables,
            settings,
            counts,
        )
        relative_files = relative_package_files(staging)
        publish_path(staging, destination, overwrite=False)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return identity, relative_files


def _write_tables(
    root: Path,
    package: M6ReferencePackageTables,
) -> tuple[tuple[str, int], ...]:
    counts = []
    for name in M6_REFERENCE_TABLE_FILES:
        rows = package.tables[name]
        _write_json_lines(root / name, rows)
        counts.append((name, len(rows)))
    return tuple(sorted(counts))


def _write_json_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(
                row,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


__all__ = ["publish_m6_reference_dataset"]
