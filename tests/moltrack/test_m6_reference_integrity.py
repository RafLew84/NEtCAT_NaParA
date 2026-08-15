from __future__ import annotations

from dataclasses import replace

import pytest

from moltrack.analysis.domain_analysis import ReferenceReadinessError
from moltrack.persistence import (
    M6ReferenceSourceRevision,
    publish_m6_reference_dataset,
)
from test_m6_reference_dataset_v2 import (
    _json,
    _json_lines,
    _m6_reviewed_state,
    _measurement,
    _settings,
)


@pytest.mark.parametrize(
    ("case", "shared_field"),
    (
        ("renamed-copy", "content_sha256"),
        ("converted-acquisition", "acquisition_fingerprint"),
        ("adjacent-lineage", "lineage_fingerprint"),
    ),
)
def test_publisher_rejects_split_leakage_beyond_file_names(
    tmp_path,
    case: str,
    shared_field: str,
) -> None:
    state = _m6_reviewed_state()
    calibration = _measurement(tmp_path, "calibration", "calibration", state, "a")
    validation = _measurement(tmp_path, "validation", "validation", state, "b")
    revision_updates = {
        shared_field: getattr(calibration.source_revision, shared_field),
    }
    if shared_field == "content_sha256":
        validation.source_revision.source_path.write_bytes(
            calibration.source_revision.source_path.read_bytes()
        )
        revision_updates = {}
    validation = replace(
        validation,
        source_revision=_recapture_source_revision(
            validation.source_revision,
            source_file_name=f"{case}.converted.mpp",
            **revision_updates,
        ),
    )
    destination = tmp_path / case

    with pytest.raises(ValueError, match=shared_field):
        publish_m6_reference_dataset(
            (calibration, validation),
            _settings(destination),
        )

    assert not destination.exists()


def test_source_revision_identity_tracks_bytes_but_ignores_relocation(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    calibration = _measurement(tmp_path, "calibration", "calibration", state, "a")
    validation = _measurement(tmp_path, "validation", "validation", state, "b")
    relocated_path = tmp_path / "relocated-calibration.mpp"
    relocated_path.write_bytes(calibration.source_revision.source_path.read_bytes())
    relocated = replace(
        calibration,
        source_revision=_recapture_source_revision(
            calibration.source_revision,
            source_path=relocated_path,
            source_file_name="relocated/calibration-copy.mpp",
        ),
    )
    drifted_path = tmp_path / "drifted-calibration.mpp"
    drifted_path.write_bytes(b"different source bytes")
    drifted = replace(
        calibration,
        source_revision=_recapture_source_revision(
            calibration.source_revision,
            source_path=drifted_path,
        ),
    )

    destinations = {
        "original": tmp_path / "original",
        "relocated": tmp_path / "relocated",
        "drifted": tmp_path / "drifted",
    }
    for name, value in (
        ("original", calibration),
        ("relocated", relocated),
        ("drifted", drifted),
    ):
        publish_m6_reference_dataset(
            (value, validation),
            _settings(destinations[name]),
        )

    revision_ids = {
        name: _calibration_source_revision_id(destination)
        for name, destination in destinations.items()
    }
    assert revision_ids["relocated"] == revision_ids["original"]
    assert revision_ids["drifted"] != revision_ids["original"]


def _calibration_source_revision_id(destination) -> str:
    rows = _json_lines(destination / "measurements.jsonl")
    return next(
        row["source_revision_id"]
        for row in rows
        if row["split"] == "calibration"
    )


def _recapture_source_revision(source, **changes):
    return M6ReferenceSourceRevision.from_path(
        changes.get("source_path", source.source_path),
        source_file_name=changes.get("source_file_name", source.source_file_name),
        acquisition_fingerprint=changes.get(
            "acquisition_fingerprint",
            source.acquisition_fingerprint,
        ),
        lineage_fingerprint=changes.get(
            "lineage_fingerprint",
            source.lineage_fingerprint,
        ),
    )


def test_child_publication_preserves_or_rotates_validation_epoch(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    calibration = _measurement(tmp_path, "calibration", "calibration", state, "a")
    validation = _measurement(tmp_path, "validation", "validation", state, "b")
    root_path = tmp_path / "root"
    child_path = tmp_path / "child"
    next_epoch_path = tmp_path / "next-epoch"
    root = publish_m6_reference_dataset(
        (calibration, validation),
        _settings(root_path),
    )
    root_bytes = {
        path.name: path.read_bytes()
        for path in root_path.iterdir()
        if path.is_file()
    }
    calibration.source_revision.source_path.write_bytes(b"changed calibration")
    changed_calibration = replace(
        calibration,
        source_revision=_recapture_source_revision(
            calibration.source_revision,
        ),
    )

    child = publish_m6_reference_dataset(
        (changed_calibration, validation),
        replace(_settings(child_path), parent_package=root_path),
    )
    child_manifest = _json(child_path / "manifest.json")
    root_manifest = _json(root_path / "manifest.json")

    assert child_manifest["parent_version_id"] == root.version_id
    assert child_manifest["dataset_version"] == 2
    assert child.validation_epoch_id == root.validation_epoch_id
    assert (
        child_manifest["partitions"]["validation"]["partition_fingerprint"]
        == root_manifest["partitions"]["validation"]["partition_fingerprint"]
    )
    assert (
        child_manifest["partitions"]["calibration"]["partition_fingerprint"]
        != root_manifest["partitions"]["calibration"]["partition_fingerprint"]
    )
    assert root_bytes == {
        path.name: path.read_bytes()
        for path in root_path.iterdir()
        if path.is_file()
    }

    validation.source_revision.source_path.write_bytes(b"changed validation")
    changed_validation = replace(
        validation,
        source_revision=_recapture_source_revision(
            validation.source_revision,
        ),
    )
    next_epoch = publish_m6_reference_dataset(
        (changed_calibration, changed_validation),
        replace(_settings(next_epoch_path), parent_package=child_path),
    )
    next_manifest = _json(next_epoch_path / "manifest.json")

    assert next_manifest["parent_version_id"] == child.version_id
    assert next_manifest["dataset_version"] == 3
    assert next_epoch.validation_epoch_id != child.validation_epoch_id


def test_validation_relocation_keeps_partition_identity_and_epoch(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    calibration = _measurement(tmp_path, "calibration", "calibration", state, "a")
    validation = _measurement(tmp_path, "validation", "validation", state, "b")
    root_path = tmp_path / "root"
    child_path = tmp_path / "relocated-child"
    root = publish_m6_reference_dataset(
        (calibration, validation),
        _settings(root_path),
    )
    relocated_path = tmp_path / "relocated-validation.mpp"
    relocated_path.write_bytes(validation.source_revision.source_path.read_bytes())
    relocated_validation = replace(
        validation,
        source_revision=_recapture_source_revision(
            validation.source_revision,
            source_path=relocated_path,
            source_file_name="relocated/validation.mpp",
        ),
    )

    child = publish_m6_reference_dataset(
        (calibration, relocated_validation),
        replace(_settings(child_path), parent_package=root_path),
    )
    root_manifest = _json(root_path / "manifest.json")
    child_manifest = _json(child_path / "manifest.json")

    assert child.validation_epoch_id == root.validation_epoch_id
    assert (
        child_manifest["partitions"]["validation"]["partition_fingerprint"]
        == root_manifest["partitions"]["validation"]["partition_fingerprint"]
    )


def test_child_publication_rejects_unmanifested_parent_payload(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, "a"),
        _measurement(tmp_path, "validation", "validation", state, "b"),
    )
    root_path = tmp_path / "root"
    child_path = tmp_path / "child"
    publish_m6_reference_dataset(measurements, _settings(root_path))
    (root_path / "injected.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unmanifested"):
        publish_m6_reference_dataset(
            measurements,
            replace(_settings(child_path), parent_package=root_path),
        )

    assert not child_path.exists()


def test_child_destination_cannot_mutate_parent_package(tmp_path) -> None:
    state = _m6_reviewed_state()
    measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, "a"),
        _measurement(tmp_path, "validation", "validation", state, "b"),
    )
    root_path = tmp_path / "root"
    child_path = root_path / "child"
    publish_m6_reference_dataset(measurements, _settings(root_path))
    before = {
        path.relative_to(root_path).as_posix()
        for path in root_path.rglob("*")
        if path.is_file()
    }

    with pytest.raises(ValueError, match="outside its parent package"):
        publish_m6_reference_dataset(
            measurements,
            replace(_settings(child_path), parent_package=root_path),
        )

    assert {
        path.relative_to(root_path).as_posix()
        for path in root_path.rglob("*")
        if path.is_file()
    } == before
    assert not child_path.exists()


def test_publisher_detects_source_drift_before_creating_a_child(
    tmp_path,
) -> None:
    state = _m6_reviewed_state()
    calibration = _measurement(tmp_path, "calibration", "calibration", state, "a")
    validation = _measurement(tmp_path, "validation", "validation", state, "b")
    root_path = tmp_path / "root"
    rejected_path = tmp_path / "stale-child"
    refreshed_path = tmp_path / "refreshed-child"
    publish_m6_reference_dataset(
        (calibration, validation),
        _settings(root_path),
    )
    source_path = calibration.source_revision.source_path
    source_path.write_bytes(b"changed calibration bytes")

    with pytest.raises(ReferenceReadinessError, match="source drift") as raised:
        publish_m6_reference_dataset(
            (calibration, validation),
            replace(_settings(rejected_path), parent_package=root_path),
        )
    assert tuple(value.code for value in raised.value.result.blockers) == (
        "source_revision_drifted",
    )
    assert not rejected_path.exists()

    refreshed = replace(
        calibration,
        source_revision=M6ReferenceSourceRevision.from_path(
            source_path,
            source_file_name=calibration.source_revision.source_file_name,
            acquisition_fingerprint=(
                calibration.source_revision.acquisition_fingerprint
            ),
            lineage_fingerprint=calibration.source_revision.lineage_fingerprint,
        ),
    )
    publish_m6_reference_dataset(
        (refreshed, validation),
        replace(_settings(refreshed_path), parent_package=root_path),
    )

    assert (
        _calibration_source_revision_id(refreshed_path)
        != _calibration_source_revision_id(root_path)
    )
