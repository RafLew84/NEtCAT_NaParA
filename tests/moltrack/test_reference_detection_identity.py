from __future__ import annotations

import pytest

from moltrack.analysis.domain_analysis import (
    DetectionIdentity,
    ReferenceReviewDecision,
    ReferenceReviewDisposition,
    ReferenceReviewFrame,
    ReferenceReviewScope,
    ReferenceReviewTarget,
    ReferenceReviewWorkspace,
)
from moltrack.persistence.reference_detection_identity import (
    reference_review_decisions_by_identity,
)


def test_reference_detection_identity_is_complete_named_and_deduplicated() -> None:
    identity = DetectionIdentity(
        physical_frame_id="frame-1",
        source_id="source-a",
    )
    duplicate = DetectionIdentity(
        physical_frame_id="frame-1",
        source_id="source-a",
    )
    reversed_fields = DetectionIdentity(
        physical_frame_id="source-a",
        source_id="frame-1",
    )

    assert {identity, duplicate, reversed_fields} == {identity, reversed_fields}
    with pytest.raises(TypeError):
        DetectionIdentity("source-a", "frame-1")  # type: ignore[misc]
    with pytest.raises(TypeError):
        DetectionIdentity(source_id="source-a")  # type: ignore[call-arg]


def test_reference_review_index_distinguishes_repeated_source_ids_by_frame() -> None:
    first = _review_frame("frame-1", "m6", "created")
    second = _review_frame("frame-2", "m6", "corrected")
    ignored = _review_frame("frame-1", "orientation", "accepted_automatic")

    indexed = reference_review_decisions_by_identity(
        ReferenceReviewWorkspace((ignored, second, first)),
        "m6",
    )

    assert indexed == {
        DetectionIdentity(
            physical_frame_id="frame-1",
            source_id="shared-source",
        ): first.decisions[0],
        DetectionIdentity(
            physical_frame_id="frame-2",
            source_id="shared-source",
        ): second.decisions[0],
    }


def _review_frame(
    physical_frame_id: str,
    target: ReferenceReviewTarget,
    disposition: ReferenceReviewDisposition,
) -> ReferenceReviewFrame:
    return ReferenceReviewFrame(
        scope=ReferenceReviewScope(
            target=target,
            physical_frame_id=physical_frame_id,
            automatic_fingerprint=f"automatic-{physical_frame_id}-{target}",
            source_geometry_fingerprint=f"geometry-{physical_frame_id}",
            annotation_revision=0,
            source_ids=("shared-source",),
        ),
        decisions=(ReferenceReviewDecision.eligible(
            "shared-source",
            disposition=disposition,
        ),),
    )
