from __future__ import annotations

import csv
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from moltrack.analysis.domain_analysis import DomainAnalysisSessionState

from .analysis_package import AnalysisExportPackageResult
from .correction_aware_export_manifest import write_correction_aware_manifest
from .correction_aware_export_payload import (
    CorrectionAwarePackagePayload,
    correction_aware_package_payload,
)
from .correction_aware_export_schema import (
    EFFECTIVE_MOLECULE_HEADERS,
    EFFECTIVE_MOLECULES_FILE,
    CorrectionAwareExportSettings,
)
from .package_io import (
    path_exists,
    publish_path,
    relative_package_files,
)


def export_correction_aware_package(
    snapshot: DomainAnalysisSessionState,
    settings: CorrectionAwareExportSettings,
) -> AnalysisExportPackageResult:
    """Publish one atomic schema-v10 correction-aware directory package."""

    if not isinstance(settings, CorrectionAwareExportSettings):
        raise TypeError("settings must be CorrectionAwareExportSettings.")
    package = correction_aware_package_payload(snapshot, settings)
    destination = settings.destination
    if path_exists(destination) and not settings.overwrite:
        raise FileExistsError(
            f"Correction-aware package destination already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    ))
    try:
        record_counts = _write_payload(staging, package)
        write_correction_aware_manifest(
            staging,
            settings,
            package,
            record_counts,
        )
        relative_files = relative_package_files(staging)
        publish_path(staging, destination, overwrite=settings.overwrite)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return AnalysisExportPackageResult(
        package_path=destination,
        package_format="directory",
        relative_files=relative_files,
        record_counts=record_counts,
    )


def _write_payload(
    root: Path,
    package: CorrectionAwarePackagePayload,
) -> tuple[tuple[str, int], ...]:
    counts = []
    for name, value in package.json_documents.items():
        _write_json(root / name, value)
        counts.append((name, _json_record_count(value)))
    for name, rows in package.json_lines.items():
        _write_json_lines(root / name, rows)
        counts.append((name, len(rows)))
    if package.activation_status == "active":
        _write_molecules(root / EFFECTIVE_MOLECULES_FILE, package.molecule_rows)
        counts.append((EFFECTIVE_MOLECULES_FILE, len(package.molecule_rows)))
    return tuple(sorted(counts))


def _write_json(path: Path, value: Any) -> None:
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


def _write_molecules(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EFFECTIVE_MOLECULE_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def _json_record_count(value: Any) -> int:
    if value is None:
        return 0
    return len(value) if isinstance(value, list) else 1


__all__ = ["export_correction_aware_package"]
