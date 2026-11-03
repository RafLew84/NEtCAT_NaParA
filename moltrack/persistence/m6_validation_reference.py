"""One-shot integrity boundary for the M6 Validation split."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import cache
import json
import os
from pathlib import Path
import tempfile

from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.m6_calibration_campaign_models import M6CalibrationReferenceGroup
from moltrack.analysis.m6_validation_campaign_models import (
    M6_VALIDATION_ACCESS_SCHEMA_VERSION,
    M6CandidateShortlist,
    M6ValidationAccessReceipt,
)

from .m6_reference_projection import (
    m6_reference_groups,
    project_verified_m6_tables,
)
from .package_io import path_exists, publish_path, remove_path
from .reference_dataset_reader import (
    ReferenceDatasetPackage,
    load_reference_dataset_package,
)


@dataclass(frozen=True)
class M6ValidationReference:
    package_path: Path
    dataset_id: str
    version_id: str
    version_fingerprint: str
    validation_epoch_id: str
    receipt: M6ValidationAccessReceipt
    groups: tuple[M6CalibrationReferenceGroup, ...]


def open_m6_validation_reference(
    package_path: str | Path,
    shortlist: M6CandidateShortlist,
) -> M6ValidationReference:
    """Consume one epoch in a lineage-stable store before exposing Validation."""

    if not isinstance(shortlist, M6CandidateShortlist):
        raise TypeError("shortlist must be an M6CandidateShortlist.")
    package = load_reference_dataset_package(package_path, expected_target="m6")
    _require_package_identity(package, shortlist)
    receipt = _consume_validation_epoch(shortlist)
    projected = project_verified_m6_tables(package, "validation")
    return M6ValidationReference(
        package_path=projected.package_path,
        dataset_id=projected.dataset_id,
        version_id=projected.version_id,
        version_fingerprint=projected.version_fingerprint,
        validation_epoch_id=projected.validation_epoch_id,
        receipt=receipt,
        groups=m6_reference_groups(projected.tables, projected.version_id),
    )


def _require_package_identity(
    package: ReferenceDatasetPackage,
    shortlist: M6CandidateShortlist,
) -> None:
    manifest = package.manifest
    epoch = manifest.get("validation_epoch")
    actual = (
        manifest.get("dataset_id"),
        manifest.get("version_id"),
        manifest.get("version_fingerprint"),
        epoch.get("epoch_id") if isinstance(epoch, dict) else None,
    )
    expected = (
        shortlist.dataset_id,
        shortlist.dataset_version_id,
        shortlist.dataset_version_fingerprint,
        shortlist.validation_epoch_id,
    )
    if actual != expected:
        raise ValueError(
            "M6 Validation package identity does not match the frozen shortlist."
        )


def _consume_validation_epoch(
    shortlist: M6CandidateShortlist,
) -> M6ValidationAccessReceipt:
    access_body = {
        "schema_version": M6_VALIDATION_ACCESS_SCHEMA_VERSION,
        "dataset_id": shortlist.dataset_id,
        "dataset_version_id": shortlist.dataset_version_id,
        "dataset_version_fingerprint": shortlist.dataset_version_fingerprint,
        "validation_epoch_id": shortlist.validation_epoch_id,
        "geometry_fingerprint": shortlist.geometry_fingerprint,
        "objective_fingerprint": shortlist.objective_fingerprint,
        "shortlist_fingerprint": shortlist.shortlist_fingerprint,
    }
    access_fingerprint = canonical_sha256(access_body)
    ledger_root = _validation_access_registry()
    ledger_root.mkdir(parents=True, exist_ok=True)
    epoch_key = canonical_sha256({
        "dataset_id": shortlist.dataset_id,
        "validation_epoch_id": shortlist.validation_epoch_id,
    })
    epoch_directory = ledger_root / epoch_key
    receipt = M6ValidationAccessReceipt(
        dataset_id=shortlist.dataset_id,
        dataset_version_id=shortlist.dataset_version_id,
        dataset_version_fingerprint=shortlist.dataset_version_fingerprint,
        validation_epoch_id=shortlist.validation_epoch_id,
        geometry_fingerprint=shortlist.geometry_fingerprint,
        objective_fingerprint=shortlist.objective_fingerprint,
        shortlist_fingerprint=shortlist.shortlist_fingerprint,
        access_fingerprint=access_fingerprint,
        opened_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    staging = Path(tempfile.mkdtemp(prefix=f".{epoch_key}-", dir=ledger_root))
    try:
        (staging / "receipt.json").write_text(
            json.dumps(asdict(receipt), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        publish_path(staging, epoch_directory, overwrite=False)
    except OSError as error:
        remove_path(staging)
        if path_exists(epoch_directory):
            _raise_consumed_epoch(epoch_directory, access_fingerprint, error)
        raise
    except BaseException:
        remove_path(staging)
        raise
    return receipt


@cache
def _validation_access_registry() -> Path:
    configured = os.environ.get("MOLTRACK_M6_VALIDATION_ACCESS_REGISTRY")
    root = (
        Path(configured)
        if configured
        else Path.home() / ".moltrack" / "m6-validation-access"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _raise_consumed_epoch(
    epoch_directory: Path,
    access_fingerprint: str,
    error: OSError,
) -> None:
    try:
        payload = json.loads(
            (epoch_directory / "receipt.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict) and payload.get("access_fingerprint") != (
        access_fingerprint
    ):
        message = "Validation access identity mismatch; epoch has already been opened."
    else:
        message = "Validation has already been opened for this immutable epoch."
    raise ValueError(message) from error


__all__ = ["M6ValidationReference", "open_m6_validation_reference"]
