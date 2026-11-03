from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSessionState,
    ReferenceReadinessError,
    ReferenceReadinessPolicy,
)
from moltrack.persistence import (
    publish_m6_reference_dataset,
    publish_orientation_reference_dataset,
)
from moltrack.persistence.reference_dataset import ReferenceDatasetSettings
from moltrack.persistence.reference_dataset_identity import ReferenceTarget
from moltrack.persistence.reference_dataset_reader import (
    load_reference_dataset_package,
)
from test_m6_reference_dataset_v2 import (
    _conflicted_state,
    _m6_reviewed_state,
    _measurement as _m6_measurement,
    _quarantined_state,
    _settings as _m6_settings,
    _stale_state,
)
from test_orientation_reference_dataset_v2 import (
    _measurement as _orientation_measurement,
    _orientation_reviewed_state,
    _settings as _orientation_settings,
)


@dataclass(frozen=True)
class _ReferenceContract:
    target: ReferenceTarget
    ready_state: Callable[[], DomainAnalysisSessionState]
    measurement: Callable[..., Any]
    settings: Callable[[Path, Path | None], ReferenceDatasetSettings]
    publish: Callable[..., Any]
    correction_revision_field: str


_CONTRACTS = (
    _ReferenceContract(
        target="m6",
        ready_state=_m6_reviewed_state,
        measurement=lambda root, group_id, split, state, content: _m6_measurement(
            root,
            group_id,
            split,
            state,
            content,
        ),
        settings=lambda destination, parent: replace(
            _m6_settings(destination),
            parent_package=parent,
        ),
        publish=publish_m6_reference_dataset,
        correction_revision_field="m6_correction_revision",
    ),
    _ReferenceContract(
        target="orientation",
        ready_state=_orientation_reviewed_state,
        measurement=(
            lambda root, group_id, split, state, content: _orientation_measurement(
                root,
                group_id,
                split,
                state,
                content.encode("ascii"),
            )
        ),
        settings=lambda destination, parent: _orientation_settings(
            destination,
            parent_package=parent,
        ),
        publish=publish_orientation_reference_dataset,
        correction_revision_field="orientation_correction_revision",
    ),
)


@pytest.mark.parametrize("contract", _CONTRACTS, ids=lambda value: value.target)
def test_reference_publication_contract_preserves_root_and_child_identity(
    tmp_path: Path,
    contract: _ReferenceContract,
) -> None:
    state = contract.ready_state()
    source_root = tmp_path / contract.target
    source_root.mkdir()
    calibration = contract.measurement(
        source_root,
        "calibration",
        "calibration",
        state,
        "a",
    )
    validation = contract.measurement(
        source_root,
        "validation",
        "validation",
        state,
        "b",
    )
    root_path = tmp_path / f"{contract.target}-root"
    root = contract.publish(
        (calibration, validation),
        contract.settings(root_path, None),
    )
    root_bytes = _package_bytes(root_path)
    changed_calibration = contract.measurement(
        source_root,
        "calibration",
        "calibration",
        state,
        "c",
    )
    child_path = tmp_path / f"{contract.target}-child"

    child = contract.publish(
        (changed_calibration, validation),
        contract.settings(child_path, root_path),
    )

    root_package = load_reference_dataset_package(
        root_path,
        expected_target=contract.target,
    )
    child_package = load_reference_dataset_package(
        child_path,
        expected_target=contract.target,
    )
    root_frames = root_package.json_lines("frames.jsonl")
    child_frames = child_package.json_lines("frames.jsonl")
    correction_set = state.domain_corrections.correction_set
    assert correction_set is not None
    expected_revision = correction_set.review_revision(contract.target)

    assert child_package.manifest["dataset_version"] == 2
    assert child_package.manifest["parent_version_id"] == root.version_id
    assert child.validation_epoch_id == root.validation_epoch_id
    assert child.version_fingerprint != root.version_fingerprint
    assert {
        row[contract.correction_revision_field] for row in root_frames + child_frames
    } == {expected_revision}
    assert {
        row["automatic_snapshot_fingerprint"] for row in root_frames
    } == {
        row["automatic_snapshot_fingerprint"] for row in child_frames
    }
    assert _package_bytes(root_path) == root_bytes


@pytest.mark.parametrize("contract", _CONTRACTS, ids=lambda value: value.target)
@pytest.mark.parametrize(
    "not_ready_state",
    (_stale_state, _conflicted_state, _quarantined_state),
    ids=("stale", "conflicted", "quarantined"),
)
def test_reference_publication_contract_rejects_non_ready_state_atomically(
    tmp_path: Path,
    contract: _ReferenceContract,
    not_ready_state: Callable[[DomainAnalysisSessionState], DomainAnalysisSessionState],
) -> None:
    state = not_ready_state(contract.ready_state())
    source_root = tmp_path / f"{contract.target}-{not_ready_state.__name__}"
    source_root.mkdir()
    measurements = (
        contract.measurement(
            source_root,
            "calibration",
            "calibration",
            state,
            "a",
        ),
        contract.measurement(
            source_root,
            "validation",
            "validation",
            state,
            "b",
        ),
    )
    destination = tmp_path / f"rejected-{contract.target}"
    expected = ReferenceReadinessPolicy().evaluate_dataset(
        measurements,
        contract.target,
    )

    with pytest.raises(ReferenceReadinessError) as raised:
        contract.publish(
            measurements,
            contract.settings(destination, None),
        )

    assert raised.value.result == expected
    assert not destination.exists()


def _package_bytes(path: Path) -> dict[str, bytes]:
    return {
        value.relative_to(path).as_posix(): value.read_bytes()
        for value in path.rglob("*")
        if value.is_file()
    }
