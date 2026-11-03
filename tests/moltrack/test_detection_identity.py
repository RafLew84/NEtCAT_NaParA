from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from moltrack.analysis.domain_analysis import (
    CorrectionSourceMapping,
    DetectionIdentity,
    DomainCorrectionWorkspace,
    PreparedCorrectionRebase,
)
from moltrack.persistence.correction_rebase_payload import (
    prepared_rebase_from_payload,
    prepared_rebase_to_payload,
)
from moltrack.persistence.domain_correction_set_payload import (
    correction_set_from_payload,
    correction_set_to_payload,
)


def test_detection_identity_requires_complete_named_fields_and_is_immutable() -> None:
    identity = DetectionIdentity(
        physical_frame_id=" frame-1 ",
        source_id=" source-a ",
    )

    assert identity.physical_frame_id == "frame-1"
    assert identity.source_id == "source-a"
    with pytest.raises(TypeError):
        DetectionIdentity("frame-1", "source-a")  # type: ignore[misc]
    with pytest.raises(TypeError):
        DetectionIdentity(physical_frame_id="frame-1")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="source_id"):
        DetectionIdentity(physical_frame_id="frame-1", source_id=" ")
    with pytest.raises(FrozenInstanceError):
        identity.source_id = "source-b"  # type: ignore[misc]


def test_rebase_identity_types_keep_the_canonical_fingerprint_and_v3_payload() -> None:
    first = DetectionIdentity(
        physical_frame_id="frame-1",
        source_id="source-a",
    )
    second = DetectionIdentity(
        physical_frame_id="frame-2",
        source_id="source-b",
    )
    prepared = PreparedCorrectionRebase(
        expected_correction_revision=2,
        active_automatic_fingerprint="active",
        candidate_automatic_fingerprint="candidate",
        portable_source_keys=(second, first),
        issues=(),
        resolutions=(),
        source_mapping=(
            CorrectionSourceMapping(
                source_identity=second,
                target_source_ids=("target-b",),
            ),
            CorrectionSourceMapping(
                source_identity=first,
                target_source_ids=("target-a",),
            ),
        ),
    )

    assert prepared.portable_source_keys == (first, second)
    assert prepared.prepared_fingerprint == (
        "9629ce20c056b005b47954bc93dc4e59a27ccbdad120150e2502450558e6292b"
    )
    payload = prepared_rebase_to_payload(prepared)
    assert payload is not None
    assert payload["portable_source_keys"] == [
        ["frame-1", "source-a"],
        ["frame-2", "source-b"],
    ]
    assert payload["source_mapping"] == [
        ["frame-1", "source-a", ["target-a"]],
        ["frame-2", "source-b", ["target-b"]],
    ]
    assert prepared_rebase_from_payload(payload) == prepared


def test_correction_workspace_round_trip_uses_identities_behind_legacy_pairs() -> None:
    identity = DetectionIdentity(
        physical_frame_id="frame-1",
        source_id="source-a",
    )
    workspace = DomainCorrectionWorkspace(
        automatic_fingerprint="automatic",
        revision=1,
        cleared_boundary_source_keys=(identity,),
        legacy_boundary_source_keys=(identity,),
    )

    payload = correction_set_to_payload(workspace)
    assert payload["cleared_boundary_source_keys"] == [["frame-1", "source-a"]]
    assert payload["legacy_boundary_source_keys"] == [["frame-1", "source-a"]]
    assert correction_set_from_payload(payload) == workspace

    with pytest.raises(TypeError, match="DetectionIdentity"):
        DomainCorrectionWorkspace(
            automatic_fingerprint="automatic",
            revision=1,
            cleared_boundary_source_keys=(("frame-1", "source-a"),),  # type: ignore[arg-type]
        )
